"""TICKET-015: `/api/v1/knowledge` — the admin knowledge-base surface (SPEC.md 5.4).

The upload seam under test: an admin posts a file and immediately gets
`{id, file_name}` back while the vectorization job is still pending; a file over
the configured cap is rejected with 413, and an unsupported extension never
reaches the database. The background job itself is a cold scheduler, so the
test decides when it runs.
"""

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.knowledge import VECTOR_INDEXED, VECTOR_UPLOADED, KnowledgeFileRow
from services.knowledge import KnowledgeJobs
from tests.doubles import ColdScheduler, InMemoryVectorStore

UPLOAD_CAP = 2048


@pytest.fixture
async def knowledge(database_url, accounts, tmp_path):
    from core.config import Settings
    from main import create_app

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = InMemoryVectorStore()
    scheduler = ColdScheduler()
    jobs = KnowledgeJobs(
        session_factory=session_factory,
        store=store,
        scheduler=scheduler,
    )
    settings = Settings(
        database_url=database_url,
        upload_dir=str(tmp_path / "uploads"),
        knowledge_max_bytes=UPLOAD_CAP,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        app.state.knowledge_jobs = jobs
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield {
                "http": http,
                "store": store,
                "scheduler": scheduler,
                "session_factory": session_factory,
                "uploads": Path(tmp_path / "uploads"),
            }
    await engine.dispose()


async def _token(http, *, role: str) -> str:
    password = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": "shared", "password": password[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _file(fixture, file_id: int) -> KnowledgeFileRow:
    async with fixture["session_factory"]() as session:
        row = await session.get(KnowledgeFileRow, file_id)
        assert row is not None
        return row


async def test_knowledge_requires_authentication(knowledge):
    response = await knowledge["http"].get("/api/v1/knowledge")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_knowledge_rejects_non_admins(knowledge):
    token = await _token(knowledge["http"], role="user")

    response = await knowledge["http"].get(
        "/api/v1/knowledge", headers=_bearer(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_upload_returns_the_id_and_file_name_and_defers_vectorization(knowledge):
    token = await _token(knowledge["http"], role="admin")
    content = "高血压防治指南。请按时服药。" * 10

    response = await knowledge["http"].post(
        "/api/v1/knowledge",
        headers=_bearer(token),
        files={"file": ("指南.md", content.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"]["file_name"] == "指南.md"
    assert isinstance(body["data"]["id"], int)

    row = await _file(knowledge, body["data"]["id"])
    assert row.vector_status == VECTOR_UPLOADED
    assert row.chunk_count == 0
    assert row.upload_by == 1
    assert row.upload_role == "admin"
    stored = list((knowledge["uploads"] / "knowledge").iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == ".md"
    assert len(stored[0].stem) == 32
    assert len(knowledge["scheduler"].coroutines) == 1

    await knowledge["scheduler"].coroutines.pop()

    indexed = await _file(knowledge, body["data"]["id"])
    assert indexed.vector_status == VECTOR_INDEXED
    assert indexed.chunk_count > 0
    assert await knowledge["store"].count_by_file_id(indexed.id) == indexed.chunk_count


async def test_upload_over_the_configured_cap_is_413(knowledge):
    token = await _token(knowledge["http"], role="admin")

    response = await knowledge["http"].post(
        "/api/v1/knowledge",
        headers=_bearer(token),
        files={"file": ("big.md", b"x" * (UPLOAD_CAP + 1), "text/markdown")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == 413
    async with knowledge["session_factory"]() as session:
        from sqlalchemy import func, select

        total = (
            await session.execute(select(func.count()).select_from(KnowledgeFileRow))
        ).scalar_one()
    assert total == 0


async def test_upload_rejects_an_unsupported_extension(knowledge):
    token = await _token(knowledge["http"], role="admin")

    response = await knowledge["http"].post(
        "/api/v1/knowledge",
        headers=_bearer(token),
        files={"file": ("notes.exe", b"x", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


async def _seed_file(fixture, name: str, file_type: str) -> int:
    from repositories.knowledge import KnowledgeRepository

    async with fixture["session_factory"]() as session:
        row = await KnowledgeRepository(session).create_file(
            file_name=name,
            file_type=file_type,
            file_size=10,
            file_path=str(fixture["uploads"] / name),
        )
        await session.commit()
        return row.id


async def _chunks(fixture, file_id: int) -> int:
    from sqlalchemy import func, select

    from models.knowledge import KnowledgeChunkRow

    async with fixture["session_factory"]() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(KnowledgeChunkRow)
                    .where(KnowledgeChunkRow.file_id == file_id)
                )
            ).scalar_one()
        )


async def _list(fixture, token, query=""):
    return await fixture["http"].get(
        f"/api/v1/knowledge{query}", headers=_bearer(token)
    )


async def test_list_searches_by_file_name_and_type_and_paginates(knowledge):
    token = await _token(knowledge["http"], role="admin")
    await _seed_file(knowledge, "高血压指南.md", "md")
    await _seed_file(knowledge, "糖尿病指南.pdf", "pdf")
    await _seed_file(knowledge, "流感指南.md", "md")

    first_page = (await _list(knowledge, token, "?page=1&page_size=2")).json()
    second_page = (await _list(knowledge, token, "?page=2&page_size=2")).json()

    assert first_page["data"]["total"] == 3
    assert first_page["data"]["page"] == 1
    assert first_page["data"]["page_size"] == 2
    assert len(first_page["data"]["items"]) == 2
    assert len(second_page["data"]["items"]) == 1
    assert set(first_page["data"]["items"][0]) >= {
        "id",
        "file_name",
        "file_type",
        "file_size",
        "chunk_count",
        "vector_status",
    }

    by_name = (await _list(knowledge, token, "?keyword=糖尿病")).json()
    assert by_name["data"]["total"] == 1
    assert by_name["data"]["items"][0]["file_name"] == "糖尿病指南.pdf"

    by_type = (await _list(knowledge, token, "?keyword=md")).json()
    assert by_type["data"]["total"] == 2

    exact_type = (await _list(knowledge, token, "?file_type=pdf")).json()
    assert exact_type["data"]["total"] == 1

    invalid = await _list(knowledge, token, "?page=0")
    assert invalid.status_code == 422
    assert invalid.json()["code"] == 422


async def test_revectorize_rebuilds_the_file_instead_of_appending(knowledge):
    token = await _token(knowledge["http"], role="admin")
    upload = await knowledge["http"].post(
        "/api/v1/knowledge",
        headers=_bearer(token),
        files={"file": ("指南.md", ("高血压。" * 150).encode(), "text/markdown")},
    )
    file_id = upload.json()["data"]["id"]
    await knowledge["scheduler"].coroutines.pop()
    before = await _file(knowledge, file_id)

    response = await knowledge["http"].post(
        f"/api/v1/knowledge/{file_id}/revectorize", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert len(knowledge["scheduler"].coroutines) == 1
    await knowledge["scheduler"].coroutines.pop()

    after = await _file(knowledge, file_id)
    assert after.vector_status == VECTOR_INDEXED
    assert after.chunk_count == before.chunk_count
    assert await _chunks(knowledge, file_id) == after.chunk_count
    assert await knowledge["store"].count_by_file_id(file_id) == after.chunk_count

    missing = await knowledge["http"].post(
        "/api/v1/knowledge/9999/revectorize", headers=_bearer(token)
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == 404


async def test_delete_removes_the_row_chunks_vectors_and_disk_file(knowledge):
    token = await _token(knowledge["http"], role="admin")
    upload = await knowledge["http"].post(
        "/api/v1/knowledge",
        headers=_bearer(token),
        files={"file": ("指南.md", ("高血压。" * 150).encode(), "text/markdown")},
    )
    file_id = upload.json()["data"]["id"]
    await knowledge["scheduler"].coroutines.pop()
    stored = list((knowledge["uploads"] / "knowledge").iterdir())
    assert len(stored) == 1

    response = await knowledge["http"].delete(
        f"/api/v1/knowledge/{file_id}", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _chunks(knowledge, file_id) == 0
    assert await knowledge["store"].count_by_file_id(file_id) == 0
    assert not stored[0].exists()
    async with knowledge["session_factory"]() as session:
        assert await session.get(KnowledgeFileRow, file_id) is None

    missing = await knowledge["http"].delete(
        "/api/v1/knowledge/9999", headers=_bearer(token)
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == 404
