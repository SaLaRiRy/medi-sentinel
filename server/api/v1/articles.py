"""TICKET-021：健康科普文章端点（`SPEC.md` 5.4「内容与统计」）。

- `GET /articles`：公开分页，只读状态为 1 的文章，可按分类过滤
- `GET /articles/{id}`：公开详情，仅已发布，命中时浏览量 +1（FUNCTIONAL_SPEC 5.17）
- `GET /articles/admin`：管理员分页，含全部状态
- `POST /articles` / `PUT /articles/{id}` / `DELETE /articles/{id}`：管理员增删改查
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
from models.article import (
    ARTICLE_CATEGORY_MAX_LENGTH,
    ARTICLE_SUMMARY_MAX_LENGTH,
    ARTICLE_TITLE_MAX_LENGTH,
    ArticleRow,
)
from repositories.articles import ArticleRepository

router = APIRouter(tags=["articles"])


class ArticleRequest(BaseModel):
    """`SPEC.md` 5.3：`ArticleRequest`。"""

    title: str = Field(min_length=1, max_length=ARTICLE_TITLE_MAX_LENGTH)
    category: str | None = Field(
        default=None, max_length=ARTICLE_CATEGORY_MAX_LENGTH
    )
    summary: str | None = Field(
        default=None, max_length=ARTICLE_SUMMARY_MAX_LENGTH
    )
    content: str | None = None
    status: int = 1


class ArticleListView(BaseModel):
    """公开列表载荷：不含正文（正文只在详情返回）。"""

    id: int
    title: str
    category: str | None = None
    cover: str | None = None
    summary: str | None = None
    view_count: int = 0
    status: int = 1
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: ArticleRow) -> "ArticleListView":
        return cls(
            id=row.id,
            title=row.title,
            category=row.category,
            cover=row.cover,
            summary=row.summary,
            view_count=row.view_count or 0,
            status=row.status,
            create_time=row.create_time,
            update_time=row.update_time,
        )


class ArticleView(ArticleListView):
    """详情载荷：列表字段加正文。"""

    content: str | None = None

    @classmethod
    def of(cls, row: ArticleRow) -> "ArticleView":
        return cls(**ArticleListView.of(row).model_dump(), content=row.content)


class ArticleCreatedView(BaseModel):
    id: int


@router.get("/articles", response_model=Envelope[PagePayload[ArticleListView]])
async def list_articles(
    session: AsyncSession = Depends(get_session),
    category: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[ArticleListView]]:
    rows, total = await ArticleRepository(session).list_public(
        offset=(page - 1) * page_size,
        limit=page_size,
        keyword=keyword,
        category=category,
    )
    return page_result(
        [ArticleListView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/articles/admin",
    response_model=Envelope[PagePayload[ArticleView]],
    responses=error_responses(401, 403, 422),
)
async def admin_articles(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[ArticleView]]:
    rows, total = await ArticleRepository(session).list_page(
        offset=(page - 1) * page_size, limit=page_size, keyword=keyword
    )
    return page_result(
        [ArticleView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/articles",
    response_model=Envelope[ArticleCreatedView],
    responses=error_responses(401, 403, 422),
)
async def create_article(
    payload: ArticleRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ArticleCreatedView]:
    row = await ArticleRepository(session).create(**payload.model_dump())
    return success(ArticleCreatedView(id=row.id))


@router.put(
    "/articles/{article_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 422),
)
async def update_article(
    article_id: int,
    payload: ArticleRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    row = await ArticleRepository(session).update(article_id, payload.model_dump())
    if row is None:
        raise ApiError(404, "文章不存在")
    return success(None)


@router.delete(
    "/articles/{article_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_article(
    article_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await ArticleRepository(session).delete(article_id)
    if not deleted:
        raise ApiError(404, "文章不存在")
    return success(None)


@router.get(
    "/articles/{article_id}",
    response_model=Envelope[ArticleView],
    responses=error_responses(404),
)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
) -> Envelope[ArticleView]:
    row = await ArticleRepository(session).view(article_id)
    if row is None:
        raise ApiError(404, "文章不存在")
    return success(ArticleView.of(row))
