"""graph-inference 的排序、覆盖率计算与参数常量（TICKET-006）。

本模块只做纯 CPU 的确定性处理：把 `GraphPort` 返回的原始疾病记录（`disease` /
`matched_symptoms` / `department`）映射为对外的候选疾病。它不访问任何外部资源，
因此可在不启动关系库、图库、向量索引的前提下被单独测试（SPEC.md 4.1 B-2、B-3）。
"""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel

# 截断规则：图谱推理最多回传前 10 条候选（沿用旧实现 `[:10]`）。
# 提示词只取前 5 条由编排负责，本 Skill 不静默截断、不在端口里隐藏该规则。
MAX_CANDIDATES = 10
# 覆盖率保留 2 位小数（SPEC.md 3.6「对外字段更名」）。
COVERAGE_DECIMALS = 2
# 旧的「科室缺失」取值是字符串 "-"，新契约要求 `null`（SPEC.md 3.6）。
DEPARTMENT_MISSING = "-"


class DiseaseCandidate(BaseModel):
    """一条候选疾病：疾病名、命中症状数、覆盖率、科室与命中到的症状。

    字段名与 `contracts/sse-events.json` 的 `disease_candidate` 完全一致：
    对外字段是 `coverage`（不是旧称）；`department` 缺失时为 `null`。
    """

    disease: str
    match_count: int
    coverage: float
    department: str | None
    matched_symptoms: list[str]


def coverage_of(match_count: int, total_symptoms: int) -> float:
    """覆盖率 = 命中数 ÷ 输入症状数，**四舍五入**保留 2 位小数。

    输入症状数为 0 时返回 0.0（本 Skill 在归一化后为空时不会走到此处）。

    用 `Decimal` 的 `ROUND_HALF_UP` 而不是内置 `round()`：内置 `round()` 是
    银行家舍入（四舍六入五成双），`1/8` 会得到 0.12，与「四舍五入」不一致
    （FUNCTIONAL_SPEC.md 5.3、SPEC.md 3.6）。
    """
    if total_symptoms <= 0:
        return 0.0
    quantum = Decimal(1).scaleb(-COVERAGE_DECIMALS)
    ratio = Decimal(match_count) / Decimal(total_symptoms)
    return float(ratio.quantize(quantum, rounding=ROUND_HALF_UP))


def normalize_department(raw: object) -> str | None:
    """科室缺失的确定性取值：`None`、空串与旧值 `"-"` 一律返回 `null`。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == DEPARTMENT_MISSING:
        return None
    return text


def _matched_symptoms_of(record: Mapping[str, Any]) -> Sequence[str]:
    matched = record["matched_symptoms"]
    if isinstance(matched, str) or not isinstance(matched, Sequence):
        raise TypeError("matched_symptoms 必须是字符串序列")
    if not all(isinstance(item, str) for item in matched):
        raise TypeError("matched_symptoms 只能包含字符串")
    return matched


def to_candidates(
    records: Sequence[Mapping[str, Any]], symptoms: Sequence[str]
) -> list[DiseaseCandidate]:
    """把图端口返回的疾病记录映射为候选列表。

    确定性规则（SKILL.md 1.4）：

    - 命中症状只保留**本次归一化症状集合内**的项，并按输入症状顺序排列，
      因此 `match_count ≤ 输入症状数`、`coverage ≤ 1`，且结果不依赖端口的返回顺序；
    - 排序键为「命中数降序，疾病名升序」，并列顺序不依赖查询结果，回放可复现；
    - **无最低命中阈值**：命中 1 个症状的疾病照常返回；
    - 显式截断到前 `MAX_CANDIDATES` 条，截断规则随输出字段 `limit` 写入 trace。
    """
    symptom_set = set(symptoms)
    candidates: list[DiseaseCandidate] = []
    for record in records:
        disease = record["disease"]
        if not isinstance(disease, str) or not disease:
            raise ValueError("disease 必须是非空字符串")
        explained = {
            item for item in _matched_symptoms_of(record) if item in symptom_set
        }
        matched = [symptom for symptom in symptoms if symptom in explained]
        if not matched:
            continue
        candidates.append(
            DiseaseCandidate(
                disease=disease,
                match_count=len(matched),
                coverage=coverage_of(len(matched), len(symptoms)),
                department=normalize_department(record.get("department")),
                matched_symptoms=matched,
            )
        )
    candidates.sort(key=lambda candidate: (-candidate.match_count, candidate.disease))
    return candidates[:MAX_CANDIDATES]
