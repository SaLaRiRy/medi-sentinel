"""Structured storage for the trace seam (B-4 / B-5).

Digests are stored, never raw patient text or raw model output; the column width
is the same bound `digest` truncates to, so nothing longer can land.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from skills.trace import DIGEST_LIMIT


class TraceSpanRow(Base):
    __tablename__ = "trace_span"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int] = mapped_column(Integer)
    input_digest: Mapped[str] = mapped_column(String(DIGEST_LIMIT))
    output_digest: Mapped[str] = mapped_column(String(DIGEST_LIMIT))
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class RouteDecisionRow(Base):
    __tablename__ = "route_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    skills_run: Mapped[list[str]] = mapped_column(JSON)
    skills_skipped: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    decided_at: Mapped[datetime] = mapped_column(DateTime, index=True)
