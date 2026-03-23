"""
全平台热榜配置
每个平台定义：name, icon, api_url/fetch_fn, 字段映射
"""

# DailyHotApi 风格的第三方聚合 API 基础地址
# 你可以自部署 DailyHotApi 后改成自己的地址
DAILYHOT_BASE = ""  # 留空则不使用 DailyHotApi

# ========== 平台注册表 ==========
# 每个条目: (调用名, 显示名, emoji图标, 分类)
# 分类: hot=热搜热榜, tech=科技, news=资讯, community=社区, media=影音游戏, other=其他

PLATFORMS = [
    # ---- 热搜热榜 ----
    ("weibo",         "微博热搜",      "🔴", "hot"),
    ("zhihu",         "知乎热榜",      "🔵", "hot"),
    ("baidu",         "百度热搜",      "🟢", "hot"),
    ("douyin",        "抖音热榜",      "🎵", "hot"),
    ("toutiao",       "今日头条",      "📰", "hot"),
    ("xiaohongshu",   "小红书",        "📕", "hot"),
    ("kuaishou",      "快手热榜",      "🟠", "hot"),
    ("tieba",         "百度贴吧",      "💬", "hot"),
    ("qq_news",       "腾讯新闻",      "🐧", "hot"),
    # ("weibo_sina",    "新浪热榜",      "🌐", "hot"),  # 与微博热搜重复

    # ---- 资讯 ----
    ("thepaper",      "澎湃新闻",      "📋", "news"),
    ("sina_news",     "新浪新闻",      "📄", "news"),
    ("netease_news",  "网易新闻",      "📮", "news"),
    ("ifanr",         "爱范儿",        "📱", "news"),
    ("kr36",          "36氪",          "💡", "news"),
    ("huxiu",         "虎嗅",          "🐯", "news"),

    # ---- 科技 ----
    ("bilibili",      "B站热门",       "📺", "tech"),
    ("juejin",        "掘金热榜",      "⛏️", "tech"),
    ("csdn",          "CSDN排行",     "💻", "tech"),
    ("ithome",        "IT之家",        "🏠", "tech"),
    ("v2ex",          "V2EX",          "🅰️", "tech"),
    ("sspai",         "少数派",        "📐", "tech"),
    ("hellogithub",   "HelloGitHub",   "🐙", "tech"),
    ("nodeseek",      "NodeSeek",      "🌍", "tech"),
    # ("cto51",         "51CTO",         "🖥️", "tech"),  # 页面解析失败，与 CSDN/掘金重复

    # ---- 社区 ----
    ("douban_group",  "豆瓣小组",      "🫘", "community"),
    # ("hupu",          "虎扑热帖",      "🏀", "community"),  # API 404，接口已变更
    # ("coolapk",       "酷安热榜",      "🥒", "community"),  # 解析失败，受众窄
    # ("ngabbs",        "NGA热帖",       "🎮", "community"),  # 403 反爬，价值低
    # ("pojie52",       "吾爱破解",      "🔓", "community"),  # 解析空数据，受众窄
    ("hostloc",       "全球主机交流",   "🌏", "community"),
    ("jianshu",       "简书",          "📝", "community"),
    ("guokr",         "果壳",          "🥜", "community"),

    # ---- 影音游戏 ----
    ("acfun",         "AcFun",         "🅰️", "media"),
    ("douban_movie",  "豆瓣电影",      "🎬", "media"),
    # ("weread",        "微信读书",      "📖", "media"),  # API 返回空数据
    ("miyoushe",      "米游社",        "🎯", "media"),
    # ("lol",           "英雄联盟",      "⚔️", "media"),  # API 响应异常，受众窄

    # ---- 其他 ----
    # ("weatheralarm",  "气象预警",      "⛈️", "other"),  # 需要 API Key
    ("earthquake",    "地震速报",      "🌍", "other"),
    ("history",       "历史上的今天",   "📅", "other"),
    # ("sensitive_dates","⚠️ 敏感日历",    "🚨", "other"),  # 独立页面 /alert，不在主页展示
    ("zhihu_daily",   "知乎日报",      "📘", "other"),
    ("ithome_xjy",    "IT之家喜加一",  "🎁", "other"),

    # ---- 国际 ----
    ("hackernews",    "Hacker News",   "🟧", "global"),
    ("github_trend",  "GitHub Trending","🐙", "global"),
    ("techcrunch",    "TechCrunch",    "🟩", "global"),
    ("bbc_news",      "BBC News",      "🔴", "global"),
    ("cnn",           "CNN",           "🔵", "global"),
    ("urban_dict",    "Urban Dictionary","📖","global"),

    # ---- 热梗 ----
    ("bili_trending",  "B站热搜词",    "🔍", "meme"),
    ("weibo_meme",     "微博热梗",     "😂", "meme"),
    ("nbnhhsh",        "能不能好好说话","🗣️", "meme"),
]

# 分类显示名
CATEGORY_NAMES = {
    "hot": "🔥 热搜热榜",
    "news": "📰 资讯",
    "tech": "💻 科技",
    "community": "👥 社区",
    "media": "🎬 影音游戏",
    "global": "🌐 国际",
    "meme": "😂 热梗",
    "other": "📋 其他",
}

CATEGORY_ORDER = ["hot", "news", "tech", "community", "media", "global", "meme", "other"]
