"""ORM rows. Importing this package registers every table on `Base.metadata`,
so Alembic sees the same schema the application uses."""

from models.accounts import AdminRow, DoctorRow, UserRow
from models.consult import ConsultMessageRow, ConsultSessionRow
from models.knowledge import KnowledgeChunkRow, KnowledgeFileRow
from models.trace import RouteDecisionRow, TraceSpanRow

__all__ = [
    "AdminRow",
    "ConsultMessageRow",
    "ConsultSessionRow",
    "DoctorRow",
    "KnowledgeChunkRow",
    "KnowledgeFileRow",
    "RouteDecisionRow",
    "TraceSpanRow",
    "UserRow",
]
