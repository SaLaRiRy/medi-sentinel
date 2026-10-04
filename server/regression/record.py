"""离线录制：确定性端口 + 脚本化 LLM → 版本化基线（AC-B-34）。

仓库默认没有大模型适配器，因此录制不依赖任何外部服务：图谱走仓库内本体
（`graph/ontology.py`）的纯计算假实现，检索走本地固定语料，LLM 走每条的脚本化
分片。真适配器落地后以它录 `v2`，`v1` 不改（ticket 023 §5）。
"""

from __future__ import annotations

import math
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from graph.ontology import RELATIONSHIPS, _NODES_BY_LABEL
from regression.divergences import ai_chain_ids, http_contract_ids, load_registry
from regression.ports import RecordingGraphPort, RecordingLlmPort, RecordingRetrievalPort
from regression.schema import Baseline, BaselineCase, CaseSet, RegressionCase, RouteView
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.ports import UnavailableGraphPort, UnavailableRetrievalPort
from skills.trace import InMemoryTraceSink

#: 本地固定语料：录制检索支路用，不触碰 Chroma / 嵌入服务。
FIXTURE_CORPUS: tuple[dict[str, Any], ...] = (
    {
        "content": "高血压患者应低盐饮食、规律服用氨氯地平并定期做血压测量，出现头晕头痛应及时就医。",
        "file_name": "高血压防治指南.md",
        "distance": 0.10,
        "keywords": ("高血压", "血压", "头晕", "头痛", "心悸", "胸闷"),
    },
    {
        "content": "发热、咳嗽、咽痛多为感冒表现，应多饮水、注意休息，必要时做血常规检查。",
        "file_name": "感冒与流感指南.md",
        "distance": 0.20,
        "keywords": ("发热", "发烧", "咳嗽", "咽痛", "嗓子痛", "流涕", "鼻塞", "头痛"),
    },
    {
        "content": "糖尿病患者需控制饮食、规律运动，并按医嘱使用二甲双胍或胰岛素，定期监测空腹血糖。",
        "file_name": "糖尿病管理指南.md",
        "distance": 0.30,
        "keywords": ("糖尿病", "多饮", "多尿", "多食", "乏力"),
    },
)


class FixtureGraphPort:
    """仓库内本体的纯计算假实现：不访问 Neo4j。"""

    async def infer_diseases(
        self, symptoms: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        present = set(symptoms)
        records: list[Mapping[str, Any]] = []
        for disease in _NODES_BY_LABEL["Disease"]:
            disease_symptoms = [
                end
                for rel, _sl, start, _el, end in RELATIONSHIPS
                if rel == "HAS_SYMPTOM" and start == disease
            ]
            matched = [symptom for symptom in disease_symptoms if symptom in present]
            if not matched:
                continue
            department = next(
                (
                    end
                    for rel, _sl, start, _el, end in RELATIONSHIPS
                    if rel == "BELONGS_TO" and start == disease
                ),
                None,
            )
            records.append(
                {
                    "disease": disease,
                    "matched_symptoms": matched,
                    "department": department,
                }
            )
        return records

    async def full_graph(self) -> Mapping[str, Any]:
        raise RuntimeError("录制不读取整图")

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any] | None:
        raise RuntimeError("录制不读取邻接")

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("录制不检索实体")

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None:
        raise RuntimeError("录制不读取疾病详情")

    async def node_counts(self) -> Mapping[str, int]:
        raise RuntimeError("录制不统计节点")


class FixtureRetrievalPort:
    """本地语料的确定性检索：关键词命中排序，不访问向量索引/嵌入服务。"""

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]:
        scored = [
            (
                -sum(1 for keyword in doc["keywords"] if keyword in query),
                doc["distance"],
                doc,
            )
            for doc in FIXTURE_CORPUS
        ]
        scored.sort(key=lambda item: (item[0], item[1]))
        if scored[0][0] == 0:
            selected = list(FIXTURE_CORPUS[:top_k])
        else:
            selected = [doc for score, _distance, doc in scored if score < 0][:top_k]
        return [
            {
                "content": doc["content"],
                "metadata": {"file_name": doc["file_name"]},
                "distance": doc["distance"],
            }
            for doc in selected
        ]


class ScriptedLlmPort:
    """脚本化 LLM：按用例预置的分片作答（不访问任何模型）。"""

    def __init__(self, chunks: Sequence[str]) -> None:
        self._chunks = list(chunks)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk


def fixture_ports(case: RegressionCase) -> tuple[Any, Any, Any]:
    graph = FixtureGraphPort() if case.graph == "hits" else UnavailableGraphPort()
    retrieval = (
        FixtureRetrievalPort() if case.retrieval == "hits" else UnavailableRetrievalPort()
    )
    return graph, retrieval, ScriptedLlmPort(case.answer)


def _skills_of(spans: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        span["name"]: span["detail"]
        for span in spans
        if span["name"] != "llm" and span.get("detail") is not None
    }


async def record_case(case: RegressionCase) -> BaselineCase:
    graph, retrieval, llm = fixture_ports(case)
    recording_graph = RecordingGraphPort(graph)
    recording_retrieval = RecordingRetrievalPort(retrieval)
    recording_llm = RecordingLlmPort(llm)
    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(
        OrchestrationPorts(
            graph=recording_graph, retrieval=recording_retrieval, llm=recording_llm
        ),
        sink,
    )
    request = ChatRequest(
        session_id=case.session_id,
        message=case.message,
        explicit_symptoms=case.explicit_symptoms or None,
    )

    started = time.perf_counter()
    frames = [
        frame async for frame in orchestrator.run(request, session_id=case.session_id)
    ]
    # 记录耗时以毫秒向上取整并夹到 ≥1：一次完成的问诊耗时非零，而离线确定性
    # 端口下的亚毫秒样本若截断成 0，P95 指标就失去意义（ticket 023 §8 的
    # 「latency 取 baseline 录制值」）。
    duration_ms = max(1, math.ceil((time.perf_counter() - started) * 1000))

    spans = [span.model_dump(mode="json") for span in sink.spans]
    route = sink.routes[0]
    answer = "".join(
        frame["content"] for frame in frames if frame["type"] == "content"
    )
    return BaselineCase(
        id=case.id,
        group=case.group,
        red_flag=case.group == "red_flag",
        input=case.input(),
        duration_ms=duration_ms,
        route=RouteView(
            skills_run=list(route.skills_run),
            skills_skipped=[
                {"skill": skipped.skill, "reason": skipped.reason}
                for skipped in route.skills_skipped
            ],
        ),
        frames=frames,
        skills=_skills_of(spans),
        ports={
            "graph": recording_graph.responses,
            "retrieval": recording_retrieval.responses,
        },
        llm_chunks=recording_llm.chunks,
        spans=spans,
        answer=answer,
        exemptions=list(case.exemptions),
    )


async def record_case_set(case_set: CaseSet) -> Baseline:
    """录制整套用例，产出可回放的版本化基线。"""
    cases = [await record_case(case) for case in case_set.cases]
    registry = load_registry()
    return Baseline(
        version=case_set.version,
        case_set_version=case_set.version,
        created_at=datetime.now(UTC).isoformat(),
        cases=cases,
        exempt_divergences=ai_chain_ids(registry),
        recorded_divergences=http_contract_ids(registry),
    )
