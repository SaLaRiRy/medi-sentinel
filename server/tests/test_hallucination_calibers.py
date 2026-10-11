"""TICKET-AC-12 第一步：四口径读数（**只测量**）。

数据取自已提交的 v3 活库基线，因此这是**真数据回归**：口径定义若被改动、
或 `_assertions` / `_deterministic_tokens` 被顺手动过，这些数字会立刻变。
"""

import json

import pytest

from regression.calibers import (
    measure_calibers,
    tokens_clinical_numbers_only,
    tokens_current,
    tokens_without_list_markers,
)
from regression.schema import default_store
from scripts import regression as regression_script


@pytest.fixture(scope="module")
def baseline():
    return default_store().load_baseline("v3")


# --- 三个 token 抽取口径 -------------------------------------------------------


def test_the_list_marker_number_is_not_a_token_under_caliber_two():
    line = "### 6. 既往有高血压，近期血压明显升高或难以控制。"

    assert "6" in tokens_current(line)
    assert "6" not in tokens_without_list_markers(line)
    # 临床内容本身仍在（高血压来自词表）
    assert "高血压" in tokens_without_list_markers(line)


def test_a_clinical_number_survives_caliber_three_but_a_bare_one_does_not():
    assert "15" in tokens_current("热敷 15–20 分钟")
    assert tokens_clinical_numbers_only("热敷 15–20 分钟")  # 至少保留紧邻单位的那一个
    assert tokens_clinical_numbers_only("### 6. 既往有高血压") == ["高血压"]


def test_a_marker_that_is_also_clinical_is_kept_once():
    line = "1. 血压 120 mmHg"

    tokens = tokens_clinical_numbers_only(line)

    assert "1" not in tokens  # 行首编号
    assert "120" in tokens  # 紧跟单位，是真临床数值


# --- 四口径读数（真数据）------------------------------------------------------


def test_the_four_calibers_report_the_measured_numbers(baseline):
    reports = measure_calibers(baseline)

    assert [report.name for report in reports] == [
        "① 现状",
        "② 排除行首列表编号",
        "③ ② + 纯数字收窄到临床",
        "④ ① 的 token 规则、分母不缩小",
    ]
    by_name = {report.name: report for report in reports}
    current = by_name["① 现状"]
    assert current.assertion_count == 1267
    assert current.evaluable == 400
    assert current.token_free == 867
    assert current.evaluable_ratio == pytest.approx(0.3157, abs=0.001)
    assert current.marked_unsupported == 33
    assert current.marked_over_all == pytest.approx(0.0260, abs=0.0002)
    # 口径②③ 只改 evaluable，不改分母
    assert by_name["② 排除行首列表编号"].evaluable == 211
    # ③ 的可判定条数比 .tmp 首版探针（189）多 7 条：单位窗口从 4 字符放宽到 6 字符后，
    # `120 mmHg`、`15–20 分钟` 这类才被正确认成临床数值（首版把它们当成了非临床数字）。
    assert by_name["③ ② + 纯数字收窄到临床"].evaluable == 196
    assert by_name["③ ② + 纯数字收窄到临床"].marked_unsupported == 13
    for report in reports:
        assert report.assertion_count == 1267


def test_the_recommended_single_number_uses_the_full_denominator(baseline):
    """对外只报一个数字时用 marked_over_all（分母固定），口径之间才可比。"""
    reports = {report.name: report for report in measure_calibers(baseline)}
    current = reports["① 现状"]

    assert current.marked_over_all == pytest.approx(33 / 1267, abs=1e-6)
    assert current.marked_over_evaluable == pytest.approx(33 / 400, abs=1e-6)


def test_measuring_calibers_is_reproducible(baseline):
    first = [report.__dict__ for report in measure_calibers(baseline)]
    second = [report.__dict__ for report in measure_calibers(baseline)]

    assert first == second


# --- CLI ---------------------------------------------------------------------


def test_the_subcommand_prints_the_four_calibers(capsys):
    code = regression_script.main(
        ["hallucination-calibers", "--baseline-version", "v3"]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 4
    assert payload[0]["assertion_count"] == 1267
    assert payload[0]["token_free"] == 867
