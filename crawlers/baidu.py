"""
百度热搜
使用 PC 端 API，自带 desc 摘要
"""

import httpx

API_URL = "https://top.baidu.com/api/board?platform=pc&tab=realtime"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    cards = data.get("data", {}).get("cards", [])
    for card in cards:
        for it in card.get("content", []):
            word = it.get("word", it.get("query", ""))
            if not word:
                continue
            desc = it.get("desc", "")
            hot_score = it.get("hotScore", "")
            url = it.get("rawUrl", it.get("url", ""))
            img = it.get("img", "")

            items.append({
                "rank": len(items) + 1,
                "title": word,
                "hot": str(hot_score),
                "url": url,
                "summary": desc,
                "img": img,
            })
            if len(items) >= 30:
                break
        if len(items) >= 30:
            break

    return _validate(items)


def _validate(items):
    valid = []
    for it in items:
        if not (it.get("title") or "").strip():
            continue
        it["title"] = it["title"].strip()
        valid.append(it)
    for i, it in enumerate(valid, 1):
        it["rank"] = i
    return valid
