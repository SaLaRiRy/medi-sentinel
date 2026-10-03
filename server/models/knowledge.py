"""知识库文件与分块（TICKET-013，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.13 / 4.3.14）。

向量化状态机（FUNCTIONAL_SPEC.md 5.6）：0 已上传 → 1 处理中 → 2 已向量化，
失败为 3。`vector_id` 的格式与向量索引中的标识一致：
`file_{文件号}_chunk_{分块序号}`。
"""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

# 向量化状态（FUNCTIONAL_SPEC.md 5.6）。
VECTOR_UPLOADED = 0
VECTOR_PROCESSING = 1
VECTOR_INDEXED = 2
VECTOR_FAILED = 3

FILE_NAME_MAX_LENGTH = 255
FILE_TYPE_MAX_LENGTH = 20
FILE_PATH_MAX_LENGTH = 500
VECTOR_ID_MAX_LENGTH = 100
ROLE_MAX_LENGTH = 20
DEFAULT_UPLOAD_ROLE = "admin"


def _now() -> datetime:
    return datetime.now(UTC)


def vector_id_of(file_id: int, chunk_index: int) -> str:
    """分块在向量索引中的标识（FUNCTIONAL_SPEC.md 4.3.14）。"""
    return f"file_{file_id}_chunk_{chunk_index}"


class KnowledgeFileRow(Base):
    __tablename__ = "t_knowledge_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(
        String(FILE_NAME_MAX_LENGTH), nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(FILE_TYPE_MAX_LENGTH), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_path: Mapped[str] = mapped_column(String(FILE_PATH_MAX_LENGTH), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vector_status: Mapped[int] = mapped_column(
        Integer, default=VECTOR_UPLOADED, nullable=False
    )
    upload_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_role: Mapped[str | None] = mapped_column(
        String(ROLE_MAX_LENGTH), default=DEFAULT_UPLOAD_ROLE, nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class KnowledgeChunkRow(Base):
    __tablename__ = "t_knowledge_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("t_knowledge_file.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(
        String(VECTOR_ID_MAX_LENGTH), nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
