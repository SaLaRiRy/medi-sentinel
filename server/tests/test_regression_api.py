"""TICKET-023 §6: the `/regression/*` endpoints (SPEC.md 5.4).

`POST /regression/runs` submits a replay job, `GET /regression/runs/{id}` polls
`{status, metrics}`, `GET /regression/baselines` lists usable versions. All three
are admin-only, and a replay never touches the running app's real ports (AC-B-35).
"""

import asyncio
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient

from skills.orchestration import OrchestrationPorts
from tests.doubles import CountingGuard

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}


async def _token(http, *, role: str) -> str:
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": "shared", "password": PASSWORDS[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _run_to_completion(http, run_id: str, headers: dict[str, str]) -> dict:
    for _ in range(200):
        response = await http.get(f"/api/v1/regression/runs/{run_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        if data["status"] in {"succeeded", "failed"}:
            return data
        await asyncio.sleep(0.01)
    raise AssertionError("replay job did not settle")


async def test_submit_then_poll_yields_the_metrics_report(client):
    token = await _token(client, role="admin")
    headers = _bearer(token)

    started = await client.post(
        "/api/v1/regression/runs",
        json={"case_set_version": "v1", "baseline_version": "v1"},
        headers=headers,
    )

    assert started.status_code == 200
    run_id = started.json()["data"]["run_id"]
    assert isinstance(run_id, str) and run_id

    data = await _run_to_completion(client, run_id, headers)
    assert data["status"] == "succeeded"
    metrics = data["metrics"]
    assert metrics["redflag_intercept_rate"] == 1.0
    assert metrics["case_count"] == 20
    assert set(metrics["latency"]) == {"intercepted", "llm", "degraded"}
    assert set(metrics["hallucination"]) == {
        "deterministic_ratio",
        "judged_ratio",
        "total",
        "judge_available",
    }


async def test_unknown_run_id_is_404(client):
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/regression/runs/does-not-exist", headers=_bearer(token)
    )

    assert response.status_code == 404


async def test_unknown_versions_are_404_on_submit(client):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/regression/runs",
        json={"case_set_version": "nope", "baseline_version": "v1"},
        headers=_bearer(token),
    )
    baseline_missing = await client.post(
        "/api/v1/regression/runs",
        json={"case_set_version": "v1", "baseline_version": "nope"},
        headers=_bearer(token),
    )

    assert response.status_code == 404
    assert baseline_missing.status_code == 404


async def test_missing_fields_are_422(client):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/regression/runs", json={}, headers=_bearer(token)
    )

    assert response.status_code == 422


async def test_the_endpoints_are_admin_only(client):
    admin = _bearer(await _token(client, role="admin"))
    user = _bearer(await _token(client, role="user"))
    body = {"case_set_version": "v1", "baseline_version": "v1"}

    assert (await client.post("/api/v1/regression/runs", json=body)).status_code == 401
    assert (
        await client.post("/api/v1/regression/runs", json=body, headers=user)
    ).status_code == 403
    assert (await client.get("/api/v1/regression/baselines")).status_code == 401
    assert (
        await client.get("/api/v1/regression/baselines", headers=user)
    ).status_code == 403
    assert (await client.get("/api/v1/regression/runs/x")).status_code == 401
    assert (
        await client.get("/api/v1/regression/runs/x", headers=user)
    ).status_code == 403

    assert (
        await client.get("/api/v1/regression/baselines", headers=admin)
    ).status_code == 200


async def test_baselines_lists_the_committed_version(client):
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/regression/baselines", headers=_bearer(token)
    )

    assert response.status_code == 200
    baselines = response.json()["data"]
    entry = next(item for item in baselines if item["baseline_version"] == "v1")
    assert entry["case_set_version"] == "v1"
    assert entry["case_count"] == 20
    assert entry["created_at"]


async def test_replay_never_calls_the_running_app_ports(database_url, accounts):
    """AC-B-35: the replay is built from the baseline, not the live adapters."""
    from core.config import Settings
    from main import create_app

    guards = OrchestrationPorts(
        graph=CountingGuard(), retrieval=CountingGuard(), llm=CountingGuard()
    )
    app = create_app(Settings(database_url=database_url), ports=guards)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            token = await _token(http, role="admin")
            headers = _bearer(token)
            started = await http.post(
                "/api/v1/regression/runs",
                json={"case_set_version": "v1", "baseline_version": "v1"},
                headers=headers,
            )
            run_id = started.json()["data"]["run_id"]
            data = await _run_to_completion(http, run_id, headers)

    assert data["status"] == "succeeded"
    assert guards.graph.calls == 0
    assert guards.retrieval.calls == 0
    assert guards.llm.calls == 0
