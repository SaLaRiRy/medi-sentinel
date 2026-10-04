"""B-5: 健康科普文章与系统公告的异步存取（TICKET-021）。

会话拥有交易边界：这里只 flush，由 `core.deps.get_session` 决定提交或回滚。
公开读取限定 `status == 1`（`FUNCTIONAL_SPEC.md` 5.17）；文章详情另把
`view_count` 加一并 flush（5.17「每次打开详情 +1 并立即提交」）。两者相互独立、
不引用其他实体，因此没有级联。
"""

from sqlalchemy import Select, func, select

from models.article import ArticleRow, NoticeRow
from repositories.base import Repository


class ArticleRepository(Repository):
    def _query(self) -> Select:
        return select(ArticleRow)

    @staticmethod
    def _ordered(query: Select) -> Select:
        """最新在前（无数据库排序键时的稳定口径：编号倒序）。"""
        return query.order_by(ArticleRow.id.desc())

    async def list_public(
        self,
        *,
        offset: int,
        limit: int,
        keyword: str | None = None,
        category: str | None = None,
    ) -> tuple[list[ArticleRow], int]:
        """公开分页：只返回已发布文章，可按标题检索与分类过滤。"""
        criteria = [ArticleRow.status == 1]
        if keyword:
            criteria.append(ArticleRow.title.like(f"%{keyword}%"))
        if category:
            criteria.append(ArticleRow.category == category)
        return await self._page(criteria, offset=offset, limit=limit)

    async def list_page(
        self, *, offset: int, limit: int, keyword: str | None = None
    ) -> tuple[list[ArticleRow], int]:
        """管理端分页：含全部状态。"""
        criteria = []
        if keyword:
            criteria.append(ArticleRow.title.like(f"%{keyword}%"))
        return await self._page(criteria, offset=offset, limit=limit)

    async def _page(
        self, criteria: list, *, offset: int, limit: int
    ) -> tuple[list[ArticleRow], int]:
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ArticleRow)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._ordered(self._query().where(*criteria))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def find_by_id(self, article_id: int) -> ArticleRow | None:
        return await self._session.get(ArticleRow, article_id)

    async def view(self, article_id: int) -> ArticleRow | None:
        """公开详情：仅已发布，命中时浏览量 +1（FUNCTIONAL_SPEC 5.17）。"""
        article = await self.find_by_id(article_id)
        if article is None or article.status != 1:
            return None
        article.view_count = (article.view_count or 0) + 1
        await self._session.flush()
        return article

    async def create(self, **fields) -> ArticleRow:
        row = ArticleRow(**fields)
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(self, article_id: int, fields: dict) -> ArticleRow | None:
        row = await self.find_by_id(article_id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return row

    async def delete(self, article_id: int) -> bool:
        row = await self.find_by_id(article_id)
        if row is None:
            return False
        await self._session.delete(row)
        return True


class NoticeRepository(Repository):
    def _query(self) -> Select:
        return select(NoticeRow)

    @staticmethod
    def _ordered(query: Select) -> Select:
        return query.order_by(NoticeRow.id.desc())

    async def list_public(self) -> list[NoticeRow]:
        """公开列表不分页：一次返回全部已发布公告（FUNCTIONAL_SPEC 5.17）。"""
        result = await self._session.execute(
            self._ordered(self._query().where(NoticeRow.status == 1))
        )
        return list(result.scalars().all())

    async def list_page(
        self, *, offset: int, limit: int, keyword: str | None = None
    ) -> tuple[list[NoticeRow], int]:
        """管理端分页：含全部状态，可按标题检索。"""
        criteria = []
        if keyword:
            criteria.append(NoticeRow.title.like(f"%{keyword}%"))
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(NoticeRow)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._ordered(self._query().where(*criteria))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def find_by_id(self, notice_id: int) -> NoticeRow | None:
        return await self._session.get(NoticeRow, notice_id)

    async def view(self, notice_id: int) -> NoticeRow | None:
        """公开详情：仅已发布（FUNCTIONAL_SPEC 5.17）。"""
        notice = await self.find_by_id(notice_id)
        if notice is None or notice.status != 1:
            return None
        return notice

    async def create(self, **fields) -> NoticeRow:
        row = NoticeRow(**fields)
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(self, notice_id: int, fields: dict) -> NoticeRow | None:
        row = await self.find_by_id(notice_id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return row

    async def delete(self, notice_id: int) -> bool:
        row = await self.find_by_id(notice_id)
        if row is None:
            return False
        await self._session.delete(row)
        return True
