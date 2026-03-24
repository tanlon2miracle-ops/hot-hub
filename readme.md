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
- ✅ **📰 News日历** — 敏感日期预警 + 历史上的今天，双 Tab 独立页面
- ✅ **🔍 审查监测** — 消失热搜检测，可疑度评分，跨平台联动分析
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
| `/alert` | 📰 News日历（敏感日期 + 历史上的今天） |
| `/censor` | 🔍 审查监测（消失热搜 + 可疑度排序） |
| `/api/censor` | 审查监测 API（JSON，支持 hours/platform/sort 参数） |
| `/api/censor/ml-status` | ML 模块就绪状态 |
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

### 📰 News日历

独立页面 `/alert`，双 Tab 设计：

**⚠️ 敏感日期预警**（75+ 事件覆盖全年）
- 按"今天 / 即将到来 / 刚过去"分组展示
- 红 🔴 / 黄 🟡 / 灰 ⚪ 颜色区分紧急程度
- 支持 `?days=7` 自定义预警范围

![敏感日期预警](docs/news-calendar-sensitive.jpg)

**📜 历史上的今天**（百度百科数据源）
- 自动获取当天历史事件、名人诞辰/逝世
- 支持按"事件 / 出生 / 逝世"分类过滤
- 展示年份、距今年数、事件详情

![历史上的今天](docs/news-calendar-history.jpg)

### 🔍 审查监测

独立页面 `/censor`，实时检测热搜消失：

**双模检测**
- 🔄 **全量 Diff**：每次爬取自动对比前后两批数据，覆盖全部 44 平台
- ⚡ **闪删高频监测**：每 5 分钟快照微博/知乎/百度/抖音/头条，捕捉快速删除

**多因子可疑度评分 v2**
- 📊 **8 维评分因子**：热度等级、曝光时长、排名位置、跨平台联动、深夜删除、极速上榜、热度突变、敏感词命中
- 🔥 **热度归一化**：基于排名百分位的 5 级热度（爆/高热/热门/温热/普通）
- ⏱️ **曝光时长回溯**：从数据库追溯条目首次出现时间，精确计算在榜时长
- 🔗 **跨平台联动**：同一话题在多个平台同时消失 → 自动聚合，可疑度大幅加权
- 🌙 **时段敏感**：深夜/凌晨删除自动加分（人工审查高发期）
- ⚡ **极速上榜检测**：短时间冲到高排名就被撤 = 敏感话题特征
- 📈 **热度突变检测**：排名骤升或热度暴涨后突然消失
- 🏷️ **敏感词规则引擎**：基于关键词库的标题初筛
- ⏳ **时间衰减加权**：指数半衰期衰减，近期事件排序优先

**前端交互**
- 默认按可疑度排序，支持切换加权排序/时间/热度
- 每条结果展示评分因子标签（hover 查看详情）
- 时间筛选（1h / 6h / 24h / 3天 / 7天）
- 平台筛选 + 统计概览（高热消失、速删、跨平台联动、突变消失数）
- ML 模块就绪状态指示

**TODO — ML 增强（需训练/接入模型）**
- 🔲 **语义敏感度分类** — BERT-base-chinese / LLM few-shot / embedding 相似度
- 🔲 **情感倾向分析** — SnowNLP / ERNIE-Sentiment / RoBERTa-wwm
- 🔲 **命名实体识别** — LAC / HanLP / spaCy，关联敏感实体库
- 🔲 **语义话题聚类** — sentence-transformers + HDBSCAN（替代字符串匹配）
- 🔲 **降温曲线检测** — 学习"正常降温" vs "审查删除"的排名时序模式

### ❌ 待修复（7 个）

快手、百度贴吧、虎嗅、HelloGitHub、NodeSeek

---

## 数据存储

SQLite 结构化存储（`data/hot_hub.db`），每次爬取生成一个 batch 快照。WAL 模式读写不阻塞，30 天自动清理。

---

## TODO

- [ ] **ML 增强** — 接入 NLP 模型提升可疑度评分精度（详见审查监测 v2 TODO）
- [ ] **快手** / **百度贴吧**：切换可用 API
- [ ] **虎嗅** / **HelloGitHub**：适配新接口
- [ ] **NodeSeek**：添加 Cookie
- [ ] **舆情风控** — 面向视频评论场景：动态敏感词库 + 每日避雷简报 + 评论预检 API + 实时告警推送
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
├── censor.py              # 🔍 审查监测（diff + 闪删 + 可疑度评分）
├── crawlers/
│   ├── platforms.py       # 平台注册表 + 分类
│   ├── extra.py           # 扩展平台爬虫
│   ├── sensitive_dates.json # ⚠️ 敏感日历数据（75+ 事件）
│   ├── history_today.py    # 📜 历史上的今天（百度百科 API）
│   ├── enricher.py        # 内容摘要补全
│   ├── weibo.py           # 微博
│   ├── zhihu.py           # 知乎
│   ├── baidu.py           # 百度
│   ├── xiaohongshu.py     # 小红书（Playwright）
│   ├── douyin.py          # 抖音
│   └── toutiao.py         # 今日头条
├── templates/
│   ├── index.html         # 热榜主页
│   ├── alert.html         # News日历页面
│   └── censor.html        # 审查监测页面
├── static/style.css       # 样式
├── data/hot_hub.db        # 数据库（gitignore）
└── requirements.txt
```

## License

MIT
