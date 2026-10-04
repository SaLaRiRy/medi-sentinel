"""case / baseline 的 pydantic 模型与磁盘装载（ticket 023 §1、§3）。

用例集与基线都是**版本控制的数据**（SPEC.md 3.8「随基线一同纳入版本控制」），
不是 pytest 夹具：`cases/<version>.json` 与 `baselines/<version>.json` 直接入库，
`RegressionStore` 只负责按版本读取它们。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

CaseGroup = Literal["red_flag", "llm", "degraded", "boundary"]
BranchMode = Literal["hits", "unavailable"]


class CaseInput(BaseModel):
    """一次问诊的输入，录制与回放共用同一份（`session_id` 固定）。"""

    session_id: int
    message: str
    explicit_symptoms: list[str] = Field(default_factory=list)


class RegressionCase(BaseModel):
    """用例集里的一条：输入 + 确定性端口接线 + 脚本化答案。"""

    id: str
    group: CaseGroup
    message: str
    session_id: int
    explicit_symptoms: list[str] = Field(default_factory=list)
    graph: BranchMode = "hits"
    retrieval: BranchMode = "hits"
    answer: list[str] = Field(default_factory=list)
    #: 有意偏离登记册里、本次对比须豁免的 id（默认空：v1 已把新行为录进基线）。
    exemptions: list[str] = Field(default_factory=list)

    def input(self) -> CaseInput:
        return CaseInput(
            session_id=self.session_id,
            message=self.message,
            explicit_symptoms=list(self.explicit_symptoms),
        )


class CaseSet(BaseModel):
    version: str
    cases: list[RegressionCase]


class SkippedSkillView(BaseModel):
    skill: str
    reason: str


class RouteView(BaseModel):
    skills_run: list[str]
    skills_skipped: list[SkippedSkillView]


class BaselineCase(BaseModel):
    """录制下来的一条用例：输入、路由、端口响应、SSE 帧、各 Skill 输出、耗时。"""

    id: str
    group: str
    red_flag: bool
    input: CaseInput
    duration_ms: int
    route: RouteView
    frames: list[dict[str, Any]]
    skills: dict[str, dict[str, Any]]
    ports: dict[str, list[Any]]
    llm_chunks: list[list[str]]
    spans: list[dict[str, Any]]
    answer: str
    exemptions: list[str] = Field(default_factory=list)


class Baseline(BaseModel):
    version: str
    case_set_version: str
    created_at: str
    cases: list[BaselineCase]
    #: 023 显式豁免的 ai-chain 子集（A-1…A-7），与只记录不消费的 http-contract 子集。
    exempt_divergences: list[str] = Field(default_factory=list)
    recorded_divergences: list[str] = Field(default_factory=list)


class CaseSetMissing(FileNotFoundError):
    def __init__(self, version: str) -> None:
        super().__init__(f"case set version not found: {version}")
        self.version = version


class BaselineMissing(FileNotFoundError):
    def __init__(self, version: str) -> None:
        super().__init__(f"baseline version not found: {version}")
        self.version = version


class RegressionStore:
    """按版本读取/写入 `cases/` 与 `baselines/`（目录可覆盖，便于测试）。"""

    def __init__(self, *, cases_dir: Path, baselines_dir: Path) -> None:
        self.cases_dir = Path(cases_dir)
        self.baselines_dir = Path(baselines_dir)

    def load_case_set(self, version: str) -> CaseSet:
        path = self.cases_dir / f"{version}.json"
        if not path.is_file():
            raise CaseSetMissing(version)
        return CaseSet.model_validate_json(path.read_text(encoding="utf-8"))

    def load_baseline(self, version: str) -> Baseline:
        path = self.baselines_dir / f"{version}.json"
        if not path.is_file():
            raise BaselineMissing(version)
        return Baseline.model_validate_json(path.read_text(encoding="utf-8"))

    def list_baselines(self) -> list[Baseline]:
        if not self.baselines_dir.is_dir():
            return []
        baselines: list[Baseline] = []
        for path in sorted(self.baselines_dir.glob("*.json")):
            try:
                baselines.append(Baseline.model_validate_json(path.read_text("utf-8")))
            except (ValueError, OSError):
                continue
        return baselines

    def write_baseline(self, baseline: Baseline, *, version: str | None = None) -> Path:
        path = self.baselines_dir / f"{version or baseline.version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(baseline.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path


def default_store() -> RegressionStore:
    """`server/regression/cases` 与 `server/regression/baselines`."""
    root = Path(__file__).resolve().parent
    return RegressionStore(cases_dir=root / "cases", baselines_dir=root / "baselines")
