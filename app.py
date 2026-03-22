"""
Hot Hub — 全网热榜聚合
FastAPI 入口 — 支持 40+ 平台
"""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from crawlers import weibo, zhihu, baidu, xiaohongshu, douyin, toutiao
from crawlers.extra import FETCH_MAP
from crawlers.platforms import PLATFORMS, CATEGORY_NAMES, CATEGORY_ORDER

app = FastAPI(title="Hot Hub")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# ---------- 缓存 ----------
_cache: dict = {}
CACHE_TTL = 300  # 5 分钟

# 原始 6 个爬虫映射
_CORE_FETCHERS = {
    "weibo": weibo.fetch,
    "zhihu": zhihu.fetch,
    "baidu": baidu.fetch,
    "xiaohongshu": xiaohongshu.fetch,
    "douyin": douyin.fetch,
    "toutiao": toutiao.fetch,
}


def _get_fetcher(key: str):
    """获取指定平台的爬虫函数"""
    return _CORE_FETCHERS.get(key) or FETCH_MAP.get(key)


async def _fetch_with_cache(name: str):
    """带缓存的抓取，单个源失败不影响其他"""
    now = time.time()
    cached = _cache.get(name)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    fetch_fn = _get_fetcher(name)
    if not fetch_fn:
        return []

    try:
        data = await fetch_fn()
    except Exception as e:
        print(f"[{name}] 抓取失败: {e}")
        if cached:
            return cached["data"]
        return []

    _cache[name] = {"data": data, "ts": now}
    return data


# ---------- 路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """聚合页"""
    # 并发抓取所有平台
    keys = [p[0] for p in PLATFORMS]
    results = await asyncio.gather(*[_fetch_with_cache(k) for k in keys])

    # 按分类组织
    platform_data = {}
    for (key, name, icon, cat), data in zip(PLATFORMS, results):
        if cat not in platform_data:
            platform_data[cat] = []
        platform_data[cat].append({
            "key": key,
            "name": name,
            "icon": icon,
            "items": data,
        })

    categories = []
    for cat_key in CATEGORY_ORDER:
        if cat_key in platform_data:
            categories.append({
                "key": cat_key,
                "name": CATEGORY_NAMES.get(cat_key, cat_key),
                "platforms": platform_data[cat_key],
            })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "categories": categories,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_platforms": len(PLATFORMS),
    })


@app.get("/api/refresh")
async def refresh():
    """手动刷新缓存"""
    _cache.clear()
    return {"status": "ok", "msg": "缓存已清空，下次访问将重新抓取"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
