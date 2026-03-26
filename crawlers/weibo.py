"""
微博热搜
使用 hot_band API（含 category/detail_tag 等元数据）
"""

import httpx

API_URL = "https://weibo.com/ajax/statuses/hot_band"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
}


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        resp = await client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

    items = []
    band_list = data.get("data", {}).get("band_list", [])
    for i, item in enumerate(band_list[:50], 1):
        word = item.get("word", "")
        if not word:
            continue
        hot = item.get("num", item.get("raw_hot", 0))
        url = f"https://s.weibo.com/weibo?q=%23{word}%23"
        category = item.get("category", "")
        detail_tag = item.get("detail_tag", "")
        # detail_tag 可能是 dict（新版API）或 str（旧版），统一处理
        if isinstance(detail_tag, dict):
            detail_tag = detail_tag.get("content", "")
        elif not isinstance(detail_tag, str):
            detail_tag = str(detail_tag)
        # 组合摘要：分类 + 详情标签
        summary_parts = []
        if category:
            summary_parts.append(f"[{category}]")
        if detail_tag:
            summary_parts.append(detail_tag)
        summary = " ".join(summary_parts)

        items.append({
            "rank": i,
            "title": word,
            "hot": hot,
            "url": url,
            "summary": summary,
        })

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
