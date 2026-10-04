"""TICKET-022：数据统计端点（`SPEC.md` 5.4「内容与统计」）。

- `GET /stat/overview`：管理员看运营总览；医生看工作台概览（字段按角色不同）
- `GET /stat/user-overview`：患者的个人概览
- `GET /stat/consult-trend` / `GET /stat/user-growth`：按天数的趋势，`days` 越界 422
- `GET /stat/appointments-by-department` / `GET /stat/knowledge-types`：分布数据

统计只读，不新增迁移；聚合规则在 `services/stat_service.py`，取数在
`repositories/stat.py`。
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    Principal,
    get_session,
    require_admin,
    require_doctor_or_admin,
    require_patient,
)
from core.roles import ROLE_ADMIN
from core.response import Envelope, error_responses, success
from core.serialization import ApiDate
from repositories.stat import StatRepository
from services import stat_service
from services.stat_service import (
    DEFAULT_TREND_DAYS,
    MAX_TREND_DAYS,
    MIN_TREND_DAYS,
)

router = APIRouter(tags=["stat"])


class StatOverviewView(BaseModel):
    """`SPEC.md` 5.4：`StatOverviewView`（按角色字段不同）。

    管理员填前六项总数，医生填后四项工作台指标；另一角色的字段为 `None`，
    由 `response_model_exclude_none=True` 从响应中略去。"""

    # 管理员运营总览
    user_count: int | None = None
    doctor_count: int | None = None
    session_count: int | None = None
    appointment_count: int | None = None
    knowledge_count: int | None = None
    article_count: int | None = None
    # 医生工作台概览
    pending_consults: int | None = None
    today_appointments: int | None = None
    replied_consults: int | None = None
    total_patients: int | None = None


class UserStatView(BaseModel):
    """`SPEC.md` 5.4：`UserStatView`（患者个人概览）。"""

    consult_count: int = 0
    appointment_count: int = 0
    record_count: int = 0
    session_count: int = 0


class StatTrendPoint(BaseModel):
    """趋势上的一天（`{date, count}`）。"""

    date: ApiDate
    count: int = 0


class StatDistributionItem(BaseModel):
    """分布的一项（`{name, value}`）。"""

    name: str
    value: int = 0


@router.get(
    "/stat/overview",
    response_model=Envelope[StatOverviewView],
    response_model_exclude_none=True,
    responses=error_responses(401, 403),
)
async def stat_overview(
    principal: Principal = Depends(require_doctor_or_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[StatOverviewView]:
    repository = StatRepository(session)
    if principal.role == ROLE_ADMIN:
        data = await stat_service.overview(repository)
    else:
        data = await stat_service.doctor_overview(repository, principal.user_id)
    return success(StatOverviewView(**data))


@router.get(
    "/stat/user-overview",
    response_model=Envelope[UserStatView],
    responses=error_responses(401, 403),
)
async def user_overview(
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[UserStatView]:
    data = await stat_service.user_overview(
        StatRepository(session), principal.user_id
    )
    return success(UserStatView(**data))


@router.get(
    "/stat/consult-trend",
    response_model=Envelope[list[StatTrendPoint]],
    responses=error_responses(401, 403, 422),
)
async def consult_trend(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    days: int = Query(DEFAULT_TREND_DAYS, ge=MIN_TREND_DAYS, le=MAX_TREND_DAYS),
) -> Envelope[list[StatTrendPoint]]:
    points = await stat_service.consult_trend(StatRepository(session), days)
    return success([StatTrendPoint(date=p.date, count=p.count) for p in points])


@router.get(
    "/stat/appointments-by-department",
    response_model=Envelope[list[StatDistributionItem]],
    responses=error_responses(401, 403),
)
async def appointments_by_department(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[StatDistributionItem]]:
    rows = await stat_service.appointment_by_department(StatRepository(session))
    return success(
        [StatDistributionItem(name=name, value=value) for name, value in rows]
    )


@router.get(
    "/stat/user-growth",
    response_model=Envelope[list[StatTrendPoint]],
    responses=error_responses(401, 403, 422),
)
async def user_growth(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    days: int = Query(DEFAULT_TREND_DAYS, ge=MIN_TREND_DAYS, le=MAX_TREND_DAYS),
) -> Envelope[list[StatTrendPoint]]:
    points = await stat_service.user_growth(StatRepository(session), days)
    return success([StatTrendPoint(date=p.date, count=p.count) for p in points])


@router.get(
    "/stat/knowledge-types",
    response_model=Envelope[list[StatDistributionItem]],
    responses=error_responses(401, 403),
)
async def knowledge_types(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[StatDistributionItem]]:
    rows = await stat_service.knowledge_type_distribution(StatRepository(session))
    return success(
        [StatDistributionItem(name=name, value=value) for name, value in rows]
    )
