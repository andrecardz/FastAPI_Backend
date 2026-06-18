from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.clinic import AppointmentStatus, PetStatus, VeterinarianStatus


class OwnerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=30)


class OwnerRead(OwnerCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PetCreate(BaseModel):
    owner_id: int
    name: str = Field(min_length=1, max_length=80)
    species: str = Field(min_length=2, max_length=60)
    breed: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    weight_kg: float | None = Field(default=None, gt=0)
    status: PetStatus = PetStatus.ACTIVE

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date nao pode estar no futuro")
        return value


class PetRead(PetCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class VeterinarianCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    crmv: str = Field(min_length=4, max_length=30)
    specialty: str = Field(min_length=2, max_length=90)
    base_consultation_fee: float = Field(ge=0)
    status: VeterinarianStatus = VeterinarianStatus.ACTIVE


class VeterinarianRead(VeterinarianCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class VaccineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    species: str = Field(min_length=2, max_length=60)
    validity_days: int = Field(gt=0)
    active: bool = True


class VaccineRead(VaccineCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    pet_id: int
    veterinarian_id: int
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=5, max_length=200)

    @model_validator(mode="after")
    def validate_period(self) -> "AppointmentCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at deve ser posterior a starts_at")
        return self


class AppointmentRead(BaseModel):
    id: int
    pet_id: int
    veterinarian_id: int
    starts_at: datetime
    ends_at: datetime
    reason: str
    status: AppointmentStatus
    total_amount: float

    model_config = ConfigDict(from_attributes=True)


class AppointmentStatusUpdate(BaseModel):
    target_status: AppointmentStatus


class MedicalRecordCreate(BaseModel):
    diagnosis: str = Field(min_length=3)
    treatment: str = Field(min_length=3)
    procedure_cost: float = Field(default=0, ge=0)
    medication_cost: float = Field(default=0, ge=0)


class MedicalRecordRead(MedicalRecordCreate):
    id: int
    appointment_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VaccinationCreate(BaseModel):
    pet_id: int
    vaccine_id: int
    appointment_id: int
    applied_at: datetime
    booster_due_at: datetime
    batch_number: str = Field(min_length=2, max_length=80)

    @model_validator(mode="after")
    def validate_booster_date(self) -> "VaccinationCreate":
        if self.booster_due_at <= self.applied_at:
            raise ValueError("booster_due_at deve ser posterior a applied_at")
        return self


class VaccinationRead(VaccinationCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict[str, Any] | list[Any]
