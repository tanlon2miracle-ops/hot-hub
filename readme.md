# Hot Hub — 全网热榜聚合

> 🔥 一个页面看完 40+ 平台的热搜热榜，Python + FastAPI 驱动。

## 功能

- ✅ 40+ 平台热榜聚合，分类展示
- ✅ 5 分钟缓存，单源失败不影响其他
- ✅ 分类快速跳转导航
- ✅ 响应式网格布局
- ✅ `/api/refresh` 手动刷新缓存

## 技术栈

- **后端**：Python 3.10+ / FastAPI
- **爬虫**：httpx + BeautifulSoup（各平台公开 API / 页面解析）
- **前端**：Jinja2 模板 + 原生 CSS

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:8000
```

---

## 平台支持状态

> ✅ 已验证可用 · ⚠️ 接口不稳定/空数据 · ❌ 待修复 · 🔲 计划中

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
| 新浪热榜 | ❌ | API 返回空数据，待换接口 |

### 📰 资讯

| 平台 | 状态 | 说明 |
|------|------|------|
| 澎湃新闻 | ✅ | thepaper.cn 侧栏 API |
| 新浪新闻 | ✅ | newsapp.sina.cn API |
| 网易新闻 | ✅ | m.163.com API |
| 爱范儿 | ✅ | ifanr.com API |
| 36氪 | ❌ | gateway API 500 错误，待修复 |
| 虎嗅 | ❌ | API 返回空数据，待修复 |

### 💻 科技

| 平台 | 状态 | 说明 |
|------|------|------|
| B站热门 | ✅ | bilibili.com 公开 API |
| 掘金热榜 | ✅ | juejin.cn API |
| CSDN排行 | ✅ | blog.csdn.net API |
| V2EX | ✅ | v2ex.com 公开 API |
| 少数派 | ✅ | sspai.com API |
| IT之家 | ❌ | 页面结构变化，选择器需更新 |
| HelloGitHub | ❌ | API 404，接口已变更 |
| NodeSeek | ❌ | 403 反爬，待加 cookie |
| 51CTO | ❌ | 页面结构解析失败 |

### 👥 社区

| 平台 | 状态 | 说明 |
|------|------|------|
| 豆瓣小组 | ✅ | douban.com 发现页解析 |
| 简书 | ✅ | jianshu.com 首页解析 |
| 果壳 | ✅ | guokr.com API |
| 虎扑 | ❌ | API 404，接口已变更 |
| 酷安 | ❌ | 页面解析失败 |
| NGA | ❌ | 403 反爬 |
| 吾爱破解 | ❌ | 页面解析空数据 |
| 全球主机交流 | ✅ | hostloc.com 论坛解析 |

### 🎬 影音游戏

| 平台 | 状态 | 说明 |
|------|------|------|
| AcFun | ✅ | acfun.cn 排行 API |
| 豆瓣电影 | ✅ | movie.douban.com API |
| 米游社 | ✅ | mihoyo.com 论坛 API |
| 微信读书 | ❌ | API 返回空数据 |
| 英雄联盟 | ❌ | API 响应格式异常 |

### 📋 其他

| 平台 | 状态 | 说明 |
|------|------|------|
| 知乎日报 | ❌ | DNS 解析失败，接口可能下线 |
| 气象预警 | ❌ | 需要和风天气 API Key |
| 地震速报 | ❌ | SSL 证书过期 |
| 历史上的今天 | ❌ | 百度百科接口返回空 |
| IT之家喜加一 | ❌ | 页面解析空数据 |

---

## 统计

| 状态 | 数量 |
|------|------|
| ✅ 已通过 | 23 |
| ❌/⚠️ 待修复 | 20 |
| **总计** | **43** |

---

## TODO

待修复和后续计划：

### 高优先级（核心热搜）
- [ ] **快手**：切换为移动端 API 或 SSR 方案
- [ ] **百度贴吧**：更换可用 API 端点
- [ ] **36氪**：排查 gateway API 500 原因，尝试备用接口

### 中优先级（内容平台）
- [ ] **虎嗅**：更换 API 端点（当前返回空）
- [ ] **IT之家**：更新页面选择器适配新版 DOM
- [ ] **HelloGitHub**：适配新版 API（v1 已下线）
- [ ] **虎扑**：适配新版帖子 API
- [ ] **英雄联盟**：修复 API 响应解析
- [ ] **微信读书**：排查飙升榜接口变更

### 低优先级（社区/工具）
- [ ] **NodeSeek**：添加 Cookie 或切换 API
- [ ] **NGA**：添加 Cookie 绕过 403
- [ ] **51CTO**：更新页面选择器
- [ ] **酷安**：更换解析方案
- [ ] **吾爱破解**：更换解析方案
- [ ] **知乎日报**：切换为 daily.zhihu.com 备用接口
- [ ] **气象预警**：接入免费天气 API（不依赖和风 Key）
- [ ] **地震速报**：添加 SSL verify=False 或换数据源
- [ ] **历史上的今天**：换数据源
- [ ] **新浪热榜**：合并到微博热搜（数据重复），或找可用接口

### 功能增强
- [ ] Docker 一键部署
- [ ] 定时自动刷新（后台任务）
- [ ] 数据历史存档
- [ ] 暗色模式
- [ ] 按关键词搜索/过滤
- [ ] 移动端优化

---

## 项目结构

```
hot-hub/
├── app.py                 # FastAPI 入口
├── crawlers/
│   ├── __init__.py
│   ├── platforms.py       # 平台注册表 + 分类配置
│   ├── extra.py           # 扩展平台爬虫（30+ 个）
│   ├── weibo.py           # 微博热搜
│   ├── zhihu.py           # 知乎热榜
│   ├── baidu.py           # 百度热搜
│   ├── xiaohongshu.py     # 小红书（待修复）
│   ├── douyin.py          # 抖音热榜
│   └── toutiao.py         # 今日头条
├── templates/
│   └── index.html         # 聚合展示页（分类版）
├── static/
│   └── style.css          # 样式
├── requirements.txt
└── README.md
```

## ⚠️ 注意

- 各平台接口随时可能变更，爬虫需要定期维护
- 已做 5 分钟缓存，请勿高频刷新
- 仅供个人学习使用

## License

MIT
