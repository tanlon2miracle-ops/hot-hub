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
from censor import init_censor_db, get_censored_items, get_censor_stats


# ---------- 生命周期 ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 DB + 调度器，关闭时停止"""
    init_db()
    init_censor_db()
    start_scheduler(interval_minutes=60)
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
    try:
        result = await fetch_all_and_save()
        return {"status": "ok", "msg": "爬取完成并已存储", **result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": f"爬取过程出错: {str(e)}"}


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


# ---------- 审查监测 API ----------

@app.get("/api/censor")
async def api_censor(hours: int = 24, platform: str = None, limit: int = 100):
    """获取消失条目列表"""
    items = get_censored_items(limit=limit, platform=platform, hours=hours)
    stats = get_censor_stats(hours=hours)
    return {"stats": stats, "items": items}


# ---------- 审查监测页面 ----------

@app.get("/censor", response_class=HTMLResponse)
async def censor_page(request: Request, hours: int = 24):
    """🔍 审查监测 — 消失的热搜"""
    items = get_censored_items(limit=200, hours=hours)
    stats = get_censor_stats(hours=hours)

    # 按可疑度排序（高的排前面）
    items.sort(key=lambda x: x.get("suspicion", {}).get("score", 0), reverse=True)

    # 按平台分组
    platform_groups = {}
    for item in items:
        p = item["platform"]
        if p not in platform_groups:
            platform_groups[p] = []
        platform_groups[p].append(item)

    # 平台名称映射
    platform_names = {p[0]: (p[1], p[2]) for p in PLATFORMS}

    return templates.TemplateResponse("censor.html", {
        "request": request,
        "stats": stats,
        "items": items,
        "platform_groups": platform_groups,
        "platform_names": platform_names,
        "hours": hours,
    })


# ---------- News 日历独立页面 ----------

@app.get("/alert", response_class=HTMLResponse)
async def alert_page(request: Request, days: int = 3):
    """📰 News 日历 — 敏感日期预警 + 历史上的今天"""
    import datetime, json, os
    from crawlers.history_today import fetch_today

    today = datetime.date.today()
    json_path = os.path.join(os.path.dirname(__file__), "crawlers", "sensitive_dates.json")

    # ---- 敏感日期 ----
    nearby_events = []
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            db = json.load(f)
        for ev in db.get("events", []):
            mm, dd = ev["date"].split("-")
            try:
                ev_date = today.replace(month=int(mm), day=int(dd))
            except ValueError:
                continue
            delta = (ev_date - today).days
            if abs(delta) <= days:
                months = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                if delta == 0:
                    distance_str = "今天"
                    css_class = "active"
                    dist_class = "dist-today"
                elif delta > 0:
                    distance_str = f"{delta}天后"
                    css_class = "upcoming"
                    dist_class = "dist-near"
                else:
                    distance_str = f"{abs(delta)}天前"
                    css_class = "past"
                    dist_class = "dist-far"

                years_ago = ""
                if ev.get("year") and ev["year"] > 0:
                    years_ago = str(today.year - ev["year"])

                nearby_events.append({
                    "title": ev["title"],
                    "date": ev["date"],
                    "year": ev.get("year") if ev.get("year", 0) > 0 else None,
                    "years_ago": years_ago,
                    "tags": ev.get("tags", []),
                    "month_str": months[int(mm)],
                    "day": dd,
                    "delta": delta,
                    "distance_str": distance_str,
                    "css_class": css_class,
                    "dist_class": dist_class,
                })

    # 按 delta 排序：今天 > 即将 > 刚过
    nearby_events.sort(key=lambda x: (abs(x["delta"]), x["delta"]))

    # 分组
    event_groups = []
    today_events = [e for e in nearby_events if e["delta"] == 0]
    upcoming_events = [e for e in nearby_events if e["delta"] > 0]
    past_events = [e for e in nearby_events if e["delta"] < 0]
    if today_events:
        event_groups.append({"label": "🔴 今天", "events": today_events})
    if upcoming_events:
        event_groups.append({"label": "🟡 即将到来", "events": upcoming_events})
    if past_events:
        event_groups.append({"label": "⚪ 刚过去", "events": past_events})

    # ---- 历史上的今天 ----
    history_events = []
    try:
        history_events = await fetch_today()
    except Exception as e:
        print(f"[history_today] 获取失败: {e}")

    return templates.TemplateResponse("alert.html", {
        "request": request,
        "today": today.strftime("%Y年%m月%d日"),
        "today_month": today.month,
        "today_day": today.day,
        "range_days": days,
        "nearby_events": nearby_events,
        "event_groups": event_groups,
        "history_events": history_events,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
