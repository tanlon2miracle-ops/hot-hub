# Hot Hub — 全网热榜聚合

> 🔥 一个页面看完微博热搜、知乎热榜、百度热搜、小红书热榜、抖音热榜、今日头条热榜。

## 功能

- ✅ 微博热搜 Top 50
- ✅ 知乎热榜 Top 50
- ✅ 百度热搜 Top 30
- ✅ 小红书热榜
- ✅ 抖音热榜
- ✅ 今日头条热榜
- ✅ 聚合网页展示，自动刷新
- ✅ 单文件部署，零依赖前端

## 技术栈

- **后端**：Python 3.10+ / FastAPI
- **爬虫**：httpx + 各平台公开 API / 页面解析
- **前端**：Jinja2 模板 + 原生 CSS（无框架）

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py

# 打开浏览器
# http://localhost:8000
```

## 项目结构

```
hot-hub/
├── app.py                 # FastAPI 入口
├── crawlers/
│   ├── __init__.py
│   ├── weibo.py           # 微博热搜
│   ├── zhihu.py           # 知乎热榜
│   ├── baidu.py           # 百度热搜
│   ├── xiaohongshu.py     # 小红书热榜
│   ├── douyin.py          # 抖音热榜
│   └── toutiao.py         # 今日头条热榜
├── templates/
│   └── index.html         # 聚合展示页
├── static/
│   └── style.css          # 样式
├── requirements.txt
└── README.md
```

## ⚠️ 注意

- 各平台接口随时可能变更，爬虫需要定期维护
- 请勿高频请求，建议缓存 5-10 分钟
- 仅供个人学习使用

## License

MIT
