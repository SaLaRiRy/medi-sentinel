"""End-to-end slice through the skeleton: HTTP -> repository -> database.

Seams under test: C-1 (response envelope, real HTTP status codes) and
B-5 (async session handed to a repository).
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from core.config import Settings
    from main import create_app

    app = create_app(Settings(database_url="sqlite+aiosqlite:///:memory:"))
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http


async def test_health_reports_service_and_database_status(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"
    assert isinstance(body["data"]["version"], str)


async def test_health_response_is_utf8_json(client):
    response = await client.get("/api/v1/health")

    assert response.headers["content-type"] == "application/json; charset=utf-8"


async def test_unknown_route_fails_with_real_404_and_matching_code(client):
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 404
    assert body["message"]
    assert body["data"] is None
