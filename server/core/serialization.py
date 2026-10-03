"""统一的时间序列化器（SPEC.md 5.1）。

线上格式对所有端点一致：日期时间为 `YYYY-MM-DD HH:mm:ss`，日期为
`YYYY-MM-DD`。Pydantic 默认把 `datetime` 序列化为 ISO-8601（带 `T` 与小数秒），
而 FastAPI 的响应序列化正好走 Pydantic 的 `dump_python(mode="json")`，所以凡是
对外的响应字段都用下面的 `ApiDateTime` / `ApiDate` 注解，而不是裸 `datetime`。

`PlainSerializer` 保留字段的 JSON Schema 为 `type: string` + `format: date-time`，
契约因此仍把该字段表达为时间戳，而载荷承载 SPEC.md 5.1 固定的格式。请求侧
（查询参数等）不经过这里：解析由 FastAPI 决定，本模块只约束“我们发出什么”。
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


def format_datetime(value: datetime) -> str:
    return value.strftime(DATETIME_FORMAT)


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(format_datetime, return_type=str, when_used="json"),
    # `PlainSerializer(return_type=str)` alone would drop the timestamp marker
    # from the generated OpenAPI; keep declaring the field as a timestamp.
    WithJsonSchema({"type": "string", "format": "date-time"}),
]
ApiDate = Annotated[
    date,
    PlainSerializer(format_date, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date"}),
]
