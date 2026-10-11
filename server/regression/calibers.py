"""确定性层的口径对照（TICKET-AC-12 第一步：**只测量，不改判定**）。

起因：AC-11 之后发现确定性层把**行首列表编号**（`### 6.`、`1.`）也当成可匹配 token，
同时放大分母与分子。但在量化过程中暴露了更根本的一件事——

**这层的局限是覆盖率（约 32%），不是准确率。** 在 v3 的 20 条真实回答上：

| 量 | 值 |
|---|---|
| 全部非空断言（`_assertions` 的产出） | **1267** |
| 其中可被字面层判定（含词表项或数字） | **400（31.6%）** |
| 不含任何可判定 token、因此无法评估 | **867（68.4%）** |

而未评估的 867 条里**大量是就医 / 急诊 / 警惕 / 尽快类安全提示**——
`_DETERMINISTIC_TERMS` 只有疾病 / 药品 / 检查节点名与数字，这些词**一个都不在词表里**。
也就是说：**这层评不到的那部分，恰恰是本场景最要紧的内容。**

因此本模块把「覆盖率」当成一等公民测量出来，而不是只报一个比率。
**本模块不修改 `_assertions` / `_deterministic_tokens` 的任何行为**——
它只用四种口径去**读**同一批数据。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from regression.metrics import _assertions, _deterministic_tokens
from regression.replay import _context_of
from regression.schema import Baseline

MARKER_PATTERN = r"(?:^|\n)\s*(?:[#>*\u2022-]+\s*)*(\d{1,3})\s*[.、)）]"
UNIT_PATTERN = r"(分钟|小时|天|日|周|月|年|次|mg|毫克|克|ml|毫升|℃|°C|mmHg|%|厘米|毫米|公斤|kg|倍|度)"

#: 行首列表编号：`### 6.` / `1.` / `- 3、` ——纯格式，不是临床数值。
_LIST_MARKER = re.compile(MARKER_PATTERN)
#: 临床单位：数字**紧跟**这些才算"临床数值"（口径③ 用）。
_UNIT = re.compile(UNIT_PATTERN)

TokenExtractor = Callable[[str], list[str]]


def tokens_current(assertion: str) -> list[str]:
    """口径①：现在的实现（词表项 + 所有数字）。"""
    return _deterministic_tokens(assertion)


def _marker_numbers(assertion: str) -> set[str]:
    return {match.group(1) for match in _LIST_MARKER.finditer(assertion)}


def tokens_without_list_markers(assertion: str) -> list[str]:
    """口径②：在①的基础上排除行首列表编号——**纯格式伪影**。"""
    markers = _marker_numbers(assertion)
    return [
        token
        for token in _deterministic_tokens(assertion)
        if not (token.isdigit() and token in markers)
    ]


def _is_clinical_number(assertion: str, token: str) -> bool:
    for match in re.finditer(re.escape(token), assertion):
        # 窗口放宽到 6 个字符：数字与单位之间常有一个空格（`120 mmHg`），
        # 也可能隔着箭形连接号（`15–20 分钟`）。
        if _UNIT.search(assertion[match.end() : match.end() + 6]):
            return True
    return False


def tokens_clinical_numbers_only(assertion: str) -> list[str]:
    """口径③：② 再加一条——纯数字只有在**紧跟单位**时才算 token。

    单位表是**测量用的首版规则**，不是最终实现：`15–20 分钟`、`24 小时尿蛋白定量`
    这类是**真实且应当被证明**的临床断言，与 `### 6.` 这种编号伪影必须区别对待。
    """
    out: list[str] = []
    for token in tokens_without_list_markers(assertion):
        if token.isdigit() and not _is_clinical_number(assertion, token):
            continue
        out.append(token)
    return out


@dataclass(frozen=True)
class CaliberReport:
    """一个口径下的读数。

    `assertion_count` 是**全部非空断言**——它是口径之间可比的那个分母
    （口径②③ 只改变 `evaluable`，不改变 `assertion_count`）。
    """

    name: str
    description: str
    assertion_count: int
    evaluable: int
    marked_unsupported: int

    @property
    def token_free(self) -> int:
        return self.assertion_count - self.evaluable

    @property
    def evaluable_ratio(self) -> float:
        return self.evaluable / self.assertion_count if self.assertion_count else 0.0

    @property
    def marked_over_evaluable(self) -> float:
        return self.marked_unsupported / self.evaluable if self.evaluable else 0.0

    @property
    def marked_over_all(self) -> float:
        """**可以对外报的单一数字**：分母固定为全部断言，口径之间可直接比较。"""
        return (
            self.marked_unsupported / self.assertion_count
            if self.assertion_count
            else 0.0
        )


def _measure(
    baseline: Baseline, *, name: str, description: str, extract: TokenExtractor
) -> CaliberReport:
    assertion_count = evaluable = marked = 0
    for case in baseline.cases:
        context = _context_of(case)
        for assertion in _assertions(case.answer):
            assertion_count += 1
            tokens = extract(assertion)
            if not tokens:
                continue
            evaluable += 1
            if not all(token in context for token in tokens):
                marked += 1
    return CaliberReport(
        name=name,
        description=description,
        assertion_count=assertion_count,
        evaluable=evaluable,
        marked_unsupported=marked,
    )


def measure_calibers(baseline: Baseline) -> list[CaliberReport]:
    """四个口径一起量。

    ① 现状；② 排除行首编号；③ ②+纯数字收窄到临床语境；
    ④ = ① 的 token 规则、但**分母固定为全部断言**、并把 `token_free` 显式报出来
    （④ 与 ① 的 token 规则相同，区别只在报告方式——这正是「分母不缩小」的含义）。
    """
    return [
        _measure(
            baseline,
            name="① 现状",
            description="词表项 + 所有数字",
            extract=tokens_current,
        ),
        _measure(
            baseline,
            name="② 排除行首列表编号",
            description="去掉 ### 6. / 1. 这类纯格式编号",
            extract=tokens_without_list_markers,
        ),
        _measure(
            baseline,
            name="③ ② + 纯数字收窄到临床",
            description="纯数字只在紧跟单位（分钟/小时/mg…）时才算",
            extract=tokens_clinical_numbers_only,
        ),
        _measure(
            baseline,
            name="④ ① 的 token 规则、分母不缩小",
            description="分列 evaluable / token_free，比率以全部断言为分母（推荐形态）",
            extract=tokens_current,
        ),
    ]


__all__ = [
    "CaliberReport",
    "measure_calibers",
    "tokens_clinical_numbers_only",
    "tokens_current",
    "tokens_without_list_markers",
]
