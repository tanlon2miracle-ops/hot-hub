"""
微博热搜
使用微博移动端 API
"""

import httpx

API_URL = "https://weibo.com/ajax/side/hotSearch"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
}


async def fetch() -> list[dict]:
    """
    返回: [{"rank": 1, "title": "...", "hot": 123456, "url": "..."}]
    """
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    realtime = data.get("data", {}).get("realtime", [])
    for i, item in enumerate(realtime[:50], 1):
        word = item.get("word", "")
        hot = item.get("num", 0)
        url = f"https://s.weibo.com/weibo?q=%23{word}%23"
        items.append({
            "rank": i,
            "title": word,
            "hot": hot,
            "url": url,
        })

    return items
