"""TICKET-AC-11：判定上下文并入图谱片段的**数据值**（且不含模板框架词）。

全部离线：用 `SimpleNamespace` 假基线做单元断言，再用**已提交的 v3 基线**
做一次真数据回归。不联网、不重录。
"""

from types import SimpleNamespace

import pytest

from regression.metrics import _evaluate, hallucination
from regression.replay import (
    _GRAPH_TEMPLATE_WORDS,
    _context_of,
    _graph_values,
    replay_case,
)
from regression.schema import default_store


def _case(*, graph_records=(), retrieval_hits=(), candidates=None, answer=""):
    """一个鸭子类型的基线用例（`_context_of` 只用到 `.ports` 与 `.skills`）。"""
    skills: dict = {}
    if candidates is not None:
        skills["graph-inference"] = {"candidates": candidates}
    return SimpleNamespace(
        ports={"graph": [list(graph_records)], "retrieval": [list(retrieval_hits)]},
        skills=skills,
        answer=answer,
    )


CANDIDATE = {
    "disease": "慢性肾炎",
    "match_count": 1,
    "coverage": 0.5,
    "department": "肾内科",
    "matched_symptoms": ["高血压"],
}
TARGET_ASSERTION = "知识图谱初步提示：慢性肾炎（覆盖率约0.50，科室：肾内科，依据症状：高血压）。"


def _candidates(count: int, prefix: str = "候选") -> list[dict]:
    return [
        {
            "disease": f"{prefix}{index}",
            "match_count": 1,
            "coverage": 0.1 * index,
            "department": "内科",
            "matched_symptoms": ["头痛"],
        }
        for index in range(1, count + 1)
    ]


# --- 数据值并入 ---------------------------------------------------------------


def test_the_graph_candidate_values_enter_the_context():
    context = _context_of(_case(candidates=[CANDIDATE]))

    assert "慢性肾炎" in context
    assert "肾内科" in context
    assert "高血压" in context
    assert "0.50" in context


def test_the_context_never_contains_template_framework_words():
    """用户点名要钉住的护栏：模板词进上下文 = 把幻觉率人为调松。"""
    context = _context_of(_case(candidates=[CANDIDATE]))

    for word in _GRAPH_TEMPLATE_WORDS:
        assert word not in context, f"判定上下文出现了模板词：{word}"


def test_the_port_records_are_used_when_the_skill_detail_is_missing():
    """没有 graph-inference 结构化输出时退回端口原始返回。"""
    record = {"disease": "感冒", "department": "呼吸内科", "matched_symptoms": ["发热"]}

    values = _graph_values(_case(graph_records=[record]))

    assert values == ["感冒", "呼吸内科", "发热"]


def test_the_skill_detail_wins_because_it_carries_the_coverage():
    values = _graph_values(
        _case(graph_records=[{"disease": "慢性肾炎"}], candidates=[CANDIDATE])
    )

    assert "0.50" in values


def test_only_the_prompt_injected_candidates_are_used():
    """模型只看到前 `PROMPT_GRAPH_LIMIT` 条——判定上下文不许超出这个集合。"""
    from skills.orchestration import PROMPT_GRAPH_LIMIT

    case = _case(candidates=_candidates(PROMPT_GRAPH_LIMIT + 5))

    values = _graph_values(case)
    context = _context_of(case)

    assert f"候选{PROMPT_GRAPH_LIMIT}" in values
    assert f"候选{PROMPT_GRAPH_LIMIT + 1}" not in context
    assert f"候选{PROMPT_GRAPH_LIMIT + 5}" not in context


def test_the_port_fallback_is_truncated_too():
    from skills.orchestration import PROMPT_GRAPH_LIMIT

    records = [
        {"disease": f"疾病{index}", "department": "内科", "matched_symptoms": []}
        for index in range(1, PROMPT_GRAPH_LIMIT + 4)
    ]

    values = _graph_values(_case(graph_records=records))

    assert values.count(f"疾病{PROMPT_GRAPH_LIMIT}") == 1
    assert f"疾病{PROMPT_GRAPH_LIMIT + 1}" not in values


def test_an_empty_graph_leaves_the_context_unchanged():
    hits = [{"content": "检索到的正文", "metadata": {"file_name": "a.md"}, "distance": 0.1}]

    assert _context_of(_case(retrieval_hits=hits)) == "检索到的正文"


# --- 判定结果 -----------------------------------------------------------------


async def test_the_target_assertion_is_now_supported():
    """AC-10 记下的靶子：断言里的疾病名与覆盖率都来自图谱，此前被判无据。"""
    context = _context_of(_case(candidates=[CANDIDATE]))

    report = await hallucination(TARGET_ASSERTION, context)

    assert report.total == 1
    assert report.deterministic_ratio == 0.0


async def test_a_real_hallucination_is_still_caught():
    """既不在检索、也不在图谱里的药名，仍然要判无据——修复不能把真幻觉洗掉。"""
    context = _context_of(_case(candidates=[CANDIDATE]))

    report = await hallucination("建议服用二甲双胍控制血糖。", context)

    assert report.deterministic_ratio == 1.0


async def test_the_denominator_does_not_depend_on_the_context():
    """用户点名的红线：换上下文只能改分子，**total 必须不变**。"""
    answer = "慢性肾炎需要复查尿常规，二甲双胍与氨氯地平都不该自行服用。"
    without_graph = _context_of(_case())
    with_graph = _context_of(_case(candidates=[CANDIDATE]))

    first = await _evaluate(answer, without_graph, None)
    second = await _evaluate(answer, with_graph, None)

    assert first.total == second.total


# --- 真数据回归 ---------------------------------------------------------------


def test_no_v3_case_puts_a_template_word_into_the_context():
    baseline = default_store().load_baseline("v3")

    for case in baseline.cases:
        context = _context_of(case)
        for word in _GRAPH_TEMPLATE_WORDS:
            assert word not in context, f"{case.id} 的上下文出现模板词：{word}"


async def test_every_v3_case_donates_its_graph_values_to_the_outcome():
    baseline = default_store().load_baseline("v3")
    case = next(item for item in baseline.cases if item.id == "llm-explicit-symptoms")
    run = await replay_case(case)

    assert "慢性肾炎" in run.outcome.context
    assert "0.50" in run.outcome.context


async def test_the_drift_metric_is_still_a_tautology():
    """AC-11 不改 drift 的恒真式性质——它仍然恒为 0（另一条独立缺陷）。"""
    from regression.replay import run_regression

    baseline = default_store().load_baseline("v3")
    report = await run_regression(baseline)

    assert report.diagnosis_drift_rate == 0.0
