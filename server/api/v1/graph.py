"""TICKET-016：知识图谱对外接口（`SPEC.md` 5.4「知识图谱」）。

- `GET /graph`：全图，用于可视化（公开）
- `GET /graph/entities/{name}/neighbors`：实体邻域子图，`depth` 真实生效（公开）
- `GET /graph/search`：按名称关键字搜索实体（公开）
- `GET /graph/diseases/{name}`：疾病详情子图（公开）
- `POST /graph/infer`：症状推理，返回按覆盖率排序的候选疾病（任意已认证角色）
- `GET /graph/stats`：按标签的节点计数（admin）

图谱查询全部经 B-3 的 `GraphPort`（真实实现走 `AsyncGraphDatabase`，`SPEC.md`
3.1），本模块不认识驱动。图库不可用时对外统一 503 —— 页面因此能呈现可理解的
错误态，而不是静默空白。症状推理复用 006 的 `graph_inference` Skill，与
`/chat/send` 链路共用同一份词表，对外字段是 `coverage`（不出现旧称）。
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    Principal,
    get_graph_port,
    get_session,
    require_admin,
    require_authenticated,
)
from core.errors import ApiError
from core.response import Envelope, error_responses, success
from graph.neo4j_adapter import MAX_DEPTH
from repositories.trace import TraceRepository
from skills.graph_inference import DiseaseCandidate, GraphInferenceSkill
from skills.ports import GraphPort
from skills.protocol import SkillContext
from skills.trace import InMemoryTraceSink, new_trace_id

router = APIRouter(tags=["graph"])

T = TypeVar("T")


class GraphQueryRequest(BaseModel):
    symptoms: list[str] = Field(min_length=1)


class GraphNode(BaseModel):
    id: str
    name: str
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphView(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphEntityView(BaseModel):
    id: str
    name: str
    label: str


class DiseaseDetailView(BaseModel):
    disease: str
    department: str | None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


#: Exceptions that mean *our projection* is wrong, not that the store is down.
PROJECTION_DEFECTS = (KeyError, TypeError, IndexError, AttributeError)


async def _reach_graph(awaitable: Awaitable[T]) -> T:
    """A graph read, with the unavailable store surfaced as 503 (SPEC.md 5.2).

    The graph is an enhancement branch for the consult chain, but these endpoints
    exist only to read it: there is nothing to degrade to, so an unreachable
    store is an upstream-unavailable failure, not a silent empty page.

    A malformed payload, though, is a defect on our side — mapping it onto 503
    would report an infrastructure outage for a projection bug, so those become
    the documented 500 instead (SPEC.md 5.2「服务内部错误」).
    """
    try:
        return await awaitable
    except ApiError:
        raise
    except PROJECTION_DEFECTS as error:
        raise ApiError(500, f"图谱载荷内部错误：{type(error).__name__}") from error
    except Exception as error:  # noqa: BLE001 - the store is the external edge
        raise ApiError(503, f"图谱服务不可用：{type(error).__name__}") from error


@router.get(
    "/graph",
    response_model=Envelope[GraphView],
    responses=error_responses(500, 503),
)
async def read_full_graph(
    graph: GraphPort = Depends(get_graph_port),
) -> Envelope[GraphView]:
    payload = await _reach_graph(graph.full_graph())
    return success(GraphView(**payload))


@router.get(
    "/graph/entities/{name}/neighbors",
    response_model=Envelope[GraphView],
    responses=error_responses(404, 422, 500, 503),
)
async def read_entity_neighbors(
    name: str,
    depth: int = Query(1, ge=1, le=MAX_DEPTH),
    graph: GraphPort = Depends(get_graph_port),
) -> Envelope[GraphView]:
    payload = await _reach_graph(graph.neighbors(name, depth))
    if payload is None:
        raise ApiError(404, "实体不存在")
    return success(GraphView(**payload))


@router.get(
    "/graph/search",
    response_model=Envelope[list[GraphEntityView]],
    responses=error_responses(422, 500, 503),
)
async def search_entities(
    keyword: str = Query(..., min_length=1),
    graph: GraphPort = Depends(get_graph_port),
) -> Envelope[list[GraphEntityView]]:
    rows = await _reach_graph(graph.search_entities(keyword))
    return success([GraphEntityView(**row) for row in rows])


@router.get(
    "/graph/diseases/{name}",
    response_model=Envelope[DiseaseDetailView],
    responses=error_responses(404, 500, 503),
)
async def read_disease_detail(
    name: str,
    graph: GraphPort = Depends(get_graph_port),
) -> Envelope[DiseaseDetailView]:
    payload = await _reach_graph(graph.disease_detail(name))
    if payload is None:
        raise ApiError(404, "疾病不存在")
    return success(DiseaseDetailView(**payload))


@router.post(
    "/graph/infer",
    response_model=Envelope[list[DiseaseCandidate]],
    responses=error_responses(401, 403, 422, 503),
)
async def infer_diseases(
    payload: GraphQueryRequest,
    principal: Principal = Depends(require_authenticated),
    graph: GraphPort = Depends(get_graph_port),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[DiseaseCandidate]]:
    # The Skill normalizes with the shared vocabulary and degrades on an
    # unreachable store; this endpoint has no answer to fall back to, so a
    # degraded result is an upstream failure here (SPEC.md 5.4「503」).
    sink = InMemoryTraceSink()
    outcome = await GraphInferenceSkill(graph).invoke(
        {"symptoms": payload.symptoms},
        SkillContext(trace_id=new_trace_id(), sink=sink),
    )
    # AC-B-28 / SPEC.md 3.7: every Skill call leaves exactly one span, persisted.
    # Commit before any status is raised so a degraded/422 call is still audited.
    repository = TraceRepository(session)
    for span in sink.spans:
        await repository.record_span(span)
    await session.commit()
    if outcome.status == "invalid_input":
        raise ApiError(422, "参数校验失败：" + (outcome.error or "症状列表非法"))
    output = outcome.output
    if outcome.status != "ok" or output is None or output.degraded:
        raise ApiError(503, "图谱服务不可用")
    return success(list(output.candidates))


@router.get(
    "/graph/stats",
    response_model=Envelope[dict[str, int]],
    responses=error_responses(401, 403, 500, 503),
)
async def graph_stats(
    principal: Principal = Depends(require_admin),
    graph: GraphPort = Depends(get_graph_port),
) -> Envelope[dict[str, int]]:
    counts: Any = await _reach_graph(graph.node_counts())
    return success({str(label): int(count) for label, count in counts.items()})
