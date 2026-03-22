"""
内容摘要提取器
从热点链接中提取正文摘要，轻量级实现
"""

import re
import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA}

# 摘要最大长度
MAX_SUMMARY_LEN = 200


async def extract_summary(url: str, timeout: float = 8) -> str:
    """
    从 URL 提取正文摘要。
    优先使用 meta description，回退到正文首段。
    """
    if not url or not url.startswith("http"):
        return ""

    try:
        async with httpx.AsyncClient(
            timeout=timeout, headers=HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return ""

    return _extract_from_html(html)


def _extract_from_html(html: str) -> str:
    """从 HTML 中提取摘要"""
    soup = BeautifulSoup(html, "lxml")

    # 1. 优先：meta description / og:description
    for attr in [
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ]:
        tag = soup.find("meta", attrs=attr)
        if tag:
            content = tag.get("content", "").strip()
            if content and len(content) > 15:
                return _clean(content)

    # 2. 回退：文章正文首段
    # 常见正文容器
    for selector in [
        "article",
        ".article-content",
        ".post-content",
        ".content",
        ".article-body",
        "#article",
        ".detail-content",
        "main",
    ]:
        container = soup.select_one(selector)
        if container:
            text = _first_paragraph(container)
            if text:
                return _clean(text)

    # 3. 最后回退：body 里的第一个有效段落
    body = soup.find("body")
    if body:
        text = _first_paragraph(body)
        if text:
            return _clean(text)

    return ""


def _first_paragraph(element) -> str:
    """提取元素内第一个有意义的段落"""
    for p in element.find_all(["p", "div"], recursive=True):
        text = p.get_text(strip=True)
        # 过滤太短的（导航、按钮等）
        if len(text) > 30:
            return text
    return ""


def _clean(text: str) -> str:
    """清理文本"""
    # 去掉多余空白
    text = re.sub(r"\s+", " ", text).strip()
    # 截断
    if len(text) > MAX_SUMMARY_LEN:
        text = text[:MAX_SUMMARY_LEN] + "..."
    return text
