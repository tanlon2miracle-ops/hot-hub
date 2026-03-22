"""
百度热搜
"""

import httpx
from bs4 import BeautifulSoup

URL = "https://top.baidu.com/board?tab=realtime"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    items = []

    # 百度热搜卡片
    cards = soup.select(".category-wrap_iQLoo .content_1YWBm")
    for i, card in enumerate(cards[:30], 1):
        title_el = card.select_one(".c-single-text-ellipsis")
        hot_el = card.select_one(".hot-index_1Bl1a")
        link_el = card.select_one("a")

        title = title_el.get_text(strip=True) if title_el else ""
        hot = hot_el.get_text(strip=True) if hot_el else ""
        url = link_el.get("href", "") if link_el else ""

        if title:
            items.append({
                "rank": i,
                "title": title,
                "hot": hot,
                "url": url,
            })

    return items
