"""Deterministic prompt assembly for the orchestration Skill (TICKET-007).

The rules are the ones the reference implementation already had
(`FUNCTIONAL_SPEC.md` 5.3–5.4, 5.7), kept as constants so they are visible in
one place and assertable without calling a model:

- system prompt = the four medical-safety constraints;
- history = at most the most recent six turns, current question excluded;
- context = retrieval fragments + graph fragments, or the fixed fallback;
- the graph contributes at most its first five candidates to the prompt, while
  the `done` frame still returns all of them (SPEC.md 3.6 "截断规则显式化").
"""

from collections.abc import Sequence
from dataclasses import dataclass

from skills.graph_inference import DiseaseCandidate
from skills.vector_retrieval import RetrievalReference

SYSTEM_PROMPT_HEADER = (
    "你是AI智能医疗问诊助手，基于提供的知识库和医疗知识图谱为用户提供健康咨询。"
    "\n请注意："
)

# The four constraints of FUNCTIONAL_SPEC.md 5.4, verbatim.
SAFETY_CONSTRAINTS: tuple[str, ...] = (
    "1. 你的回答仅供参考，不能替代专业医生的诊断",
    "2. 如有严重症状，请建议用户及时就医",
    "3. 结合知识库内容和图谱推理结果给出专业、易懂的建议",
    "4. 回答要条理清晰，适当分点说明",
)

SYSTEM_PROMPT = "\n".join((SYSTEM_PROMPT_HEADER, *SAFETY_CONSTRAINTS))

HISTORY_LIMIT = 6
PROMPT_GRAPH_LIMIT = 5
CONTEXT_FALLBACK = "暂无相关知识库内容。"

USER_PROMPT_TEMPLATE = (
    "参考知识：\n{context}\n\n用户问题：{query}\n\n请基于以上参考信息回答用户问题。"
)


@dataclass(frozen=True)
class ChatTurn:
    """One prior message, as read back from storage (role `user` | `assistant`)."""

    role: str
    content: str


def knowledge_fragment(reference: RetrievalReference) -> str:
    # 「[文档N] <整块正文>」：引用项给前端的是前 200 字符，提示词用的是整块正文
    # （FUNCTIONAL_SPEC.md 5.3）。
    return f"[文档{reference.index}] {reference.context}"


def graph_fragment(candidates: Sequence[DiseaseCandidate]) -> str:
    lines = ["知识图谱推理结果："]
    for candidate in candidates:
        parts = [f"覆盖率 {candidate.coverage:.2f}"]
        if candidate.department:
            parts.append(f"科室 {candidate.department}")
        parts.append(f"依据症状 {'、'.join(candidate.matched_symptoms)}")
        lines.append(f"- {candidate.disease}（{'，'.join(parts)}）")
    return "\n".join(lines)


def build_context(
    references: Sequence[RetrievalReference],
    candidates: Sequence[DiseaseCandidate],
) -> str:
    """Join both branches' fragments; both empty falls back to the fixed text."""
    fragments = [knowledge_fragment(reference) for reference in references]
    if candidates:
        fragments.append(graph_fragment(candidates[:PROMPT_GRAPH_LIMIT]))
    if not fragments:
        return CONTEXT_FALLBACK
    return "\n\n".join(fragments)


def build_prompt(
    *, history: Sequence[ChatTurn], message: str, context: str
) -> str:
    """Assemble the single prompt handed to `LlmPort.stream` (B-3)."""
    sections = [SYSTEM_PROMPT]
    recent = list(history)[-HISTORY_LIMIT:]
    if recent:
        lines = ["[历史对话]", *(f"{turn.role}：{turn.content}" for turn in recent)]
        sections.append("\n".join(lines))
    sections.append(
        "[当前问题]\n" + USER_PROMPT_TEMPLATE.format(context=context, query=message)
    )
    return "\n\n".join(sections)
