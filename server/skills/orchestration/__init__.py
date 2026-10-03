"""orchestration：唯一的编排 Skill，也是唯一调用大模型的 Skill（TICKET-007）。

契约见本目录 `SKILL.md`。对外只暴露 B-1 入口（`Orchestrator.run`）与它需要的
请求/端口类型；下面四个 Skill 只通过 B-2 协议被调用，外部依赖只通过 B-3 端口接入。
"""

from skills.orchestration.frames import (
    candidate_payload,
    coverage_note,
    done_payload,
    reference_payload,
)
from skills.orchestration.prompt import (
    CONTEXT_FALLBACK,
    HISTORY_LIMIT,
    PROMPT_GRAPH_LIMIT,
    SAFETY_CONSTRAINTS,
    SYSTEM_PROMPT,
    ChatTurn,
    build_context,
    build_prompt,
    graph_fragment,
    knowledge_fragment,
)
from skills.orchestration.skill import (
    GRAPH_INFERENCE,
    GRAPH_SKIPPED_REASON,
    LLM_SPAN,
    ORCHESTRATION,
    SAFETY_GATE,
    SCHEMA_VERSION,
    SYMPTOM_NORMALIZATION,
    VECTOR_RETRIEVAL,
    ChatRequest,
    OrchestrationPorts,
    Orchestrator,
)

__all__ = [
    "CONTEXT_FALLBACK",
    "GRAPH_INFERENCE",
    "GRAPH_SKIPPED_REASON",
    "HISTORY_LIMIT",
    "LLM_SPAN",
    "ORCHESTRATION",
    "PROMPT_GRAPH_LIMIT",
    "SAFETY_CONSTRAINTS",
    "SAFETY_GATE",
    "SCHEMA_VERSION",
    "SYMPTOM_NORMALIZATION",
    "SYSTEM_PROMPT",
    "VECTOR_RETRIEVAL",
    "ChatRequest",
    "ChatTurn",
    "OrchestrationPorts",
    "Orchestrator",
    "build_context",
    "build_prompt",
    "candidate_payload",
    "coverage_note",
    "done_payload",
    "graph_fragment",
    "knowledge_fragment",
    "reference_payload",
]
