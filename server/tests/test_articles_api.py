"""TICKET-021: `/api/v1/articles` — 健康科普文章（`SPEC.md` 5.4「内容与统计」）。

观察面是 C-1 契约边界：对真实应用发 HTTP 请求。公开列表只读状态为 1 的文章，
可按分类过滤（FUNCTIONAL_SPEC 5.17）；公开详情限定已发布并每次 `view_count + 1`
（FUNCTIONAL_SPEC 2.8 / 5.17）。管理端分页看全部状态，增删改查限 `admin`；
更新/删除不存在的记录返回 404（本票语义，与 015/017/018/019/020 一致）。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.article import ArticleRow

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


async def _seed_article(
    database_url: str,
    *,
    title: str,
    category: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    view_count: int = 0,
    status: int = 1,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = ArticleRow(
                title=title,
                category=category,
                summary=summary,
                content=content,
                view_count=view_count,
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _stored_article(database_url: str, article_id: int):
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(ArticleRow, article_id)
    finally:
        await engine.dispose()


async def test_public_list_needs_no_authentication(client, database_url):
    await _seed_article(database_url, title="高血压防治")

    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert [item["title"] for item in response.json()["data"]["items"]] == ["高血压防治"]


async def test_public_list_returns_only_published_newest_first(client, database_url):
    first = await _seed_article(database_url, title="旧文章", category="健康科普")
    second = await _seed_article(database_url, title="新文章", category="疾病预防")
    await _seed_article(database_url, title="草稿", category="健康科普", status=0)

    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [second, first]
    assert "content" not in payload["items"][0]


async def test_public_list_filters_by_category(client, database_url):
    await _seed_article(database_url, title="科普文章", category="健康科普")
    await _seed_article(database_url, title="预防文章", category="疾病预防")

    response = await client.get("/api/v1/articles?category=健康科普")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert [item["title"] for item in payload["items"]] == ["科普文章"]


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
async def test_public_list_rejects_out_of_range_pagination(client, query):
    response = await client.get(f"/api/v1/articles?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_public_detail_increments_the_view_count(client, database_url):
    article_id = await _seed_article(
        database_url, title="详情文章", summary="摘要", content="正文"
    )

    first = await client.get(f"/api/v1/articles/{article_id}")
    second = await client.get(f"/api/v1/articles/{article_id}")

    assert first.status_code == 200
    assert first.json()["data"]["content"] == "正文"
    assert first.json()["data"]["view_count"] == 1
    assert second.json()["data"]["view_count"] == 2
    assert (await _stored_article(database_url, article_id)).view_count == 2


async def test_public_detail_of_a_missing_article_is_404(client):
    response = await client.get("/api/v1/articles/9999")

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_public_detail_of_an_unpublished_article_is_404(client, database_url):
    article_id = await _seed_article(database_url, title="草稿", status=0)

    response = await client.get(f"/api/v1/articles/{article_id}")

    assert response.status_code == 404
    assert response.json()["code"] == 404
    assert (await _stored_article(database_url, article_id)).view_count == 0


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/articles/admin")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_admin_list_rejects_non_admins(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await client.get("/api/v1/articles/admin", headers=_bearer(token))

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_list_pages_all_statuses_and_searches(client, database_url):
    first = await _seed_article(database_url, title="高血压防治", status=1)
    second = await _seed_article(database_url, title="糖尿病饮食", status=0)
    third = await _seed_article(database_url, title="运动康复", status=1)
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/articles/admin?page=1&page_size=2", headers=_bearer(token)
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 3
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2
    # Newest first, every status visible (the draft is the second newest).
    assert [item["id"] for item in payload["items"]] == [third, second]
    assert {item["status"] for item in payload["items"]} == {0, 1}

    searched = await client.get(
        "/api/v1/articles/admin?keyword=饮食", headers=_bearer(token)
    )
    assert [item["id"] for item in searched.json()["data"]["items"]] == [second]
    assert first not in [item["id"] for item in searched.json()["data"]["items"]]


async def test_admin_list_rejects_out_of_range_query(client):
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/articles/admin?page=0", headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_create_requires_admin(client):
    response = await client.post("/api/v1/articles", json={"title": "新文章"})
    assert response.status_code == 401
    assert response.json()["code"] == 401

    token = await _token(client, role="user")
    response = await client.post(
        "/api/v1/articles", json={"title": "新文章"}, headers=_bearer(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_create_article_with_defaults(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/articles", json={"title": "只有标题"}, headers=_bearer(token)
    )

    assert response.status_code == 200
    row = await _stored_article(database_url, response.json()["data"]["id"])
    assert row.title == "只有标题"
    assert row.status == 1
    assert row.view_count == 0
    assert row.content is None


async def test_update_article_flips_it_to_unpublished(client, database_url):
    article_id = await _seed_article(
        database_url, title="旧标题", content="旧正文", status=1
    )
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/articles/{article_id}",
        json={"title": "新标题", "category": "用药指南", "content": "新正文", "status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    row = await _stored_article(database_url, article_id)
    assert row.title == "新标题"
    assert row.category == "用药指南"
    assert row.content == "新正文"
    assert row.status == 0


async def test_update_of_a_missing_article_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/articles/9999", json={"title": "新标题"}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_delete_article(client, database_url):
    article_id = await _seed_article(database_url, title="待删")
    token = await _token(client, role="admin")

    response = await client.delete(
        f"/api/v1/articles/{article_id}", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored_article(database_url, article_id) is None


async def test_delete_of_a_missing_article_is_404(client):
    token = await _token(client, role="admin")

    response = await client.delete("/api/v1/articles/9999", headers=_bearer(token))

    assert response.status_code == 404
    assert response.json()["code"] == 404


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "x" * 201}])
async def test_create_article_rejects_invalid_titles(client, body):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/articles", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422
