"""知识图谱灌数（TICKET-013，幂等）。

Run from `server/`:  .venv\\Scripts\\python.exe scripts\\init_graph.py

建 6 条唯一性约束并按 `MERGE` 语义灌入本体与种子数据：重复执行不新增、不删除
（`FUNCTIONAL_SPEC.md` 6.7）。查询走 `AsyncGraphDatabase`（`SPEC.md` 3.1）。
"""

import asyncio
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from collections.abc import Callable  # noqa: E402

from adapters import build_graph_store  # noqa: E402
from core.config import Settings, get_settings  # noqa: E402
from graph.seed import SeedReport, seed_graph  # noqa: E402
from graph.store import GraphStore  # noqa: E402

StoreFactory = Callable[[Settings], GraphStore]


async def _seed(store: GraphStore) -> SeedReport:
    try:
        return await seed_graph(store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            await close()


def main(*, store_factory: StoreFactory | None = None) -> int:
    settings = get_settings()
    factory = store_factory or build_graph_store
    try:
        report = asyncio.run(_seed(factory(settings)))
    except Exception as error:
        print(f"图谱灌数失败：{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(
        "图谱灌数完成："
        f"节点 {report.stats.total_nodes} 个，关系 {report.stats.total_relationships} 条"
        f"（本次合并 {report.nodes_merged} 节点 / {report.relationships_merged} 关系）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
