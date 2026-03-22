"""
定时爬取调度器
使用 APScheduler 后台定时执行，与 FastAPI 生命周期集成
"""

import asyncio
import time
from typing import Optional

from crawlers import weibo, zhihu, baidu, xiaohongshu, douyin, toutiao
from crawlers.extra import FETCH_MAP
from crawlers.platforms import PLATFORMS
from crawlers.enricher import enrich_summaries
from storage import init_db, save_batch, cleanup_old_data

# 核心爬虫映射
_CORE_FETCHERS = {
    "weibo": weibo.fetch,
    "zhihu": zhihu.fetch,
    "baidu": baidu.fetch,
    "xiaohongshu": xiaohongshu.fetch,
    "douyin": douyin.fetch,
    "toutiao": toutiao.fetch,
}


def get_fetcher(key: str):
    return _CORE_FETCHERS.get(key) or FETCH_MAP.get(key)


async def fetch_one(key: str) -> list:
    """安全地爬取单个平台"""
    fn = get_fetcher(key)
    if not fn:
        return []
    try:
        data = await fn()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[scheduler] {key} failed: {e}")
        return []


async def fetch_all_and_save() -> dict:
    """并发爬取所有平台 + 存储到 SQLite"""
    t0 = time.time()
    keys = [p[0] for p in PLATFORMS]
    results = await asyncio.gather(*[fetch_one(k) for k in keys])

    # 组装结果
    all_data = {}
    for key, data in zip(keys, results):
        if data:  # 只保存有数据的
            all_data[key] = data

    # 补全摘要（仅对 top 条目）
    try:
        all_data = await enrich_summaries(all_data)
    except Exception as e:
        print(f"[scheduler] enrich failed: {e}")

    # 写入数据库
    batch_id = save_batch(all_data)
    elapsed = time.time() - t0
    print(f"[scheduler] Batch #{batch_id} done in {elapsed:.1f}s, "
          f"{len(all_data)}/{len(keys)} platforms")

    return {
        "batch_id": batch_id,
        "platforms": len(all_data),
        "elapsed": round(elapsed, 1),
    }


# ========== APScheduler 集成 ==========

_scheduler = None


def start_scheduler(interval_minutes: int = 10):
    """启动后台定时任务"""
    global _scheduler

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("[scheduler] APScheduler not installed, running without scheduler")
        print("[scheduler] Install with: pip install apscheduler>=3.10")
        return None

    if _scheduler and _scheduler.running:
        print("[scheduler] Already running")
        return _scheduler

    _scheduler = AsyncIOScheduler()

    # 定时爬取：默认每 10 分钟
    _scheduler.add_job(
        fetch_all_and_save,
        IntervalTrigger(minutes=interval_minutes),
        id="fetch_hot",
        name="定时爬取热榜",
        replace_existing=True,
    )

    # 每天凌晨 3 点清理 30 天前的旧数据
    _scheduler.add_job(
        _cleanup_job,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old",
        name="清理旧数据",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"[scheduler] Started — fetch every {interval_minutes}min, cleanup at 03:00")
    return _scheduler


def stop_scheduler():
    """停止定时任务"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[scheduler] Stopped")
    _scheduler = None


def get_scheduler_status() -> dict:
    """获取调度器状态"""
    if not _scheduler:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": _scheduler.running, "jobs": jobs}


async def _cleanup_job():
    """清理任务包装"""
    cleanup_old_data(keep_days=30)
