"""
审查监测 — 热榜消失条目检测 + 舆情分析引擎

检测层：
  方案一：Diff 对比（每小时，覆盖全平台）
  方案二：高频监测（5-10 分钟，针对闪删大户）

分析层（可疑度评分 v2）：
  ✅ 热度归一化（平台内排名百分位）    — 已实现
  ✅ 曝光时长回溯                      — 已实现
  ✅ 跨平台联动检测（标题模糊匹配）     — 已实现
  ✅ 时间衰减因子（越新越重要）          — v2 新增
  ✅ 热度突变检测（骤升骤降）            — v2 新增
  ✅ 上榜速度异常（刚冲上来就被撤）      — v2 新增
  ✅ 时段敏感（深夜/凌晨删除更可疑）     — v2 新增

TODO（需要 ML 模型）：
  🔲 语义敏感度分类 — 基于标题文本判断政治/社会敏感度
  🔲 情感倾向分析   — 标题/摘要的正负面情绪
  🔲 实体识别       — 提取人名/机构/事件，关联敏感实体库
  🔲 话题聚类       — 基于 embedding 的语义相似聚类（替代当前的字符串匹配）
  🔲 历史模式学习   — 学习"正常降温"曲线 vs "审查删除"曲线
"""

import json
import re
import time
import sqlite3
import math
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Callable

DB_PATH = Path(__file__).parent / "data" / "hot_hub.db"

# 闪删大户 — 高频监测目标
FLASH_DELETE_TARGETS = ["weibo", "zhihu", "baidu", "douyin", "toutiao"]

# ============================================================
# 平台 & 内容过滤（审查监测默认不展示的噪音）
# ============================================================

# 这些平台的条目正常上下榜，与审查无关，默认排除
EXCLUDED_PLATFORMS = {
    # 科技类 — 上下榜是正常技术内容生命周期
    "juejin", "csdn", "v2ex", "sspai", "hellogithub", "nodeseek",
    "hackernews", "github_trend", "techcrunch",
    # 影音/游戏 — 内容上下榜无审查意义
    "acfun", "douban_movie", "miyoushe",
    "bili_trending",
    # 热梗 — 更新频繁，噪音大
    "weibo_meme", "nbnhhsh",
    # 其他 — 工具/日报类
    "zhihu_daily", "ithome_xjy", "earthquake", "history",
    "urban_dict",
    # 国际纯英文 — 中文审查监测意义不大
    "bbc_news", "cnn",
}

# 标题噪音关键词 — 命中即降到 noise 级别，默认隐藏
_NOISE_KEYWORDS = [
    # 广告/营销/促销
    "优惠", "折扣", "满减", "限时", "秒杀", "领券", "红包", "免费领",
    "抽奖", "福利", "补贴", "打折", "特价", "买一送", "半价",
    # IT 产品发布/评测（正常商业行为，非审查）
    "发布会", "新品发布", "上市", "开售", "首发", "预售", "评测",
    "跑分", "拆解", "开箱", "体验", "配置", "参数", "价格",
    # 手机/数码品牌（产品类）
    "iPhone", "华为Mate", "华为P", "小米", "OPPO", "vivo",
    "三星Galaxy", "Redmi", "一加", "荣耀",
    "MacBook", "iPad", "AirPods",
    # 游戏/娱乐（正常更新）
    "赛季更新", "新赛季", "版本更新", "活动预告",
    # 榜单自身
    "热搜榜", "热榜",
]

# 广告/软文特征：标题以品牌+产品词开头
_AD_PATTERNS = [
    r"^(华为|小米|OPPO|vivo|三星|苹果|荣耀|一加|联想|戴尔).{0,4}(手机|笔记本|平板|耳机|手表|电视)",
    r"^(京东|淘宝|拼多多|天猫|抖音电商).{0,6}(活动|促销|大促|补贴)",
    r"^(Steam|Epic|PS|Xbox|任天堂).{0,6}(打折|限免|喜加一|促销)",
]
import re as _re
_AD_COMPILED = [_re.compile(p) for p in _AD_PATTERNS]


def _is_noise(title: str, platform: str) -> bool:
    """判断是否为噪音条目（广告/IT产品/营销）"""
    if platform in EXCLUDED_PLATFORMS:
        return True
    if not title:
        return False
    for kw in _NOISE_KEYWORDS:
        if kw in title:
            return True
    for pat in _AD_COMPILED:
        if pat.search(title):
            return True
    return False


# 各平台热度量纲参考（用于归一化）
PLATFORM_HOT_SCALE = {
    "weibo": 5_000_000,
    "zhihu": 30_000_000,
    "baidu": 5_000_000,
    "douyin": 10_000_000,
    "toutiao": 5_000_000,
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


# ============================================================
# 热度等级
# ============================================================

def calc_heat_level(rank: int, total: int) -> dict:
    """
    根据排名百分位计算热度等级
    返回 { level: 1-5, label: str, icon: str }
    """
    if total <= 0 or rank <= 0:
        return {"level": 0, "label": "未知", "icon": "⬜"}

    percentile = rank / total

    if percentile <= 0.06:
        return {"level": 5, "label": "爆", "icon": "🔥🔥🔥"}
    elif percentile <= 0.2:
        return {"level": 4, "label": "高热", "icon": "🔥🔥"}
    elif percentile <= 0.4:
        return {"level": 3, "label": "热门", "icon": "🔥"}
    elif percentile <= 0.6:
        return {"level": 2, "label": "温热", "icon": "🌡️"}
    else:
        return {"level": 1, "label": "普通", "icon": "➖"}


# ============================================================
# v2 可疑度评分引擎
# ============================================================

def _time_decay_factor(disappeared_at: str, half_life_hours: float = 12.0) -> float:
    """
    时间衰减因子：越新的事件权重越高
    使用指数衰减，half_life_hours 为半衰期
    返回 0.0 ~ 1.0
    """
    try:
        t = datetime.strptime(disappeared_at, "%Y-%m-%d %H:%M:%S")
        age_hours = (datetime.now() - t).total_seconds() / 3600
        return math.exp(-0.693 * age_hours / half_life_hours)
    except Exception:
        return 0.5


def _night_deletion_bonus(disappeared_at: str) -> int:
    """
    深夜/凌晨删除加分（00:00-06:00 删除更可疑，因为这段时间人工审查概率高）
    返回额外分数 0-10
    """
    try:
        t = datetime.strptime(disappeared_at, "%Y-%m-%d %H:%M:%S")
        hour = t.hour
        if 0 <= hour < 6:
            return 8
        elif 6 <= hour < 8:
            return 4
        elif 22 <= hour <= 23:
            return 3
        return 0
    except Exception:
        return 0


def _rapid_rise_bonus(first_seen_at: str, last_seen_at: str,
                      rank: int, total: int) -> int:
    """
    上榜速度异常：短时间内冲到高排名就被删 = 很可能是敏感话题
    返回额外分数 0-15
    """
    if rank <= 0 or total <= 0:
        return 0
    try:
        t1 = datetime.strptime(first_seen_at, "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(last_seen_at, "%Y-%m-%d %H:%M:%S")
        alive_minutes = max(1, (t2 - t1).total_seconds() / 60)

        percentile = rank / total
        # 30 分钟内冲到 Top 10% → 极速上升
        if alive_minutes <= 30 and percentile <= 0.1:
            return 15
        elif alive_minutes <= 60 and percentile <= 0.2:
            return 10
        elif alive_minutes <= 120 and percentile <= 0.15:
            return 7
        return 0
    except Exception:
        return 0


def calc_suspicion_score(heat_level: int, duration_minutes: int,
                         detection_mode: str, rank: int,
                         cross_platform_count: int = 1,
                         disappeared_at: str = "",
                         first_seen_at: str = "",
                         last_seen_at: str = "",
                         total_in_list: int = 50,
                         hot_numeric: float = 0,
                         title: str = "") -> dict:
    """
    综合评估"疑似审查"可信度 v2
    分数 0-100，越高越可疑
    返回 { score, weighted_score, label, color, factors }
    """
    factors = []
    score = 0

    # ---- 1. 热度因子（max 48） ----
    heat_score = heat_level * 8
    # 如果有具体热度数值，额外加分
    if hot_numeric > 1_000_000:
        heat_score += 8
    elif hot_numeric > 100_000:
        heat_score += 4
    heat_score = min(48, heat_score)
    score += heat_score
    if heat_score > 0:
        factors.append({"name": "热度", "score": heat_score, "detail": f"等级{heat_level}"})

    # ---- 2. 曝光时长因子（max 25） ----
    dur_score = 0
    if duration_minutes <= 5:
        dur_score = 25
    elif duration_minutes <= 15:
        dur_score = 20
    elif duration_minutes <= 30:
        dur_score = 15
    elif duration_minutes <= 60:
        dur_score = 10
    elif duration_minutes <= 180:
        dur_score = 5
    score += dur_score
    if dur_score > 0:
        factors.append({"name": "曝光短", "score": dur_score, "detail": f"{duration_minutes}分钟"})

    # ---- 3. 闪删检测 bonus（+5） ----
    if detection_mode == "flash":
        score += 5
        factors.append({"name": "闪删检测", "score": 5, "detail": "5分钟快照"})

    # ---- 4. 排名因子（max 10） ----
    rank_score = 0
    if rank <= 3:
        rank_score = 10
    elif rank <= 10:
        rank_score = 6
    elif rank <= 20:
        rank_score = 3
    score += rank_score
    if rank_score > 0:
        factors.append({"name": "排名高", "score": rank_score, "detail": f"第{rank}名"})

    # ---- 5. 跨平台联动（max 25） ----
    cross_score = 0
    if cross_platform_count >= 4:
        cross_score = 25
    elif cross_platform_count >= 3:
        cross_score = 18
    elif cross_platform_count >= 2:
        cross_score = 12
    score += cross_score
    if cross_score > 0:
        factors.append({"name": "跨平台", "score": cross_score, "detail": f"{cross_platform_count}平台"})

    # ---- 6. 深夜删除 bonus（max 8） ----
    night_score = _night_deletion_bonus(disappeared_at) if disappeared_at else 0
    score += night_score
    if night_score > 0:
        factors.append({"name": "深夜删除", "score": night_score, "detail": disappeared_at[-8:]})

    # ---- 7. 极速上榜 bonus（max 15） ----
    rapid_score = 0
    if first_seen_at and last_seen_at:
        rapid_score = _rapid_rise_bonus(first_seen_at, last_seen_at, rank, total_in_list)
    score += rapid_score
    if rapid_score > 0:
        factors.append({"name": "极速上榜", "score": rapid_score, "detail": f"{duration_minutes}min到Top{rank}"})

    # ---- 8. 标题敏感词初筛（max 10，规则引擎，非 ML） ----
    keyword_score = _keyword_sensitivity_score(title) if title else 0
    score += keyword_score
    if keyword_score > 0:
        factors.append({"name": "敏感词", "score": keyword_score, "detail": "规则匹配"})

    # 原始分数上限
    raw_score = min(100, max(0, score))

    # ---- 时间衰减加权（用于排序，不改变 raw score） ----
    decay = _time_decay_factor(disappeared_at) if disappeared_at else 1.0
    weighted_score = round(raw_score * (0.3 + 0.7 * decay), 1)

    if raw_score >= 70:
        return {"score": raw_score, "weighted_score": weighted_score,
                "label": "高度可疑", "color": "#e74c3c", "factors": factors}
    elif raw_score >= 45:
        return {"score": raw_score, "weighted_score": weighted_score,
                "label": "值得关注", "color": "#e67e22", "factors": factors}
    elif raw_score >= 25:
        return {"score": raw_score, "weighted_score": weighted_score,
                "label": "可能正常", "color": "#f39c12", "factors": factors}
    else:
        return {"score": raw_score, "weighted_score": weighted_score,
                "label": "正常降温", "color": "#95a5a6", "factors": factors}


# ============================================================
# 规则引擎：标题敏感词初筛
# ============================================================

# 高权重关键词（政治/社会事件/维权/安全）
_SENSITIVE_HIGH = [
    "官员", "书记", "局长", "部长", "市长", "省长", "主席",
    "维权", "上访", "抗议", "游行", "罢工", "罢课",
    "爆炸", "坍塌", "垮塌", "矿难", "火灾", "事故",
    "警察", "城管", "暴力执法", "打人",
    "贪腐", "受贿", "落马", "双规", "被查",
    "封城", "封控", "隔离", "核酸",
    "言论", "删帖", "封号", "审查", "敏感",
    "军事", "台海", "南海",
]
# 中权重关键词
_SENSITIVE_MID = [
    "通报", "回应", "辟谣", "道歉", "处分", "免职",
    "热搜", "撤热搜", "压热搜",
    "央视", "新华社", "官方",
    "房价", "失业", "裁员", "降薪",
    "学生", "教师", "医院", "医生",
]


def _keyword_sensitivity_score(title: str) -> int:
    """基于规则的标题敏感度打分（0-10）"""
    if not title:
        return 0
    score = 0
    for kw in _SENSITIVE_HIGH:
        if kw in title:
            score += 5
            break  # 只计一次高权重
    for kw in _SENSITIVE_MID:
        if kw in title:
            score += 3
            break
    return min(10, score)


# ============================================================
# 分析模块实现（Phase 1：轻量 NLP + 统计）
# ============================================================

class SensitivityClassifier:
    """
    TODO: 语义敏感度分类器（Phase 4 — 需微调 BERT）
    当前仅占位，等积累标注数据后实现
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.ready = False

    def load(self):
        pass

    def predict(self, title: str) -> dict:
        return {"score": 0.0, "label": "unknown", "categories": []}


class SentimentAnalyzer:
    """
    Phase 1.2 — 基于 SnowNLP 的轻量情感分析
    SnowNLP 输出 0-1 的正面概率，我们映射为 polarity -1~1
    精度一般但零成本启动，后续可替换为 BERT
    """
    def __init__(self):
        self.ready = False
        self._snownlp = None

    def _ensure_loaded(self):
        if self._snownlp is not None:
            return True
        try:
            import snownlp as _sn
            self._snownlp = _sn
            self.ready = True
            return True
        except ImportError:
            return False

    def analyze(self, text: str) -> dict:
        """
        返回 { polarity: -1.0~1.0, score: 0~1, label: positive/negative/neutral }
        polarity = (snownlp_score - 0.5) * 2  → 映射到 [-1, 1]
        """
        if not text or not self._ensure_loaded():
            return {"polarity": 0.0, "score": 0.5, "label": "neutral"}
        try:
            s = self._snownlp.SnowNLP(text)
            score = s.sentiments  # 0~1, 1=positive
            polarity = round((score - 0.5) * 2, 3)
            if score >= 0.6:
                label = "positive"
            elif score <= 0.4:
                label = "negative"
            else:
                label = "neutral"
            return {"polarity": polarity, "score": round(score, 3), "label": label}
        except Exception:
            return {"polarity": 0.0, "score": 0.5, "label": "neutral"}


# 敏感实体词典路径
_SENSITIVE_ENTITIES_PATH = Path(__file__).parent / "data" / "sensitive_entities.json"

# 默认敏感实体词典（如果 json 文件不存在则使用）
_DEFAULT_SENSITIVE_ENTITIES = {
    "person_titles": [
        "书记", "省长", "市长", "县长", "区长", "局长", "部长", "主任",
        "院长", "校长", "处长", "科长", "厅长", "司长", "主席", "副主席",
        "总理", "副总理", "委员", "纪委", "监委", "政委",
    ],
    "org_keywords": [
        "中央", "国务院", "公安", "城管", "纪委", "监委", "法院", "检察院",
        "政府", "人大", "政协", "军区", "武警", "央行", "证监会", "银保监",
    ],
    "sensitive_locations": [
        "天安门", "中南海", "新疆", "西藏", "香港", "台湾", "澳门",
    ],
    "event_keywords": [
        "维权", "上访", "请愿", "示威", "罢工", "集会", "游行",
        "坍塌", "垮塌", "爆炸", "矿难", "事故", "火灾",
        "贪腐", "受贿", "行贿", "落马", "双规", "留置", "被查",
    ],
}


def _load_sensitive_entities() -> dict:
    """加载敏感实体词典"""
    if _SENSITIVE_ENTITIES_PATH.exists():
        try:
            with open(_SENSITIVE_ENTITIES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT_SENSITIVE_ENTITIES


class EntityExtractor:
    """
    Phase 1.3 — 基于 jieba 分词 + 敏感实体词典的轻量 NER
    提取人名/地名/机构，并标记是否命中敏感实体库
    """
    def __init__(self):
        self.ready = False
        self._jieba = None
        self._entities_dict = None

    def _ensure_loaded(self):
        if self._jieba is not None:
            return True
        try:
            import jieba
            import jieba.posseg as pseg
            self._jieba = jieba
            self._pseg = pseg
            self._entities_dict = _load_sensitive_entities()

            # 把敏感实体加入 jieba 词典，提升分词准确度
            for category, words in self._entities_dict.items():
                for w in words:
                    jieba.suggest_freq(w, tune=True)

            self.ready = True
            return True
        except ImportError:
            return False

    def extract(self, text: str) -> list:
        """
        返回 [{ text: str, type: str, is_sensitive: bool }]
        type: person / location / organization / event / unknown
        """
        if not text or not self._ensure_loaded():
            return []

        results = []
        seen = set()

        # 1) jieba 词性标注提取实体
        words = self._pseg.cut(text)
        for word, flag in words:
            word = word.strip()
            if len(word) < 2 or word in seen:
                continue
            entity_type = None
            if flag.startswith("nr"):     # 人名
                entity_type = "person"
            elif flag.startswith("ns"):   # 地名
                entity_type = "location"
            elif flag.startswith("nt"):   # 机构
                entity_type = "organization"

            if entity_type:
                is_sensitive = self._check_sensitive(word, entity_type)
                results.append({
                    "text": word,
                    "type": entity_type,
                    "is_sensitive": is_sensitive,
                })
                seen.add(word)

        # 2) 规则匹配：检查敏感关键词是否出现在文本中
        for kw in self._entities_dict.get("person_titles", []):
            if kw in text and kw not in seen:
                results.append({"text": kw, "type": "person", "is_sensitive": True})
                seen.add(kw)
        for kw in self._entities_dict.get("org_keywords", []):
            if kw in text and kw not in seen:
                results.append({"text": kw, "type": "organization", "is_sensitive": True})
                seen.add(kw)
        for kw in self._entities_dict.get("sensitive_locations", []):
            if kw in text and kw not in seen:
                results.append({"text": kw, "type": "location", "is_sensitive": True})
                seen.add(kw)
        for kw in self._entities_dict.get("event_keywords", []):
            if kw in text and kw not in seen:
                results.append({"text": kw, "type": "event", "is_sensitive": True})
                seen.add(kw)

        return results

    def _check_sensitive(self, word: str, entity_type: str) -> bool:
        """检查一个实体是否在敏感词典中"""
        if not self._entities_dict:
            return False
        all_sensitive = []
        for v in self._entities_dict.values():
            all_sensitive.extend(v)
        return word in all_sensitive or any(s in word for s in all_sensitive)


class TopicClusterer:
    """
    TODO: 语义话题聚类（Phase 2.3 — 需 sentence-transformers + HDBSCAN）
    当前使用字符串匹配，积累数据后升级为 embedding 聚类
    """
    def __init__(self):
        self.ready = False

    def cluster(self, titles: list) -> list:
        return []


class DissipationCurveDetector:
    """
    Phase 1.1 — 降温曲线检测（纯统计方法）
    通过分析排名时序判断是"正常降温"还是"异常删除"

    正常降温特征：
      - 排名逐渐上升（数字变大，越来越靠后）
      - 变化平缓，无突变
      - 在榜时间较长

    审查删除特征：
      - 排名稳定或仍在上升中突然消失
      - 最后几个数据点排名平稳或改善
      - 在榜时间可能很短
    """
    def __init__(self):
        self.ready = True  # 纯统计，无需模型加载

    def detect(self, rank_series: list) -> dict:
        """
        rank_series: [(timestamp_str, rank_int), ...] 按时间升序
        返回 {
            pattern: 'natural_decay' | 'abrupt_removal' | 'stable_removal' | 'unknown',
            confidence: 0.0-1.0,
            detail: str,
            slope: float,       # 排名变化斜率（正=降温，负=升温）
            last_rank: int,
            volatility: float,  # 排名波动性
        }
        """
        if not rank_series or len(rank_series) < 2:
            return {"pattern": "unknown", "confidence": 0.0,
                    "detail": "数据点不足", "slope": 0, "last_rank": 0, "volatility": 0}

        ranks = [r[1] for r in rank_series]
        n = len(ranks)
        last_rank = ranks[-1]

        # ---- 线性回归计算斜率 ----
        # x = [0, 1, 2, ...], y = ranks
        x_mean = (n - 1) / 2.0
        y_mean = sum(ranks) / n
        numerator = sum((i - x_mean) * (r - y_mean) for i, r in enumerate(ranks))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator > 0 else 0

        # ---- 最后 N 点趋势（更关注消失前的状态） ----
        tail_n = min(3, n)
        tail_ranks = ranks[-tail_n:]
        tail_slope = (tail_ranks[-1] - tail_ranks[0]) / max(tail_n - 1, 1)

        # ---- 排名波动性（标准差） ----
        rank_var = sum((r - y_mean) ** 2 for r in ranks) / n
        volatility = math.sqrt(rank_var)

        # ---- 判断逻辑 ----
        # 1) 排名在改善（数字变小）或稳定 → 然后突然消失 = 最可疑
        if tail_slope <= 0 and last_rank <= n * 0.5:
            # 排名在上升或稳定，且位置靠前
            pattern = "abrupt_removal"
            confidence = min(0.95, 0.6 + abs(tail_slope) * 0.05 + (1 - last_rank / max(n * 2, 1)) * 0.3)
            detail = f"排名稳定/上升中消失(末段斜率{tail_slope:+.1f}, 末位#{last_rank})"

        elif tail_slope <= 1.0 and slope <= 1.0:
            # 排名变化平缓但也不是明显下滑 → 可能被删
            pattern = "stable_removal"
            confidence = min(0.8, 0.4 + (1 - slope / 5) * 0.2 + (1 - last_rank / max(n * 3, 1)) * 0.2)
            detail = f"排名平稳中消失(总斜率{slope:+.1f}, 末位#{last_rank})"

        elif slope > 2.0 and last_rank > n * 0.6:
            # 排名持续下滑（数字变大），靠后位置消失 → 自然降温
            pattern = "natural_decay"
            confidence = min(0.9, 0.5 + slope * 0.05 + last_rank / max(n * 3, 1) * 0.2)
            detail = f"排名持续下滑(斜率{slope:+.1f}, 末位#{last_rank})"

        else:
            # 不确定
            pattern = "unknown"
            confidence = 0.3
            detail = f"模式不明确(斜率{slope:+.1f}, 末段{tail_slope:+.1f}, 末位#{last_rank})"

        return {
            "pattern": pattern,
            "confidence": round(confidence, 2),
            "detail": detail,
            "slope": round(slope, 2),
            "last_rank": last_rank,
            "volatility": round(volatility, 2),
        }


def _get_rank_series(conn, platform: str, title: str,
                     before_batch_id: int) -> list:
    """
    从数据库提取某条目的排名时序
    返回 [(created_at, rank), ...] 按时间升序
    """
    rows = conn.execute(
        """SELECT fb.created_at, hi.rank
           FROM hot_item hi
           JOIN fetch_batch fb ON hi.batch_id = fb.id
           WHERE hi.platform = ? AND hi.title = ?
           AND hi.batch_id <= ?
           ORDER BY fb.created_at ASC""",
        (platform, title, before_batch_id),
    ).fetchall()
    return [(r["created_at"], r["rank"] or 50) for r in rows]


# 全局模型实例（懒加载）
_sensitivity_clf = SensitivityClassifier()
_sentiment_analyzer = SentimentAnalyzer()
_entity_extractor = EntityExtractor()
_topic_clusterer = TopicClusterer()
_curve_detector = DissipationCurveDetector()

# 预初始化轻量模块（SnowNLP / jieba 首次加载较慢，提前触发）
_sentiment_analyzer._ensure_loaded()
_entity_extractor._ensure_loaded()


def get_ml_status() -> dict:
    """获取各 ML 模块就绪状态"""
    return {
        "sensitivity_classifier": _sensitivity_clf.ready,
        "sentiment_analyzer": _sentiment_analyzer.ready,
        "entity_extractor": _entity_extractor.ready,
        "topic_clusterer": _topic_clusterer.ready,
        "curve_detector": _curve_detector.ready,
    }


# ============================================================
# 热度突变检测
# ============================================================

def detect_hot_surge(conn, platform: str, title: str,
                     current_batch_id: int) -> dict:
    """
    检测一个条目在消失前是否经历了热度骤升
    （热度骤升后被删 = 更可疑）
    返回 { surged: bool, surge_ratio: float, detail: str }
    """
    rows = conn.execute(
        """SELECT hi.hot, hi.rank, fb.created_at
           FROM hot_item hi
           JOIN fetch_batch fb ON hi.batch_id = fb.id
           WHERE hi.platform = ? AND hi.title = ? AND hi.batch_id <= ?
           ORDER BY hi.batch_id DESC LIMIT 5""",
        (platform, title, current_batch_id),
    ).fetchall()

    if len(rows) < 2:
        return {"surged": False, "surge_ratio": 0, "detail": ""}

    hots = [_parse_hot(r["hot"]) for r in rows]
    # 最近的排名
    ranks = [r["rank"] or 50 for r in rows]

    # 热度突变：最新一次 vs 前几次的均值
    latest = hots[0] if hots[0] > 0 else 1
    older_avg = sum(hots[1:]) / len(hots[1:]) if any(hots[1:]) else 1
    older_avg = max(older_avg, 1)

    surge_ratio = latest / older_avg

    # 排名突变：排名骤升（数字变小）
    rank_change = ranks[-1] - ranks[0] if len(ranks) >= 2 else 0

    if surge_ratio >= 3.0 or rank_change >= 15:
        return {
            "surged": True,
            "surge_ratio": round(surge_ratio, 1),
            "detail": f"热度x{surge_ratio:.1f}, 排名↑{rank_change}位",
        }
    return {"surged": False, "surge_ratio": round(surge_ratio, 1), "detail": ""}


# ============================================================
# 数据库初始化
# ============================================================

def init_censor_db():
    """初始化审查监测表"""
    conn = _get_db()
    try:
        conn.executescript("""
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

def _batch_trace_first_seen(conn, items_to_trace: list, before_batch_id: int) -> dict:
    """
    批量回溯 first_seen，避免 N+1 查询
    items_to_trace: [(platform, title), ...]
    返回 { (platform, title): first_seen_at }
    """
    if not items_to_trace:
        return {}

    by_platform = {}
    for p, t in items_to_trace:
        by_platform.setdefault(p, []).append(t)

    results = {}
    for platform, titles in by_platform.items():
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
# 方案一：Diff 对比（全平台）
# ============================================================

def diff_batches(current_batch_id: int = None) -> list:
    """
    对比最近两个 batch，找出消失的条目
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

        old_items = conn.execute(
            "SELECT platform, title, url, hot, rank FROM hot_item WHERE batch_id=?",
            (old_batch["id"],),
        ).fetchall()
        new_items = conn.execute(
            "SELECT platform, title FROM hot_item WHERE batch_id=?",
            (new_batch["id"],),
        ).fetchall()

        new_set = {(r["platform"], r["title"]) for r in new_items}

        platform_totals = {}
        for item in old_items:
            p = item["platform"]
            platform_totals[p] = platform_totals.get(p, 0) + 1

        vanished_keys = []
        vanished_items = []
        for item in old_items:
            key = (item["platform"], item["title"])
            if key not in new_set:
                vanished_keys.append(key)
                vanished_items.append(item)

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
# 方案二：高频快照（闪删大户）
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
        total = len(old_snap)

        new_titles = {item.get("title", "") for item in new_snap}

        vanished = [item for item in old_snap
                    if item.get("title") and item["title"] not in new_titles]

        if not vanished:
            return []

        earlier_snaps = conn.execute(
            """SELECT snapshot_at, data FROM flash_snapshot
               WHERE platform=? AND id < ? ORDER BY id ASC""",
            (platform, rows[1]["id"]),
        ).fetchall()

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
# 跨平台关联（字符串匹配 + TODO: embedding 语义匹配）
# ============================================================

def _normalize_title(title: str) -> str:
    """标题归一化，用于跨平台模糊匹配"""
    s = re.sub(r'[#＃【】\[\]《》\s]', '', title)
    return s.lower()


def _build_cross_platform_map(items: list) -> dict:
    """
    构建跨平台关联映射
    返回 { normalized_title: { platforms: set, items: [indices] } }
    """
    clusters = {}
    for i, item in enumerate(items):
        norm = _normalize_title(item.get("title", ""))
        if not norm or len(norm) < 4:
            continue
        if norm in clusters:
            clusters[norm]["platforms"].add(item["platform"])
            clusters[norm]["indices"].append(i)
        else:
            clusters[norm] = {
                "platforms": {item["platform"]},
                "indices": [i],
                "title": item.get("title", ""),
            }

    # 子串匹配（A 包含 B 或 B 包含 A 且 len >= 6）
    norms = list(clusters.keys())
    merges = {}
    for i, a in enumerate(norms):
        if a in merges:
            continue
        for b in norms[i+1:]:
            if b in merges:
                continue
            if len(a) >= 6 and len(b) >= 6:
                if a in b or b in a:
                    canonical = a if len(a) >= len(b) else b
                    other = b if canonical == a else a
                    merges[other] = canonical
                    clusters[canonical]["platforms"] |= clusters[other]["platforms"]
                    clusters[canonical]["indices"] += clusters[other]["indices"]

    for old in merges:
        if old in clusters:
            del clusters[old]

    return clusters


# ============================================================
# 查询接口
# ============================================================

def get_censored_items(limit: int = 100, platform: str = None,
                       hours: int = 24, sort_by: str = "suspicion",
                       show_noise: bool = False) -> list:
    """
    获取最近消失的条目（含跨平台关联 + v2 可疑度评分）
    sort_by: suspicion | weighted | time | heat
    show_noise: False=过滤广告/IT科技等噪音（默认），True=显示全部
    """
    conn = _get_db()
    try:
        query = """SELECT * FROM censored_item
                   WHERE disappeared_at >= datetime('now', 'localtime', ?)"""
        params = [f"-{hours} hours"]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        # 如果不显示噪音，在 SQL 层排除噪音平台
        if not show_noise and not platform:
            placeholders = ",".join("?" * len(EXCLUDED_PLATFORMS))
            query += f" AND platform NOT IN ({placeholders})"
            params.extend(sorted(EXCLUDED_PLATFORMS))

        query += " ORDER BY disappeared_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = [dict(r) for r in rows]

        # 标题级噪音过滤（非排除平台中的广告/IT产品）
        if not show_noise:
            results = [r for r in results
                       if not _is_noise(r.get("title", ""), r.get("platform", ""))]

        # 跨平台关联
        cross_map = _build_cross_platform_map(results)

        idx_to_cross = {}
        idx_to_group = {}
        for norm, cluster in cross_map.items():
            count = len(cluster["platforms"])
            platforms_list = sorted(cluster["platforms"])
            for idx in cluster["indices"]:
                idx_to_cross[idx] = count
                idx_to_group[idx] = {
                    "count": count,
                    "platforms": platforms_list,
                    "group_title": cluster["title"],
                }

        # 批量检测热度突变
        surge_cache = {}
        for i, d in enumerate(results):
            key = (d["platform"], d["title"], d.get("batch_seen", 0))
            if key not in surge_cache:
                surge_cache[key] = detect_hot_surge(
                    conn, d["platform"], d["title"], d.get("batch_seen", 0)
                )

        for i, d in enumerate(results):
            cross_count = idx_to_cross.get(i, 1)
            surge_key = (d["platform"], d["title"], d.get("batch_seen", 0))
            surge = surge_cache.get(surge_key, {"surged": False})

            # 热度等级
            d["heat_info"] = calc_heat_level(
                d.get("rank_when_seen", 0),
                d.get("total_in_list", 50),
            )

            # v2 可疑度评分
            d["suspicion"] = calc_suspicion_score(
                d.get("heat_level", 0),
                d.get("duration_minutes", 0),
                d.get("detection_mode", "diff"),
                d.get("rank_when_seen", 0),
                cross_platform_count=cross_count,
                disappeared_at=d.get("disappeared_at", ""),
                first_seen_at=d.get("first_seen_at", ""),
                last_seen_at=d.get("last_seen_at", ""),
                total_in_list=d.get("total_in_list", 50),
                hot_numeric=d.get("hot_numeric", 0),
                title=d.get("title", ""),
            )

            # 热度突变
            d["surge"] = surge

            # 跨平台信息
            d["cross_platform"] = idx_to_group.get(i, {"count": 1, "platforms": [d["platform"]]})

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

            # ---- 分析模块填充 ----
            # 情感分析（SnowNLP — Phase 1.2）
            title_text = d.get("title", "")
            if _sentiment_analyzer.ready and title_text:
                d["sentiment"] = _sentiment_analyzer.analyze(title_text)

            # 实体识别（jieba — Phase 1.3）
            if _entity_extractor.ready and title_text:
                d["entities"] = _entity_extractor.extract(title_text)

            # 降温曲线检测（统计 — Phase 1.1）
            if _curve_detector.ready:
                rank_series = _get_rank_series(
                    conn, d["platform"], title_text, d.get("batch_seen", 0)
                )
                d["curve"] = _curve_detector.detect(rank_series)

            # 敏感度分类（TODO — Phase 4）
            if _sensitivity_clf.ready and title_text:
                d["sensitivity"] = _sensitivity_clf.predict(title_text)

        # 排序
        if sort_by == "weighted":
            results.sort(key=lambda x: x.get("suspicion", {}).get("weighted_score", 0), reverse=True)
        elif sort_by == "time":
            results.sort(key=lambda x: x.get("disappeared_at", ""), reverse=True)
        elif sort_by == "heat":
            results.sort(key=lambda x: x.get("heat_level", 0), reverse=True)
        else:  # suspicion (default)
            results.sort(key=lambda x: x.get("suspicion", {}).get("score", 0), reverse=True)

        return results
    finally:
        conn.close()


def get_censor_stats(hours: int = 24, show_noise: bool = False) -> dict:
    """统计审查概况（默认排除噪音平台和标题）"""
    conn = _get_db()
    try:
        # 构建噪音平台排除条件
        if show_noise:
            noise_clause = ""
            noise_params = []
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PLATFORMS))
            noise_clause = f" AND platform NOT IN ({placeholders})"
            noise_params = sorted(EXCLUDED_PLATFORMS)

        base_where = "disappeared_at >= datetime('now', 'localtime', ?)"

        total = conn.execute(
            f"SELECT COUNT(*) as cnt FROM censored_item WHERE {base_where}{noise_clause}",
            [f"-{hours} hours"] + noise_params,
        ).fetchone()["cnt"]

        by_platform = conn.execute(
            f"""SELECT platform, COUNT(*) as cnt FROM censored_item
               WHERE {base_where}{noise_clause}
               GROUP BY platform ORDER BY cnt DESC""",
            [f"-{hours} hours"] + noise_params,
        ).fetchall()

        by_mode = conn.execute(
            f"""SELECT detection_mode, COUNT(*) as cnt FROM censored_item
               WHERE {base_where}{noise_clause}
               GROUP BY detection_mode""",
            [f"-{hours} hours"] + noise_params,
        ).fetchall()

        high_heat = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM censored_item
               WHERE {base_where}{noise_clause}
               AND heat_level >= 4""",
            [f"-{hours} hours"] + noise_params,
        ).fetchone()["cnt"]

        quick_delete = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM censored_item
               WHERE {base_where}{noise_clause}
               AND duration_minutes > 0 AND duration_minutes < 30""",
            [f"-{hours} hours"] + noise_params,
        ).fetchone()["cnt"]

        surge_count = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM censored_item
               WHERE {base_where}{noise_clause}
               AND heat_level >= 3 AND duration_minutes < 60""",
            [f"-{hours} hours"] + noise_params,
        ).fetchone()["cnt"]

        all_items = conn.execute(
            f"""SELECT title, platform FROM censored_item
               WHERE {base_where}{noise_clause}""",
            [f"-{hours} hours"] + noise_params,
        ).fetchall()

        # 标题级噪音过滤
        if not show_noise:
            all_items_filtered = [dict(r) for r in all_items
                                  if not _is_noise(r["title"], r["platform"])]
        else:
            all_items_filtered = [dict(r) for r in all_items]

        cross_map = _build_cross_platform_map(all_items_filtered)
        cross_events = sum(1 for c in cross_map.values() if len(c["platforms"]) >= 2)

        return {
            "total": total,
            "hours": hours,
            "high_heat_count": high_heat,
            "quick_delete_count": quick_delete,
            "cross_platform_events": cross_events,
            "surge_count": surge_count,
            "by_platform": [dict(r) for r in by_platform],
            "by_mode": [dict(r) for r in by_mode],
            "ml_status": get_ml_status(),
        }
    finally:
        conn.close()
