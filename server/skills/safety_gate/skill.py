"""safety-gate: 编排第一顺位的确定性红旗检测（TICKET-003）。

契约见同目录 `SKILL.md`。本 Skill 零外部依赖、零端口：不访问数据库、图库、
向量索引与大模型，因此同一输入的结果可复现（SPEC.md 3.4 / 3.5）。
"""

from typing import Literal

from pydantic import BaseModel, Field

from skills.protocol import Skill
from skills.safety_gate.rules import (
    LEVEL_ORDER,
    NEGATION_MARKERS,
    NEGATION_WINDOW,
    RULES,
    RULES_VERSION,
    RedFlagLevel,
    RedFlagRule,
)

SCHEMA_VERSION = "safety-gate-schema-v1"

_LEVEL_MESSAGE: dict[RedFlagLevel, str] = {
    "emergency": (
        "检测到需要立即处理的急症信号：{labels}。"
        "请立即拨打 120 或前往最近的急诊科，不要自行等待或自行用药。"
    ),
    "urgent": (
        "检测到需要尽快就医的警示信号：{labels}。"
        "请尽快到医院就诊；症状加重时立即拨打 120。"
    ),
}

_LEVEL_ACTION: dict[RedFlagLevel, str] = {
    "emergency": "立即拨打 120 或前往最近的急诊科就诊。",
    "urgent": "尽快到医院就诊，由医生当面评估；症状加重时立即拨打 120。",
}


class RedFlagMatch(BaseModel):
    """一条命中的红旗。字段名与冻结的 `safety` 帧契约逐字一致（`id` / `label` /
    `matched_surface` / `severity`），因此可原样投影成 wire 载荷。`id` 与
    `matched_surface` 排在最前，保证受限摘要在截断后仍带着审计信息
    （SKILL.md 第 2 节「trace 与审计」）。"""

    id: str
    matched_surface: str
    severity: RedFlagLevel
    label: str


class SafetyGateInput(BaseModel):
    message: str = Field(min_length=1, description="患者本轮问诊的原始描述文本")


class SafetyGateOutput(BaseModel):
    rule_version: str
    red_flags: list[RedFlagMatch]
    level: RedFlagLevel | None
    decision: Literal["intercept", "allow"]
    message: str
    suggested_action: str


def detect_red_flags(message: str) -> list[RedFlagMatch]:
    """按规则表顺序返回全部命中项；同一规则多处出现只记首次命中的片段。"""
    matches: list[RedFlagMatch] = []
    for rule in RULES:
        matched_surface = _first_match(message, rule)
        if matched_surface is not None:
            matches.append(
                RedFlagMatch(
                    id=rule.id,
                    matched_surface=matched_surface,
                    severity=rule.level,
                    label=rule.label,
                )
            )
    return matches


def _first_match(message: str, rule: RedFlagRule) -> str | None:
    for pattern in rule.patterns:
        start = 0
        while True:
            index = message.find(pattern, start)
            if index < 0:
                break
            if not _is_negated(message, index):
                return pattern
            start = index + len(pattern)
    return None


def _is_negated(message: str, index: int) -> bool:
    window = message[max(0, index - NEGATION_WINDOW) : index]
    return window.endswith(NEGATION_MARKERS)


class SafetyGateSkill(Skill):
    name = "safety-gate"
    input_schema = SafetyGateInput
    output_schema = SafetyGateOutput

    async def run(self, data: SafetyGateInput) -> SafetyGateOutput:
        matches = detect_red_flags(data.message)
        if not matches:
            return SafetyGateOutput(
                rule_version=RULES_VERSION,
                red_flags=[],
                level=None,
                decision="allow",
                message="",
                suggested_action="",
            )

        level = max(matches, key=lambda match: LEVEL_ORDER[match.severity]).severity
        labels = "、".join(match.label for match in matches)
        return SafetyGateOutput(
            rule_version=RULES_VERSION,
            red_flags=matches,
            level=level,
            decision="intercept",
            message=_LEVEL_MESSAGE[level].format(labels=labels),
            suggested_action=_LEVEL_ACTION[level],
        )
