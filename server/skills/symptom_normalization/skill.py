"""symptom-normalization: 编排第二顺位的确定性症状归一化（TICKET-004）。

契约见同目录 `SKILL.md`。本 Skill 零外部依赖、零端口：不访问数据库、图库、向量索引
与大模型，因此同一输入的结果可复现（SPEC.md 3.4 / 3.6）。
"""

from pydantic import BaseModel, Field

from skills.protocol import Skill
from skills.symptom_normalization.vocabulary import (
    VOCABULARY_VERSION,
    extract_symptoms,
)

SCHEMA_VERSION = "symptom-normalization-schema-v1"


class SymptomNormalizationInput(BaseModel):
    message: str = Field(min_length=1, description="患者本轮问诊的原始描述文本")


class SymptomNormalizationOutput(BaseModel):
    vocabulary_version: str
    symptoms: list[str]


class SymptomNormalizationSkill(Skill):
    name = "symptom-normalization"
    input_schema = SymptomNormalizationInput
    output_schema = SymptomNormalizationOutput

    async def run(self, data: SymptomNormalizationInput) -> SymptomNormalizationOutput:
        return SymptomNormalizationOutput(
            vocabulary_version=VOCABULARY_VERSION,
            symptoms=extract_symptoms(data.message),
        )
