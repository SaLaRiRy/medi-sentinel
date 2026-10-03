"""TICKET-011：可观测性对外接口。

- `GET /traces/{trace_id}`：一次问诊的全部 span 与路由决策（含结构化 detail）
- `GET /traces`：按 trace_id / Skill 名 / 时间范围 / 是否降级分页检索
- `GET /skills`：五个 Skill 的名称、类别、Schema 版本与词表版本
- 追踪检索类端点仅管理员可用（401 未认证 / 403 已认证但非管理员）

TICKET-014 解除了 `contracts/` 的冻结边界：这些端点现在随生成机制进入
`contracts/openapi.json`，不再对 OpenAPI 隐藏。
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from core.deps import ROLE_ADMIN, ROLE_DOCTOR, ROLE_USER, Principal, get_principal
from skills.orchestration import OrchestrationPorts
from tests.doubles import HitsGraphPort, HitsRetrievalPort, ScriptedLlmPort

SERVER_ROOT = Path(__file__).resolve().parents[1]
MESSAGE = "我头疼发烧三天了"
ADMIN = Principal(user_id=1, role=ROLE_ADMIN)
DOCTOR = Principal(user_id=2, role=ROLE_DOCTOR)
PATIENT = Principal(user_id=3, role=ROLE_USER)
GRAPH_RECORDS = [
    {"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"}
]
RETRIEVAL_HITS = [
    {
        "content": "发热期间应多饮水、注意休息。",
        "metadata": {"file_name": "感冒与流感指南.md"},
        "distance": 0.21,
    }
]
SIX_RED_FLAGS = "胸痛，喘不上气，剧烈头痛，一侧肢体无力，意识不清，吐血"


def parse_sse(text: str) -> list[dict]:
    frames = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        frames.append(json.loads(block[len("data: ") :]))
    return frames


@pytest.fixture
def database_url(tmp_path) -> str:
    db_path = tmp_path / "observability.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
def ports() -> OrchestrationPorts:
    return OrchestrationPorts(
        graph=HitsGraphPort(GRAPH_RECORDS),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=ScriptedLlmPort(["您好，", "建议监测体温。"]),
    )


@pytest.fixture
def app(database_url, ports):
    from core.config import Settings
    from main import create_app

    return create_app(Settings(database_url=database_url), ports=ports)


@asynccontextmanager
async def client_as(app, principal):
    """Open the app with `principal` resolved by the B-4 auth seam's dependency."""
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as http:
                yield http
    finally:
        app.dependency_overrides.pop(get_principal, None)


async def test_traces_and_skills_are_published_in_the_openapi_contract(app):
    """TICKET-014：解冻后可观测性端点出现在契约里（生成 == 提交）。"""
    paths = app.openapi()["paths"]

    assert "/api/v1/chat/send" in paths
    assert "/api/v1/traces" in paths
    assert "/api/v1/traces/{trace_id}" in paths
    assert "/api/v1/skills" in paths


async def test_skills_returns_the_five_manifests_to_any_authenticated_user(app):
    async with client_as(app, DOCTOR) as client:
        response = await client.get("/api/v1/skills")

    assert response.status_code == 200
    manifests = response.json()["data"]
    assert [manifest["name"] for manifest in manifests] == [
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
    ]
    by_name = {manifest["name"]: manifest for manifest in manifests}
    assert by_name["safety-gate"] == {
        "name": "safety-gate",
        "category": "Process Rules Skill",
        "schema_version": "safety-gate-schema-v1",
        "vocabulary_version": "safety-gate-rules-v1",
    }
    assert by_name["symptom-normalization"] == {
        "name": "symptom-normalization",
        "category": "确定性能力 Skill",
        "schema_version": "symptom-normalization-schema-v1",
        "vocabulary_version": "symptom-vocabulary-v1",
    }
    assert by_name["vector-retrieval"]["schema_version"] == "vector-retrieval-schema-v1"
    assert by_name["vector-retrieval"]["vocabulary_version"] is None
    assert by_name["graph-inference"]["schema_version"] == "graph-inference-schema-v1"
    assert by_name["graph-inference"]["vocabulary_version"] is None
    assert by_name["orchestration"]["schema_version"] == "orchestration-schema-v1"
    assert by_name["orchestration"]["category"] == "编排 Skill（Agent 本体）"


async def test_skills_requires_authentication(app):
    async with client_as(app, None) as client:
        response = await client.get("/api/v1/skills")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def _run_consult(client, message: str = MESSAGE) -> str:
    response = await client.post("/api/v1/chat/send", json={"message": message})
    assert response.status_code == 200
    return next(
        frame["trace_id"]
        for frame in parse_sse(response.text)
        if frame["type"] == "trace"
    )


async def test_trace_by_id_returns_every_span_and_the_route(app):
    async with client_as(app, ADMIN) as client:
        trace_id = await _run_consult(client)
        response = await client.get(f"/api/v1/traces/{trace_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["trace_id"] == trace_id
    # 「按时间顺序还原」（AC-B-32）：span 按 started_at 升序，编排是包住其余步骤的根 span。
    names = [span["name"] for span in data["spans"]]
    assert set(names) == {
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "llm",
        "orchestration",
    }
    started = [span["started_at"] for span in data["spans"]]
    assert started == sorted(started)
    assert names[0] == "orchestration"
    assert names[-1] == "llm"
    assert all(span["trace_id"] == trace_id for span in data["spans"])
    assert data["route"]["skills_run"] == [
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
    ]


async def test_trace_by_id_exposes_the_structured_audit_detail(app):
    """003 挂账第 1 条经 API 出口可读：多红旗时审计信息不再被截断丢失。"""
    async with client_as(app, ADMIN) as client:
        trace_id = await _run_consult(client, SIX_RED_FLAGS)
        response = await client.get(f"/api/v1/traces/{trace_id}")

    safety = next(
        span for span in response.json()["data"]["spans"] if span["name"] == "safety-gate"
    )
    assert safety["detail"]["rule_version"] == "safety-gate-rules-v1"
    assert [flag["id"] for flag in safety["detail"]["red_flags"]] == [
        "chest-pain",
        "dyspnea",
        "severe-headache",
        "stroke",
        "altered-consciousness",
        "severe-bleeding",
    ]


async def test_repeated_trace_lookup_is_stable(app):
    async with client_as(app, ADMIN) as client:
        trace_id = await _run_consult(client)
        first = await client.get(f"/api/v1/traces/{trace_id}")
        second = await client.get(f"/api/v1/traces/{trace_id}")

    assert first.status_code == 200
    assert first.json() == second.json()


async def test_trace_by_id_is_404_for_an_unknown_trace(app):
    async with client_as(app, ADMIN) as client:
        response = await client.get("/api/v1/traces/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_trace_search_filters_and_pages(app):
    async with client_as(app, ADMIN) as client:
        first = await _run_consult(client)
        second = await _run_consult(client, "现在还有点咳嗽")

        by_id = await client.get("/api/v1/traces", params={"trace_id": second})
        by_skill = await client.get("/api/v1/traces", params={"skill": "graph-inference"})
        paged = await client.get("/api/v1/traces", params={"page": 1, "page_size": 1})

    assert by_id.status_code == 200
    body = by_id.json()["data"]
    assert body["total"] == 1
    assert [item["trace_id"] for item in body["items"]] == [second]
    assert body["page"] == 1 and body["page_size"] == 20

    skill_body = by_skill.json()["data"]
    assert skill_body["total"] == 2
    assert all("graph-inference" in item["skills_run"] for item in skill_body["items"])

    paged_body = paged.json()["data"]
    assert paged_body["total"] == 2
    assert len(paged_body["items"]) == 1
    assert paged_body["page_size"] == 1
    assert {first, second} >= {paged_body["items"][0]["trace_id"]}


async def test_trace_search_rejects_an_invalid_page_size(app):
    async with client_as(app, ADMIN) as client:
        response = await client.get("/api/v1/traces", params={"page_size": 0})

    assert response.status_code == 422
    assert response.json()["code"] == 422


@pytest.mark.parametrize("principal", [PATIENT, DOCTOR])
async def test_trace_endpoints_are_403_for_non_admins(app, principal):
    async with client_as(app, principal) as client:
        listing = await client.get("/api/v1/traces")
        by_id = await client.get("/api/v1/traces/whatever")

    assert listing.status_code == 403
    assert listing.json()["code"] == 403
    assert by_id.status_code == 403
    assert by_id.json()["code"] == 403


async def test_trace_endpoints_are_401_when_unauthenticated(app):
    async with client_as(app, None) as client:
        listing = await client.get("/api/v1/traces")
        by_id = await client.get("/api/v1/traces/whatever")

    assert listing.status_code == 401
    assert by_id.status_code == 401
