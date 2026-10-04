from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every configurable value in one place (SPEC.md 5.1 / 7.1)."""

    # TICKET-027: `env_ignore_empty` keeps a blank value in `.env` (the shape
    # shipped by `.env.example`) from overriding a code default, so "blank" reads
    # as "use the default / not provided" for every field.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True
    )

    project_name: str = "MediSentinel"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # TICKET-027: credentials come from the environment (`.env`) only — never from
    # source. Blank means "not provided"; `db.session.Database` refuses to build and
    # raises a clear error instead of falling back to a wrong default. Tests inject
    # their own URL (SQLite memory/tmp file).
    database_url: str = ""

    # Graph store (FUNCTIONAL_SPEC 6.2/6.6): Bolt. The endpoint and user are plain
    # defaults; the password is a credential and stays blank until supplied via env.
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Vector index + embeddings (FUNCTIONAL_SPEC 6.2/6.6): local Chroma collection,
    # OpenAI-compatible embedding service. Only the key comes from the environment.
    chroma_persist_dir: str = "chroma_db"
    chroma_collection: str = "medical_knowledge"
    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.8-flash"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 2048
    embedding_batch_size: int = 10

    # Chunking and retrieval parameters (FUNCTIONAL_SPEC 5.5 / 6.6).
    chunk_size: int = 500
    chunk_overlap: int = 80
    retrieval_top_k: int = 5

    # Token rules keep the reference behaviour (FUNCTIONAL_SPEC 5.8): HS256 and a
    # 24-hour lifetime. The signing key is a credential and comes from the
    # environment; blank only for local/test runs that never leave the process.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Uploads keep the reference root and layout (FUNCTIONAL_SPEC 5.18): avatars
    # under `<upload_dir>/avatar`, served under `/uploads33`. The avatar cap is
    # what turns an oversized upload into 413 (SPEC.md 5.2).
    upload_dir: str = "D:/uploads33"
    uploads_url_prefix: str = "/uploads33"
    avatar_subdir: str = "avatar"
    avatar_max_bytes: int = 2 * 1024 * 1024

    # Knowledge uploads live under `<upload_dir>/knowledge` and carry their own
    # cap: an oversized document is 413 (SPEC.md 5.4「AI 问诊与知识库」).
    knowledge_subdir: str = "knowledge"
    knowledge_max_bytes: int = 10 * 1024 * 1024

    # AC-B-24: during a 20-consult burst no single synchronous stall on the
    # event loop may exceed this. The blocking-call detection test reads it.
    event_loop_block_threshold_ms: int = 250

    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
