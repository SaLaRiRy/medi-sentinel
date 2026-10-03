"""医学本体与种子数据（TICKET-013）。

节点标签与关系类型取自 `FUNCTIONAL_SPEC.md` 6.2 / 4.5：**6 类节点**
（疾病 / 症状 / 科室 / 药物 / 检查 / 食物）与**7 类关系**。节点在各自标签内以
`name` 唯一（对应 6 条唯一性约束，见 `scripts/init_graph.py`）。

种子数据以 `server/docs_seed/` 的三篇中文文档为锚（高血压、感冒、糖尿病），
并补齐词表中的标准症状与支撑节点。这里只有纯数据，不含任何 I/O，因此可在
不启动图数据库的前提下被单独校验（`SPEC.md` 4.1 B-2 / B-3）。
"""

from __future__ import annotations

Node = tuple[str, str]
Relationship = tuple[str, str, str, str, str]

# 6 类节点标签（顺序即唯一性约束的创建顺序）。
NODE_LABELS: tuple[str, ...] = (
    "Disease",
    "Symptom",
    "Department",
    "Drug",
    "Check",
    "Food",
)

# 7 类关系（名称与前端展示映射一致，FUNCTIONAL_SPEC.md 6.5「图谱关系名」）。
RELATIONSHIP_TYPES: tuple[str, ...] = (
    "HAS_SYMPTOM",
    "BELONGS_TO",
    "RECOMMEND_DRUG",
    "NEED_CHECK",
    "ACCOMPANY_WITH",
    "SHOULD_EAT",
    "AVOID_EAT",
)

_NODES_BY_LABEL: dict[str, tuple[str, ...]] = {
    "Disease": ("高血压", "感冒", "糖尿病"),
    "Symptom": (
        "头痛",
        "头晕",
        "头胀",
        "心悸",
        "胸闷",
        "乏力",
        "发热",
        "咳嗽",
        "咽痛",
        "流涕",
        "鼻塞",
        "多饮",
        "多尿",
        "多食",
        "体重下降",
        "恶心",
        "呕吐",
        "腹痛",
        "腹泻",
    ),
    "Department": ("心血管内科", "呼吸内科", "内分泌科", "消化内科"),
    "Drug": ("氨氯地平", "缬沙坦", "奥司他韦", "对乙酰氨基酚", "二甲双胍", "胰岛素"),
    "Check": ("血压测量", "血常规", "空腹血糖", "糖化血红蛋白"),
    "Food": ("绿叶蔬菜", "粗粮", "咸菜", "高糖水果", "含糖饮料"),
}

NODES: tuple[Node, ...] = tuple(
    (label, name) for label in NODE_LABELS for name in _NODES_BY_LABEL[label]
)


def _edges(
    rel: str, start: str, targets: tuple[tuple[str, str], ...]
) -> tuple[Relationship, ...]:
    """从一个疾病出发、指向若干同类节点的一组关系。"""
    return tuple(
        (rel, "Disease", start, end_label, end_name) for end_label, end_name in targets
    )


def _targets(label: str, *names: str) -> tuple[tuple[str, str], ...]:
    return tuple((label, name) for name in names)


def _symptoms(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Symptom", *names)


def _departments(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Department", *names)


def _drugs(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Drug", *names)


def _checks(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Check", *names)


def _diseases(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Disease", *names)


def _foods(*names: str) -> tuple[tuple[str, str], ...]:
    return _targets("Food", *names)

_HIGH_BLOOD_PRESSURE = "高血压"
_COLD = "感冒"
_DIABETES = "糖尿病"

# 每个疾病覆盖 7 类关系中的若干类，三篇种子文档合起来覆盖全部 7 类。
RELATIONSHIPS: tuple[Relationship, ...] = (
    *_edges(
        "HAS_SYMPTOM",
        _HIGH_BLOOD_PRESSURE,
        _symptoms("头痛", "头晕", "头胀", "心悸", "胸闷", "乏力"),
    ),
    *_edges("BELONGS_TO", _HIGH_BLOOD_PRESSURE, _departments("心血管内科")),
    *_edges("RECOMMEND_DRUG", _HIGH_BLOOD_PRESSURE, _drugs("氨氯地平", "缬沙坦")),
    *_edges("NEED_CHECK", _HIGH_BLOOD_PRESSURE, _checks("血压测量")),
    *_edges("ACCOMPANY_WITH", _HIGH_BLOOD_PRESSURE, _diseases(_DIABETES)),
    *_edges("SHOULD_EAT", _HIGH_BLOOD_PRESSURE, _foods("绿叶蔬菜")),
    *_edges("AVOID_EAT", _HIGH_BLOOD_PRESSURE, _foods("咸菜")),
    *_edges(
        "HAS_SYMPTOM",
        _COLD,
        _symptoms("发热", "咳嗽", "咽痛", "流涕", "鼻塞", "乏力", "头痛"),
    ),
    *_edges("BELONGS_TO", _COLD, _departments("呼吸内科")),
    *_edges("RECOMMEND_DRUG", _COLD, _drugs("对乙酰氨基酚", "奥司他韦")),
    *_edges("NEED_CHECK", _COLD, _checks("血常规")),
    *_edges("SHOULD_EAT", _COLD, _foods("绿叶蔬菜")),
    *_edges("AVOID_EAT", _COLD, _foods("含糖饮料")),
    *_edges(
        "HAS_SYMPTOM",
        _DIABETES,
        _symptoms("多饮", "多尿", "多食", "体重下降", "乏力"),
    ),
    *_edges("BELONGS_TO", _DIABETES, _departments("内分泌科")),
    *_edges("RECOMMEND_DRUG", _DIABETES, _drugs("二甲双胍", "胰岛素")),
    *_edges("NEED_CHECK", _DIABETES, _checks("空腹血糖", "糖化血红蛋白")),
    *_edges("ACCOMPANY_WITH", _DIABETES, _diseases(_HIGH_BLOOD_PRESSURE)),
    *_edges("SHOULD_EAT", _DIABETES, _foods("粗粮")),
    *_edges("AVOID_EAT", _DIABETES, _foods("高糖水果")),
)
