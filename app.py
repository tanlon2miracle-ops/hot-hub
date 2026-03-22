"""
Hot Hub — 全网热榜聚合
FastAPI 入口
"""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from crawlers import weibo, zhihu, baidu, xiaohongshu, douyin, toutiao

app = FastAPI(title="Hot Hub")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# ---------- 缓存 ----------
_cache: dict = {}
CACHE_TTL = 300  # 5 分钟


async def _fetch_with_cache(name: str, fetch_fn):
    """带缓存的抓取，单个源失败不影响其他"""
    now = time.time()
    cached = _cache.get(name)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    try:
        data = await fetch_fn()
    except Exception as e:
        print(f"[{name}] 抓取失败: {e}")
        # 返回过期缓存兜底
        if cached:
            return cached["data"]
        return []

    _cache[name] = {"data": data, "ts": now}
    return data


# ---------- 路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """聚合页"""
    results = await asyncio.gather(
        _fetch_with_cache("weibo", weibo.fetch),
        _fetch_with_cache("zhihu", zhihu.fetch),
        _fetch_with_cache("baidu", baidu.fetch),
        _fetch_with_cache("xiaohongshu", xiaohongshu.fetch),
        _fetch_with_cache("douyin", douyin.fetch),
        _fetch_with_cache("toutiao", toutiao.fetch),
    )

    platforms = [
        {"name": "微博热搜", "icon": "🔴", "items": results[0]},
        {"name": "知乎热榜", "icon": "🔵", "items": results[1]},
        {"name": "百度热搜", "icon": "🟢", "items": results[2]},
        {"name": "小红书热榜", "icon": "📕", "items": results[3]},
        {"name": "抖音热榜", "icon": "🎵", "items": results[4]},
        {"name": "今日头条", "icon": "📰", "items": results[5]},
    ]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "platforms": platforms,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.get("/api/refresh")
async def refresh():
    """手动刷新缓存"""
    _cache.clear()
    return {"status": "ok", "msg": "缓存已清空，下次访问将重新抓取"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
