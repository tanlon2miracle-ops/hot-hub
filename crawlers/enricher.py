"""
后台摘要补全
对没有自带 summary 的热点条目，异步抓取 URL 页面提取摘要
仅对 Top N 条目执行，避免请求过多
"""

import asyncio
from crawlers.summarizer import extract_summary

# 每个平台最多补全前 N 条
TOP_N = 5
# 并发限制
CONCURRENCY = 5


async def enrich_summaries(platform_data: dict) -> dict:
    """
    为缺少 summary 的条目补全摘要
    platform_data: {"weibo": [{rank, title, hot, url, summary?}, ...], ...}
    """
    # 搜索页 URL 不适合抓摘要（会拿到站点通用描述）
    SKIP_DOMAINS = [
        "search.bilibili.com", "s.weibo.com", "www.douyin.com/search",
        "s.search.bilibili.com", "search.douyin.com",
    ]

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = []

    for platform, items in platform_data.items():
        for item in items[:TOP_N]:
            if item.get("summary"):
                continue  # 已有摘要
            url = item.get("url", "")
            if not url:
                continue
            # 跳过搜索类 URL
            if any(d in url for d in SKIP_DOMAINS):
                continue

            async def _fill(it=item):
                async with sem:
                    try:
                        summary = await extract_summary(it["url"])
                        if summary:
                            it["summary"] = summary
                    except Exception:
                        pass

            tasks.append(_fill())

    if tasks:
        await asyncio.gather(*tasks)

    return platform_data
