"""统一的时间序列化器（SPEC.md 5.1）。

线上格式对所有端点一致：日期时间为 `YYYY-MM-DD HH:mm:ss`，日期为
`YYYY-MM-DD`。Pydantic 默认把 `datetime` 序列化为 ISO-8601（带 `T` 与小数秒），
而 FastAPI 的响应序列化正好走 Pydantic 的 `dump_python(mode="json")`，所以凡是
对外的响应字段都用下面的 `ApiDateTime` / `ApiDate` 注解，而不是裸 `datetime`。

`PlainSerializer` 会把字段的 JSON Schema 变成裸 `type: string`，所以这里用
`WithJsonSchema` 把契约声明成**实际发出的形状**：`type: string` + `pattern`。
不再声明 `format: date-time` —— 那是 RFC3339（带 `T` 与小数秒），与 SPEC.md 5.1
规定的空格分隔格式不符，声明它会得到一个描述不了实际值的契约。请求侧（查询参数
等）不经过这里：解析由 FastAPI 决定，本模块只约束“我们发出什么”。
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def format_datetime(value: datetime) -> str:
    return value.strftime(DATETIME_FORMAT)


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(format_datetime, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": DATETIME_PATTERN}),
]
ApiDate = Annotated[
    date,
    PlainSerializer(format_date, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": DATE_PATTERN}),
]

#: 请求侧（查询参数）的时间边界。FastAPI 会把裸 `datetime` 声明成 `format:
#: date-time`（RFC3339），与 SPEC.md 5.1 固定的线上格式不符（TICKET-016 挂账 b）。
#: 这里只覆盖 Schema 声明，不改解析 —— Pydantic 仍按 `datetime` 宽松解析，客户端
#: 按契约声明的 `YYYY-MM-DD HH:mm:ss` 发送即可。
DateTimeQuery = Annotated[
    datetime,
    WithJsonSchema({"type": "string", "pattern": DATETIME_PATTERN}),
]
