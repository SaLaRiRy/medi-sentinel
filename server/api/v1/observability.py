"""TICKET-011：可观测性对外接口（trace 回放出口 + Skill 清单）。

- `GET /traces/{trace_id}`：一次问诊的全部 span 与路由决策（B-4/B-5 读回）
- `GET /traces`：按 trace_id / Skill 名 / 时间范围 / 是否降级分页检索
- `GET /skills`：五个 Skill 的名称、类别、Schema 版本与词表版本

TICKET-014 解除了 `contracts/` 的冻结边界，这三个端点不再对 OpenAPI 隐藏，而是
随 `scripts/export_contract.py` 正常进入 `contracts/openapi.json`（C-1 seam）。

权限（`SPEC.md` 5.4）：追踪检索类端点仅管理员（401 未认证 / 403 非管理员）；
`/skills` 任意已认证用户可读。身份由 `core.deps.get_principal` 这个 B-4 从属 seam
提供，令牌层（TICKET-012）接入后只需让它填 `request.state`，本模块不变。

事务语义（TICKET-010 挂账第 1 条，本票拍板）：助手消息与 trace 在**同一事务**里提交
（见 `api/v1/chat.py` 的 `_commit_turn`）。因此查不到某次问诊的 trace 只可能是两种
情形之一 —— 这次问诊从未跑完，或它写库失败并整体回滚 —— 接口不区分二者，一律
404。这是刻意的：trace 只在回合真正落库时才存在，不会出现「有助手消息却无 trace」
或「有 trace 却无助手消息」的偏斜记录。
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import Principal, get_session, require_admin, require_authenticated
from core.errors import ApiError
from core.response import Envelope, PagePayload, page_result, success
from core.serialization import ApiDateTime
from repositories.trace import TraceRepository
from skills.manifest import SKILL_MANIFESTS
from skills.trace import RouteDecision, SkippedSkill, Span, TraceQuery, TraceSummary

router = APIRouter(tags=["observability"])


class SpanView(BaseModel):
    trace_id: str
    name: str
    status: str
    duration_ms: int
    input_digest: str
    output_digest: str
    detail: dict[str, Any] | None = None
    started_at: ApiDateTime

    @classmethod
    def of(cls, span: Span) -> "SpanView":
        return cls(**span.model_dump())


class RouteView(BaseModel):
    skills_run: list[str]
    skills_skipped: list[SkippedSkill]
    decided_at: ApiDateTime

    @classmethod
    def of(cls, decision: RouteDecision) -> "RouteView":
        return cls(
            skills_run=list(decision.skills_run),
            skills_skipped=list(decision.skills_skipped),
            decided_at=decision.decided_at,
        )


class TraceView(BaseModel):
    trace_id: str
    spans: list[SpanView]
    route: RouteView | None


class TraceSummaryView(BaseModel):
    trace_id: str
    started_at: ApiDateTime
    span_count: int
    skills_run: list[str]
    degraded: list[str]

    @classmethod
    def of(cls, summary: TraceSummary) -> "TraceSummaryView":
        return cls(**summary.model_dump())


class SkillManifestView(BaseModel):
    name: str
    category: str
    schema_version: str
    vocabulary_version: str | None


@router.get(
    "/traces",
    response_model=Envelope[PagePayload[TraceSummaryView]],
)
async def list_traces(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    trace_id: str | None = None,
    skill: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    degraded: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[TraceSummaryView]]:
    query = TraceQuery(
        trace_id=trace_id,
        skill=skill,
        start=start,
        end=end,
        degraded=degraded,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items, total = await TraceRepository(session).search(query)
    return page_result(
        [TraceSummaryView.of(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/traces/{trace_id}",
    response_model=Envelope[TraceView],
)
async def read_trace(
    trace_id: str,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TraceView]:
    repository = TraceRepository(session)
    spans = list(await repository.spans_for(trace_id))
    route = await repository.route_for(trace_id)
    if not spans and route is None:
        # 从未发生，或写失败并整体回滚 —— 二者在本事务语义下不可区分（见模块 docstring）。
        raise ApiError(404, "trace 不存在")
    return success(
        TraceView(
            trace_id=trace_id,
            spans=[SpanView.of(span) for span in spans],
            route=None if route is None else RouteView.of(route),
        )
    )


@router.get(
    "/skills",
    response_model=Envelope[list[SkillManifestView]],
)
async def list_skills(
    principal: Principal = Depends(require_authenticated),
) -> Envelope[list[SkillManifestView]]:
    return success(
        [
            SkillManifestView(
                name=manifest.name,
                category=manifest.category,
                schema_version=manifest.schema_version,
                vocabulary_version=manifest.vocabulary_version,
            )
            for manifest in SKILL_MANIFESTS
        ]
    )
