"""vector-retrieval 的检索后处理与参数常量（TICKET-005）。

本模块只做纯 CPU 的确定性处理：把 `RetrievalPort` 返回的原始命中（`content` /
`metadata` / `distance`）映射为对外的引用项。它不访问任何外部资源，因此可在不启动
关系库、图库、向量索引的前提下被单独测试（SPEC.md 3.6 / 4.1 B-2、B-3）。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

RETRIEVAL_TOP_K = 5
SNIPPET_LENGTH = 200


class RetrievalReference(BaseModel):
    """一条引用来源：序号、文件名、正文前若干字符、距离，以及提示词用的整块正文。

    `snippet` 与 `context` 来自同一条命中：前者是 wire 契约 `reference` 的正文
    （前 `SNIPPET_LENGTH` 字符），后者是编排拼上下文用的整块正文
    （`FUNCTIONAL_SPEC.md` 5.3「[文档N] <整块正文>」）。`distance` 与 `context`
    都只写入 Skill 输出与 trace，不进入契约 —— 契约 `reference` 是
    `additionalProperties: false` 且只含 `index` / `file_name` / `snippet`。
    """

    index: int
    file_name: str
    snippet: str
    distance: float
    context: str


def snippet_of(content: str, limit: int = SNIPPET_LENGTH) -> str:
    """引用项正文：取分块正文的前 `limit` 个字符（默认 200），不追加省略号。"""
    return content[:limit]


def to_references(hits: Sequence[Mapping[str, Any]]) -> list[RetrievalReference]:
    """把检索命中映射为引用项：序号从 1 起、文件名、正文前 200 字符、距离。

    这里**显式**截断到前 `RETRIEVAL_TOP_K` 条（SPEC.md 3.6「截断规则显式化」）：
    即便端口返回更多，也只保留最前面的若干条，序号连续从 1 重编。无最低命中阈值 ——
    距离再大的命中也照常保留（SPEC.md 附：Skill 清单）。
    """
    return [
        RetrievalReference(
            index=position,
            file_name=hit["metadata"]["file_name"],
            snippet=snippet_of(hit["content"]),
            distance=hit["distance"],
            context=hit["content"],
        )
        for position, hit in enumerate(hits[:RETRIEVAL_TOP_K], start=1)
    ]
