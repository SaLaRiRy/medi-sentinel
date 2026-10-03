"""vector-retrieval: 编排第 3a 顺位的确定性知识检索（TICKET-005）。

契约见同目录 `SKILL.md`。本 Skill 只依赖 B-3 的 `RetrievalPort`：不直接访问关系库、
图库或向量索引，也不声明 `LlmPort`（嵌入模型调用不算大模型调用，SPEC.md 3.4）。
"""

from pydantic import BaseModel, Field

from skills.ports import RetrievalPort
from skills.protocol import Skill
from skills.vector_retrieval.retrieval import (
    RETRIEVAL_TOP_K,
    SNIPPET_LENGTH,
    RetrievalReference,
    to_references,
)

SCHEMA_VERSION = "vector-retrieval-schema-v1"


class VectorRetrievalInput(BaseModel):
    query: str = Field(min_length=1, description="用于检索的问句")


class VectorRetrievalOutput(BaseModel):
    # 截断参数排在引用项之前：受限摘要被截断时仍保留「按什么规则截断」这一审计信息
    # （SKILL.md 第 2 节「trace 与审计」）。
    top_k: int
    snippet_length: int
    degraded: bool
    degraded_reason: str | None
    references: list[RetrievalReference]


class VectorRetrievalSkill(Skill):
    name = "vector-retrieval"
    input_schema = VectorRetrievalInput
    output_schema = VectorRetrievalOutput

    def __init__(self, retrieval: RetrievalPort) -> None:
        self._retrieval = retrieval

    async def run(self, data: VectorRetrievalInput) -> VectorRetrievalOutput:
        try:
            hits = await self._retrieval.search(data.query, top_k=RETRIEVAL_TOP_K)
            references = to_references(hits)
        except Exception as error:
            # 索引不可用或端口返回结构非法：降级不阻断问答（SPEC.md 3.6）。
            return self._degraded(f"{type(error).__name__}: {error}")
        return VectorRetrievalOutput(
            top_k=RETRIEVAL_TOP_K,
            snippet_length=SNIPPET_LENGTH,
            degraded=False,
            degraded_reason=None,
            references=references,
        )

    def _degraded(self, reason: str) -> VectorRetrievalOutput:
        return VectorRetrievalOutput(
            top_k=RETRIEVAL_TOP_K,
            snippet_length=SNIPPET_LENGTH,
            degraded=True,
            degraded_reason=reason,
            references=[],
        )
