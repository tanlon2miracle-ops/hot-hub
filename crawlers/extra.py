"""
通用爬虫：大部分平台使用相似的公开 API 或 HTML 解析
这里集中实现，由 registry 统一调度
"""

import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA}


async def _get_json(url, headers=None, **kwargs):
    h = {**HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=10, headers=h, follow_redirects=True) as c:
        r = await c.get(url, **kwargs)
        r.raise_for_status()
        return r.json()


async def _get_html(url, headers=None):
    h = {**HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=10, headers=h, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.text


def _validate_items(items: list) -> list:
    """过滤无效条目：title 为空或纯空白的直接丢弃，重新编号 rank"""
    valid = []
    for item in items:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        item["title"] = title
        # url 清洗
        url = (item.get("url") or "").strip()
        item["url"] = url
        valid.append(item)
    # 重新编号
    for i, item in enumerate(valid, 1):
        item["rank"] = i
    return valid


# ========== B站 ==========
async def fetch_bilibili():
    data = await _get_json("https://api.bilibili.com/x/web-interface/popular?ps=30&pn=1")
    items = []
    for i, v in enumerate(data.get("data", {}).get("list", [])[:30], 1):
        desc = v.get("desc", "")
        rcmd = v.get("rcmd_reason", {}).get("content", "")
        summary = desc if desc and desc != v.get("title", "") else rcmd
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": f'{v.get("stat", {}).get("view", 0) // 10000}万播放',
            "url": f'https://www.bilibili.com/video/{v.get("bvid", "")}',
            "summary": summary,
        })
    return items


# ========== AcFun ==========
async def fetch_acfun():
    data = await _get_json("https://www.acfun.cn/rest/pc-direct/rank/channel?channelId=&subChannelId=&rankPeriod=DAY&rankLimit=30")
    items = []
    for i, v in enumerate(data.get("rankList", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": str(v.get("bananaCount", "")),
            "url": f'https://www.acfun.cn/v/ac{v.get("dougaId", "")}',
        })
    return items


# ========== 快手 ==========
async def fetch_kuaishou():
    # 快手 Web 端热搜
    try:
        html = await _get_html("https://www.kuaishou.com/brilliant")
        soup = BeautifulSoup(html, "lxml")
        import re, json as j
        m = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        if m:
            state = j.loads(m.group(1))
            items = []
            for key, val in state.items():
                if "BrilliantPhotoList" in key and isinstance(val, dict):
                    caption = val.get("caption", "")
                    pid = val.get("id", "")
                    if caption:
                        items.append({
                            "rank": len(items) + 1,
                            "title": caption,
                            "hot": "",
                            "url": f"https://www.kuaishou.com/short-video/{pid}" if pid else "",
                        })
                    if len(items) >= 30:
                        break
            if items:
                return items
    except Exception:
        pass
    return []


# ========== 百度贴吧 ==========
async def fetch_tieba():
    # 百度贴吧旧接口已返回 HTML 而非 JSON，改用 HTML 解析
    try:
        html = await _get_html("https://tieba.baidu.com/hottopic/browse/topicList")
        soup = BeautifulSoup(html, "lxml")
        items = []
        # 尝试从页面提取热议话题
        for i, el in enumerate(soup.select(".topic-top-item, .topic-item, a.topic-text")[:30], 1):
            title = el.get_text(strip=True)
            href = el.get("href", "")
            if not title or len(title) < 2:
                continue
            url = f"https://tieba.baidu.com{href}" if href.startswith("/") else href
            items.append({"rank": i, "title": title, "hot": "", "url": url})
        if items:
            return items
    except Exception:
        pass
    # 回退：尝试直接从 JSON 解析（兼容旧版本）
    try:
        data = await _get_json("https://tieba.baidu.com/hottopic/browse/topicList?res_type=1")
        items = []
        for i, v in enumerate(data.get("data", {}).get("bang_topic", {}).get("topic_list", [])[:30], 1):
            items.append({
                "rank": i,
                "title": v.get("topic_name", ""),
                "hot": v.get("discuss_num", ""),
                "url": v.get("topic_url", ""),
            })
        return items
    except Exception:
        return []


# ========== 腾讯新闻 ==========
async def fetch_qq_news():
    data = await _get_json("https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=30")
    items = []
    for i, v in enumerate(data.get("idlist", [{}])[0].get("newslist", [])[:30], 1):
        if not v.get("title"):
            continue
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": v.get("hotEvent", {}).get("hotScore", ""),
            "url": v.get("url", v.get("surl", "")),
            "summary": v.get("abstract", v.get("desc", "")),
        })
    return items


# ========== 新浪热榜 ==========
async def fetch_weibo_sina():
    data = await _get_json("https://www.sina.com.cn/api/hotword.json")
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("name", ""),
            "hot": v.get("fclick", ""),
            "url": v.get("url", ""),
        })
    return items


# ========== 新浪新闻 ==========
async def fetch_sina_news():
    data = await _get_json("https://newsapp.sina.cn/api/hotlist?newsId=HB-1-snhs%2FtopNew-all&_=1")
    items = []
    info = data.get("data", {}).get("hotList", [])
    for i, v in enumerate(info[:30], 1):
        info2 = v.get("info", {})
        items.append({
            "rank": i,
            "title": info2.get("title", v.get("title", "")),
            "hot": "",
            "url": info2.get("url", v.get("url", "")),
        })
    return items


# ========== 网易新闻 ==========
async def fetch_netease_news():
    data = await _get_json("https://m.163.com/fe/api/hot/news/flow?page=0&size=30")
    items = []
    for i, v in enumerate(data.get("data", {}).get("list", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://www.163.com/dy/article/{v.get("skipID", "")}' if v.get("skipID") else "",
        })
    return items


# ========== 澎湃新闻 ==========
async def fetch_thepaper():
    data = await _get_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar")
    items = []
    hot = data.get("data", {}).get("hotNews", [])
    for i, v in enumerate(hot[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("name", ""),
            "hot": "",
            "url": f'https://www.thepaper.cn/newsDetail_forward_{v.get("contId", "")}' if v.get("contId") else "",
        })
    return items


# ========== 爱范儿 ==========
async def fetch_ifanr():
    data = await _get_json("https://sso.ifanr.com/api/v5/wp/buzz/?limit=30")
    items = []
    for i, v in enumerate(data.get("objects", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("post_title", ""),
            "hot": "",
            "url": v.get("post_url", ""),
        })
    return items


# ========== 36氪 ==========
async def fetch_kr36():
    data = await _get_json("https://36kr.com/api/newsflash?per_page=30")
    items = []
    for i, v in enumerate(data.get("data", {}).get("items", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://36kr.com/newsflashes/{v.get("id", "")}' if v.get("id") else "",
            "summary": v.get("description", "")[:200],
        })
    return items


# ========== 虎嗅 ==========
async def fetch_huxiu():
    # 虎嗅 API 需要 POST + platform 参数（2026 年接口变更）
    headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.huxiu.com/",
        "Origin": "https://www.huxiu.com",
    }
    async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as c:
        resp = await c.post(
            "https://api-article.huxiu.com/web/article/articleList",
            data={"platform": "www", "page": 1, "pagesize": 30,
                  "refer_page": "channel", "channel_id": 0},
        )
        resp.raise_for_status()
        data = resp.json()
    items = []
    for i, v in enumerate(data.get("data", {}).get("datalist", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://www.huxiu.com/article/{v.get("aid", "")}' if v.get("aid") else "",
        })
    # 如果 API 返回空，回退到 HTML 解析
    if not items:
        try:
            resp2 = await c.get("https://www.huxiu.com/channel/all.html")
            soup = BeautifulSoup(resp2.text, "lxml")
            for i, a in enumerate(soup.select("h2 a, .article-item-title a")[:30], 1):
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if title and len(title) > 3:
                    url = f"https://www.huxiu.com{href}" if href.startswith("/") else href
                    items.append({"rank": i, "title": title, "hot": "", "url": url})
        except Exception:
            pass
    return items


# ========== 掘金 ==========
async def fetch_juejin():
    data = await _get_json(
        "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot&spider=0",
        headers={"Content-Type": "application/json"},
    )
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        info = v.get("content", {})
        items.append({
            "rank": i,
            "title": info.get("title", ""),
            "hot": "",
            "url": f'https://juejin.cn/post/{info.get("content_id", "")}' if info.get("content_id") else "",
        })
    return items


# ========== CSDN ==========
async def fetch_csdn():
    data = await _get_json("https://blog.csdn.net/phoenix/web/blog/hot-rank?page=0&pageSize=30")
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("articleTitle", ""),
            "hot": v.get("hotRankScore", ""),
            "url": v.get("articleDetailUrl", ""),
        })
    return items


# ========== IT之家 ==========
async def fetch_ithome():
    data = await _get_json("https://m.ithome.com/api/news/newslistpageget?categoryid=0&dt=0&startid=0")
    items = []
    for i, v in enumerate(data.get("Result", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": v.get("slink", v.get("url", "")),
            "summary": v.get("description", "")[:200],
        })
    return items


# ========== IT之家喜加一 ==========
async def fetch_ithome_xjy():
    data = await _get_json("https://m.ithome.com/api/news/newslistpageget?categoryid=39&dt=0&startid=0")
    items = []
    for i, v in enumerate(data.get("Result", [])[:20], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": v.get("slink", v.get("url", "")),
            "summary": v.get("description", "")[:200],
        })
    return items


# ========== V2EX ==========
async def fetch_v2ex():
    data = await _get_json("https://www.v2ex.com/api/topics/hot.json")
    items = []
    for i, v in enumerate(data[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": f'{v.get("replies", 0)}回复',
            "url": v.get("url", ""),
        })
    return items


# ========== 少数派 ==========
async def fetch_sspai():
    data = await _get_json("https://sspai.com/api/v1/article/tag/page/get?limit=30&offset=0&tag=%E7%83%AD%E9%97%A8%E6%96%87%E7%AB%A0")
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://sspai.com/post/{v.get("id", "")}' if v.get("id") else "",
        })
    return items


# ========== HelloGitHub ==========
async def fetch_hellogithub():
    # /v1/ 根接口返回热门项目列表（/v1/periodical/hot/ 已 404）
    data = await _get_json("https://api.hellogithub.com/v1/?page=1&page_size=30")
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        name = v.get("name", v.get("full_name", ""))
        title = v.get("title", v.get("title_en", ""))
        display = f"{name} - {title}" if name and title else (name or title)
        items.append({
            "rank": i,
            "title": display,
            "hot": f'⭐{v.get("stars_str", v.get("stars", ""))}',
            "url": v.get("github_url", v.get("url", "")),
            "summary": v.get("summary", v.get("summary_en", ""))[:100],
        })
    return items


# ========== NodeSeek ==========
async def fetch_nodeseek():
    # NodeSeek 有 Cloudflare 防护，需要更完整的 headers
    nodeseek_headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    async with httpx.AsyncClient(timeout=15, headers=nodeseek_headers,
                                  follow_redirects=True) as c:
        resp = await c.get("https://www.nodeseek.com/")
    html = resp.text
    if resp.status_code == 403 or "post-title" not in html:
        return []  # 被 CF 拦截，静默返回空
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".post-title a")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://www.nodeseek.com{href}" if href.startswith("/") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== 51CTO ==========
async def fetch_cto51():
    html = await _get_html("https://www.51cto.com/")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".home-hot .hot-list a") or soup.select(".article-list .title a")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": href})
    return items


# ========== 豆瓣小组 ==========
async def fetch_douban_group():
    html = await _get_html("https://www.douban.com/group/explore", headers={"Referer": "https://www.douban.com/"})
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".channel-item .title a") or soup.select(".article h3 a")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": href})
    return items


# ========== 豆瓣电影 ==========
async def fetch_douban_movie():
    data = await _get_json(
        "https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&page_limit=30&page_start=0",
        headers={"Referer": "https://movie.douban.com/"},
    )
    items = []
    for i, v in enumerate(data.get("subjects", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": f'⭐{v.get("rate", "")}',
            "url": v.get("url", ""),
        })
    return items


# ========== 虎扑 ==========
async def fetch_hupu():
    data = await _get_json("https://bbs.hupu.com/api/v2/bbs/topicThreads?topicId=0&page=1&pageSize=30")
    items = []
    for i, v in enumerate(data.get("data", {}).get("topicThreads", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": f'{v.get("replies", 0)}回复',
            "url": f'https://bbs.hupu.com/{v.get("tid", "")}' if v.get("tid") else "",
        })
    return items


# ========== 酷安 ==========
async def fetch_coolapk():
    html = await _get_html("https://www.coolapk.com/")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".feed-item .feed-title a") or soup.select(".item-title a")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://www.coolapk.com{href}" if href.startswith("/") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== NGA ==========
async def fetch_ngabbs():
    html = await _get_html("https://bbs.nga.cn/thread.php?fid=-7")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".topic a") or soup.select("#topicrows a.topic")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://bbs.nga.cn{href}" if href.startswith("/") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== 吾爱破解 ==========
async def fetch_pojie52():
    html = await _get_html("https://www.52pojie.cn/forum.php?mod=guide&view=hot")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".tl th a.xst")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://www.52pojie.cn/{href}" if not href.startswith("http") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== 全球主机交流 ==========
async def fetch_hostloc():
    html = await _get_html("https://hostloc.com/forum.php?mod=forumdisplay&fid=45&orderby=views")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".tl th a.xst") or soup.select(".common a.xst")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://hostloc.com/{href}" if not href.startswith("http") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== 简书 ==========
async def fetch_jianshu():
    html = await _get_html("https://www.jianshu.com/")
    soup = BeautifulSoup(html, "lxml")
    items = []
    posts = soup.select(".note-list li .title") or soup.select("a.title")
    for i, a in enumerate(posts[:20], 1):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = f"https://www.jianshu.com{href}" if href.startswith("/") else href
        if title:
            items.append({"rank": i, "title": title, "hot": "", "url": url})
    return items


# ========== 果壳 ==========
async def fetch_guokr():
    data = await _get_json("https://www.guokr.com/apis/minisite/article.json?retrieve_type=by_subject&limit=20&offset=0")
    items = []
    for i, v in enumerate(data.get("result", [])[:20], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://www.guokr.com/article/{v.get("id", "")}/' if v.get("id") else "",
        })
    return items


# ========== 微信读书 ==========
async def fetch_weread():
    data = await _get_json("https://weread.qq.com/web/bookListInCategory/rising?maxIndex=0&count=30")
    items = []
    for i, v in enumerate(data.get("books", [])[:30], 1):
        info = v.get("bookInfo", v)
        items.append({
            "rank": i,
            "title": info.get("title", ""),
            "hot": info.get("author", ""),
            "url": f'https://weread.qq.com/web/bookDetail/{info.get("bookId", "")}' if info.get("bookId") else "",
        })
    return items


# ========== 米游社 ==========
async def fetch_miyoushe():
    data = await _get_json("https://bbs-api.mihoyo.com/post/wapi/getForumPostList?forum_id=1&gids=2&is_good=false&is_hot=true&page_size=20&sort_type=1")
    items = []
    import re
    for i, v in enumerate(data.get("data", {}).get("list", [])[:20], 1):
        post = v.get("post", {})
        subject = post.get("subject", "")
        # 清理米游社富文本颜色标记
        # 格式: s0¹ / s0² / ss2² / ss 等 — s{1,2} + 可选数字 + 上标数字
        # 这些标记在每个字符前作为样式控制
        subject = re.sub(r's{1,2}\d*[⁰¹²³⁴⁵⁶⁷⁸⁹]+', '', subject)
        # 清理剩余的独立 ss 标记（没有上标数字的情况）
        subject = re.sub(r'(?<=[\u4e00-\u9fff])ss(?=[\u4e00-\u9fff])', '', subject)
        subject = re.sub(r'^ss(?=[\u4e00-\u9fff])', '', subject)
        subject = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', subject)
        subject = subject.strip()
        content = post.get("content", "").strip()
        summary = re.sub(r'[\x00-\x1f]', '', content)[:100] if content else ""
        # 同样清理 summary 里的标记
        summary = re.sub(r's{1,2}\d*[⁰¹²³⁴⁵⁶⁷⁸⁹]+', '', summary)
        summary = re.sub(r'(?<=[\u4e00-\u9fff])ss(?=[\u4e00-\u9fff\w])', '', summary)
        summary = re.sub(r'(?<=[\u4e00-\u9fff])sss(?=[A-Z])', '', summary)
        items.append({
            "rank": i,
            "title": subject,
            "hot": "",
            "url": f'https://www.miyoushe.com/ys/article/{post.get("post_id", "")}' if post.get("post_id") else "",
            "summary": summary,
        })
    return items


# ========== 英雄联盟 ==========
async def fetch_lol():
    data = await _get_json("https://apps.game.qq.com/cmc/cross?serviceId=18&filter=&sortby=sIdxTime&source=web_pc&limit=20&offset=0")
    items = []
    for i, v in enumerate(data.get("data", {}).get("items", [])[:20], 1):
        items.append({
            "rank": i,
            "title": v.get("sTitle", ""),
            "hot": "",
            "url": v.get("sUrl", ""),
        })
    return items


# ========== 气象预警 ==========
async def fetch_weatheralarm():
    data = await _get_json("https://devapi.qweather.com/v7/warning/list?range=cn&key=your_key_here")
    # 需要和风天气 API key，暂返回空
    return []


# ========== 地震速报 ==========
async def fetch_earthquake():
    # 中国地震台网 CENC 公开数据
    h = {**HEADERS}
    async with httpx.AsyncClient(timeout=10, headers=h, verify=False, follow_redirects=True) as c:
        # 优先用 CENC 新版 API
        try:
            r = await c.get("https://news.ceic.ac.cn/index.html?time=2")
            # 回退到老 API
        except Exception:
            pass
        r = await c.get("https://www.ceic.ac.cn/ajax/google?rand=0&num=20")
        if r.status_code != 200:
            # 尝试 USGS 作为后备
            r = await c.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
            r.raise_for_status()
            data = r.json()
            items = []
            for i, f in enumerate(data.get("features", [])[:20], 1):
                p = f.get("properties", {})
                items.append({
                    "rank": i,
                    "title": p.get("title", f'M{p.get("mag","")} {p.get("place","")}'),
                    "hot": p.get("time", ""),
                    "url": p.get("url", ""),
                })
            return items
        data = r.json()
    items = []
    for i, v in enumerate(data[:20], 1):
        items.append({
            "rank": i,
            "title": f'M{v.get("M", "")} {v.get("LOCATION_C", "")}',
            "hot": v.get("O_TIME", ""),
            "url": f'https://www.ceic.ac.cn/{v.get("id", "")}' if v.get("id") else "",
        })
    return items


# ========== 历史上的今天 ==========
async def fetch_history():
    import datetime
    today = datetime.date.today()
    data = await _get_json(f"https://baike.baidu.com/cms/home/eventsOnHistory/{today.month:02d}.json")
    # 新格式: {"03": {"0301": [...], "0302": [...]}}
    key = f"{today.month:02d}{today.day:02d}"
    month_key = f"{today.month:02d}"
    month_data = data.get(month_key, data)
    if isinstance(month_data, dict):
        events = month_data.get(key, [])
    else:
        events = data.get(key, [])
    items = []
    for i, v in enumerate(events[:20], 1):
        import re
        title = re.sub(r'<[^>]+>', '', v.get("title", ""))  # 去掉 HTML 标签
        items.append({
            "rank": i,
            "title": title,
            "hot": v.get("year", ""),
            "url": v.get("link", ""),
        })
    return items


# ========== 敏感日历（临近历史大事件预警） ==========
async def fetch_sensitive_dates():
    """读取 data/sensitive_dates.json，返回前后 3 天内的敏感历史事件"""
    import datetime, json, os
    today = datetime.date.today()
    json_path = os.path.join(os.path.dirname(__file__), "sensitive_dates.json")
    if not os.path.exists(json_path):
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    events = db.get("events", [])
    items = []
    for ev in events:
        mm, dd = ev["date"].split("-")
        try:
            ev_date = today.replace(month=int(mm), day=int(dd))
        except ValueError:
            continue
        delta = abs((today - ev_date).days)
        if delta <= 3:
            year_str = f"{ev.get('year', '')}年" if ev.get("year") else ""
            distance = "今天" if delta == 0 else (f"{delta}天后" if ev_date > today else f"{delta}天前")
            tags_str = " ".join(f"[{t}]" for t in ev.get("tags", []))
            items.append({
                "rank": 0,
                "title": f"⚠️ {ev['title']}（{year_str}{ev['date']}，{distance}）",
                "hot": f"{tags_str}",
                "url": "",
            })
    # 按距离排序：越近越靠前
    items.sort(key=lambda x: x["title"])
    for i, item in enumerate(items, 1):
        item["rank"] = i
    return items


# ========== 知乎日报 ==========
async def fetch_zhihu_daily():
    data = await _get_json("https://daily.zhihu.com/api/4/news/latest")
    items = []
    for i, v in enumerate(data.get("stories", [])[:20], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": v.get("hint", ""),
            "url": v.get("url", f'https://daily.zhihu.com/story/{v.get("id", "")}'),
        })
    return items


# ========== Hacker News ==========
async def fetch_hackernews():
    ids = await _get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    items = []
    # 批量取前 30 条详情
    async def _get_item(sid):
        return await _get_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")

    import asyncio
    details = await asyncio.gather(*[_get_item(sid) for sid in ids[:30]])
    for i, v in enumerate(details, 1):
        if not v:
            continue
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": f'{v.get("score", 0)} points',
            "url": v.get("url", f'https://news.ycombinator.com/item?id={v.get("id", "")}'),
            "summary": f'{v.get("descendants", 0)} comments',
        })
    return items


# ========== GitHub Trending ==========
async def fetch_github_trend():
    html = await _get_html("https://github.com/trending")
    soup = BeautifulSoup(html, "lxml")
    items = []
    repos = soup.select("article.Box-row")
    for i, repo in enumerate(repos[:25], 1):
        h2 = repo.select_one("h2 a")
        if not h2:
            continue
        name = h2.get_text(strip=True).replace("\n", "").replace(" ", "")
        href = h2.get("href", "")
        url = f"https://github.com{href}" if href.startswith("/") else href
        desc_el = repo.select_one("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        stars_el = repo.select_one(".float-sm-right") or repo.select_one("span.d-inline-block.float-sm-right")
        stars = stars_el.get_text(strip=True) if stars_el else ""
        items.append({
            "rank": i,
            "title": name,
            "hot": stars,
            "url": url,
            "summary": desc[:200],
        })
    return items


# ========== TechCrunch ==========
async def fetch_techcrunch():
    html = await _get_html("https://techcrunch.com/feed/")
    soup = BeautifulSoup(html, "xml")
    items = []
    for i, item in enumerate(soup.find_all("item")[:20], 1):
        title = item.find("title").text if item.find("title") else ""
        link = item.find("link").text if item.find("link") else ""
        desc = item.find("description")
        summary = ""
        if desc:
            # RSS description 是 HTML，提取纯文本
            desc_soup = BeautifulSoup(desc.text, "lxml")
            summary = desc_soup.get_text(strip=True)[:200]
        items.append({
            "rank": i,
            "title": title,
            "hot": "",
            "url": link,
            "summary": summary,
        })
    return items


# ========== BBC News ==========
async def fetch_bbc_news():
    html = await _get_html("https://feeds.bbci.co.uk/news/rss.xml")
    soup = BeautifulSoup(html, "xml")
    items = []
    for i, item in enumerate(soup.find_all("item")[:25], 1):
        title = item.find("title").text if item.find("title") else ""
        link = item.find("link").text if item.find("link") else ""
        desc = item.find("description")
        summary = desc.text[:200] if desc else ""
        items.append({
            "rank": i,
            "title": title,
            "hot": "",
            "url": link,
            "summary": summary,
        })
    return items


# ========== CNN ==========
async def fetch_cnn():
    html = await _get_html("http://rss.cnn.com/rss/edition.rss")
    soup = BeautifulSoup(html, "xml")
    items = []
    for i, item in enumerate(soup.find_all("item")[:25], 1):
        title = item.find("title").text if item.find("title") else ""
        link = item.find("link").text if item.find("link") else ""
        desc = item.find("description")
        summary = ""
        if desc:
            desc_soup = BeautifulSoup(desc.text, "lxml")
            summary = desc_soup.get_text(strip=True)[:200]
        items.append({
            "rank": i,
            "title": title,
            "hot": "",
            "url": link,
            "summary": summary,
        })
    return items


# ========== B站热搜词 ==========
async def fetch_bili_trending():
    data = await _get_json("https://api.bilibili.com/x/web-interface/search/square?limit=30")
    items = []
    trending = data.get("data", {}).get("trending", {}).get("list", [])
    for i, v in enumerate(trending[:30], 1):
        keyword = v.get("keyword", v.get("show_name", ""))
        items.append({
            "rank": i,
            "title": keyword,
            "hot": "",
            "url": f"https://search.bilibili.com/all?keyword={keyword}",
        })
    return items


# ========== 微博热梗（幽默/搞笑类热搜）==========
async def fetch_weibo_meme():
    h = {**HEADERS, "Referer": "https://weibo.com/"}
    data = await _get_json("https://weibo.com/ajax/statuses/hot_band", headers=h)
    items = []
    band = data.get("data", {}).get("band_list", [])
    # 筛选幽默/搞笑/情感/综艺类别 + 带"好笑/搞笑/梗"标签的
    meme_cats = {"幽默", "幽默,情感", "搞笑", "综艺", "作品衍生"}
    for v in band:
        cat = v.get("category", "")
        word = v.get("word", "")
        if not word:
            continue
        # 匹配分类或关键词
        is_meme = cat in meme_cats or "梗" in word or "笑" in word or "搞笑" in cat
        if is_meme:
            detail = v.get("detail_tag", "")
            items.append({
                "rank": len(items) + 1,
                "title": word,
                "hot": v.get("num", ""),
                "url": f"https://s.weibo.com/weibo?q=%23{word}%23",
                "summary": f"[{cat}] {detail}" if detail else f"[{cat}]",
            })
        if len(items) >= 20:
            break
    return items


# ========== 能不能好好说话（缩写翻译）==========
async def fetch_nbnhhsh():
    """抓当前B站热搜词中的缩写，翻译成人话"""
    import httpx as _hx
    # 先拿B站热搜
    data = await _get_json("https://api.bilibili.com/x/web-interface/search/square?limit=30")
    trending = data.get("data", {}).get("trending", {}).get("list", [])

    # 筛选含纯字母缩写的词
    import re
    abbrs = []
    for t in trending:
        kw = t.get("keyword", "")
        # 找其中的纯字母部分(>=2字母)
        matches = re.findall(r'[a-zA-Z]{2,}', kw)
        for m in matches:
            if m.lower() not in ("the", "and", "for", "blg", "top", "fps", "cos", "pdd"):
                abbrs.append(m)
        if len(abbrs) >= 10:
            break

    if not abbrs:
        # 用一些常见网络热梗缩写
        abbrs = ["yyds", "xswl", "nsdd", "dbq", "zqsg", "nbcs", "ssfd", "plgg", "xjj", "awsl"]

    items = []
    async with _hx.AsyncClient(timeout=8, headers=HEADERS) as client:
        for abbr in abbrs[:15]:
            try:
                r = await client.post(
                    "https://lab.magiconch.com/api/nbnhhsh/guess",
                    json={"text": abbr}
                )
                if r.status_code == 200:
                    results = r.json()
                    if results and results[0].get("trans"):
                        trans = results[0]["trans"][:3]  # 最多3个翻译
                        items.append({
                            "rank": len(items) + 1,
                            "title": abbr.upper(),
                            "hot": "",
                            "url": f"https://lab.magiconch.com/nbnhhsh/?q={abbr}",
                            "summary": " / ".join(trans),
                        })
            except Exception:
                continue
            if len(items) >= 10:
                break

    return items


# ========== Urban Dictionary ==========
async def fetch_urban_dict():
    data = await _get_json("https://api.urbandictionary.com/v0/words_of_the_day")
    items = []
    for i, v in enumerate(data.get("list", [])[:15], 1):
        definition = v.get("definition", "").replace("[", "").replace("]", "")
        items.append({
            "rank": i,
            "title": v.get("word", ""),
            "hot": f'{v.get("thumbs_up", 0)} likes',
            "url": v.get("permalink", ""),
            "summary": definition[:200],
        })
    return items


# ========== 调度表（带校验包装） ==========

def _wrap(fn):
    """包装爬虫函数，自动校验返回数据"""
    async def wrapped():
        items = await fn()
        return _validate_items(items) if items else []
    wrapped.__name__ = fn.__name__
    return wrapped


FETCH_MAP = {
    "bilibili": _wrap(fetch_bilibili),
    "acfun": _wrap(fetch_acfun),
    "kuaishou": _wrap(fetch_kuaishou),
    "tieba": _wrap(fetch_tieba),
    "qq_news": _wrap(fetch_qq_news),
    "weibo_sina": _wrap(fetch_weibo_sina),
    "sina_news": _wrap(fetch_sina_news),
    "netease_news": _wrap(fetch_netease_news),
    "thepaper": _wrap(fetch_thepaper),
    "ifanr": _wrap(fetch_ifanr),
    "kr36": _wrap(fetch_kr36),
    "huxiu": _wrap(fetch_huxiu),
    "juejin": _wrap(fetch_juejin),
    "csdn": _wrap(fetch_csdn),
    "ithome": _wrap(fetch_ithome),
    "ithome_xjy": _wrap(fetch_ithome_xjy),
    "v2ex": _wrap(fetch_v2ex),
    "sspai": _wrap(fetch_sspai),
    "hellogithub": _wrap(fetch_hellogithub),
    "nodeseek": _wrap(fetch_nodeseek),
    "cto51": _wrap(fetch_cto51),
    "douban_group": _wrap(fetch_douban_group),
    "douban_movie": _wrap(fetch_douban_movie),
    "hupu": _wrap(fetch_hupu),
    "coolapk": _wrap(fetch_coolapk),
    "ngabbs": _wrap(fetch_ngabbs),
    "pojie52": _wrap(fetch_pojie52),
    "hostloc": _wrap(fetch_hostloc),
    "jianshu": _wrap(fetch_jianshu),
    "guokr": _wrap(fetch_guokr),
    "weread": _wrap(fetch_weread),
    "miyoushe": _wrap(fetch_miyoushe),
    "lol": _wrap(fetch_lol),
    "weatheralarm": _wrap(fetch_weatheralarm),
    "earthquake": _wrap(fetch_earthquake),
    "history": _wrap(fetch_history),
    "sensitive_dates": _wrap(fetch_sensitive_dates),
    "zhihu_daily": _wrap(fetch_zhihu_daily),
    "hackernews": _wrap(fetch_hackernews),
    "github_trend": _wrap(fetch_github_trend),
    "techcrunch": _wrap(fetch_techcrunch),
    "bbc_news": _wrap(fetch_bbc_news),
    "cnn": _wrap(fetch_cnn),
    "bili_trending": _wrap(fetch_bili_trending),
    "weibo_meme": _wrap(fetch_weibo_meme),
    "nbnhhsh": _wrap(fetch_nbnhhsh),
    "urban_dict": _wrap(fetch_urban_dict),
}
