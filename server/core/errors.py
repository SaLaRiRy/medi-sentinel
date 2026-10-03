"""Errors are carried by real HTTP status codes, and `code` matches (SPEC.md 5.2)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.response import Envelope, EnvelopeJSONResponse


class ApiError(Exception):
    """Business failure with an explicit status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _envelope(status_code: int, message: str) -> EnvelopeJSONResponse:
    body = Envelope[None](code=status_code, message=message, data=None)
    return EnvelopeJSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> EnvelopeJSONResponse:
        return _envelope(exc.status_code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> EnvelopeJSONResponse:
        return _envelope(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> EnvelopeJSONResponse:
        details = [
            f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
            for error in exc.errors()
        ]
        return _envelope(422, "参数校验失败：" + "；".join(details))
