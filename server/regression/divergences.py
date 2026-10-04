"""有意偏离登记册的只读视图（ticket 023 开工前置；`.scratch/medisentinel/intentional-divergences.md`）。

023 的对比逻辑**显式豁免 `ai-chain` 子集（A-1…A-7）**：这些是相对 legacy 的有意
变更，不能进 023 的漂移率 / 幻觉率分母；`http-contract` 子集（H-1…H-12）在 023 里
**只记录不消费**，留给 024。本模块把登记册读成结构化条目，登记册本身仍是唯一事实源。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

EXEMPT_SCOPE = "ai-chain"
RECORDED_ONLY_SCOPE = "http-contract"

#: 仓库根 = server/regression/ → server/ → 仓库根。
REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / ".scratch/medisentinel/intentional-divergences.md"
)

_ROW = re.compile(r"^(A|H)-\d+$")


@dataclass(frozen=True)
class Divergence:
    id: str
    scope: str
    description: str


def parse_registry(text: str) -> list[Divergence]:
    """Parse the ID / description / scope columns out of the registry tables."""
    divergences: list[Divergence] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not _ROW.match(cells[0]):
            continue
        divergences.append(
            Divergence(id=cells[0], scope=cells[-1], description=cells[2])
        )
    return divergences


def load_registry(path: Path | None = None) -> list[Divergence]:
    registry = Path(path) if path is not None else REGISTRY_PATH
    return parse_registry(registry.read_text(encoding="utf-8"))


def ai_chain_ids(divergences: list[Divergence]) -> list[str]:
    """The `ai-chain` ids 023 exempts from drift / hallucination denominators."""
    return [item.id for item in divergences if item.scope == EXEMPT_SCOPE]


def http_contract_ids(divergences: list[Divergence]) -> list[str]:
    """The `http-contract` ids 023 records but never consumes (024's input)."""
    return [item.id for item in divergences if item.scope == RECORDED_ONLY_SCOPE]
