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
    data = await _get_json("https://api-article.huxiu.com/web/article/articleList?page=1&pagesize=30")
    items = []
    for i, v in enumerate(data.get("data", {}).get("datalist", [])[:30], 1):
        items.append({
            "rank": i,
            "title": v.get("title", ""),
            "hot": "",
            "url": f'https://www.huxiu.com/article/{v.get("aid", "")}' if v.get("aid") else "",
        })
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
    data = await _get_json("https://api.hellogithub.com/v1/periodical/hot/?page=1&page_size=30")
    items = []
    for i, v in enumerate(data.get("data", [])[:30], 1):
        items.append({
            "rank": i,
            "title": f'{v.get("name", "")} - {v.get("title", "")}',
            "hot": f'⭐{v.get("stars_str", "")}',
            "url": v.get("github_url", v.get("url", "")),
        })
    return items


# ========== NodeSeek ==========
async def fetch_nodeseek():
    html = await _get_html("https://www.nodeseek.com/")
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
    for i, v in enumerate(data.get("data", {}).get("list", [])[:20], 1):
        post = v.get("post", {})
        items.append({
            "rank": i,
            "title": post.get("subject", ""),
            "hot": "",
            "url": f'https://www.miyoushe.com/ys/article/{post.get("post_id", "")}' if post.get("post_id") else "",
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


# ========== 调度表 ==========
FETCH_MAP = {
    "bilibili": fetch_bilibili,
    "acfun": fetch_acfun,
    "kuaishou": fetch_kuaishou,
    "tieba": fetch_tieba,
    "qq_news": fetch_qq_news,
    "weibo_sina": fetch_weibo_sina,
    "sina_news": fetch_sina_news,
    "netease_news": fetch_netease_news,
    "thepaper": fetch_thepaper,
    "ifanr": fetch_ifanr,
    "kr36": fetch_kr36,
    "huxiu": fetch_huxiu,
    "juejin": fetch_juejin,
    "csdn": fetch_csdn,
    "ithome": fetch_ithome,
    "ithome_xjy": fetch_ithome_xjy,
    "v2ex": fetch_v2ex,
    "sspai": fetch_sspai,
    "hellogithub": fetch_hellogithub,
    "nodeseek": fetch_nodeseek,
    "cto51": fetch_cto51,
    "douban_group": fetch_douban_group,
    "douban_movie": fetch_douban_movie,
    "hupu": fetch_hupu,
    "coolapk": fetch_coolapk,
    "ngabbs": fetch_ngabbs,
    "pojie52": fetch_pojie52,
    "hostloc": fetch_hostloc,
    "jianshu": fetch_jianshu,
    "guokr": fetch_guokr,
    "weread": fetch_weread,
    "miyoushe": fetch_miyoushe,
    "lol": fetch_lol,
    "weatheralarm": fetch_weatheralarm,
    "earthquake": fetch_earthquake,
    "history": fetch_history,
    "zhihu_daily": fetch_zhihu_daily,
}
