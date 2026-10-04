"""手工级联清理（TICKET-020，`FUNCTIONAL_SPEC.md` 5.11 / AC-E-08）。

账号类引用只建索引不建外键，因此删除患者/医生时关联业务数据必须按**固定顺序**
由应用层清理。顺序即规则：先子后父，绝不留下悬挂的子记录。本模块是级联顺序的
唯一定义处，`AccountRepository.delete` 在删除账号行之前调用它。
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.appointment import AppointmentRow
from models.consult import ConsultMessageRow, ConsultSessionRow
from models.doctor_consult import DoctorConsultRow, DoctorReplyRow
from models.health_record import HealthRecordRow


async def purge_patient_scope(session: AsyncSession, user_id: int) -> None:
    """患者的关联数据，按 `FUNCTIONAL_SPEC.md` 5.11「删除患者」1–6 的顺序。"""
    target_sessions = select(ConsultSessionRow.id).where(
        ConsultSessionRow.user_id == user_id
    )
    await session.execute(
        delete(ConsultMessageRow).where(
            ConsultMessageRow.session_id.in_(target_sessions)
        )
    )
    await session.execute(
        delete(ConsultSessionRow).where(ConsultSessionRow.user_id == user_id)
    )

    target_consults = select(DoctorConsultRow.id).where(
        DoctorConsultRow.user_id == user_id
    )
    await session.execute(
        delete(DoctorReplyRow).where(DoctorReplyRow.consult_id.in_(target_consults))
    )
    await session.execute(
        delete(DoctorConsultRow).where(DoctorConsultRow.user_id == user_id)
    )

    await session.execute(
        delete(AppointmentRow).where(AppointmentRow.user_id == user_id)
    )
    await session.execute(
        delete(HealthRecordRow).where(HealthRecordRow.user_id == user_id)
    )


async def purge_doctor_scope(session: AsyncSession, doctor_id: int) -> None:
    """医生的关联数据，按 `FUNCTIONAL_SPEC.md` 5.11「删除医生」1–4 的顺序。

    **未指派的工单不在删除范围内**，会继续存在且保持「待分配」。
    """
    target_consults = select(DoctorConsultRow.id).where(
        DoctorConsultRow.doctor_id == doctor_id
    )
    await session.execute(
        delete(DoctorReplyRow).where(DoctorReplyRow.consult_id.in_(target_consults))
    )
    await session.execute(
        delete(DoctorConsultRow).where(DoctorConsultRow.doctor_id == doctor_id)
    )
    await session.execute(
        delete(AppointmentRow).where(AppointmentRow.doctor_id == doctor_id)
    )
    await session.execute(
        delete(HealthRecordRow).where(HealthRecordRow.doctor_id == doctor_id)
    )
