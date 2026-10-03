from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every configurable value in one place (SPEC.md 5.1 / 7.1)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "MediSentinel"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # Credentials stay exactly as the reference implementation had them (SPEC.md 7.1):
    # hardcoded defaults, overridable by environment for tests only.
    database_url: str = "mysql+aiomysql://root:root@127.0.0.1:3306/medi_sentinel"

    # AC-B-24: during a 20-consult burst no single synchronous stall on the
    # event loop may exceed this. The blocking-call detection test reads it.
    event_loop_block_threshold_ms: int = 250

    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
