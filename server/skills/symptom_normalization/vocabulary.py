"""症状归一化的唯一词表与归一化算法（TICKET-004）。

本模块是全项目**唯一一份**症状词表：标准词、口语别名与否定式规则都在这里。
按 SPEC.md 3.6「有意修复」，旧实现里「30 词提取表 + 22 条别名表」两张割裂的词表在这里
合并为一份；对话链路（从原文提取）与症状推理链路（对显式症状列表归一化）都复用它，
因此同一输入在两条链路得到同一批标准症状（SPEC.md 4.1 B-2、6.1 AC-B-17/18）。
"""

from collections.abc import Sequence
from typing import NamedTuple

VOCABULARY_VERSION = "symptom-vocabulary-v1"

# 否定式表述的判定（SKILL.md 1.4）：只看命中片段之前紧邻的窗口，且否定标记必须
# **作为窗口后缀**出现。跨标点不延伸；与安全门（TICKET-003）使用同一保守规则。
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


class SymptomTerm(NamedTuple):
    """一个标准症状及其全部表面词；`surfaces` 的第一项是该标准词本身。"""

    standard: str
    surfaces: tuple[str, ...]


# 顺序无关：输出按各表面词在文本中的首次出现位置排序（见 extract_symptoms）。
SYMPTOM_TERMS: tuple[SymptomTerm, ...] = (
    SymptomTerm("头痛", ("头痛", "头疼", "头胀")),
    SymptomTerm("发热", ("发热", "发烧", "发高烧", "高烧", "低烧")),
    SymptomTerm("咳嗽", ("咳嗽",)),
    SymptomTerm("乏力", ("乏力", "没力气", "疲倦", "疲劳")),
    SymptomTerm("恶心", ("恶心", "想吐")),
    SymptomTerm("呕吐", ("呕吐",)),
    SymptomTerm("腹泻", ("腹泻", "拉肚子")),
    SymptomTerm("腹痛", ("腹痛", "肚子痛", "胃疼")),
    SymptomTerm("胸闷", ("胸闷", "胸口闷")),
    SymptomTerm("心悸", ("心悸",)),
    SymptomTerm("头晕", ("头晕", "头昏")),
    SymptomTerm("失眠", ("失眠",)),
    SymptomTerm("皮疹", ("皮疹",)),
    SymptomTerm("瘙痒", ("瘙痒",)),
    SymptomTerm("水肿", ("水肿",)),
    SymptomTerm("出血", ("出血",)),
    SymptomTerm("关节痛", ("关节痛", "关节疼")),
    SymptomTerm("腰痛", ("腰痛", "腰疼")),
    SymptomTerm("视力模糊", ("视力模糊", "看不清")),
    SymptomTerm("耳鸣", ("耳鸣",)),
    SymptomTerm("鼻塞", ("鼻塞",)),
    SymptomTerm("咽痛", ("咽痛", "喉咙痛", "嗓子痛")),
    SymptomTerm("流涕", ("流涕", "流鼻涕")),
    SymptomTerm("高血压", ("高血压",)),
    SymptomTerm("糖尿病", ("糖尿病",)),
    SymptomTerm("感冒", ("感冒",)),
    SymptomTerm("过敏", ("过敏",)),
    SymptomTerm("便秘", ("便秘",)),
    SymptomTerm("尿频", ("尿频",)),
    SymptomTerm("胸痛", ("胸痛", "胸口痛")),
)

STANDARD_SYMPTOMS: tuple[str, ...] = tuple(term.standard for term in SYMPTOM_TERMS)


def _is_negated(text: str, index: int) -> bool:
    window = text[max(0, index - NEGATION_WINDOW) : index]
    return window.endswith(NEGATION_MARKERS)


def _surface_hits(text: str) -> list[tuple[int, str, bool]]:
    """每次表面词命中记一条 `(出现位置, 标准症状, 是否被否定)`，按位置从先到后排序。"""
    hits: list[tuple[int, str, bool]] = []
    for term in SYMPTOM_TERMS:
        for surface in term.surfaces:
            start = 0
            while (index := text.find(surface, start)) >= 0:
                hits.append((index, term.standard, _is_negated(text, index)))
                start = index + 1
    hits.sort(key=lambda hit: hit[0])
    return hits


def extract_symptoms(text: str) -> list[str]:
    """对话链路入口：原始文本 → 标准症状集合。

    按各表面词的首次出现位置排序、按标准症状去重（别名与标准词合并为一项）。
    """
    ordered: list[str] = []
    for _position, standard, negated in _surface_hits(text):
        if not negated and standard not in ordered:
            ordered.append(standard)
    return ordered


def normalize_terms(terms: Sequence[str]) -> list[str]:
    """症状推理链路入口：显式症状列表 → 标准症状集合。

    逐项去首尾空白；已知表面词（含别名）替换为标准词并剔除否定式；未知词按原样保留
    （维持既有 `/graph/infer` 行为）。保持首次出现顺序并去重。与 `extract_symptoms`
    共用同一份 `SYMPTOM_TERMS`，两条链路因此得到同一标准症状集合。
    """
    ordered: list[str] = []
    for raw in terms:
        term = raw.strip()
        if not term:
            continue
        hits = _surface_hits(term)
        if not hits:
            if term not in ordered:
                ordered.append(term)
            continue
        for _position, standard, negated in hits:
            if not negated and standard not in ordered:
                ordered.append(standard)
    return ordered
