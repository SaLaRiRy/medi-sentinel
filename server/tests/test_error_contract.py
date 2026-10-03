"""C-1 / SPEC.md 5.1-5.2: every failure carries a real status code, and `code` matches it."""

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from core.errors import ApiError, register_error_handlers
from core.response import EnvelopeJSONResponse


class ProbeBody(BaseModel):
    name: str


def _app_with_probe_routes() -> FastAPI:
    app = FastAPI(default_response_class=EnvelopeJSONResponse)
    register_error_handlers(app)

    @app.post("/probe")
    async def probe(body: ProbeBody) -> dict[str, Any]:
        return {"name": body.name}

    @app.get("/probe/conflict")
    async def conflict() -> None:
        raise ApiError(409, "用户名已存在")

    return app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=_app_with_probe_routes()), base_url="http://test"
    ) as http:
        yield http


async def test_validation_failure_returns_422_in_the_envelope(client):
    response = await client.post("/probe", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body["data"] is None
    assert "参数校验失败" in body["message"]


async def test_business_error_carries_its_real_status_and_message(client):
    response = await client.get("/probe/conflict")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == 409
    assert body["message"] == "用户名已存在"
    assert body["data"] is None
