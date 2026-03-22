"""
知乎热榜
方案：使用知乎创作者热门 API（无需 cookie 认证）
"""

import httpx

# 这个 API 端点不需要认证，返回当前热门问题
API_URL = "https://www.zhihu.com/api/v4/creators/rank/hot?domain=0&period=hour&limit=50"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.zhihu.com/",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for i, entry in enumerate(data.get("data", [])[:50], 1):
        q = entry.get("question", {})
        title = q.get("title", "")
        qid = q.get("id", "")
        url = f"https://www.zhihu.com/question/{qid}" if qid else ""
        reaction = entry.get("reaction", {})
        pv = reaction.get("pv", 0)
        hot_text = f"{pv // 10000}万浏览" if pv >= 10000 else str(pv)

        if title:
            items.append({
                "rank": i,
                "title": title,
                "hot": hot_text,
                "url": url,
            })

    return items
