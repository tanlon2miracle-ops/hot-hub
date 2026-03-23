"""
历史上的今天 — 从百度百科获取
返回当天的历史事件列表
"""

import re
import json
import datetime
from typing import List, Dict
import httpx


async def fetch_today() -> List[Dict]:
    """获取今天的历史事件"""
    today = datetime.date.today()
    month = f"{today.month:02d}"
    day = f"{today.month:02d}{today.day:02d}"

    url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month}.json"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://baike.baidu.com/",
        })
        resp.raise_for_status()
        data = resp.json()

    events = data.get(month, {}).get(day, [])
    results = []
    for ev in events:
        title = _strip_html(ev.get("title", ""))
        desc = _strip_html(ev.get("desc", ""))
        year = ev.get("year", "")
        ev_type = ev.get("type", "event")  # birth / death / event
        link = ev.get("link", "")

        # 类型 emoji
        type_icon = {"birth": "👶", "death": "✝️"}.get(ev_type, "📜")

        results.append({
            "year": year,
            "title": title,
            "desc": desc,
            "type": ev_type,
            "type_icon": type_icon,
            "link": link,
        })

    return results


async def fetch_date(month: int, day: int) -> List[Dict]:
    """获取指定日期的历史事件"""
    mm = f"{month:02d}"
    dd = f"{month:02d}{day:02d}"

    url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{mm}.json"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://baike.baidu.com/",
        })
        resp.raise_for_status()
        data = resp.json()

    events = data.get(mm, {}).get(dd, [])
    results = []
    for ev in events:
        title = _strip_html(ev.get("title", ""))
        desc = _strip_html(ev.get("desc", ""))
        year = ev.get("year", "")
        ev_type = ev.get("type", "event")
        link = ev.get("link", "")
        type_icon = {"birth": "👶", "death": "✝️"}.get(ev_type, "📜")

        results.append({
            "year": year,
            "title": title,
            "desc": desc,
            "type": ev_type,
            "type_icon": type_icon,
            "link": link,
        })

    return results


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    return re.sub(r'<[^>]+>', '', text).strip()
