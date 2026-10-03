"""SSE frame payloads, projected to the contract's shapes (C-1, SPEC.md 5.5).

The projection matters: the Skill outputs carry more than the wire contract
allows. `RetrievalReference.distance` is recorded in the trace but must not
appear in the `done` frame, whose `reference` schema is
`additionalProperties: false` with `index` / `file_name` / `snippet` only
(TICKET-005 挂账第 1 条).
"""

from collections.abc import Sequence

from skills.graph_inference import DiseaseCandidate
from skills.vector_retrieval import RetrievalReference

from skills.orchestration.prompt import PROMPT_GRAPH_LIMIT


def reference_payload(reference: RetrievalReference) -> dict:
    """The contract `reference`: three fields, no `distance`."""
    return {
        "index": reference.index,
        "file_name": reference.file_name,
        "snippet": reference.snippet,
    }


def candidate_payload(candidate: DiseaseCandidate) -> dict:
    """The contract `disease_candidate`, already the Skill's output shape."""
    return candidate.model_dump(mode="json")


def coverage_note(*, graph_skipped: bool, candidate_count: int) -> str | None:
    """A deterministic note about what the coverage list does and does not cover."""
    if graph_skipped:
        return "未识别到可用症状，本次未进行图谱推理。"
    if candidate_count > PROMPT_GRAPH_LIMIT:
        return (
            f"图谱候选共 {candidate_count} 条，提示词仅采用前 {PROMPT_GRAPH_LIMIT} 条。"
        )
    return None


def done_payload(
    *,
    references: Sequence[RetrievalReference],
    candidates: Sequence[DiseaseCandidate],
    graph_skipped: bool,
    degraded: Sequence[str],
    cost_time: int,
    trace_id: str,
) -> dict:
    return {
        "type": "done",
        "references": [reference_payload(reference) for reference in references],
        "graph": [candidate_payload(candidate) for candidate in candidates],
        "coverage_note": coverage_note(
            graph_skipped=graph_skipped, candidate_count=len(candidates)
        ),
        "degraded": list(degraded),
        "cost_time": cost_time,
        "trace_id": trace_id,
    }
