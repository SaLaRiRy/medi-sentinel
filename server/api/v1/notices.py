"""TICKET-021：系统公告端点（`SPEC.md` 5.4「内容与统计」）。

- `GET /notices`：公开列表，**不分页**，一次返回全部已发布公告（FUNCTIONAL_SPEC 5.17）
- `GET /notices/{id}`：公开详情，仅已发布，否则 404
- `GET /notices/admin`：管理员分页，含全部状态
- `POST /notices` / `PUT /notices/{id}` / `DELETE /notices/{id}`：管理员增删改查
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import Principal, get_session, require_admin
from core.errors import ApiError
from core.response import (
    Envelope,
    PagePayload,
    error_responses,
    page_result,
    success,
)
from core.serialization import ApiDateTime
from models.article import NOTICE_TITLE_MAX_LENGTH, NoticeRow
from repositories.articles import NoticeRepository

router = APIRouter(tags=["notices"])


class NoticeRequest(BaseModel):
    """`SPEC.md` 5.3：`NoticeRequest`。"""

    title: str = Field(min_length=1, max_length=NOTICE_TITLE_MAX_LENGTH)
    content: str = ""
    status: int = 1


class NoticeView(BaseModel):
    id: int
    title: str
    content: str | None = ""
    status: int = 1
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: NoticeRow) -> "NoticeView":
        return cls(
            id=row.id,
            title=row.title,
            content=row.content,
            status=row.status,
            create_time=row.create_time,
            update_time=row.update_time,
        )


class NoticeCreatedView(BaseModel):
    id: int


@router.get("/notices", response_model=Envelope[list[NoticeView]])
async def list_notices(
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[NoticeView]]:
    rows = await NoticeRepository(session).list_public()
    return success([NoticeView.of(row) for row in rows])


@router.get(
    "/notices/admin",
    response_model=Envelope[PagePayload[NoticeView]],
    responses=error_responses(401, 403, 422),
)
async def admin_notices(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[NoticeView]]:
    rows, total = await NoticeRepository(session).list_page(
        offset=(page - 1) * page_size, limit=page_size, keyword=keyword
    )
    return page_result(
        [NoticeView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/notices",
    response_model=Envelope[NoticeCreatedView],
    responses=error_responses(401, 403, 422),
)
async def create_notice(
    payload: NoticeRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[NoticeCreatedView]:
    row = await NoticeRepository(session).create(**payload.model_dump())
    return success(NoticeCreatedView(id=row.id))


@router.put(
    "/notices/{notice_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 422),
)
async def update_notice(
    notice_id: int,
    payload: NoticeRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    row = await NoticeRepository(session).update(notice_id, payload.model_dump())
    if row is None:
        raise ApiError(404, "公告不存在")
    return success(None)


@router.delete(
    "/notices/{notice_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_notice(
    notice_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await NoticeRepository(session).delete(notice_id)
    if not deleted:
        raise ApiError(404, "公告不存在")
    return success(None)


@router.get(
    "/notices/{notice_id}",
    response_model=Envelope[NoticeView],
    responses=error_responses(404),
)
async def get_notice(
    notice_id: int,
    session: AsyncSession = Depends(get_session),
) -> Envelope[NoticeView]:
    row = await NoticeRepository(session).view(notice_id)
    if row is None:
        raise ApiError(404, "公告不存在")
    return success(NoticeView.of(row))
