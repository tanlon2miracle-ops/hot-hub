# CHANGELOG — Hot Hub 项目演进记录

> 为新加入的同学梳理项目从 0 到 1 的关键节点，方便快速上手。

---

## 🏗️ 第一阶段：基础搭建（03-22）

### `73f6a03` — 项目诞生
- FastAPI + Jinja2 + httpx，6 个核心平台爬虫（微博/知乎/百度/小红书/抖音/头条）
- 纯内存缓存，无持久化

### `127a012` — 扩展至 40+ 平台
- 新增 `crawlers/extra.py` 统一通用爬虫框架
- 覆盖科技/资讯/社区/影音等 8 大分类

### `dd977c1` — 小红书 Playwright 方案
- 小红书接口完全走 JS 渲染，引入 Playwright 作为重 JS 平台的爬取方案
- **设计决策**：只在必须时用 Playwright，其余平台保持轻量 httpx

### `75cdef3` — SQLite 持久化 + 定时调度
- 引入 `storage.py`（SQLite WAL 模式），每次爬取生成一个 batch 快照
- APScheduler 定时任务（每小时全量爬取）
- **关键数据模型**：`fetch_batch` + `hot_item` 两张表
- 这是后续审查监测的数据基础

---

## 📰 第二阶段：内容增强（03-23 上午）

### `9993d1b` — 智能内容摘要
- `crawlers/enricher.py` — 自动为热榜 Top 条目补充内容简介
- 限制只处理前 N 条，控制 API 调用量

### `a49222c` — 批量修复 7 个坏爬虫
- 系统性排查所有平台接口，修复返回格式变更/404/反爬等问题

### `6b98866` — 国际平台接入
- Hacker News / GitHub Trending / TechCrunch / BBC / CNN

### `2180cef` — 热梗分类
- B 站热搜词 / 微博热梗 / 能不能好好说话 / 梗百科

---

## 📅 第三阶段：News 日历（03-23 下午）

### `24bf66a` — 敏感日期日历
- `crawlers/sensitive_dates.json` — 75+ 敏感日期事件库（覆盖全年 12 个月）
- 日期接近时自动预警（前后 N 天）

### `c068871` — 独立 /alert 页面
- 从主页拆分为独立页面 `/alert`
- 时间线 UI，红/黄/灰三色区分紧急程度

### `f2ee589` — 历史上的今天
- 接入百度百科 API，自动获取当天历史事件/名人诞辰/逝世
- 双 Tab 设计：敏感日期 + 历史上的今天

---

## 🔍 第四阶段：审查监测 v1（03-23 晚）

### `32deb7d` — 审查监测 MVP
- **核心思路**：对比前后两个 batch，找出"消失的热搜"
- 双模检测：
  - 🔄 **全量 Diff**（每小时，覆盖所有平台）
  - ⚡ **闪删快照**（每 5 分钟，只监测微博/知乎/百度/抖音/头条）
- 新增 `censor.py` 模块 + `censored_item` / `flash_snapshot` 两张表
- **这是项目最核心的功能，后续所有分析都建立在此之上**

### `1d65988` — 热度归一化 + 曝光回溯
- 基于排名百分位的 5 级热度（爆/高热/热门/温热/普通）
- 从数据库追溯条目首次出现时间，精确计算在榜时长
- **技术要点**：批量回溯优化，避免 N+1 查询

### `6f6b857` — 可疑度评分 + 前端重构
- 0-100 分可疑度评分引擎
- 考量因子：热度等级 / 曝光时长 / 排名位置 / 闪删检测
- 独立 `/censor` 页面，支持排序/筛选/时间范围

### `9a201e1` — 跨平台联动检测
- 同一话题在多个平台同时消失 → 自动聚合
- 字符串归一化 + 子串匹配
- 跨平台联动大幅加权可疑度

---

## 🔍 第五阶段：审查监测 v2（03-24）

### `d5eeb9b` — 多因子评分引擎
- 从 4 因子扩展到 **8 维评分**：
  - 热度 / 曝光时长 / 排名 / 跨平台 / **深夜删除** / **极速上榜** / **热度突变** / **敏感词**
- 时间衰减加权（指数半衰期），近期事件排序优先
- 敏感词规则引擎（高/中权重关键词库）
- 前端展示每个因子标签 + hover 详情
- ML 模块接口占位（5 个类定义好了 interface）

### `bd1ab48` — 噪音过滤
- 默认排除 IT 科技 / 广告营销 / 产品评测等与审查无关的条目
- 三层过滤：平台排除 + 关键词匹配 + 品牌正则
- 前端噪音开关（一键切换显示全部）

---

## 🗺️ 第六阶段：Roadmap + NLP 模块（03-25 ~ 03-26）

### `791de7d` — Roadmap 技术体系规划
- `docs/ROADMAP.md` — 5 Phase 渐进式路线图
- 与 BettaFish 对标差距分析
- 技术选型参考表（轻量先行 → 后续升级）

### `7286162` — Phase 1 NLP 三件套
- **降温曲线检测**（纯统计）：线性回归斜率 + 末段趋势分析，区分"正常降温" vs "异常删除"
- **情感分析**（SnowNLP）：中文情感打分，零成本启动
- **实体识别**（jieba + 敏感词典）：提取人名/地名/机构 + 敏感实体匹配
- ML 状态从 0/5 ready 提升到 **3/5 ready**

### `f024e9c` — 爬虫健康修复
- 微博 `detail_tag` 从 str 变 dict → 类型兼容
- HelloGitHub API 404 → 切换到 `/v1/` 根接口
- 贴吧/虎嗅/NodeSeek 增加容错回退
- 成功率从 86% 提升到 **91%**

---

## 📁 项目结构速览

```
hot-hub/
├── app.py              # FastAPI 入口（路由 + 生命周期）
├── storage.py          # SQLite 存储（batch + hot_item）
├── scheduler.py        # APScheduler 调度（全量 + 闪删）
├── censor.py           # 🔍 审查监测核心（检测 + 评分 + NLP）
├── crawlers/
│   ├── platforms.py    # 44 平台注册表
│   ├── extra.py        # 通用爬虫（30+ 平台）
│   ├── weibo.py        # 微博专用
│   ├── zhihu.py / baidu.py / douyin.py / toutiao.py
│   ├── xiaohongshu.py  # Playwright 渲染
│   ├── enricher.py     # 内容摘要
│   ├── history_today.py        # 历史上的今天
│   └── sensitive_dates.json    # 敏感日期库
├── templates/          # Jinja2 模板
├── static/             # CSS + 图片
├── data/               # SQLite DB + 敏感实体词典
├── docs/
│   └── ROADMAP.md      # 技术路线图
└── requirements.txt
```

## 🔑 新人快速上手

1. **跑起来**：`pip install -r requirements.txt && python app.py`
2. **看数据**：打开 `http://localhost:8000`（热榜）/ `/censor`（审查监测）/ `/alert`（News 日历）
3. **理解核心**：先读 `censor.py` 的 `calc_suspicion_score()` 和 `diff_batches()`
4. **加新平台**：在 `crawlers/extra.py` 写一个 `async def fetch_xxx()` + 在 `platforms.py` 注册
5. **看路线图**：`docs/ROADMAP.md` 了解下一步计划
