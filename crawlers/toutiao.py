"""
今日头条热榜
"""

import httpx

API_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.toutiao.com/",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for i, item in enumerate(data.get("data", [])[:30], 1):
        title = item.get("Title", "")
        hot_value = item.get("HotValue", "")
        url = item.get("Url", "")
        items.append({
            "rank": i,
            "title": title,
            "hot": hot_value,
            "url": url,
        })

    return items
