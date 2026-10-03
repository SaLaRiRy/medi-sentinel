"""TICKET-015：管理端知识库接口（`SPEC.md` 5.4「AI 问诊与知识库」）。

- `GET /knowledge`：按文件名或类型检索的分页列表
- `POST /knowledge`：上传文档，落盘后立即返回 `{id, file_name}`，向量化在后台跑
- `POST /knowledge/{id}/revectorize`：重新向量化（先清旧分块与旧向量再重建）
- `DELETE /knowledge/{id}`：删向量索引 → 删分块 → 删磁盘文件 → 删文件记录

四个端点都要求 `admin`（012 的 `require_admin`）。上传后状态从 0「已上传」
经 1「处理中」到 2「已向量化」，失败为 3（`FUNCTIONAL_SPEC.md` 5.6）；状态机
本身在 `services.knowledge` 的 B-5 任务里，本模块只负责落盘、建记录与投递。
"""

from __future__ import annotations

import secrets
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.deps import Principal, get_active_settings, get_session, require_admin
from core.errors import ApiError
from core.response import Envelope, PagePayload, page_result, success
from core.serialization import ApiDateTime
from models.knowledge import KnowledgeFileRow
from rag.loader import SUPPORTED_SUFFIXES
from repositories.knowledge import KnowledgeRepository

router = APIRouter(tags=["knowledge"])

UNSUPPORTED_TYPE_MESSAGE = "不支持的文件类型，仅支持 txt/doc/pdf/markdown"
OVERSIZE_MESSAGE = "文件超过大小上限"


class KnowledgeFileView(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    chunk_count: int
    vector_status: int
    upload_by: int | None = None
    upload_role: str | None = None
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: KnowledgeFileRow) -> "KnowledgeFileView":
        return cls(
            id=row.id,
            file_name=row.file_name,
            file_type=row.file_type,
            file_size=row.file_size or 0,
            chunk_count=row.chunk_count or 0,
            vector_status=row.vector_status,
            upload_by=row.upload_by,
            upload_role=row.upload_role,
            create_time=row.create_time,
            update_time=row.update_time,
        )


class KnowledgeUploadView(BaseModel):
    id: int
    file_name: str


@router.get(
    "/knowledge",
    response_model=Envelope[PagePayload[KnowledgeFileView]],
)
async def list_knowledge(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    file_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[KnowledgeFileView]]:
    rows, total = await KnowledgeRepository(session).list_files(
        offset=(page - 1) * page_size,
        limit=page_size,
        keyword=keyword,
        file_type=file_type,
    )
    return page_result(
        [KnowledgeFileView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/knowledge", response_model=Envelope[KnowledgeUploadView])
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_admin),
    settings: Settings = Depends(get_active_settings),
    session: AsyncSession = Depends(get_session),
) -> Envelope[KnowledgeUploadView]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ApiError(400, UNSUPPORTED_TYPE_MESSAGE)
    content = await file.read()
    if len(content) > settings.knowledge_max_bytes:
        raise ApiError(413, OVERSIZE_MESSAGE)

    stored_name = secrets.token_hex(16) + suffix
    directory = Path(settings.upload_dir) / settings.knowledge_subdir
    await anyio.to_thread.run_sync(lambda: directory.mkdir(parents=True, exist_ok=True))
    await anyio.to_thread.run_sync((directory / stored_name).write_bytes, content)

    row = await KnowledgeRepository(session).create_file(
        file_name=file.filename or stored_name,
        file_type=suffix.lstrip("."),
        file_size=len(content),
        file_path=str(directory / stored_name),
        upload_by=principal.user_id,
        upload_role=principal.role,
    )
    # Commit before scheduling: the background job opens its own session and
    # must see the row (SPEC.md 3.1「每请求一个异步会话」只约束请求路径).
    await session.commit()
    request.app.state.knowledge_jobs.schedule_vectorize(row.id)
    return success(KnowledgeUploadView(id=row.id, file_name=row.file_name))


@router.post(
    "/knowledge/{file_id}/revectorize",
    response_model=Envelope[None],
)
async def revectorize_knowledge(
    request: Request,
    file_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    if await KnowledgeRepository(session).find_file(file_id) is None:
        raise ApiError(404, "知识库文件不存在")
    # The job re-reads the row in its own session and does the whole 1 → 2 / 3
    # rebuild, so a stale request session cannot resurrect old chunks.
    request.app.state.knowledge_jobs.schedule_vectorize(file_id)
    return success(None)


@router.delete("/knowledge/{file_id}", response_model=Envelope[None])
async def delete_knowledge(
    request: Request,
    file_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await request.app.state.knowledge_jobs.delete(file_id, session=session)
    if not deleted:
        raise ApiError(404, "知识库文件不存在")
    return success(None)
