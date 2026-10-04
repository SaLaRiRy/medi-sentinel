"""TICKET-022: `/api/v1/stat/*` — 数据统计（`SPEC.md` 5.4「内容与统计」）。

观察面是 C-1 契约边界：对真实应用发 HTTP 请求，断言的是「管理员看到运营总览、
医生看到工作台概览、患者看到个人概览」以及趋势与分布的形状。统计只读，不新增
迁移；六项总数与各维度聚合见 `FUNCTIONAL_SPEC.md` 2.9。天数参数越界返回 422。
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow, UserRow
from models.appointment import AppointmentRow
from models.article import ArticleRow
from models.consult import ConsultSessionRow
from models.department import DepartmentRow
from models.doctor_consult import (
    CONSULT_STATUS_PENDING,
    CONSULT_STATUS_REPLIED,
    DoctorConsultRow,
)
from models.health_record import HealthRecordRow
from models.knowledge import KnowledgeFileRow

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}


async def _token(http, *, role: str, username: str = "shared") -> str:
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORDS[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed(database_url: str, rows: list) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add_all(rows)
            await session.commit()
    finally:
        await engine.dispose()


def _today() -> date:
    """统计口径的「今天」是 UTC 自然日（与模型 `datetime.now(UTC)` 一致）。"""
    return datetime.now(UTC).date()


def _at(day: date) -> datetime:
    return datetime.combine(day, time.min)


def _appointment(user_id: int, *, doctor_id: int, department_id: int, day: date):
    return AppointmentRow(
        user_id=user_id,
        doctor_id=doctor_id,
        department_id=department_id,
        visit_date=day,
        time_slot="上午",
    )


# --- 鉴权与角色 -------------------------------------------------------------


async def test_overview_requires_authentication(client):
    response = await client.get("/api/v1/stat/overview")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_overview_rejects_patients(client):
    token = await _token(client, role="user")

    response = await client.get("/api/v1/stat/overview", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_user_overview_is_for_patients_only(client):
    for role in ("doctor", "admin"):
        token = await _token(client, role=role)

        response = await client.get(
            "/api/v1/stat/user-overview", headers=_bearer(token)
        )

        assert response.status_code == 403
        assert response.json()["code"] == 403


@pytest.mark.parametrize(
    "endpoint",
    [
        "consult-trend",
        "appointments-by-department",
        "user-growth",
        "knowledge-types",
    ],
)
async def test_admin_only_endpoints_reject_other_roles(client, endpoint):
    unauthenticated = await client.get(f"/api/v1/stat/{endpoint}")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == 401

    for role in ("user", "doctor"):
        token = await _token(client, role=role)
        response = await client.get(
            f"/api/v1/stat/{endpoint}", headers=_bearer(token)
        )
        assert response.status_code == 403
        assert response.json()["code"] == 403


# --- 管理员运营概览 / 医生工作台概览 ---------------------------------------


async def test_admin_overview_counts_the_six_totals(client, database_url):
    await _seed(
        database_url,
        [
            UserRow(username="p2", password="pw1234", real_name="李四"),
            DoctorRow(username="d2", password="pw1234", real_name="王医生"),
            ConsultSessionRow(user_id=1),
            _appointment(1, doctor_id=1, department_id=1, day=_today()),
            KnowledgeFileRow(
                file_name="a.md", file_type="markdown", file_path="/a", file_size=1
            ),
            ArticleRow(title="科普"),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get("/api/v1/stat/overview", headers=_bearer(token))

    assert response.status_code == 200
    data = response.json()["data"]
    # conftest 已种下 shared/disabled 两个患者与 shared 一位医生。
    assert data == {
        "user_count": 3,
        "doctor_count": 2,
        "session_count": 1,
        "appointment_count": 1,
        "knowledge_count": 1,
        "article_count": 1,
    }
    # 医生的字段不泄漏给管理员（字段按角色不同）。
    assert "pending_consults" not in data


async def test_doctor_overview_counts_the_workload(client, database_url):
    await _seed(
        database_url,
        [
            DoctorRow(username="d2", password="pw1234", real_name="王医生"),
            DoctorConsultRow(
                user_id=1, doctor_id=1, chief_complaint="a",
                status=CONSULT_STATUS_PENDING,
            ),
            DoctorConsultRow(
                user_id=1, doctor_id=None, chief_complaint="b",
                status=CONSULT_STATUS_PENDING,
            ),
            DoctorConsultRow(
                user_id=1, doctor_id=1, chief_complaint="c",
                status=CONSULT_STATUS_REPLIED,
            ),
            DoctorConsultRow(
                user_id=1, doctor_id=2, chief_complaint="d",
                status=CONSULT_STATUS_PENDING,
            ),
            _appointment(1, doctor_id=1, department_id=1, day=_today()),
            _appointment(
                1, doctor_id=1, department_id=1, day=_today() - timedelta(days=1)
            ),
            _appointment(1, doctor_id=2, department_id=1, day=_today()),
            HealthRecordRow(user_id=2, doctor_id=1, record_type="门诊记录"),
            HealthRecordRow(user_id=2, doctor_id=1, record_type="复诊记录"),
        ],
    )
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/stat/overview", headers=_bearer(token))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "pending_consults": 2,
        "today_appointments": 1,
        "replied_consults": 1,
        # 档案患者 {2} ∪ 预约患者 {1} ∪ 问诊患者 {1} = 2
        "total_patients": 2,
    }
    assert "user_count" not in data


async def test_user_overview_counts_only_the_callers_own_rows(client, database_url):
    await _seed(
        database_url,
        [
            DoctorConsultRow(user_id=1, doctor_id=1, chief_complaint="a"),
            DoctorConsultRow(user_id=2, doctor_id=None, chief_complaint="b"),
            _appointment(1, doctor_id=1, department_id=1, day=_today()),
            _appointment(2, doctor_id=1, department_id=1, day=_today()),
            HealthRecordRow(user_id=1, doctor_id=1, record_type="门诊记录"),
            HealthRecordRow(user_id=2, doctor_id=1, record_type="门诊记录"),
            ConsultSessionRow(user_id=1),
            ConsultSessionRow(user_id=2),
        ],
    )
    token = await _token(client, role="user")

    response = await client.get("/api/v1/stat/user-overview", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "consult_count": 1,
        "appointment_count": 1,
        "record_count": 1,
        "session_count": 1,
    }


async def test_user_overview_is_zero_for_a_fresh_patient(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "fresh",
            "password": "patient-pass",
            "confirm_password": "patient-pass",
            "real_name": "新患者",
        },
    )
    token = response.json()["data"]["access_token"]

    overview = await client.get(
        "/api/v1/stat/user-overview", headers=_bearer(token)
    )

    assert overview.status_code == 200
    assert overview.json()["data"] == {
        "consult_count": 0,
        "appointment_count": 0,
        "record_count": 0,
        "session_count": 0,
    }


# --- 趋势 -----------------------------------------------------------------


async def test_consult_trend_defaults_to_seven_days_and_counts_per_day(
    client, database_url
):
    today = _today()
    await _seed(
        database_url,
        [
            ConsultSessionRow(user_id=1, create_time=_at(today)),
            ConsultSessionRow(user_id=1, create_time=_at(today)),
            ConsultSessionRow(
                user_id=1, create_time=_at(today - timedelta(days=2))
            ),
            # 窗口外的旧会话不计入。
            ConsultSessionRow(
                user_id=1, create_time=_at(today - timedelta(days=9))
            ),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get("/api/v1/stat/consult-trend", headers=_bearer(token))

    assert response.status_code == 200
    points = response.json()["data"]
    expected_dates = [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(6, -1, -1)
    ]
    assert [point["date"] for point in points] == expected_dates
    counts = {point["date"]: point["count"] for point in points}
    assert counts[today.isoformat()] == 2
    assert counts[(today - timedelta(days=2)).isoformat()] == 1
    assert sum(point["count"] for point in points) == 3


async def test_trend_accepts_an_explicit_window(client, database_url):
    today = _today()
    await _seed(
        database_url,
        [
            ConsultSessionRow(user_id=1, create_time=_at(today)),
            ConsultSessionRow(
                user_id=1, create_time=_at(today - timedelta(days=4))
            ),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/stat/consult-trend?days=3", headers=_bearer(token)
    )

    assert response.status_code == 200
    points = response.json()["data"]
    assert [point["date"] for point in points] == [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(2, -1, -1)
    ]
    assert sum(point["count"] for point in points) == 1


async def test_user_growth_counts_new_patients_per_day(client, database_url):
    today = _today()
    await _seed(
        database_url,
        [
            UserRow(
                username="new-today", password="pw1234",
                create_time=_at(today),
            ),
            UserRow(
                username="new-old", password="pw1234",
                create_time=_at(today - timedelta(days=3)),
            ),
            UserRow(
                username="outside", password="pw1234",
                create_time=_at(today - timedelta(days=30)),
            ),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get("/api/v1/stat/user-growth?days=5", headers=_bearer(token))

    assert response.status_code == 200
    points = response.json()["data"]
    counts = {point["date"]: point["count"] for point in points}
    assert len(points) == 5
    # conftest 的 shared / disabled 两位患者也建于今天（UTC），故今天为 2 + 1。
    assert counts[today.isoformat()] == 3
    assert counts[(today - timedelta(days=3)).isoformat()] == 1
    assert sum(point["count"] for point in points) == 4


@pytest.mark.parametrize("endpoint", ["consult-trend", "user-growth"])
@pytest.mark.parametrize("days", ["0", "-1", "366", "1000", "abc"])
async def test_trend_days_out_of_range_is_422(client, endpoint, days):
    token = await _token(client, role="admin")

    response = await client.get(
        f"/api/v1/stat/{endpoint}?days={days}", headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


# --- 分布 -----------------------------------------------------------------


async def test_appointments_by_department_lists_every_department(client, database_url):
    await _seed(
        database_url,
        [
            DepartmentRow(name="内科", sort_order=0),
            DepartmentRow(name="外科", sort_order=1),
            _appointment(1, doctor_id=1, department_id=1, day=_today()),
            _appointment(1, doctor_id=1, department_id=1, day=_today()),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/stat/appointments-by-department", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"name": "内科", "value": 2},
        {"name": "外科", "value": 0},
    ]


async def test_knowledge_types_counts_files_by_type(client, database_url):
    await _seed(
        database_url,
        [
            KnowledgeFileRow(
                file_name="a.md", file_type="markdown", file_path="/a", file_size=1
            ),
            KnowledgeFileRow(
                file_name="b.md", file_type="markdown", file_path="/b", file_size=1
            ),
            KnowledgeFileRow(
                file_name="c.pdf", file_type="pdf", file_path="/c", file_size=1
            ),
        ],
    )
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/stat/knowledge-types", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"name": "markdown", "value": 2},
        {"name": "pdf", "value": 1},
    ]
