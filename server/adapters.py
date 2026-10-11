"""Concrete B-3 adapters built from `Settings` (TICKET-013, TICKET-025).

One place where the process turns configuration into the real graph and vector
stores plus the streaming model client. All three are lazily connected: the graph
driver opens on first query, the Chroma collection on first use, and the model's
HTTP client on first call, so constructing the app does not require Neo4j, Chroma
or an API key (and a missing store degrades the branch, SPEC.md 3.6).
"""

from core.config import Settings
from graph.neo4j_adapter import Neo4jGraphAdapter
from graph.store import GraphStore
from rag.chroma_adapter import ChromaVectorStore, OpenAiCompatibleEmbedder
from rag.hybrid import HybridRetriever
from rag.rerank import OnnxReranker
from rag.store import VectorStore
from skills.fallback_llm import FallbackLlmAdapter
from skills.llm_http import HttpLlmAdapter
from skills.ports import LlmPort, UnavailableLlmPort


def build_graph_store(settings: Settings) -> GraphStore:
    return Neo4jGraphAdapter(
        settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
    )


def build_vector_store(settings: Settings) -> VectorStore:
    embedder = OpenAiCompatibleEmbedder(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )
    # 混合检索（向量 + BM25 → RRF）与本地重排都写在检索端口的实现层里：编排层仍然
    # 只调一次 `search`，端口签名与调用序列不变，回归回放因此不受影响
    # （TICKET-AC-02 / TICKET-AC-04）。
    reranker = (
        OnnxReranker(settings.rerank_model_dir) if settings.rerank_model_dir else None
    )
    return HybridRetriever(
        ChromaVectorStore(
            persist_dir=settings.chroma_persist_dir,
            collection_name=settings.chroma_collection,
            embedder=embedder,
        ),
        reranker=reranker,
    )


def build_llm(settings: Settings) -> LlmPort:
    """The real streaming model adapter, or the unavailable port.

    Generation cannot degrade (SPEC.md 5.2): with no key or no base URL there is
    nothing to call, so the port that ends the stream with a 503 error frame
    stays in place (TICKET-009). With both set the app talks to the real model.
    """
    if settings.openai_api_key and settings.openai_base_url:
        primary = HttpLlmAdapter(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )
        if settings.fallback_llm_model:
            # 故障转移：同一 key 换模型名，生成能力不降级（TICKET-AC-08）。
            return FallbackLlmAdapter(
                primary,
                HttpLlmAdapter(
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                    model=settings.fallback_llm_model,
                ),
            )
        return primary
    return UnavailableLlmPort()
