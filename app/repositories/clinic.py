from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.models.clinic import (
    Appointment,
    AppointmentStatus,
    AuditEvent,
    MedicalRecord,
    Owner,
    Pet,
    PetStatus,
    VaccinationRecord,
    Vaccine,
    Veterinarian,
)


ACTIVE_APPOINTMENT_STATUSES = (
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_PROGRESS,
)


class ClinicRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, instance: Any) -> Any:
        self.db.add(instance)
        self.db.flush()
        self.db.refresh(instance)
        return instance

    def get_owner(self, owner_id: int) -> Owner | None:
        return self.db.get(Owner, owner_id)

    def get_pet(self, pet_id: int) -> Pet | None:
        return self.db.get(Pet, pet_id)

    def get_veterinarian(self, veterinarian_id: int) -> Veterinarian | None:
        return self.db.get(Veterinarian, veterinarian_id)

    def get_vaccine(self, vaccine_id: int) -> Vaccine | None:
        return self.db.get(Vaccine, vaccine_id)

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        return self.db.get(Appointment, appointment_id)

    def get_medical_record_by_appointment(self, appointment_id: int) -> MedicalRecord | None:
        stmt = select(MedicalRecord).where(MedicalRecord.appointment_id == appointment_id)
        return self.db.scalar(stmt)

    def owner_email_exists(self, email: str) -> bool:
        return self.db.scalar(select(Owner.id).where(Owner.email == email)) is not None

    def veterinarian_crmv_exists(self, crmv: str) -> bool:
        return self.db.scalar(select(Veterinarian.id).where(Veterinarian.crmv == crmv)) is not None

    def vaccine_name_exists(self, name: str) -> bool:
        return self.db.scalar(select(Vaccine.id).where(Vaccine.name == name)) is not None

    def find_conflicting_appointment(
        self,
        pet_id: int,
        veterinarian_id: int,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: int | None = None,
    ) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
            or_(Appointment.pet_id == pet_id, Appointment.veterinarian_id == veterinarian_id),
        )
        if exclude_id is not None:
            stmt = stmt.where(Appointment.id != exclude_id)
        return self.db.scalar(stmt.limit(1))

    def list_appointments(
        self,
        limit: int,
        offset: int,
        status: AppointmentStatus | None = None,
        pet_id: int | None = None,
        veterinarian_id: int | None = None,
    ) -> list[Appointment]:
        stmt: Select[tuple[Appointment]] = select(Appointment).order_by(Appointment.starts_at.desc())
        filters = []
        if status is not None:
            filters.append(Appointment.status == status)
        if pet_id is not None:
            filters.append(Appointment.pet_id == pet_id)
        if veterinarian_id is not None:
            filters.append(Appointment.veterinarian_id == veterinarian_id)
        if filters:
            stmt = stmt.where(and_(*filters))
        return list(self.db.scalars(stmt.limit(limit).offset(offset)))

    def create_audit_event(self, entity_name: str, entity_id: int, action: str, details: dict[str, object]) -> AuditEvent:
        event = AuditEvent(entity_name=entity_name, entity_id=entity_id, action=action, details=details)
        return self.add(event)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)
