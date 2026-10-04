"""ORM rows. Importing this package registers every table on `Base.metadata`,
so Alembic sees the same schema the application uses."""

from models.accounts import AdminRow, DoctorRow, UserRow
from models.appointment import AppointmentRow
from models.consult import ConsultMessageRow, ConsultSessionRow
from models.department import DepartmentRow
from models.doctor_consult import DoctorConsultRow, DoctorReplyRow
from models.health_record import HealthRecordRow
from models.knowledge import KnowledgeChunkRow, KnowledgeFileRow
from models.trace import RouteDecisionRow, TraceSpanRow

__all__ = [
    "AdminRow",
    "AppointmentRow",
    "ConsultMessageRow",
    "ConsultSessionRow",
    "DepartmentRow",
    "DoctorRow",
    "DoctorConsultRow",
    "DoctorReplyRow",
    "HealthRecordRow",
    "KnowledgeChunkRow",
    "KnowledgeFileRow",
    "RouteDecisionRow",
    "TraceSpanRow",
    "UserRow",
]
