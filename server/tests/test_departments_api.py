"""TICKET-020: `/api/v1/departments` — 科室主数据（`SPEC.md` 5.4）。

观察面是 C-1 契约边界：对真实应用发 HTTP 请求。公开列表只读状态为 1 的科室，
按 `sort_order` 升序、同值按编号倒序，`doctor_count` 只统计已分配且状态为 1 的
医生（`FUNCTIONAL_SPEC.md` 5.13）。删除仍有关联医生的科室返回 409 且不落库
（`FUNCTIONAL_SPEC.md` 5.12 / AC-E-07）。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow
from models.department import DepartmentRow

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


async def _new_engine(database_url: str):
    engine = create_async_engine(database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_department(
    database_url: str,
    *,
    name: str,
    description: str | None = None,
    sort_order: int = 0,
    status: int = 1,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DepartmentRow(
                name=name,
                description=description,
                sort_order=sort_order,
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _seed_doctor(
    database_url: str,
    *,
    username: str,
    real_name: str,
    department_id: int | None = None,
    status: int = 1,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DoctorRow(
                username=username,
                password="doctor-pass",
                real_name=real_name,
                department_id=department_id,
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _stored_department(database_url: str, department_id: int):
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(DepartmentRow, department_id)
    finally:
        await engine.dispose()


async def test_public_list_needs_no_authentication(client, database_url):
    await _seed_department(database_url, name="内科", sort_order=1)

    response = await client.get("/api/v1/departments")

    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert [item["name"] for item in response.json()["data"]] == ["内科"]


async def test_public_list_filters_sorts_and_counts_doctors(client, database_url):
    first = await _seed_department(database_url, name="外科", sort_order=2)
    second = await _seed_department(database_url, name="内科", sort_order=1)
    third = await _seed_department(database_url, name="儿科", sort_order=1)
    await _seed_department(database_url, name="停用科室", sort_order=0, status=0)
    await _seed_doctor(
        database_url, username="doc1", real_name="李医生", department_id=second
    )
    await _seed_doctor(
        database_url,
        username="doc2",
        real_name="停用医生",
        department_id=second,
        status=0,
    )
    await _seed_doctor(
        database_url, username="doc3", real_name="王医生", department_id=third
    )
    await _seed_doctor(database_url, username="doc4", real_name="无科室医生")

    response = await client.get("/api/v1/departments")

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [third, second, first]
    counts = {item["id"]: item["doctor_count"] for item in items}
    assert counts == {first: 0, second: 1, third: 1}
    assert items[0]["description"] is None
    assert items[0]["sort_order"] == 1


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/departments/admin")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_admin_list_rejects_non_admins(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await client.get(
            "/api/v1/departments/admin", headers=_bearer(token)
        )

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_list_paginates_all_statuses(client, database_url):
    for index in range(3):
        await _seed_department(database_url, name=f"科室{index}", sort_order=index)
    hidden = await _seed_department(database_url, name="停用科室", status=0)
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/departments/admin?page=1&page_size=2", headers=_bearer(token)
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 4
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2
    # Same ordering as the public list, but every status shows up: 停用科室 and
    # 科室0 share sort 0, so the newer (higher id) 停用科室 leads.
    assert payload["items"][0]["id"] == hidden


async def test_admin_list_rejects_out_of_range_query(client):
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/departments/admin?page=0", headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_create_requires_admin(client):
    response = await client.post("/api/v1/departments", json={"name": "内科"})
    assert response.status_code == 401
    assert response.json()["code"] == 401

    token = await _token(client, role="doctor")
    response = await client.post(
        "/api/v1/departments", json={"name": "内科"}, headers=_bearer(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_create_department(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/departments",
        json={"name": "心内科", "description": "心血管", "sort_order": 3},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    department_id = response.json()["data"]["id"]
    row = await _stored_department(database_url, department_id)
    assert row.name == "心内科"
    assert row.description == "心血管"
    assert row.sort_order == 3
    assert row.status == 1


async def test_create_department_defaults_sort_order_and_status(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/departments", json={"name": "默认科室"}, headers=_bearer(token)
    )

    assert response.status_code == 200
    row = await _stored_department(database_url, response.json()["data"]["id"])
    assert row.sort_order == 0
    assert row.status == 1


async def test_create_rejects_a_duplicate_name_with_409(client, database_url):
    await _seed_department(database_url, name="内科")
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/departments", json={"name": "内科"}, headers=_bearer(token)
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x" * 51}])
async def test_create_rejects_invalid_names_with_422(client, body):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/departments", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_update_department(client, database_url):
    department_id = await _seed_department(database_url, name="旧名")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/departments/{department_id}",
        json={"name": "新名", "description": "描述", "sort_order": 9},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    row = await _stored_department(database_url, department_id)
    assert row.name == "新名"
    assert row.description == "描述"
    assert row.sort_order == 9


async def test_update_of_a_missing_department_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/departments/9999", json={"name": "新名"}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_update_to_another_departments_name_is_409(client, database_url):
    await _seed_department(database_url, name="内科")
    other = await _seed_department(database_url, name="外科")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/departments/{other}", json={"name": "内科"}, headers=_bearer(token)
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409
    assert (await _stored_department(database_url, other)).name == "外科"


async def test_update_may_keep_its_own_name(client, database_url):
    department_id = await _seed_department(database_url, name="内科")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/departments/{department_id}",
        json={"name": "内科", "sort_order": 5},
        headers=_bearer(token),
    )

    assert response.status_code == 200


async def test_delete_requires_admin(client):
    response = await client.delete("/api/v1/departments/1")
    assert response.status_code == 401
    assert response.json()["code"] == 401

    token = await _token(client, role="user")
    response = await client.delete(
        "/api/v1/departments/1", headers=_bearer(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_delete_of_a_missing_department_is_404(client):
    token = await _token(client, role="admin")

    response = await client.delete(
        "/api/v1/departments/9999", headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_delete_a_department_with_doctors_is_409_and_changes_nothing(
    client, database_url
):
    department_id = await _seed_department(database_url, name="内科")
    doctor_id = await _seed_doctor(
        database_url, username="doc1", real_name="李医生", department_id=department_id
    )
    token = await _token(client, role="admin")

    response = await client.delete(
        f"/api/v1/departments/{department_id}", headers=_bearer(token)
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409
    assert await _stored_department(database_url, department_id) is not None
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            assert await session.get(DoctorRow, doctor_id) is not None
    finally:
        await engine.dispose()


async def test_delete_an_empty_department(client, database_url):
    department_id = await _seed_department(database_url, name="空科室")
    token = await _token(client, role="admin")

    response = await client.delete(
        f"/api/v1/departments/{department_id}", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored_department(database_url, department_id) is None
