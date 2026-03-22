"""
小红书热榜
方案：使用 Playwright 无头浏览器渲染发现页，从 DOM 提取热门笔记标题
（小红书反爬极严，纯 HTTP 请求无法获取数据）
"""

import asyncio

# 全局 browser 实例（复用，避免每次都启动）
_browser = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    global _browser
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            _browser = await pw.chromium.launch(headless=True)
        return _browser


async def _fetch_with_playwright() -> list[dict]:
    """用 Playwright 打开小红书发现页，提取热门笔记"""
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900},
    )
    page = await context.new_page()

    try:
        await page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded", timeout=20000)

        # 等待笔记卡片渲染
        await page.wait_for_selector(".note-item", timeout=8000)

        # 关闭登录弹窗（如果有）
        try:
            close_btn = page.locator('[class*="close"]').first
            if await close_btn.is_visible(timeout=2000):
                await close_btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # 从 DOM 提取笔记标题和链接
        items = await page.evaluate("""() => {
            const cards = document.querySelectorAll('.note-item');
            const results = [];
            cards.forEach((card, index) => {
                const titleEl = card.querySelector('[class*="title"]') || card.querySelector('span');
                const linkEl = card.querySelector('a[href*="/explore/"]');
                const title = titleEl ? titleEl.textContent.trim() : '';
                const href = linkEl ? linkEl.href : '';
                if (title) {
                    results.push({
                        rank: index + 1,
                        title: title.substring(0, 100),
                        hot: '',
                        url: href,
                    });
                }
            });
            return results;
        }""")

        return items[:30] if items else []

    except Exception as e:
        print(f"[xiaohongshu] Playwright 抓取失败: {e}")
        return []
    finally:
        await context.close()


async def fetch() -> list[dict]:
    """主入口：使用 Playwright 渲染方案"""
    try:
        items = await _fetch_with_playwright()
        if items:
            return items
    except ImportError:
        print("[xiaohongshu] playwright 未安装，跳过")
    except Exception as e:
        print(f"[xiaohongshu] 错误: {e}")

    return []
