"""
审查监测 — 热榜消失条目检测
方案一：Diff 对比（每小时，覆盖全平台）
方案二：高频监测（5-10 分钟，针对闪删大户）
"""

import json
import time
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "hot_hub.db"

# 闪删大户 — 高频监测目标
FLASH_DELETE_TARGETS = ["weibo", "zhihu", "baidu", "douyin", "toutiao"]


def _get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_censor_db():
    """初始化审查监测表"""
    conn = _get_db()
    try:
        conn.executescript("""
            -- 消失条目记录表
            CREATE TABLE IF NOT EXISTS censored_item (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                platform        TEXT NOT NULL,
                title           TEXT NOT NULL,
                url             TEXT DEFAULT '',
                hot             TEXT DEFAULT '',
                rank_when_seen  INTEGER DEFAULT 0,
                first_seen_at   TEXT NOT NULL,
                last_seen_at    TEXT NOT NULL,
                disappeared_at  TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 0,
                batch_seen      INTEGER NOT NULL,
                batch_gone      INTEGER NOT NULL,
                detection_mode  TEXT DEFAULT 'diff',
                confirmed       INTEGER DEFAULT 0,
                UNIQUE(platform, title, batch_gone)
            );

            -- 高频快照表（闪删大户专用）
            CREATE TABLE IF NOT EXISTS flash_snapshot (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                platform    TEXT NOT NULL,
                snapshot_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                data        TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_censored_platform ON censored_item(platform);
            CREATE INDEX IF NOT EXISTS idx_censored_time ON censored_item(disappeared_at);
            CREATE INDEX IF NOT EXISTS idx_flash_platform ON flash_snapshot(platform, snapshot_at);
        """)
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 方案一：Diff 对比（全平台，每小时跟随主爬取）
# ============================================================

def diff_batches(current_batch_id: int = None) -> list:
    """
    对比最近两个 batch，找出消失的条目
    返回 [{ platform, title, url, hot, rank, first_seen, disappeared_at, duration_min }]
    """
    conn = _get_db()
    try:
        # 获取最近两个 batch
        if current_batch_id:
            batches = conn.execute(
                "SELECT id, created_at FROM fetch_batch WHERE id <= ? ORDER BY id DESC LIMIT 2",
                (current_batch_id,),
            ).fetchall()
        else:
            batches = conn.execute(
                "SELECT id, created_at FROM fetch_batch ORDER BY id DESC LIMIT 2"
            ).fetchall()

        if len(batches) < 2:
            return []

        new_batch = batches[0]
        old_batch = batches[1]

        # 拿两个 batch 的数据
        old_items = conn.execute(
            "SELECT platform, title, url, hot, rank FROM hot_item WHERE batch_id=?",
            (old_batch["id"],),
        ).fetchall()
        new_items = conn.execute(
            "SELECT platform, title FROM hot_item WHERE batch_id=?",
            (new_batch["id"],),
        ).fetchall()

        # 新 batch 的 (platform, title) 集合
        new_set = {(r["platform"], r["title"]) for r in new_items}

        disappeared = []
        for item in old_items:
            key = (item["platform"], item["title"])
            if key not in new_set:
                disappeared.append({
                    "platform": item["platform"],
                    "title": item["title"],
                    "url": item["url"],
                    "hot": item["hot"],
                    "rank_when_seen": item["rank"],
                    "first_seen_at": old_batch["created_at"],
                    "last_seen_at": old_batch["created_at"],
                    "disappeared_at": new_batch["created_at"],
                    "batch_seen": old_batch["id"],
                    "batch_gone": new_batch["id"],
                    "detection_mode": "diff",
                })

        # 写入数据库
        _save_censored(conn, disappeared)

        return disappeared
    finally:
        conn.close()


def _save_censored(conn, items: list):
    """保存消失条目（去重）"""
    for item in items:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO censored_item
                   (platform, title, url, hot, rank_when_seen,
                    first_seen_at, last_seen_at, disappeared_at,
                    batch_seen, batch_gone, detection_mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["platform"], item["title"], item.get("url", ""),
                    item.get("hot", ""), item.get("rank_when_seen", 0),
                    item["first_seen_at"], item["last_seen_at"],
                    item["disappeared_at"],
                    item["batch_seen"], item["batch_gone"],
                    item.get("detection_mode", "diff"),
                ),
            )
        except Exception as e:
            print(f"[censor] Save error: {e}")
    conn.commit()


# ============================================================
# 方案二：高频快照（闪删大户，5-10 分钟）
# ============================================================

def save_flash_snapshot(platform: str, items: list):
    """保存一次高频快照"""
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO flash_snapshot (platform, data) VALUES (?, ?)",
            (platform, json.dumps(items, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def diff_flash_snapshots(platform: str) -> list:
    """对比最近两次高频快照，找出闪删条目"""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, snapshot_at, data FROM flash_snapshot
               WHERE platform=? ORDER BY id DESC LIMIT 2""",
            (platform,),
        ).fetchall()

        if len(rows) < 2:
            return []

        new_snap = json.loads(rows[0]["data"])
        old_snap = json.loads(rows[1]["data"])

        new_titles = {item.get("title", "") for item in new_snap}
        disappeared = []

        for item in old_snap:
            title = item.get("title", "")
            if title and title not in new_titles:
                disappeared.append({
                    "platform": platform,
                    "title": title,
                    "url": item.get("url", ""),
                    "hot": item.get("hot", ""),
                    "rank_when_seen": item.get("rank", 0),
                    "first_seen_at": rows[1]["snapshot_at"],
                    "last_seen_at": rows[1]["snapshot_at"],
                    "disappeared_at": rows[0]["snapshot_at"],
                    "batch_seen": rows[1]["id"],
                    "batch_gone": rows[0]["id"],
                    "detection_mode": "flash",
                })

        _save_censored(conn, disappeared)
        return disappeared
    finally:
        conn.close()


def cleanup_flash_snapshots(keep_hours: int = 24):
    """清理旧的高频快照"""
    conn = _get_db()
    try:
        conn.execute(
            "DELETE FROM flash_snapshot WHERE snapshot_at < datetime('now', 'localtime', ?)",
            (f"-{keep_hours} hours",),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 查询接口
# ============================================================

def get_censored_items(limit: int = 100, platform: str = None,
                       hours: int = 24) -> list:
    """获取最近消失的条目"""
    conn = _get_db()
    try:
        query = """SELECT * FROM censored_item
                   WHERE disappeared_at >= datetime('now', 'localtime', ?)"""
        params = [f"-{hours} hours"]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY disappeared_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_censor_stats(hours: int = 24) -> dict:
    """统计审查概况"""
    conn = _get_db()
    try:
        total = conn.execute(
            """SELECT COUNT(*) as cnt FROM censored_item
               WHERE disappeared_at >= datetime('now', 'localtime', ?)""",
            (f"-{hours} hours",),
        ).fetchone()["cnt"]

        by_platform = conn.execute(
            """SELECT platform, COUNT(*) as cnt FROM censored_item
               WHERE disappeared_at >= datetime('now', 'localtime', ?)
               GROUP BY platform ORDER BY cnt DESC""",
            (f"-{hours} hours",),
        ).fetchall()

        by_mode = conn.execute(
            """SELECT detection_mode, COUNT(*) as cnt FROM censored_item
               WHERE disappeared_at >= datetime('now', 'localtime', ?)
               GROUP BY detection_mode""",
            (f"-{hours} hours",),
        ).fetchall()

        return {
            "total": total,
            "hours": hours,
            "by_platform": [dict(r) for r in by_platform],
            "by_mode": [dict(r) for r in by_mode],
        }
    finally:
        conn.close()
