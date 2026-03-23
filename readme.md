# Hot Hub — 全网热榜聚合

> 🔥 一个页面看完 40+ 平台的热搜热榜，Python + FastAPI 驱动。

## 功能

- ✅ **44 个平台**热榜聚合，8 大分类展示
- ✅ **SQLite 结构化存储**，历史数据可追溯
- ✅ **定时自动爬取**（默认每小时），30 天自动清理
- ✅ **智能内容摘要** — 自动为热榜条目补充内容简介
- ✅ 没有爬到数据的平台自动隐藏，页面只展示有效内容
- ✅ 5 分钟内存缓存 + 数据库持久化双层架构
- ✅ 分类快速跳转导航
- ✅ 响应式网格布局
- ✅ 数据校验 — 自动过滤空标题和脏数据

## 技术栈

- **后端**：Python 3.10+ / FastAPI
- **爬虫**：httpx + BeautifulSoup（各平台公开 API / 页面解析）
- **存储**：SQLite（WAL 模式，支持并发读写）
- **调度**：APScheduler（异步调度，与 FastAPI 生命周期集成）
- **前端**：Jinja2 模板 + 原生 CSS
- **浏览器渲染**：Playwright（用于小红书等 JS 渲染页面）

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:8000
```

启动后：
1. 自动初始化 SQLite 数据库（`data/hot_hub.db`）
2. 如果数据库为空，立即执行首次爬取
3. 之后每小时自动爬取一次
4. 每天凌晨 3:00 自动清理 30 天前的旧数据

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 聚合热榜页面（优先读 DB，回退实时爬取） |
| `/api/refresh` | GET | 手动触发爬取并保存到数据库 |
| `/api/status` | GET | 查看调度器状态和最新批次信息 |
| `/api/history` | GET | 获取爬取批次历史（`?limit=20`） |
| `/api/platform/{name}` | GET | 查看某平台的历史数据（`?limit=10`） |

---

## 平台支持状态（44 个）

> ✅ 已验证可用（37 个） · ❌ 待修复（7 个）

### 🔥 热搜热榜

| 平台 | 状态 | 说明 |
|------|------|------|
| 微博热搜 | ✅ | weibo.com AJAX API |
| 知乎热榜 | ✅ | creators/rank API（无需 cookie） |
| 百度热搜 | ✅ | top.baidu.com HTML 解析 |
| 抖音热榜 | ✅ | douyin.com Web API |
| 今日头条 | ✅ | toutiao.com 热榜 API |
| 腾讯新闻 | ✅ | r.inews.qq.com API |
| 小红书 | ✅ | Playwright 浏览器渲染，DOM 提取热门笔记 |
| 快手 | ❌ | Web 端 SSR 解析失败，待换方案 |
| 百度贴吧 | ❌ | API 返回非 JSON，待修复 |

### 📰 资讯

| 平台 | 状态 | 说明 |
|------|------|------|
| 澎湃新闻 | ✅ | thepaper.cn 侧栏 API |
| 新浪新闻 | ✅ | newsapp.sina.cn API |
| 网易新闻 | ✅ | m.163.com API |
| 爱范儿 | ✅ | ifanr.com API |
| 36氪 | ✅ | 36kr.com gateway API |
| 虎嗅 | ❌ | API 返回空数据，待修复 |

### 💻 科技

| 平台 | 状态 | 说明 |
|------|------|------|
| B站热门 | ✅ | bilibili.com 公开 API |
| 掘金热榜 | ✅ | juejin.cn API |
| CSDN排行 | ✅ | blog.csdn.net API |
| V2EX | ✅ | v2ex.com 公开 API |
| 少数派 | ✅ | sspai.com API |
| IT之家 | ✅ | ithome.com 页面解析 |
| HelloGitHub | ❌ | API 404，接口已变更 |
| NodeSeek | ❌ | 403 反爬，待加 cookie |

### 👥 社区

| 平台 | 状态 | 说明 |
|------|------|------|
| 豆瓣小组 | ✅ | douban.com 发现页解析 |
| 简书 | ✅ | jianshu.com 首页解析 |
| 果壳 | ✅ | guokr.com API |
| 全球主机交流 | ✅ | hostloc.com 论坛解析 |

### 🎬 影音游戏

| 平台 | 状态 | 说明 |
|------|------|------|
| AcFun | ✅ | acfun.cn 排行 API |
| 豆瓣电影 | ✅ | movie.douban.com API |
| 米游社 | ✅ | mihoyo.com 论坛 API（已修复富文本标记清理） |

### 🌐 国际

| 平台 | 状态 | 说明 |
|------|------|------|
| Hacker News | ✅ | HN 官方 API |
| GitHub Trending | ✅ | github.com 趋势页解析 |
| TechCrunch | ✅ | techcrunch.com RSS/API |
| BBC News | ✅ | bbc.com 头条 API |
| CNN | ✅ | cnn.com 头条 API |
| Urban Dictionary | ✅ | 每日热词 + 释义 |

### 😂 热梗

| 平台 | 状态 | 说明 |
|------|------|------|
| B站热搜词 | ✅ | Bilibili 实时搜索热词 Top 30 |
| 微博热梗 | ✅ | 筛选幽默/综艺/作品衍生类热搜 |
| 能不能好好说话 | ✅ | 热搜缩写翻译（YYDS → 永远滴神） |

### 📋 其他

| 平台 | 状态 | 说明 |
|------|------|------|
| 知乎日报 | ✅ | daily.zhihu.com API |
| 地震速报 | ✅ | 中国地震台网 |
| 历史上的今天 | ✅ | 历史事件 API |
| IT之家喜加一 | ✅ | 免费游戏信息 |

---

## 统计

| 状态 | 数量 |
|------|------|
| ✅ 已通过 | 37 |
| ❌ 待修复 | 7 |
| **总计** | **44** |

---

## 数据存储

采用 SQLite 结构化存储，数据库文件位于 `data/hot_hub.db`。

### 表结构

```
fetch_batch          # 爬取批次
├── id               # 批次 ID（自增）
├── created_at       # 爬取时间
├── platform_count   # 成功平台数
└── item_count       # 总条目数

hot_item             # 热榜条目
├── id               # 条目 ID
├── batch_id         # 所属批次（外键）
├── platform         # 平台 key（weibo/zhihu/...）
├── rank             # 排名
├── title            # 标题
├── hot              # 热度值
├── url              # 链接
├── summary          # 内容摘要（自动补全）
└── extra            # 扩展 JSON 字段
```

### 存储策略

- **每次爬取 = 一个 batch**，完整记录当时各平台的快照
- **WAL 模式**：读写不互斥，页面访问和后台爬取互不阻塞
- **30 天自动清理**：每天凌晨 3:00 清理过期数据 + VACUUM

---

## TODO

### 高优先级
- [ ] **快手**：切换为移动端 API 或 SSR 方案
- [ ] **百度贴吧**：更换可用 API 端点

### 中优先级
- [ ] **虎嗅**：更换 API 端点（当前返回空）
- [ ] **HelloGitHub**：适配新版 API（v1 已下线）

### 低优先级
- [ ] **NodeSeek**：添加 Cookie 或切换 API

### 功能增强
- [x] ~~定时自动刷新（后台任务）~~
- [x] ~~数据历史存档~~
- [x] ~~国际平台（HN、GitHub、TechCrunch、BBC、CNN）~~
- [x] ~~热梗分类（B站热搜词、微博热梗、nbnhhsh）~~
- [x] ~~内容摘要自动补全~~
- [x] ~~数据校验（过滤空标题和脏数据）~~
- [x] ~~米游社富文本标记清理~~
- [ ] Docker 一键部署
- [ ] 暗色模式
- [ ] 按关键词搜索/过滤
- [ ] 移动端优化
- [ ] 热榜趋势对比（基于历史数据）

---

## 项目结构

```
hot-hub/
├── app.py                 # FastAPI 入口 + 路由
├── storage.py             # SQLite 结构化存储
├── scheduler.py           # APScheduler 定时爬取调度
├── crawlers/
│   ├── __init__.py
│   ├── platforms.py       # 平台注册表 + 分类配置
│   ├── extra.py           # 扩展平台爬虫
│   ├── enricher.py        # 内容摘要自动补全
│   ├── summarizer.py      # 摘要处理（搜索页 URL 跳过逻辑等）
│   ├── weibo.py           # 微博热搜
│   ├── zhihu.py           # 知乎热榜
│   ├── baidu.py           # 百度热搜
│   ├── xiaohongshu.py     # 小红书（Playwright）
│   ├── douyin.py          # 抖音热榜
│   └── toutiao.py         # 今日头条
├── templates/
│   └── index.html         # 聚合展示页
├── static/
│   └── style.css          # 样式
├── data/                  # SQLite 数据库（gitignore）
│   └── hot_hub.db
├── requirements.txt
└── README.md
```

## ⚠️ 注意

- 各平台接口随时可能变更，爬虫需要定期维护
- 默认每小时爬取一次，可在启动时调整 `start_scheduler(interval_minutes=N)`
- `data/` 目录已加入 `.gitignore`，数据库不会上传到 Git
- 仅供个人学习使用

## License

MIT
