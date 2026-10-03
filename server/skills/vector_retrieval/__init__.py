"""vector-retrieval：编排第 3a 顺位的确定性知识检索 Skill（契约见 `SKILL.md`）。"""

from skills.vector_retrieval.retrieval import (
    RETRIEVAL_TOP_K,
    SNIPPET_LENGTH,
    RetrievalReference,
    snippet_of,
    to_references,
)
from skills.vector_retrieval.skill import (
    SCHEMA_VERSION,
    VectorRetrievalInput,
    VectorRetrievalOutput,
    VectorRetrievalSkill,
)

__all__ = [
    "RETRIEVAL_TOP_K",
    "SCHEMA_VERSION",
    "SNIPPET_LENGTH",
    "RetrievalReference",
    "VectorRetrievalInput",
    "VectorRetrievalOutput",
    "VectorRetrievalSkill",
    "snippet_of",
    "to_references",
]
