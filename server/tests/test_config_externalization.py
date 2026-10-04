"""TICKET-027：配置外置的防回归扫描。

Seam：`core.config` 的**字段默认值**与源码字面量（配置来源改变，行为不变），
外加 `db.session.Database` 对缺失连接串的显式拒绝。

本文件不实例化 `Settings()`：真实环境里的 `.env` 会覆盖默认值，而本票要断言的
恰恰是「源码/默认值里不再出现凭据」。故只读 `model_fields` 的 default 与
`config.py` 的文本。
"""

import ast
import re
from pathlib import Path

import pytest

from core.config import Settings
from db.session import Database

CONFIG_PATH = Path(__file__).resolve().parents[1] / "core" / "config.py"

# 外置前的历史硬编码值：源码不得再出现（含注释）。
FORBIDDEN_LITERALS = (
    "12345678",  # Neo4j 口令
    "root:123456@",  # 关系库连接串里的口令
    "root:root@",  # 工作区里未提交的临时口令
    "medi-sentinel-jwt-secret",  # 令牌签名密钥
    "mysql+aiomysql://",  # 生产连接串
)

# 敏感字段：默认值必须留空，由环境变量 / `.env` 提供。
MUST_BE_EMPTY_DEFAULTS = (
    "database_url",
    "neo4j_password",
    "jwt_secret_key",
    "openai_api_key",
)

_CREDENTIAL_URL = re.compile(
    r"^[a-z][a-z0-9+.\-]*://[^/@\s]+:[^/@\s]+@", re.IGNORECASE
)
_API_KEY = re.compile(r"sk-[A-Za-z0-9._\-]{8,}")
_HARDCODED_PASSWORD = re.compile(r"^\d{6,}$")


def _string_literals(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


@pytest.mark.parametrize("literal", FORBIDDEN_LITERALS)
def test_config_source_does_not_reintroduce_historical_secrets(literal):
    source = CONFIG_PATH.read_text(encoding="utf-8")

    assert literal not in source, f"config.py 又出现硬编码凭据：{literal!r}"


def test_config_string_literals_carry_no_credentials():
    literals = _string_literals(CONFIG_PATH.read_text(encoding="utf-8"))

    offenders = [
        literal
        for literal in literals
        if _CREDENTIAL_URL.match(literal)
        or _API_KEY.search(literal)
        or _HARDCODED_PASSWORD.match(literal)
    ]

    assert offenders == [], f"config.py 字面量疑似凭据：{offenders!r}"


@pytest.mark.parametrize("field", MUST_BE_EMPTY_DEFAULTS)
def test_sensitive_field_default_is_blank(field):
    default = Settings.model_fields[field].default

    assert default == "", f"{field} 默认值必须为空，由 .env 提供"


def test_database_refuses_to_start_without_a_connection_string():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Database("")


def test_blank_env_value_falls_back_to_the_code_default(monkeypatch):
    """`.env.example` 里的空值不能被当成「显式置空」而覆盖默认值。

    `_env_file=None` 跳过真实 `.env`，只让这个空环境变量参与解析，断言稳定。
    """
    monkeypatch.setenv("NEO4J_URI", "")

    settings = Settings(_env_file=None)

    assert settings.neo4j_uri == "bolt://127.0.0.1:7687"
