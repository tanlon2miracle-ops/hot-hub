"""
抖音热榜
"""

import httpx

API_URL = "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
}


async def fetch() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(API_URL)
            resp.raise_for_status()
            data = resp.json()

        items = []
        word_list = data.get("data", {}).get("word_list", [])
        for i, item in enumerate(word_list[:30], 1):
            word = item.get("word", "")
            hot_value = item.get("hot_value", 0)
            url = f"https://www.douyin.com/search/{word}"
            items.append({
                "rank": i,
                "title": word,
                "hot": hot_value,
                "url": url,
            })
        return items

    except Exception:
        return []
