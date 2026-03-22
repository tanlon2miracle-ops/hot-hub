"""
知乎热榜
"""

import httpx

API_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.zhihu.com/hot",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for i, entry in enumerate(data.get("data", [])[:50], 1):
        target = entry.get("target", {})
        title = target.get("title", "")
        hot = entry.get("detail_text", "")
        qid = target.get("id", "")
        url = f"https://www.zhihu.com/question/{qid}" if qid else ""
        items.append({
            "rank": i,
            "title": title,
            "hot": hot,
            "url": url,
        })

    return items
