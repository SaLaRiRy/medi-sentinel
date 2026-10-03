"""graph-inference: 编排第 3b 顺位的确定性图谱推理（TICKET-006）。

契约见同目录 `SKILL.md`。本 Skill 只依赖 B-3 的 `GraphPort`：不直接访问关系库、
图库或向量索引，也不声明 `LlmPort`。词表复用 symptom-normalization 的
`normalize_terms`，因此 `/chat/send` 链路与 `/graph/infer` 链路产出同一标准症状集合
（SPEC.md 3.6 / 6.1 AC-B-18）。
"""

from typing import Any

from pydantic import BaseModel, Field

from skills.graph_inference.inference import (
    COVERAGE_DECIMALS,
    MAX_CANDIDATES,
    DiseaseCandidate,
    to_candidates,
)
from skills.ports import GraphPort
from skills.protocol import Skill
from skills.symptom_normalization import normalize_terms

SCHEMA_VERSION = "graph-inference-schema-v1"


class GraphInferenceInput(BaseModel):
    symptoms: list[str] = Field(
        min_length=1, description="症状推理链路的显式症状列表（可含口语别名）"
    )


class GraphInferenceOutput(BaseModel):
    # 截断与取整参数排在候选之前：受限摘要被截断时仍保留「按什么规则排序、截断、
    # 保留几位小数」这一审计信息（SKILL.md 第 2 节「trace 与审计」）。
    limit: int
    coverage_decimals: int
    degraded: bool
    degraded_reason: str | None
    symptoms: list[str]
    candidates: list[DiseaseCandidate]


class GraphInferenceSkill(Skill):
    name = "graph-inference"
    input_schema = GraphInferenceInput
    output_schema = GraphInferenceOutput

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    def trace_detail(
        self, request: GraphInferenceInput, response: GraphInferenceOutput
    ) -> dict[str, Any]:
        """排序/截断参数、输入症状与全部候选疾病结构化落库（回放可复现）。"""
        return {
            "limit": response.limit,
            "coverage_decimals": response.coverage_decimals,
            "degraded": response.degraded,
            "degraded_reason": response.degraded_reason,
            "symptoms": list(response.symptoms),
            "candidates": [
                candidate.model_dump(mode="json")
                for candidate in response.candidates
            ],
        }

    async def run(self, data: GraphInferenceInput) -> GraphInferenceOutput:
        symptoms = normalize_terms(data.symptoms)
        if not symptoms:
            # 归一化后为空：直接返回空列表，不查询图数据库（FUNCTIONAL_SPEC 5.3）。
            return self._result(symptoms, candidates=[])
        try:
            records = await self._graph.infer_diseases(symptoms)
            candidates = to_candidates(records, symptoms)
        except Exception as error:
            # 图库不可用或端口返回结构非法：降级不阻断问答（SPEC.md 3.6）。
            return self._result(
                symptoms, candidates=[], degraded=f"{type(error).__name__}: {error}"
            )
        return self._result(symptoms, candidates=candidates)

    def _result(
        self,
        symptoms: list[str],
        *,
        candidates: list[DiseaseCandidate],
        degraded: str | None = None,
    ) -> GraphInferenceOutput:
        return GraphInferenceOutput(
            limit=MAX_CANDIDATES,
            coverage_decimals=COVERAGE_DECIMALS,
            degraded=degraded is not None,
            degraded_reason=degraded,
            symptoms=symptoms,
            candidates=candidates,
        )
