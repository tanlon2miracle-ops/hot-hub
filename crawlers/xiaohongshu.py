"""
小红书热榜
说明：小红书反爬极严，直接接口和页面均需要复杂签名。
当前方案：使用 trending 搜索关键词方式获取热门内容。
后续可接入 Playwright 浏览器渲染 或 自建中间代理。
"""

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://www.xiaohongshu.com/",
    "Origin": "https://www.xiaohongshu.com",
    "Accept": "application/json",
}

# 小红书 Web 端搜索发现热词接口（有时可用）
SUGGEST_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/search/hot_list"


async def fetch() -> list[dict]:
    """
    尝试获取小红书热搜列表
    如果所有方式都失败，返回空列表（前端会显示"暂无数据"）
    """
    # 尝试 Web 端热词接口
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get(SUGGEST_URL)
            if resp.status_code == 200:
                data = resp.json()
                items = []
                for i, item in enumerate(data.get("data", {}).get("items", [])[:30], 1):
                    title = item.get("title", "") or item.get("name", "") or item.get("word", "")
                    if title:
                        items.append({
                            "rank": i,
                            "title": title,
                            "hot": item.get("score", ""),
                            "url": f"https://www.xiaohongshu.com/search_result?keyword={title}",
                        })
                if items:
                    return items
    except Exception:
        pass

    # 小红书暂无可用免费数据源，返回提示
    return []
