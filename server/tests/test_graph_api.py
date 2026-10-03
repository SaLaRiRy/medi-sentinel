"""TICKET-016: the graph-view REST surface (SPEC.md 5.4「知识图谱」).

Four public read-only endpoints (full graph, entity neighbourhood, keyword
search, disease detail), the authenticated symptom inference endpoint, and the
admin stats endpoint. The graph store is replaced at B-3 by an in-memory stub,
so no Neo4j is started; the adapter's own Cypher and payload building are
asserted separately in `test_graph_adapter.py`.
"""

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from core.deps import ROLE_ADMIN, ROLE_DOCTOR, ROLE_USER, Principal, get_principal
from skills.orchestration import OrchestrationPorts
from tests.doubles import HitsRetrievalPort, StubLlmPort

ADMIN = Principal(user_id=1, role=ROLE_ADMIN)
DOCTOR = Principal(user_id=2, role=ROLE_DOCTOR)
PATIENT = Principal(user_id=3, role=ROLE_USER)

FULL_GRAPH = {
    "nodes": [
        {"id": "Disease:高血压", "name": "高血压", "label": "Disease"},
        {"id": "Symptom:头痛", "name": "头痛", "label": "Symptom"},
        {"id": "Department:心血管内科", "name": "心血管内科", "label": "Department"},
    ],
    "edges": [
        {
            "source": "Disease:高血压",
            "target": "Symptom:头痛",
            "type": "HAS_SYMPTOM",
        },
        {
            "source": "Disease:高血压",
            "target": "Department:心血管内科",
            "type": "BELONGS_TO",
        },
    ],
}

SUBGRAPH = {
    "nodes": [
        {"id": "Disease:高血压", "name": "高血压", "label": "Disease"},
        {"id": "Symptom:头痛", "name": "头痛", "label": "Symptom"},
    ],
    "edges": [
        {
            "source": "Disease:高血压",
            "target": "Symptom:头痛",
            "type": "HAS_SYMPTOM",
        }
    ],
}

SEARCH_RESULTS = [
    {"id": "Disease:高血压", "name": "高血压", "label": "Disease"},
    {"id": "Symptom:头痛", "name": "头痛", "label": "Symptom"},
]

DETAIL = {
    "disease": "高血压",
    "department": "心血管内科",
    "nodes": [
        {"id": "Disease:高血压", "name": "高血压", "label": "Disease"},
        {"id": "Drug:氨氯地平", "name": "氨氯地平", "label": "Drug"},
    ],
    "edges": [
        {
            "source": "Disease:高血压",
            "target": "Drug:氨氯地平",
            "type": "RECOMMEND_DRUG",
        }
    ],
}

COUNTS = {"Disease": 3, "Symptom": 19}
CANDIDATE_RECORDS = [
    {
        "disease": "感冒",
        "matched_symptoms": ["发热", "头痛", "咳嗽"],
        "department": "呼吸内科",
    },
    {"disease": "偏头痛", "matched_symptoms": ["头痛"], "department": None},
]


class StubGraphPort:
    """Canned graph payloads that record every call (SPEC.md 4.1 B-3)."""

    def __init__(self, *, fail: bool = False, error: Exception | None = None) -> None:
        self.fail = fail
        self.error = error
        self.calls: list[tuple] = []

    def _check(self) -> None:
        if self.fail:
            raise RuntimeError("graph unavailable")
        if self.error is not None:
            raise self.error

    async def infer_diseases(self, symptoms):
        self.calls.append(("infer_diseases", tuple(symptoms)))
        self._check()
        return CANDIDATE_RECORDS

    async def full_graph(self):
        self.calls.append(("full_graph",))
        self._check()
        return FULL_GRAPH

    async def neighbors(self, entity, depth=1):
        self.calls.append(("neighbors", entity, depth))
        self._check()
        return None if entity == "不存在" else SUBGRAPH

    async def search_entities(self, keyword):
        self.calls.append(("search_entities", keyword))
        self._check()
        return SEARCH_RESULTS

    async def disease_detail(self, name):
        self.calls.append(("disease_detail", name))
        self._check()
        return None if name == "不存在" else DETAIL

    async def node_counts(self):
        self.calls.append(("node_counts",))
        self._check()
        return COUNTS


@pytest.fixture
def graph_port() -> StubGraphPort:
    return StubGraphPort()


@pytest.fixture
def app(database_url, graph_port):
    from core.config import Settings
    from main import create_app

    ports = OrchestrationPorts(
        graph=graph_port, retrieval=HitsRetrievalPort(), llm=StubLlmPort()
    )
    return create_app(Settings(database_url=database_url), ports=ports)


@asynccontextmanager
async def client_as(app, principal):
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as http:
                yield http
    finally:
        app.dependency_overrides.pop(get_principal, None)


async def test_the_four_read_only_graph_endpoints_are_public(app):
    async with client_as(app, None) as client:
        overview = await client.get("/api/v1/graph")
        neighbours = await client.get("/api/v1/graph/entities/高血压/neighbors")
        search = await client.get("/api/v1/graph/search", params={"keyword": "高"})
        detail = await client.get("/api/v1/graph/diseases/高血压")

    assert overview.status_code == 200
    assert overview.json()["data"] == FULL_GRAPH
    assert neighbours.status_code == 200
    assert neighbours.json()["data"] == SUBGRAPH
    assert search.status_code == 200
    assert search.json()["data"] == SEARCH_RESULTS
    assert detail.status_code == 200
    assert detail.json()["data"] == DETAIL


async def test_neighbours_depth_is_real_and_bounded(app, graph_port):
    async with client_as(app, None) as client:
        default = await client.get("/api/v1/graph/entities/高血压/neighbors")
        deeper = await client.get(
            "/api/v1/graph/entities/高血压/neighbors", params={"depth": 3}
        )
        too_shallow = await client.get(
            "/api/v1/graph/entities/高血压/neighbors", params={"depth": 0}
        )
        too_deep = await client.get(
            "/api/v1/graph/entities/高血压/neighbors", params={"depth": 6}
        )

    assert default.status_code == 200
    assert deeper.status_code == 200
    assert ("neighbors", "高血压", 1) in graph_port.calls
    assert ("neighbors", "高血压", 3) in graph_port.calls
    assert too_shallow.status_code == 422
    assert too_shallow.json()["code"] == 422
    assert too_deep.status_code == 422


async def test_search_requires_a_keyword(app):
    async with client_as(app, None) as client:
        response = await client.get("/api/v1/graph/search")

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_unknown_entity_and_disease_are_404(app):
    async with client_as(app, None) as client:
        entity = await client.get("/api/v1/graph/entities/不存在/neighbors")
        disease = await client.get("/api/v1/graph/diseases/不存在")

    assert entity.status_code == 404
    assert entity.json()["code"] == 404
    assert disease.status_code == 404
    assert disease.json()["code"] == 404


async def test_graph_unavailable_is_503_on_every_endpoint(database_url):
    from core.config import Settings
    from main import create_app

    app = create_app(
        Settings(database_url=database_url),
        ports=OrchestrationPorts(
            graph=StubGraphPort(fail=True),
            retrieval=HitsRetrievalPort(),
            llm=StubLlmPort(),
        ),
    )
    async with client_as(app, ADMIN) as client:
        responses = [
            await client.get("/api/v1/graph"),
            await client.get("/api/v1/graph/entities/高血压/neighbors"),
            await client.get("/api/v1/graph/search", params={"keyword": "高"}),
            await client.get("/api/v1/graph/diseases/高血压"),
            await client.post("/api/v1/graph/infer", json={"symptoms": ["头痛"]}),
            await client.get("/api/v1/graph/stats"),
        ]

    for response in responses:
        assert response.status_code == 503
        assert response.json()["code"] == 503
        assert response.json()["message"]


async def test_a_projection_defect_is_500_not_an_upstream_outage(database_url):
    """A malformed payload is our bug, not the store being down (SPEC.md 5.2)."""
    from core.config import Settings
    from main import create_app

    app = create_app(
        Settings(database_url=database_url),
        ports=OrchestrationPorts(
            graph=StubGraphPort(error=KeyError("labels")),
            retrieval=HitsRetrievalPort(),
            llm=StubLlmPort(),
        ),
    )
    async with client_as(app, ADMIN) as client:
        response = await client.get("/api/v1/graph")

    assert response.status_code == 500
    assert response.json()["code"] == 500
    assert response.json()["message"]


async def test_infer_ranks_by_coverage_and_never_exposes_probability(app):
    async with client_as(app, PATIENT) as client:
        response = await client.post(
            "/api/v1/graph/infer", json={"symptoms": ["头疼", "发烧"]}
        )

    assert response.status_code == 200
    candidates = response.json()["data"]
    assert candidates == [
        {
            "disease": "感冒",
            "match_count": 2,
            "coverage": 1.0,
            "department": "呼吸内科",
            "matched_symptoms": ["头痛", "发热"],
        },
        {
            "disease": "偏头痛",
            "match_count": 1,
            "coverage": 0.5,
            "department": None,
            "matched_symptoms": ["头痛"],
        },
    ]
    assert all("probability" not in candidate for candidate in candidates)


async def test_infer_normalizes_colloquial_symptoms_before_querying(app, graph_port):
    async with client_as(app, PATIENT) as client:
        await client.post("/api/v1/graph/infer", json={"symptoms": ["头疼", "拉肚子"]})

    assert ("infer_diseases", ("头痛", "腹泻")) in graph_port.calls


async def test_infer_persists_exactly_one_graph_inference_span(app):
    """AC-B-28: the Skill call leaves exactly one span, and it is persisted."""
    from sqlalchemy import select

    from models.trace import TraceSpanRow

    async with client_as(app, PATIENT) as client:
        response = await client.post(
            "/api/v1/graph/infer", json={"symptoms": ["头痛", "发热"]}
        )
        assert response.status_code == 200
        async with app.state.database.session_factory() as session:
            rows = list((await session.execute(select(TraceSpanRow))).scalars().all())

    assert [row.name for row in rows] == ["graph-inference"]
    assert rows[0].status == "ok"
    assert rows[0].trace_id


async def test_infer_rejects_an_empty_symptom_list(app):
    async with client_as(app, PATIENT) as client:
        response = await client.post("/api/v1/graph/infer", json={"symptoms": []})

    assert response.status_code == 422
    assert response.json()["code"] == 422


@pytest.mark.parametrize("principal", [None, DOCTOR, PATIENT])
async def test_infer_requires_an_authenticated_allowed_role(app, principal):
    async with client_as(app, principal) as client:
        response = await client.post("/api/v1/graph/infer", json={"symptoms": ["头痛"]})

    if principal is None:
        assert response.status_code == 401
    else:
        # Doctor and patient are both allowed by SPEC.md 5.4.
        assert response.status_code == 200


async def test_stats_is_admin_only(app):
    async with client_as(app, None) as client:
        anonymous = await client.get("/api/v1/graph/stats")
    async with client_as(app, DOCTOR) as client:
        forbidden = await client.get("/api/v1/graph/stats")
    async with client_as(app, ADMIN) as client:
        allowed = await client.get("/api/v1/graph/stats")

    assert anonymous.status_code == 401
    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["data"] == COUNTS


def test_the_graph_endpoints_are_published_in_the_contract(app):
    paths = app.openapi()["paths"]

    assert "/api/v1/graph" in paths
    assert "/api/v1/graph/entities/{name}/neighbors" in paths
    assert "/api/v1/graph/search" in paths
    assert "/api/v1/graph/diseases/{name}" in paths
    assert "/api/v1/graph/infer" in paths
    assert "/api/v1/graph/stats" in paths
