"""
Hot Hub — 全网热榜聚合
FastAPI 入口 — 支持 40+ 平台 + 结构化存储 + 定时爬取
"""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from crawlers import weibo, zhihu, baidu, xiaohongshu, douyin, toutiao
from crawlers.extra import FETCH_MAP
from crawlers.platforms import PLATFORMS, CATEGORY_NAMES, CATEGORY_ORDER
from storage import init_db, get_latest_batch, get_batch_list, get_platform_history
from scheduler import (
    fetch_all_and_save, start_scheduler, stop_scheduler,
    get_scheduler_status, get_fetcher,
)


# ---------- 生命周期 ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 DB + 调度器，关闭时停止"""
    init_db()
    start_scheduler(interval_minutes=10)
    # 启动后立即执行一次爬取（如果数据库为空）
    latest = get_latest_batch()
    if not latest:
        asyncio.create_task(fetch_all_and_save())
    yield
    stop_scheduler()


app = FastAPI(title="Hot Hub", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# ---------- 内存缓存（页面请求用，不影响存储） ----------
_cache: dict = {}
CACHE_TTL = 300  # 5 分钟

# 核心爬虫映射
_CORE_FETCHERS = {
    "weibo": weibo.fetch,
    "zhihu": zhihu.fetch,
    "baidu": baidu.fetch,
    "xiaohongshu": xiaohongshu.fetch,
    "douyin": douyin.fetch,
    "toutiao": toutiao.fetch,
}


async def _fetch_with_cache(name: str):
    """带缓存的抓取，单个源失败不影响其他"""
    now = time.time()
    cached = _cache.get(name)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    fetch_fn = _CORE_FETCHERS.get(name) or FETCH_MAP.get(name)
    if not fetch_fn:
        return []

    try:
        data = await fetch_fn()
        if not isinstance(data, list):
            data = []
    except Exception as e:
        print(f"[{name}] 抓取失败: {e}")
        if cached:
            return cached["data"]
        return []

    _cache[name] = {"data": data, "ts": now}
    return data


# ---------- 页面路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """聚合页 — 优先从数据库读取最新数据，回退到实时爬取"""
    latest = get_latest_batch()

    if latest and latest["data"]:
        # 从数据库读取
        platform_data = {}
        for key, name, icon, cat in PLATFORMS:
            entries = latest["data"].get(key, [])
            if not entries:
                continue
            if cat not in platform_data:
                platform_data[cat] = []
            platform_data[cat].append({
                "key": key, "name": name, "icon": icon, "entries": entries,
            })
        update_time = latest["created_at"]
    else:
        # 回退：实时爬取
        keys = [p[0] for p in PLATFORMS]
        results = await asyncio.gather(*[_fetch_with_cache(k) for k in keys])
        platform_data = {}
        for (key, name, icon, cat), data in zip(PLATFORMS, results):
            entries = data if isinstance(data, list) else []
            if not entries:
                continue
            if cat not in platform_data:
                platform_data[cat] = []
            platform_data[cat].append({
                "key": key, "name": name, "icon": icon, "entries": entries,
            })
        update_time = time.strftime("%Y-%m-%d %H:%M:%S")

    categories = []
    for cat_key in CATEGORY_ORDER:
        if cat_key in platform_data:
            categories.append({
                "key": cat_key,
                "name": CATEGORY_NAMES.get(cat_key, cat_key),
                "platforms": platform_data[cat_key],
            })

    active_count = sum(len(cat["platforms"]) for cat in categories)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "categories": categories,
        "update_time": update_time,
        "total_platforms": active_count,
    })


# ---------- API 路由 ----------

@app.get("/api/refresh")
async def refresh():
    """手动触发一次爬取并保存"""
    _cache.clear()
    result = await fetch_all_and_save()
    return {"status": "ok", "msg": "爬取完成并已存储", **result}


@app.get("/api/status")
async def status():
    """查看调度器和存储状态"""
    latest = get_latest_batch()
    sched = get_scheduler_status()
    return {
        "scheduler": sched,
        "latest_batch": {
            "batch_id": latest["batch_id"] if latest else None,
            "created_at": latest["created_at"] if latest else None,
            "platform_count": latest["platform_count"] if latest else 0,
            "item_count": latest["item_count"] if latest else 0,
        },
    }


@app.get("/api/history")
async def history(limit: int = 20):
    """获取爬取批次历史"""
    return {"batches": get_batch_list(limit)}


@app.get("/api/platform/{platform}")
async def platform_history(platform: str, limit: int = 10):
    """获取某个平台的历史数据"""
    data = get_platform_history(platform, limit)
    return {"platform": platform, "records": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
