"""契约生成期的统一修正（C-1，SPEC.md 5.6）。

FastAPI 会为每个带校验输入的端点自动声明一个 422 `HTTPValidationError` 分支，
但本应用唯一的失败外壳是 `Envelope`（`core/errors.py`，SPEC.md 5.1）。契约必须
描述真实会发出的响应，否则「每个端点的实际响应均满足契约 Schema（含成功与全部
错误码分支）」（AC-B-41）就无从谈起。

`install_envelope_error_responses` 在生成 OpenAPI 后把校验错误分支改写成统一外壳，
因此 `contracts/openapi.json` 依旧由应用生成（不手改），只是声明的 422 与实际
响应一致。这是契约生成侧的修正，不改任何端点的运行时行为。
"""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from core.response import ERROR_ENVELOPE_REF, Envelope

#: FastAPI 为 `Envelope[None]` 生成的组件名，恰好是失败外壳的形状。
ERROR_ENVELOPE_NAME = ERROR_ENVELOPE_REF.rsplit("/", 1)[-1]
ENVELOPE_MEDIA_TYPE = "application/json; charset=utf-8"


def _error_envelope_schema() -> dict[str, Any]:
    return Envelope[None].model_json_schema(
        ref_template="#/components/schemas/{model}"
    )


def _uses_validation_error(schema: dict[str, Any]) -> bool:
    return str(schema.get("$ref", "")).endswith("HTTPValidationError")


def _rewrite_validation_error_responses(contract: dict[str, Any]) -> None:
    """Wherever FastAPI declared `HTTPValidationError`, declare the envelope."""
    components = contract.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault(ERROR_ENVELOPE_NAME, _error_envelope_schema())

    for path_item in contract.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            for response in responses.values():
                content = response.get("content")
                if not isinstance(content, dict):
                    continue
                if any(
                    _uses_validation_error(media.get("schema", {}))
                    for media in content.values()
                ):
                    response["content"] = {
                        ENVELOPE_MEDIA_TYPE: {
                            "schema": {"$ref": ERROR_ENVELOPE_REF}
                        }
                    }


def install_envelope_error_responses(app: FastAPI) -> None:
    """Make the generated contract declare the envelope for the error branches."""
    original: Callable[[], dict[str, Any]] = app.openapi

    def openapi() -> dict[str, Any]:
        contract = original()
        _rewrite_validation_error_responses(contract)
        return contract

    app.openapi = openapi  # type: ignore[method-assign]
