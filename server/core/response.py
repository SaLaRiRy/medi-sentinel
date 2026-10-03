"""The single response envelope (SPEC.md 5.1)."""

from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

JSON_MEDIA_TYPE = "application/json; charset=utf-8"

T = TypeVar("T")

#: The `SPEC.md` 5.2 error table, used for the declared error branches.
ERROR_DESCRIPTIONS = {
    400: "请求语义错误",
    401: "未认证或认证失效",
    403: "已认证但无权限",
    404: "资源不存在",
    409: "状态冲突",
    413: "载荷过大",
    422: "参数校验失败",
    500: "服务内部错误",
    502: "上游返回非法",
    503: "上游不可用",
    504: "上游超时",
}


class Envelope(BaseModel, Generic[T]):
    code: int = 200
    message: str = "操作成功"
    data: T | None = None


class PagePayload(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class EnvelopeJSONResponse(JSONResponse):
    """JSON responses carry the charset, and non-ASCII stays unescaped."""

    media_type = JSON_MEDIA_TYPE


def success(data: T | None = None, message: str = "操作成功") -> Envelope[T]:
    return Envelope(code=200, message=message, data=data)


def page_result(
    items: list[T],
    total: int,
    page: int,
    page_size: int,
    message: str = "操作成功",
) -> Envelope[PagePayload[T]]:
    payload = PagePayload(items=items, total=total, page=page, page_size=page_size)
    return Envelope(code=200, message=message, data=payload)


def error_responses(*codes: int) -> dict[int, dict[str, object]]:
    """Declared error branches that carry the same envelope as the handler.

    Every failure exits through `core.errors` as `Envelope[None]` (SPEC.md 5.1 /
    5.2), so a route that documents its error codes uses this helper instead of
    letting FastAPI's bare `HTTPValidationError` stand in for one of them.
    """
    return {
        code: {
            "model": Envelope[None],
            "description": ERROR_DESCRIPTIONS.get(code, ""),
        }
        for code in codes
    }
