# Hot Hub — 全网热榜聚合

> 🔥 一个页面看完 40+ 平台的热搜热榜，Python + FastAPI 驱动。

![preview](static/preview.jpg)

## 功能

- ✅ **44 个平台**热榜聚合，8 大分类展示
- ✅ **SQLite 结构化存储**，历史数据可追溯
- ✅ **定时自动爬取**（默认每小时），30 天自动清理
- ✅ **智能内容摘要** — 自动为热榜条目补充内容简介
- ✅ 空数据平台自动隐藏，只展示有效内容
- ✅ 5 分钟内存缓存 + 数据库持久化双层架构
- ✅ 分类导航 + 响应式网格布局
- ✅ 数据校验 — 自动过滤空标题和脏数据

## 技术栈

- **后端**：Python 3.10+ / FastAPI
- **爬虫**：httpx + BeautifulSoup + Playwright
- **存储**：SQLite（WAL 模式）
- **调度**：APScheduler
- **前端**：Jinja2 + 原生 CSS

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:8000
```

启动后自动初始化数据库、首次爬取，之后每小时自动更新。

## API

| 路径 | 说明 |
|------|------|
| `/` | 聚合热榜页面 |
| `/api/refresh` | 手动触发爬取 |
| `/api/status` | 调度器状态 |
| `/api/history` | 爬取批次历史 |
| `/api/platform/{name}` | 单平台历史数据 |

---

## 支持平台（44 个）

### ✅ 已接入（37 个）

| 分类 | 平台 |
|------|------|
| 🔥 热搜 | 微博、知乎、百度、抖音、今日头条、腾讯新闻、小红书 |
| 📰 资讯 | 澎湃新闻、新浪新闻、网易新闻、爱范儿、36氪 |
| 💻 科技 | B站热门、掘金、CSDN、V2EX、少数派、IT之家 |
| 👥 社区 | 豆瓣小组、简书、果壳、全球主机交流 |
| 🎬 影音 | AcFun、豆瓣电影、米游社 |
| 🌐 国际 | Hacker News、GitHub Trending、TechCrunch、BBC、CNN、Urban Dictionary |
| 😂 热梗 | B站热搜词、微博热梗、能不能好好说话 |
| 📋 其他 | 知乎日报、地震速报、历史上的今天、IT之家喜加一 |

### ❌ 待修复（7 个）

快手、百度贴吧、虎嗅、HelloGitHub、NodeSeek

---

## 数据存储

SQLite 结构化存储（`data/hot_hub.db`），每次爬取生成一个 batch 快照。WAL 模式读写不阻塞，30 天自动清理。

---

## TODO

- [ ] **快手** / **百度贴吧**：切换可用 API
- [ ] **虎嗅** / **HelloGitHub**：适配新接口
- [ ] **NodeSeek**：添加 Cookie
- [ ] **舆情监测** — 自定义关键词订阅，跨平台追踪热度变化，触发告警推送
- [ ] Docker 一键部署
- [ ] 暗色模式
- [ ] 关键词搜索/过滤
- [ ] 移动端优化
- [ ] 热榜趋势对比

---

## 项目结构

```
hot-hub/
├── app.py                 # FastAPI 入口 + 路由
├── storage.py             # SQLite 存储
├── scheduler.py           # 定时爬取调度
├── crawlers/
│   ├── platforms.py       # 平台注册表 + 分类
│   ├── extra.py           # 扩展平台爬虫
│   ├── enricher.py        # 内容摘要补全
│   ├── weibo.py           # 微博
│   ├── zhihu.py           # 知乎
│   ├── baidu.py           # 百度
│   ├── xiaohongshu.py     # 小红书（Playwright）
│   ├── douyin.py          # 抖音
│   └── toutiao.py         # 今日头条
├── templates/index.html   # 页面模板
├── static/style.css       # 样式
├── data/hot_hub.db        # 数据库（gitignore）
└── requirements.txt
```

## License

MIT
