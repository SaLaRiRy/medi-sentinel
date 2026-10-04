"""数据统计的聚合规则（TICKET-022，`FUNCTIONAL_SPEC.md` 2.9）。

规则集中在这里，路由只负责角色与查询参数校验，仓储只负责取数。统计全部基于既有
实体，不新增迁移。趋势的「最近 N 个自然日」按 UTC 计算并与仓储的窗口一致
（见 `repositories/stat.py`）；`days` 的上下界由路由声明，越界返回 422
（`SPEC.md` 5.4）。
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from repositories.stat import StatRepository

DEFAULT_TREND_DAYS = 7
MIN_TREND_DAYS = 1
MAX_TREND_DAYS = 365


def today() -> date:
    """统计口径的「今天」，与模型 `datetime.now(UTC)` 保持一致。"""
    return datetime.now(UTC).date()


def recent_days(days: int, *, end: date | None = None) -> list[date]:
    """最近 `days` 个自然日，含今天，按日期升序（FUNCTIONAL_SPEC 2.9）。"""
    last = end or today()
    return [last - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


@dataclass(frozen=True)
class TrendPoint:
    """趋势上的一天：日期 + 当天计数。"""

    date: date
    count: int


async def overview(repository: StatRepository) -> dict[str, int]:
    """管理员运营总览：患者、医生、AI 会话、预约、知识文件、文章六项总数。"""
    return {
        "user_count": await repository.count_users(),
        "doctor_count": await repository.count_doctors(),
        "session_count": await repository.count_sessions(),
        "appointment_count": await repository.count_appointments(),
        "knowledge_count": await repository.count_knowledge_files(),
        "article_count": await repository.count_articles(),
    }


async def doctor_overview(
    repository: StatRepository, doctor_id: int
) -> dict[str, int]:
    """医生工作台概览：待处理工单、今日预约、已回复工单、患者总数。"""
    return {
        "pending_consults": await repository.count_pending_consults(doctor_id),
        "today_appointments": await repository.count_appointments_on(
            doctor_id, today()
        ),
        "replied_consults": await repository.count_replied_consults(doctor_id),
        "total_patients": await repository.count_doctor_patients(doctor_id),
    }


async def user_overview(
    repository: StatRepository, user_id: int
) -> dict[str, int]:
    """患者个人概览：本人的人工问诊、预约、健康档案、AI 会话四项计数。"""
    return {
        "consult_count": await repository.count_user_consults(user_id),
        "appointment_count": await repository.count_user_appointments(user_id),
        "record_count": await repository.count_user_records(user_id),
        "session_count": await repository.count_user_sessions(user_id),
    }


async def consult_trend(repository: StatRepository, days: int) -> list[TrendPoint]:
    """最近 N 个自然日各自新建的 AI 会话数，按日期升序。"""
    window = recent_days(days)
    counts = await repository.session_counts_per_day(
        start=window[0], end=window[-1]
    )
    return [TrendPoint(date=day, count=counts.get(day, 0)) for day in window]


async def user_growth(repository: StatRepository, days: int) -> list[TrendPoint]:
    """最近 N 个自然日各自新增患者数，按日期升序。"""
    window = recent_days(days)
    counts = await repository.user_counts_per_day(
        start=window[0], end=window[-1]
    )
    return [TrendPoint(date=day, count=counts.get(day, 0)) for day in window]


async def appointment_by_department(
    repository: StatRepository,
) -> list[tuple[str, int]]:
    """每个科室的预约数，无预约的科室计 0。"""
    return await repository.appointments_by_department()


async def knowledge_type_distribution(
    repository: StatRepository,
) -> list[tuple[str, int]]:
    """按文件类型统计知识文件数。"""
    return await repository.knowledge_type_counts()
