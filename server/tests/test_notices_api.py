"""TICKET-021: `/api/v1/notices` — 系统公告（`SPEC.md` 5.4「内容与统计」）。

公开列表**不分页**、一次返回全部已发布公告（FUNCTIONAL_SPEC 5.17）；公开详情
仅已发布，未发布或不存在都映射为 404（本票把旧的 `data: null` 语义收进真实状态码）。
管理端分页看全部状态，增删改查限 `admin`。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.article import NoticeRow

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


async def _seed_notice(
    database_url: str,
    *,
    title: str,
    content: str | None = "",
    status: int = 1,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = NoticeRow(title=title, content=content, status=status)
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _stored_notice(database_url: str, notice_id: int):
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(NoticeRow, notice_id)
    finally:
        await engine.dispose()


async def test_public_list_needs_no_authentication_and_hides_drafts(
    client, database_url
):
    older = await _seed_notice(database_url, title="旧公告")
    newer = await _seed_notice(database_url, title="新公告", content="正文")
    await _seed_notice(database_url, title="草稿公告", status=0)

    response = await client.get("/api/v1/notices")

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [newer, older]
    assert items[0]["content"] == "正文"


async def test_public_detail_returns_a_published_notice(client, database_url):
    notice_id = await _seed_notice(database_url, title="公告", content="内容")

    response = await client.get(f"/api/v1/notices/{notice_id}")

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "公告"
    assert response.json()["data"]["content"] == "内容"


async def test_public_detail_of_a_missing_notice_is_404(client):
    response = await client.get("/api/v1/notices/9999")

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_public_detail_of_an_unpublished_notice_is_404(client, database_url):
    notice_id = await _seed_notice(database_url, title="草稿", status=0)

    response = await client.get(f"/api/v1/notices/{notice_id}")

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/notices/admin")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_admin_list_rejects_non_admins(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await client.get("/api/v1/notices/admin", headers=_bearer(token))

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_list_pages_all_statuses_and_searches(client, database_url):
    first = await _seed_notice(database_url, title="系统维护", status=1)
    second = await _seed_notice(database_url, title="停诊通知", status=0)
    await _seed_notice(database_url, title="版本更新", status=1)
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/notices/admin?page=1&page_size=2", headers=_bearer(token)
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 3
    assert payload["page"] == 1
    assert len(payload["items"]) == 2
    assert {item["status"] for item in payload["items"]} == {0, 1}

    searched = await client.get(
        "/api/v1/notices/admin?keyword=停诊", headers=_bearer(token)
    )
    assert [item["id"] for item in searched.json()["data"]["items"]] == [second]
    assert first not in [item["id"] for item in searched.json()["data"]["items"]]


async def test_create_requires_admin(client):
    response = await client.post("/api/v1/notices", json={"title": "新公告"})
    assert response.status_code == 401
    assert response.json()["code"] == 401

    token = await _token(client, role="doctor")
    response = await client.post(
        "/api/v1/notices", json={"title": "新公告"}, headers=_bearer(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_create_notice_with_defaults(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/notices", json={"title": "只有标题"}, headers=_bearer(token)
    )

    assert response.status_code == 200
    row = await _stored_notice(database_url, response.json()["data"]["id"])
    assert row.title == "只有标题"
    assert row.content == ""
    assert row.status == 1


async def test_update_notice_flips_it_to_unpublished(client, database_url):
    notice_id = await _seed_notice(database_url, title="旧公告", content="旧正文")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/notices/{notice_id}",
        json={"title": "新公告", "content": "新正文", "status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    row = await _stored_notice(database_url, notice_id)
    assert row.title == "新公告"
    assert row.content == "新正文"
    assert row.status == 0


async def test_update_of_a_missing_notice_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/notices/9999", json={"title": "新公告"}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_delete_notice(client, database_url):
    notice_id = await _seed_notice(database_url, title="待删公告")
    token = await _token(client, role="admin")

    response = await client.delete(
        f"/api/v1/notices/{notice_id}", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored_notice(database_url, notice_id) is None


async def test_delete_of_a_missing_notice_is_404(client):
    token = await _token(client, role="admin")

    response = await client.delete("/api/v1/notices/9999", headers=_bearer(token))

    assert response.status_code == 404
    assert response.json()["code"] == 404


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "x" * 201}])
async def test_create_notice_rejects_invalid_titles(client, body):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/notices", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422
