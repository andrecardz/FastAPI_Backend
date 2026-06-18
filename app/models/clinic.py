from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


class PetStatus(str, Enum):
    ACTIVE = "active"
    IN_TREATMENT = "in_treatment"
    INACTIVE = "inactive"
    DECEASED = "deceased"


class VeterinarianStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    INACTIVE = "inactive"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


def enum_column(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(enum_cls, name=name, values_callable=lambda values: [item.value for item in values])


def json_type() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    species: Mapped[str] = mapped_column(String(60), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    status: Mapped[PetStatus] = mapped_column(enum_column(PetStatus, "pet_status"), default=PetStatus.ACTIVE, nullable=False)

    owner: Mapped[Owner] = relationship(back_populates="pets")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="pet")
    vaccinations: Mapped[list["VaccinationRecord"]] = relationship(back_populates="pet")


class Veterinarian(Base):
    __tablename__ = "veterinarians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    crmv: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    specialty: Mapped[str] = mapped_column(String(90), nullable=False)
    base_consultation_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[VeterinarianStatus] = mapped_column(
        enum_column(VeterinarianStatus, "veterinarian_status"),
        default=VeterinarianStatus.ACTIVE,
        nullable=False,
    )

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="veterinarian")


class Vaccine(Base):
    __tablename__ = "vaccines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    species: Mapped[str] = mapped_column(String(60), nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    records: Mapped[list["VaccinationRecord"]] = relationship(back_populates="vaccine")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_vet_status_start_end", "veterinarian_id", "status", "starts_at", "ends_at"),
        Index("ix_appointments_pet_status_start_end", "pet_id", "status", "starts_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False, index=True)
    veterinarian_id: Mapped[int] = mapped_column(ForeignKey("veterinarians.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        enum_column(AppointmentStatus, "appointment_status"),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    pet: Mapped[Pet] = relationship(back_populates="appointments")
    veterinarian: Mapped[Veterinarian] = relationship(back_populates="appointments")
    medical_record: Mapped["MedicalRecord | None"] = relationship(back_populates="appointment", uselist=False)
    vaccinations: Mapped[list["VaccinationRecord"]] = relationship(back_populates="appointment")


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), nullable=False, unique=True)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    treatment: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    medication_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    appointment: Mapped[Appointment] = relationship(back_populates="medical_record")


class VaccinationRecord(Base):
    __tablename__ = "vaccination_records"
    __table_args__ = (
        UniqueConstraint("pet_id", "vaccine_id", "applied_at", name="uq_pet_vaccine_applied_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False, index=True)
    vaccine_id: Mapped[int] = mapped_column(ForeignKey("vaccines.id"), nullable=False, index=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), nullable=False, index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booster_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(80), nullable=False)

    pet: Mapped[Pet] = relationship(back_populates="vaccinations")
    vaccine: Mapped[Vaccine] = relationship(back_populates="records")
    appointment: Mapped[Appointment] = relationship(back_populates="vaccinations")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
