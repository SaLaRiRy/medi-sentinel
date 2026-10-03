"""The single response envelope (SPEC.md 5.1)."""

from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

JSON_MEDIA_TYPE = "application/json; charset=utf-8"

T = TypeVar("T")


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
