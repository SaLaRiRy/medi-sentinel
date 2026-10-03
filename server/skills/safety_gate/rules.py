"""safety-gate 的红旗规则表与规则版本（TICKET-003）。

这是全项目**唯一一份**红旗规则表：顺序即输出顺序，匹配规则为子串包含，
不使用分词、不做同义词扩展、不做大小写或繁简转换（见 SKILL.md 1.3）。
`RULES_VERSION` 随每次判定写入输出，供审计与回放比对。
"""

from typing import Literal, NamedTuple

RedFlagLevel = Literal["urgent", "critical"]

# 严重级高低：critical > urgent。
LEVEL_ORDER: dict[RedFlagLevel, int] = {"urgent": 1, "critical": 2}

RULES_VERSION = "safety-gate-rules-v1"

# 否定式表述的判定（SKILL.md 第 3 节）：只看命中片段之前紧邻的窗口，且否定标记
# 必须**作为窗口后缀**出现。这样「不但胸痛」「不过胸痛」不会被误判为否定，
# 而「没有胸痛」「并无胸痛」「未出现胸痛」会。
NEGATION_WINDOW = 5
NEGATION_MARKERS: tuple[str, ...] = (
    "没有",
    "否认",
    "并非",
    "并不",
    "从未",
    "不曾",
    "未见",
    "未出现",
    "不伴有",
    "不伴",
    "毫无",
    "排除",
    "没",
    "无",
    "未",
    "不",
)


class RedFlagRule(NamedTuple):
    id: str
    level: RedFlagLevel
    label: str
    patterns: tuple[str, ...]


RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule(
        id="chest-pain",
        level="critical",
        label="急性胸痛",
        patterns=(
            "胸痛",
            "胸口痛",
            "胸口疼",
            "胸口剧痛",
            "胸部剧痛",
            "心前区疼痛",
            "心绞痛",
            "压榨性疼痛",
        ),
    ),
    RedFlagRule(
        id="dyspnea",
        level="critical",
        label="呼吸困难",
        patterns=(
            "喘不上气",
            "喘不过气",
            "上不来气",
            "呼吸困难",
            "呼吸急促",
            "憋气",
            "窒息",
            "喘鸣",
        ),
    ),
    RedFlagRule(
        id="severe-headache",
        level="urgent",
        label="剧烈头痛",
        patterns=("剧烈头痛", "头疼欲裂", "头痛欲裂", "炸裂样头痛", "雷击样头痛"),
    ),
    RedFlagRule(
        id="stroke",
        level="critical",
        label="卒中征象",
        patterns=(
            "口角歪斜",
            "嘴歪",
            "半身不遂",
            "偏瘫",
            "一侧肢体无力",
            "言语不清",
            "说话不清",
            "口齿不清",
            "突然不能说话",
        ),
    ),
    RedFlagRule(
        id="altered-consciousness",
        level="critical",
        label="意识障碍",
        patterns=(
            "昏迷",
            "意识不清",
            "意识模糊",
            "唤不醒",
            "叫不醒",
            "晕厥",
            "昏倒",
            "晕倒",
            "抽搐",
            "惊厥",
            "不省人事",
        ),
    ),
    RedFlagRule(
        id="severe-bleeding",
        level="critical",
        label="大出血",
        patterns=(
            "呕血",
            "吐血",
            "咯血",
            "咳血",
            "便血",
            "血便",
            "大出血",
            "大量出血",
            "阴道大出血",
            "阴道出血",
        ),
    ),
    RedFlagRule(
        id="anaphylaxis",
        level="critical",
        label="严重过敏",
        patterns=("喉头水肿", "喉咙肿胀", "过敏性休克"),
    ),
    RedFlagRule(
        id="poisoning-overdose",
        level="critical",
        label="中毒/过量/自伤",
        patterns=("中毒", "服毒", "药物过量", "吃药自杀", "割腕", "自杀", "喝了农药"),
    ),
    RedFlagRule(
        id="severe-abdominal-pain",
        level="urgent",
        label="剧烈腹痛",
        patterns=("剧烈腹痛", "腹部剧痛", "肚子剧痛", "肚子疼得厉害", "疼得直不起腰"),
    ),
    RedFlagRule(
        id="pregnancy-emergency",
        level="urgent",
        label="孕期急症",
        patterns=("孕期出血", "怀孕出血", "孕妇腹痛", "孕期腹痛"),
    ),
    RedFlagRule(
        id="black-stool",
        level="urgent",
        label="消化道出血征象",
        patterns=("黑便", "柏油样便"),
    ),
)
