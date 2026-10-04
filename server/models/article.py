"""健康科普文章与系统公告（TICKET-021，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.11/4.3.12）。

两者都是**独立实体**，不引用也不被任何其他实体引用（`FUNCTIONAL_SPEC.md` 4.6）。
`status` 沿用通用启用/发布语义（1 已发布，其余已下架，5.10 / 5.20）；文章多出
`view_count`（详情每次访问 +1，5.17）与展示用的 `cover` / `summary`。标题在数据库
层没有唯一约束，与 `FUNCTIONAL_SPEC.md` 4.3.11/4.3.12 一致。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

ARTICLE_TITLE_MAX_LENGTH = 200
ARTICLE_CATEGORY_MAX_LENGTH = 50
ARTICLE_COVER_MAX_LENGTH = 255
ARTICLE_SUMMARY_MAX_LENGTH = 500

NOTICE_TITLE_MAX_LENGTH = 200


def _now() -> datetime:
    return datetime.now(UTC)


class ArticleRow(Base):
    __tablename__ = "t_article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(
        String(ARTICLE_TITLE_MAX_LENGTH), nullable=False
    )
    category: Mapped[str | None] = mapped_column(
        String(ARTICLE_CATEGORY_MAX_LENGTH), nullable=True
    )
    cover: Mapped[str | None] = mapped_column(
        String(ARTICLE_COVER_MAX_LENGTH), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(
        String(ARTICLE_SUMMARY_MAX_LENGTH), nullable=True
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class NoticeRow(Base):
    __tablename__ = "t_notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(
        String(NOTICE_TITLE_MAX_LENGTH), nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
