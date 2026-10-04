"""TICKET-026：演示数据 `server/seeds/demo_v1.sql` 的冒烟验证。

两条腿：

* **静态断言**（任何环境都跑）：文件是 DML-only、每条 `INSERT` 都是 upsert、编号固定
  落在 9001+ 段、演示账号口令能用 `core.security.verify_password` 通过登录校验。
* **集成断言**（目标库可达时）：在一次性 schema 上 `alembic upgrade head`，把**真实
  文件**连续加载两次，断言关键表行数与外键完整性。目标库不可达时跳过——演示数据本身
  就是往 MySQL 灌的，冒烟验证在目标库上做才有意义。
"""

import asyncio
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from core.security import verify_password

SERVER_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = SERVER_ROOT / "seeds" / "demo_v1.sql"
DEMO_PASSWORD = "123456"

#: 一次性验证 schema；与开发库 `medi_sentinel` 分开，验证完即删。
CHECK_SCHEMA = "medi_sentinel_demo_seedcheck"

ACCOUNT_USERS = ("patient1", "doctor1", "admin1")


def _sql_text() -> str:
    return SEED_PATH.read_text(encoding="utf-8")


def _statements() -> list[str]:
    """去掉 `--` 注释后按 `;` 切分；种子数据里没有含分号的字符串字面量。"""
    body = "\n".join(
        line for line in _sql_text().splitlines() if not line.strip().startswith("--")
    )
    return [statement.strip() for statement in body.split(";") if statement.strip()]


def test_seed_file_exists_and_is_dml_only_upserts():
    assert SEED_PATH.is_file(), f"缺少演示数据文件：{SEED_PATH}"
    statements = _statements()
    assert statements, "演示数据文件为空"

    for statement in statements:
        upper = statement.upper()
        assert upper.startswith("INSERT INTO "), statement[:60]
        assert "ON DUPLICATE KEY UPDATE" in upper, statement[:60]
        for forbidden in (
            "CREATE TABLE",
            "ALTER TABLE",
            "DROP TABLE",
            "TRUNCATE",
            "DELETE FROM",
        ):
            assert forbidden not in upper, f"{forbidden} 出现在：{statement[:60]}"


def test_seed_uses_fixed_ids_in_the_9000_segment():
    """编号固定，且不落进既有数据段（既有：1 号患者、1–3 号会话与知识文件）。"""
    all_ids: list[int] = []
    for statement in _statements():
        values = statement.split("VALUES", 1)[1]
        ids = [int(match.group(1)) for match in re.finditer(r"\(\s*(\d+)\s*,", values)]
        assert ids, statement[:60]
        assert min(ids) >= 9000, f"存在低于 9000 的固定编号：{sorted(ids)[:5]}"
        assert len(set(ids)) == len(ids), f"同一张表内编号重复：{statement[:60]}"
        all_ids.extend(ids)

    assert all_ids, "没有解析出任何固定编号"


def test_seeded_account_passwords_pass_the_real_login_comparator():
    """口令必须能过 `AuthService.login` 用的比对函数（明文相等）。"""
    found: dict[str, str] = {}
    account_row = re.compile(r"\(\s*\d+\s*,\s*'([^']+)'\s*,\s*'([^']*)'")
    for statement in _statements():
        if not re.match(r"INSERT INTO (t_user|t_doctor|t_admin)\b", statement):
            continue
        for match in account_row.finditer(statement):
            found[match.group(1)] = match.group(2)

    missing = sorted(set(ACCOUNT_USERS) - set(found))
    assert not missing, f"缺少演示账号：{missing}"
    for username in ACCOUNT_USERS:
        assert verify_password(DEMO_PASSWORD, found[username]), username


# ---------------------------------------------------------------------------
# 集成：在目标 MySQL 上真正加载两次
# ---------------------------------------------------------------------------

EXPECTED_COUNTS = {
    "users": 3,
    "doctors": 3,
    "admins": 1,
    "departments": 4,
    "appointments": 3,
    "health_records": 2,
    "consults": 3,
    "replies": 1,
    "articles": 3,
    "notices": 2,
    "sessions": 2,
    "messages": 4,
    # 外键完整性：以下三项必须为 0
    "orphan_replies": 0,
    "orphan_messages": 0,
    "dangling_appointments": 0,
}

COUNT_QUERIES = {
    "users": "SELECT COUNT(*) FROM t_user WHERE id IN (9001, 9002, 9003)",
    "doctors": "SELECT COUNT(*) FROM t_doctor WHERE id IN (9001, 9002, 9003)",
    "admins": "SELECT COUNT(*) FROM t_admin WHERE id = 9001",
    "departments": (
        "SELECT COUNT(*) FROM t_department WHERE id IN (9001, 9002, 9003, 9004)"
    ),
    "appointments": "SELECT COUNT(*) FROM t_appointment WHERE id IN (9001, 9002, 9003)",
    "health_records": "SELECT COUNT(*) FROM t_health_record WHERE id IN (9001, 9002)",
    "consults": "SELECT COUNT(*) FROM t_doctor_consult WHERE id IN (9001, 9002, 9003)",
    "replies": "SELECT COUNT(*) FROM t_doctor_reply WHERE id = 9001",
    "articles": "SELECT COUNT(*) FROM t_article WHERE id IN (9001, 9002, 9003)",
    "notices": "SELECT COUNT(*) FROM t_notice WHERE id IN (9001, 9002)",
    "sessions": "SELECT COUNT(*) FROM t_consult_session WHERE id IN (9001, 9002)",
    "messages": (
        "SELECT COUNT(*) FROM t_consult_message WHERE id IN (9001, 9002, 9003, 9004)"
    ),
    "orphan_replies": (
        "SELECT COUNT(*) FROM t_doctor_reply r "
        "LEFT JOIN t_doctor_consult c ON r.consult_id = c.id "
        "WHERE r.id = 9001 AND c.id IS NULL"
    ),
    "orphan_messages": (
        "SELECT COUNT(*) FROM t_consult_message m "
        "LEFT JOIN t_consult_session s ON m.session_id = s.id "
        "WHERE m.id IN (9001, 9002, 9003, 9004) AND s.id IS NULL"
    ),
    "dangling_appointments": (
        "SELECT COUNT(*) FROM t_appointment a "
        "LEFT JOIN t_user u ON a.user_id = u.id "
        "LEFT JOIN t_doctor d ON a.doctor_id = d.id "
        "WHERE a.id IN (9001, 9002, 9003) AND (u.id IS NULL OR d.id IS NULL)"
    ),
}


def _split_database(url: str) -> tuple[str, str]:
    """把 DSN 拆成 `<服务端>/<库名>`；用于换名建库与连服务端。"""
    head, _, database = url.rpartition("/")
    return head, database


async def _create_database(server_url: str) -> None:
    engine = create_async_engine(server_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS {CHECK_SCHEMA} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    finally:
        await engine.dispose()


async def _drop_database(server_url: str) -> None:
    engine = create_async_engine(server_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP DATABASE IF EXISTS {CHECK_SCHEMA}"))
    finally:
        await engine.dispose()


def _migrate(check_url: str) -> None:
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", check_url)
    command.upgrade(config, "head")


async def _seed_and_count(check_url: str) -> dict[str, int]:
    engine = create_async_engine(check_url)
    try:
        async with engine.begin() as connection:
            for statement in _statements():
                # exec_driver_sql：原样发 SQL，避免 text() 把 '09:00' 当成绑定参数
                await connection.exec_driver_sql(statement)
        counts: dict[str, int] = {}
        async with engine.connect() as connection:
            for label, query in COUNT_QUERIES.items():
                counts[label] = int(
                    (await connection.execute(text(query))).scalar_one()
                )
        return counts
    finally:
        await engine.dispose()


def test_seed_loads_twice_on_the_target_database_with_foreign_keys_intact():
    url = get_settings().database_url
    if not url.startswith("mysql"):
        pytest.skip(f"目标库不是 MySQL（{url.split(':', 1)[0]}），跳过集成验证")

    head, _ = _split_database(url)
    server_url = f"{head}/"
    check_url = f"{head}/{CHECK_SCHEMA}"

    try:
        asyncio.run(_create_database(server_url))
    except Exception as exc:  # noqa: BLE001 - 连不上目标库就跳过，而不是误报失败
        pytest.skip(f"MySQL 不可达，跳过集成验证：{exc}")

    try:
        _migrate(check_url)
        first = asyncio.run(_seed_and_count(check_url))
        second = asyncio.run(_seed_and_count(check_url))
    finally:
        asyncio.run(_drop_database(server_url))

    assert first == EXPECTED_COUNTS, first
    assert second == first, "重复加载后行数发生变化，upsert 不幂等"
