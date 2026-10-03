"""Skill 清单（TICKET-011）：五个 Skill 的名称、类别、Schema 版本与词表版本。

版本号不在这里重抄一遍，而是从各 Skill 自身的模块读取，避免「两处并存矛盾」
（`SPEC.md` 3.4 要求 `SKILL.md` 四节与运行时行为一致）。类别沿用 `SKILL.md` 的措辞。
"""

from dataclasses import dataclass

from skills.graph_inference import SCHEMA_VERSION as GRAPH_SCHEMA_VERSION
from skills.orchestration import SCHEMA_VERSION as ORCHESTRATION_SCHEMA_VERSION
from skills.safety_gate import RULES_VERSION as SAFETY_RULES_VERSION
from skills.safety_gate import SCHEMA_VERSION as SAFETY_SCHEMA_VERSION
from skills.symptom_normalization import (
    SCHEMA_VERSION as NORMALIZATION_SCHEMA_VERSION,
)
from skills.symptom_normalization import VOCABULARY_VERSION
from skills.vector_retrieval import SCHEMA_VERSION as RETRIEVAL_SCHEMA_VERSION

#: 与 `SPEC.md` 3.4 / 各 `SKILL.md` 的「类别」一栏逐字一致。
PROCESS_RULES_SKILL = "Process Rules Skill"
CAPABILITY_SKILL = "确定性能力 Skill"
ORCHESTRATION_SKILL = "编排 Skill（Agent 本体）"


@dataclass(frozen=True)
class SkillManifest:
    name: str
    category: str
    schema_version: str
    #: 该 Skill 依赖的词表版本；没有词表的 Skill 为 `None`。
    vocabulary_version: str | None


#: 顺序与 `SPEC.md` 3.4 的 Skill 表一致。
SKILL_MANIFESTS: tuple[SkillManifest, ...] = (
    SkillManifest(
        name="safety-gate",
        category=PROCESS_RULES_SKILL,
        schema_version=SAFETY_SCHEMA_VERSION,
        # 安全门的「词表」就是那份唯一的红旗规则表。
        vocabulary_version=SAFETY_RULES_VERSION,
    ),
    SkillManifest(
        name="symptom-normalization",
        category=CAPABILITY_SKILL,
        schema_version=NORMALIZATION_SCHEMA_VERSION,
        vocabulary_version=VOCABULARY_VERSION,
    ),
    SkillManifest(
        name="vector-retrieval",
        category=CAPABILITY_SKILL,
        schema_version=RETRIEVAL_SCHEMA_VERSION,
        vocabulary_version=None,
    ),
    SkillManifest(
        name="graph-inference",
        category=CAPABILITY_SKILL,
        schema_version=GRAPH_SCHEMA_VERSION,
        vocabulary_version=None,
    ),
    SkillManifest(
        name="orchestration",
        category=ORCHESTRATION_SKILL,
        schema_version=ORCHESTRATION_SCHEMA_VERSION,
        vocabulary_version=None,
    ),
)
