"""AC-B-41 挂账（TICKET-019 统一补）：旧端点必须声明 SPEC.md 5.4 的错误分支。

007–015（以及同为「200/422 only」的 017 预约端点）此前只让 FastAPI 自动声明
422，契约里看不到真实会发出的 401 / 403 / 404 / 409 / 413 / 503 / 504。这些
端点运行时确实会发这些状态码（例如无令牌 401、非管理员 403），契约必须如实声明，
否则「每个端点的实际响应均满足契约 Schema（含全部错误码分支）」无从谈起。
"""

from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]

# SPEC.md 5.4 逐端点声明的错误码（成功码 200 不在此列，FastAPI 自动声明）。
SPEC_ERROR_BRANCHES = {
    ("/api/v1/auth/login", "post"): {400, 401, 403, 422},
    ("/api/v1/auth/register", "post"): {400, 409, 422},
    ("/api/v1/profile/info", "get"): {401},
    ("/api/v1/profile/update", "put"): {401, 422},
    ("/api/v1/profile/password", "put"): {400, 401, 422},
    ("/api/v1/profile/avatar", "post"): {401, 413, 422},
    ("/api/v1/chat/sessions", "get"): {401, 403},
    ("/api/v1/chat/sessions/{session_id}/messages", "get"): {401, 403, 404},
    ("/api/v1/chat/send", "post"): {401, 403, 409, 422, 503, 504},
    ("/api/v1/chat/admin/sessions", "get"): {401, 403, 422},
    ("/api/v1/knowledge", "get"): {401, 403, 422},
    ("/api/v1/knowledge", "post"): {401, 403, 413, 422},
    ("/api/v1/knowledge/{file_id}/revectorize", "post"): {401, 403, 404},
    ("/api/v1/knowledge/{file_id}", "delete"): {401, 403, 404},
    ("/api/v1/traces", "get"): {401, 403, 422},
    ("/api/v1/traces/{trace_id}", "get"): {401, 403, 404},
    ("/api/v1/skills", "get"): {401},
    ("/api/v1/appointments", "post"): {401, 403, 422},
    ("/api/v1/appointments/my", "get"): {401, 403},
    ("/api/v1/appointments/doctor", "get"): {401, 403},
    ("/api/v1/appointments/admin", "get"): {401, 403, 422},
    ("/api/v1/appointments/{appointment_id}/status", "put"): {401, 403, 404, 422},
    ("/api/v1/appointments/admin/{appointment_id}", "delete"): {401, 403, 404},
    ("/api/v1/consults", "post"): {401, 403, 422},
    ("/api/v1/consults/my", "get"): {401, 403},
    ("/api/v1/consults/pending", "get"): {401, 403},
    ("/api/v1/consults/{consult_id}/replies", "post"): {401, 403, 404, 409, 422},
    ("/api/v1/consults/admin", "get"): {401, 403, 422},
    ("/api/v1/consults/admin/{consult_id}", "delete"): {401, 403, 404},
}


@pytest.fixture(scope="module")
def paths() -> dict:
    from core.config import Settings
    from main import create_app

    return create_app(Settings()).openapi()["paths"]


@pytest.mark.parametrize(
    "path,method", sorted(SPEC_ERROR_BRANCHES), ids=str
)
def test_endpoint_declares_every_spec_error_branch(paths, path, method):
    declared = set(paths[path][method]["responses"])
    expected = SPEC_ERROR_BRANCHES[(path, method)]

    missing = expected - {int(code) for code in declared}
    assert not missing, f"{method.upper()} {path} 缺少错误分支：{sorted(missing)}"


@pytest.mark.parametrize(
    "path,method", sorted(SPEC_ERROR_BRANCHES), ids=str
)
def test_declared_error_branches_carry_the_envelope(paths, path, method):
    """每个非 2xx 分支声明的都是全局处理器实际返回的 `Envelope[None]`。"""
    responses = paths[path][method]["responses"]

    for code, response in responses.items():
        if code.startswith("2"):
            continue
        content = response.get("content", {})
        assert list(content) == ["application/json; charset=utf-8"], (
            f"{method.upper()} {path} 的 {code} 分支媒体类型不符：{list(content)}"
        )
        for media in content.values():
            ref = media["schema"].get("$ref", "")
            assert ref.endswith("Envelope_NoneType_"), (
                f"{method.upper()} {path} 的 {code} 分支不是统一外壳：{ref}"
            )
