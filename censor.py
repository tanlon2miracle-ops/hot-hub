"""
审查监测 — 热榜消失条目检测
方案一：Diff 对比（每小时，覆盖全平台）
方案二：高频监测（5-10 分钟，针对闪删大户）
+ 热度归一化（平台内排名百分位）
+ 曝光时长回溯
"""

import json
import time
import sqlite3
import math
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "hot_hub.db"

# 闪删大户 — 高频监测目标
FLASH_DELETE_TARGETS = ["weibo", "zhihu", "baidu", "douyin", "toutiao"]

# 各平台热度量纲参考（用于归一化）
# key: platform, value: 典型 Top1 热度值（估算）
# 实际用排名百分位，这里备用
PLATFORM_HOT_SCALE = {
    "weibo": 5_000_000,    # 微博热搜 top1 约 500 万+
    "zhihu": 30_000_000,   # 知乎热榜 top1 约 3000 万热力值
    "baidu": 5_000_000,    # 百度热搜 top1 约 500 万
    "douyin": 10_000_000,  # 抖音 top1 约 1000 万
    "toutiao": 5_000_000,  # 头条 top1 约 500 万
    "xiaohongshu": 500_000,
}


def _get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _parse_hot(hot_str: str) -> float:
    """解析热度字符串为数值（兼容 '523万'、'5234567'、'1.2亿' 等格式）"""
    if not hot_str:
        return 0
    s = str(hot_str).strip().replace(",", "").replace(" ", "")
    try:
        if "亿" in s:
            return float(s.replace("亿", "")) * 100_000_000
        elif "万" in s:
            return float(s.replace("万", "")) * 10_000
        else:
            return float(s)
    except (ValueError, TypeError):
        return 0


def calc_heat_level(rank: int, total: int) -> dict:
    """
    根据排名百分位计算热度等级
    返回 { level: 1-5, label: str, icon: str }
    """
    if total <= 0 or rank <= 0:
        return {"level": 0, "label": "未知", "icon": "⬜"}

    percentile = rank / total  # 越小 = 越热

    if percentile <= 0.06:   # Top 3 (50条榜的前3)
        return {"level": 5, "label": "爆", "icon": "🔥🔥🔥"}
    elif percentile <= 0.2:  # Top 10
        return {"level": 4, "label": "高热", "icon": "🔥🔥"}
    elif percentile <= 0.4:  # Top 20
        return {"level": 3, "label": "热门", "icon": "🔥"}
    elif percentile <= 0.6:
        return {"level": 2, "label": "温热", "icon": "🌡️"}
    else:
        return {"level": 1, "label": "普通", "icon": "➖"}


def calc_suspicion_score(heat_level: int, duration_minutes: int,
                         detection_mode: str, rank: int) -> dict:
    """
    综合评估"疑似审查"可信度
    分数 0-100，越高越可疑
    返回 { score: int, label: str, color: str }
    """
    score = 0

    # 1. 热度越高越可疑（高热条目不该突然消失）
    score += heat_level * 12  # max 60

    # 2. 曝光时间越短越可疑（刚上榜就消失 = 闪删）
    if duration_minutes <= 5:
        score += 25
    elif duration_minutes <= 15:
        score += 20
    elif duration_minutes <= 30:
        score += 15
    elif duration_minutes <= 60:
        score += 10
    elif duration_minutes <= 180:
        score += 5
    # 超过 3 小时的正常降温概率高，不加分

    # 3. 闪删检测到的 +5（比常规 diff 更精确）
    if detection_mode == "flash":
        score += 5

    # 4. 排名越靠前越可疑
    if rank <= 3:
        score += 10
    elif rank <= 10:
        score += 5

    score = min(100, max(0, score))

    if score >= 70:
        return {"score": score, "label": "高度可疑", "color": "#e74c3c"}
    elif score >= 45:
        return {"score": score, "label": "值得关注", "color": "#e67e22"}
    elif score >= 25:
        return {"score": score, "label": "可能正常", "color": "#f39c12"}
    else:
        return {"score": score, "label": "正常降温", "color": "#95a5a6"}


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
                hot_numeric     REAL DEFAULT 0,
                heat_level      INTEGER DEFAULT 0,
                rank_when_seen  INTEGER DEFAULT 0,
                total_in_list   INTEGER DEFAULT 0,
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

        # 自动迁移：添加新字段
        cols = [r[1] for r in conn.execute("PRAGMA table_info(censored_item)").fetchall()]
        migrations = {
            "hot_numeric": "ALTER TABLE censored_item ADD COLUMN hot_numeric REAL DEFAULT 0",
            "heat_level": "ALTER TABLE censored_item ADD COLUMN heat_level INTEGER DEFAULT 0",
            "total_in_list": "ALTER TABLE censored_item ADD COLUMN total_in_list INTEGER DEFAULT 0",
        }
        for col, sql in migrations.items():
            if col not in cols:
                conn.execute(sql)
                print(f"[censor] Migrated: added {col}")

        conn.commit()
    finally:
        conn.close()


# ============================================================
# 曝光时长回溯
# ============================================================

def _trace_first_seen(conn, platform: str, title: str, before_batch_id: int) -> str:
    """回溯找到这条热搜最早出现的时间"""
    row = conn.execute(
        """SELECT fb.created_at FROM hot_item hi
           JOIN fetch_batch fb ON hi.batch_id = fb.id
           WHERE hi.platform = ? AND hi.title = ? AND hi.batch_id <= ?
           ORDER BY hi.batch_id ASC LIMIT 1""",
        (platform, title, before_batch_id),
    ).fetchone()
    return row["created_at"] if row else None


def _batch_trace_first_seen(conn, items_to_trace: list, before_batch_id: int) -> dict:
    """
    批量回溯 first_seen，避免 N+1 查询
    items_to_trace: [(platform, title), ...]
    返回 { (platform, title): first_seen_at }
    """
    if not items_to_trace:
        return {}

    # 按 platform 分组查询，减少 SQL 次数
    by_platform = {}
    for p, t in items_to_trace:
        by_platform.setdefault(p, []).append(t)

    results = {}
    for platform, titles in by_platform.items():
        # 一次查出该平台所有相关条目的最早出现时间
        placeholders = ",".join("?" * len(titles))
        rows = conn.execute(
            f"""SELECT hi.platform, hi.title, MIN(fb.created_at) as first_at
                FROM hot_item hi
                JOIN fetch_batch fb ON hi.batch_id = fb.id
                WHERE hi.platform = ? AND hi.title IN ({placeholders})
                AND hi.batch_id <= ?
                GROUP BY hi.platform, hi.title""",
            [platform] + titles + [before_batch_id],
        ).fetchall()
        for row in rows:
            results[(row["platform"], row["title"])] = row["first_at"]

    return results


def _calc_duration(first_seen: str, disappeared: str) -> int:
    """计算曝光时长（分钟）"""
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        t1 = datetime.strptime(first_seen, fmt)
        t2 = datetime.strptime(disappeared, fmt)
        return max(0, int((t2 - t1).total_seconds() / 60))
    except Exception:
        return 0


# ============================================================
# 方案一：Diff 对比（全平台，每小时跟随主爬取）
# ============================================================

def diff_batches(current_batch_id: int = None) -> list:
    """
    对比最近两个 batch，找出消失的条目
    - 回溯 first_seen_at 计算曝光时长
    - 计算热度等级
    """
    conn = _get_db()
    try:
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

        # 上一个 batch 的数据（带排名和热度）
        old_items = conn.execute(
            "SELECT platform, title, url, hot, rank FROM hot_item WHERE batch_id=?",
            (old_batch["id"],),
        ).fetchall()
        new_items = conn.execute(
            "SELECT platform, title FROM hot_item WHERE batch_id=?",
            (new_batch["id"],),
        ).fetchall()

        new_set = {(r["platform"], r["title"]) for r in new_items}

        # 统计每个平台在 old_batch 中的条目总数（用于百分位）
        platform_totals = {}
        for item in old_items:
            p = item["platform"]
            platform_totals[p] = platform_totals.get(p, 0) + 1

        # 先找出所有消失的条目
        vanished_keys = []
        vanished_items = []
        for item in old_items:
            key = (item["platform"], item["title"])
            if key not in new_set:
                vanished_keys.append(key)
                vanished_items.append(item)

        # 批量回溯 first_seen（避免 N+1）
        first_seen_map = _batch_trace_first_seen(conn, vanished_keys, old_batch["id"])

        disappeared = []
        for item in vanished_items:
            platform = item["platform"]
            rank = item["rank"] or 0
            total = platform_totals.get(platform, 50)
            hot_str = item["hot"] or ""

            first_seen = first_seen_map.get(
                (platform, item["title"]), old_batch["created_at"]
            )
            duration = _calc_duration(first_seen, new_batch["created_at"])
            heat = calc_heat_level(rank, total)

            disappeared.append({
                "platform": platform,
                "title": item["title"],
                "url": item["url"],
                "hot": hot_str,
                "hot_numeric": _parse_hot(hot_str),
                "heat_level": heat["level"],
                "rank_when_seen": rank,
                "total_in_list": total,
                "first_seen_at": first_seen,
                "last_seen_at": old_batch["created_at"],
                "disappeared_at": new_batch["created_at"],
                "duration_minutes": duration,
                "batch_seen": old_batch["id"],
                "batch_gone": new_batch["id"],
                "detection_mode": "diff",
            })

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
                   (platform, title, url, hot, hot_numeric, heat_level,
                    rank_when_seen, total_in_list,
                    first_seen_at, last_seen_at, disappeared_at,
                    duration_minutes, batch_seen, batch_gone, detection_mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["platform"], item["title"], item.get("url", ""),
                    item.get("hot", ""), item.get("hot_numeric", 0),
                    item.get("heat_level", 0),
                    item.get("rank_when_seen", 0), item.get("total_in_list", 0),
                    item["first_seen_at"], item["last_seen_at"],
                    item["disappeared_at"], item.get("duration_minutes", 0),
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
    """对比最近两次高频快照，找出闪删条目（含热度+曝光时长）"""
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
        total = len(old_snap)

        new_titles = {item.get("title", "") for item in new_snap}

        # 找出消失的标题
        vanished = [item for item in old_snap
                    if item.get("title") and item["title"] not in new_titles]

        if not vanished:
            return []

        # 批量回溯：一次查出所有更早的快照
        earlier_snaps = conn.execute(
            """SELECT snapshot_at, data FROM flash_snapshot
               WHERE platform=? AND id < ? ORDER BY id ASC""",
            (platform, rows[1]["id"]),
        ).fetchall()

        # 预解析历史快照中每个 title 的最早出现时间
        title_first_seen = {}
        for snap in earlier_snaps:
            snap_data = json.loads(snap["data"])
            snap_time = snap["snapshot_at"]
            for i in snap_data:
                t = i.get("title", "")
                if t and t not in title_first_seen:
                    title_first_seen[t] = snap_time

        disappeared = []
        for item in vanished:
            title = item["title"]
            rank = item.get("rank", 0) or 0
            hot_str = str(item.get("hot", ""))
            heat = calc_heat_level(rank, total)

            actual_first = title_first_seen.get(title, rows[1]["snapshot_at"])
            total_duration = _calc_duration(actual_first, rows[0]["snapshot_at"])

            disappeared.append({
                "platform": platform,
                "title": title,
                "url": item.get("url", ""),
                "hot": hot_str,
                "hot_numeric": _parse_hot(hot_str),
                "heat_level": heat["level"],
                "rank_when_seen": rank,
                "total_in_list": total,
                "first_seen_at": actual_first,
                "last_seen_at": rows[1]["snapshot_at"],
                "disappeared_at": rows[0]["snapshot_at"],
                "duration_minutes": total_duration,
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
        results = []
        for r in rows:
            d = dict(r)
            # 附加热度等级信息
            d["heat_info"] = calc_heat_level(
                d.get("rank_when_seen", 0),
                d.get("total_in_list", 50),
            )
            # 可疑度评分
            d["suspicion"] = calc_suspicion_score(
                d.get("heat_level", 0),
                d.get("duration_minutes", 0),
                d.get("detection_mode", "diff"),
                d.get("rank_when_seen", 0),
            )
            # 曝光时长格式化
            mins = d.get("duration_minutes", 0)
            if mins >= 1440:
                d["duration_display"] = f"{mins // 1440}天{(mins % 1440) // 60}小时"
            elif mins >= 60:
                d["duration_display"] = f"{mins // 60}小时{mins % 60}分"
            elif mins > 0:
                d["duration_display"] = f"{mins}分钟"
            else:
                d["duration_display"] = "< 1分钟"
            results.append(d)
        return results
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

        # 高热消失（heat_level >= 4）
        high_heat = conn.execute(
            """SELECT COUNT(*) as cnt FROM censored_item
               WHERE disappeared_at >= datetime('now', 'localtime', ?)
               AND heat_level >= 4""",
            (f"-{hours} hours",),
        ).fetchone()["cnt"]

        # 速删（曝光 < 30 分钟）
        quick_delete = conn.execute(
            """SELECT COUNT(*) as cnt FROM censored_item
               WHERE disappeared_at >= datetime('now', 'localtime', ?)
               AND duration_minutes > 0 AND duration_minutes < 30""",
            (f"-{hours} hours",),
        ).fetchone()["cnt"]

        return {
            "total": total,
            "hours": hours,
            "high_heat_count": high_heat,
            "quick_delete_count": quick_delete,
            "by_platform": [dict(r) for r in by_platform],
            "by_mode": [dict(r) for r in by_mode],
        }
    finally:
        conn.close()
