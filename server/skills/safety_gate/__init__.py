"""safety-gate：编排第一顺位的确定性红旗检测 Skill（契约见 `SKILL.md`）。"""

from skills.safety_gate.rules import (
    LEVEL_ORDER,
    RULES,
    RULES_VERSION,
    RedFlagLevel,
    RedFlagRule,
)
from skills.safety_gate.skill import (
    SCHEMA_VERSION,
    RedFlagMatch,
    SafetyGateInput,
    SafetyGateOutput,
    SafetyGateSkill,
    detect_red_flags,
)

__all__ = [
    "LEVEL_ORDER",
    "RULES",
    "RULES_VERSION",
    "SCHEMA_VERSION",
    "RedFlagLevel",
    "RedFlagMatch",
    "RedFlagRule",
    "SafetyGateInput",
    "SafetyGateOutput",
    "SafetyGateSkill",
    "detect_red_flags",
]
