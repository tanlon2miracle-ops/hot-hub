"""
结构化存储 — SQLite
每次爬取的数据按 (平台, 时间批次) 存储，支持历史查询
"""

import json
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "hot_hub.db"


def _ensure_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """获取数据库连接（自动提交 & 关闭）"""
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 并发读写更好
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化表结构"""
    with get_db() as db:
        db.executescript("""
            -- 爬取批次表：每次定时任务 = 一个 batch
            CREATE TABLE IF NOT EXISTS fetch_batch (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                platform_count INTEGER DEFAULT 0,
                item_count  INTEGER DEFAULT 0
            );

            -- 热榜条目表：每条热搜/热帖
            CREATE TABLE IF NOT EXISTS hot_item (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id    INTEGER NOT NULL,
                platform    TEXT NOT NULL,
                rank        INTEGER,
                title       TEXT NOT NULL,
                hot         TEXT DEFAULT '',
                url         TEXT DEFAULT '',
                summary     TEXT DEFAULT '',
                extra       TEXT DEFAULT '{}',
                FOREIGN KEY (batch_id) REFERENCES fetch_batch(id)
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_item_platform ON hot_item(platform);
            CREATE INDEX IF NOT EXISTS idx_item_batch ON hot_item(batch_id);
        """)

        # 自动迁移：如果旧表没有 summary 列，添加它
        cols = [row[1] for row in db.execute("PRAGMA table_info(hot_item)").fetchall()]
        if "summary" not in cols:
            db.execute("ALTER TABLE hot_item ADD COLUMN summary TEXT DEFAULT ''")
            print("[storage] Migrated: added summary column")


def save_batch(results: dict) -> int:
    """
    保存一次完整爬取结果
    results: { "weibo": [{rank, title, hot, url}, ...], "zhihu": [...], ... }
    返回 batch_id
    """
    platform_count = 0
    item_count = 0

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO fetch_batch (platform_count, item_count) VALUES (0, 0)"
        )
        batch_id = cur.lastrowid

        for platform, items in results.items():
            if not items:
                continue
            platform_count += 1
            for item in items:
                db.execute(
                    """INSERT INTO hot_item (batch_id, platform, rank, title, hot, url, summary, extra)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        batch_id,
                        platform,
                        item.get("rank", 0),
                        item.get("title", ""),
                        str(item.get("hot", "")),
                        item.get("url", ""),
                        item.get("summary", ""),
                        json.dumps({k: v for k, v in item.items()
                                    if k not in ("rank", "title", "hot", "url", "summary")},
                                   ensure_ascii=False),
                    ),
                )
                item_count += 1

        db.execute(
            "UPDATE fetch_batch SET platform_count=?, item_count=? WHERE id=?",
            (platform_count, item_count, batch_id),
        )

    print(f"[storage] Batch #{batch_id} saved: {platform_count} platforms, {item_count} items")
    return batch_id


def get_latest_batch():
    """获取最新一次爬取的完整数据"""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM fetch_batch ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None

        batch_id = row["id"]
        items = db.execute(
            "SELECT * FROM hot_item WHERE batch_id=? ORDER BY platform, rank",
            (batch_id,),
        ).fetchall()

        # 按平台分组
        data = {}
        for item in items:
            p = item["platform"]
            if p not in data:
                data[p] = []
            data[p].append({
                "rank": item["rank"],
                "title": item["title"],
                "hot": item["hot"],
                "url": item["url"],
                "summary": item["summary"] if "summary" in item.keys() else "",
            })

        return {
            "batch_id": batch_id,
            "created_at": row["created_at"],
            "platform_count": row["platform_count"],
            "item_count": row["item_count"],
            "data": data,
        }


def get_batch_list(limit: int = 20):
    """获取最近的爬取批次列表"""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM fetch_batch ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_platform_history(platform: str, limit: int = 10):
    """获取某平台最近 N 次爬取的历史数据"""
    with get_db() as db:
        rows = db.execute(
            """SELECT hi.*, fb.created_at as batch_time
               FROM hot_item hi
               JOIN fetch_batch fb ON hi.batch_id = fb.id
               WHERE hi.platform = ?
               ORDER BY hi.batch_id DESC, hi.rank ASC
               LIMIT ?""",
            (platform, limit * 50),  # 每批最多50条
        ).fetchall()
        return [dict(r) for r in rows]


def cleanup_old_data(keep_days: int = 30):
    """清理超过 N 天的旧数据"""
    with get_db() as db:
        db.execute(
            """DELETE FROM hot_item WHERE batch_id IN (
                SELECT id FROM fetch_batch
                WHERE created_at < datetime('now', 'localtime', ?)
            )""",
            (f"-{keep_days} days",),
        )
        db.execute(
            "DELETE FROM fetch_batch WHERE created_at < datetime('now', 'localtime', ?)",
            (f"-{keep_days} days",),
        )
        db.execute("VACUUM")
    print(f"[storage] Cleaned data older than {keep_days} days")
