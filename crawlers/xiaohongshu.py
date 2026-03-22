"""
小红书热榜
通过非官方接口获取
"""

import httpx

# 小红书没有稳定的公开 API，使用第三方聚合或页面解析
# 这里使用一个常见的 workaround
API_URL = "https://edith.xiaohongshu.com/api/sns/v1/search/hot_list"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://www.xiaohongshu.com/",
    "Origin": "https://www.xiaohongshu.com",
}


async def fetch() -> list[dict]:
    """
    小红书热榜抓取
    注意：小红书反爬较严，此接口可能需要定期更新
    """
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(API_URL)
            resp.raise_for_status()
            data = resp.json()

        items = []
        hot_list = data.get("data", {}).get("items", [])
        for i, item in enumerate(hot_list[:30], 1):
            title = item.get("title", "") or item.get("name", "")
            score = item.get("score", "") or item.get("hot_value", "")
            word = item.get("word", title)
            url = f"https://www.xiaohongshu.com/search_result?keyword={word}"
            items.append({
                "rank": i,
                "title": title,
                "hot": score,
                "url": url,
            })
        return items

    except Exception:
        # 备用方案：返回空列表，前端显示"暂无数据"
        return []
