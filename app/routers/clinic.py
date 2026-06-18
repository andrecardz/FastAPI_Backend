from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.clinic import (
    Appointment,
    AppointmentStatus,
    MedicalRecord,
    Owner,
    Pet,
    VaccinationRecord,
    Vaccine,
    Veterinarian,
)
from app.schemas.clinic import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatusUpdate,
    MedicalRecordCreate,
    MedicalRecordRead,
    OwnerCreate,
    OwnerRead,
    PetCreate,
    PetRead,
    VaccinationCreate,
    VaccinationRead,
    VaccineCreate,
    VaccineRead,
    VeterinarianCreate,
    VeterinarianRead,
)
from app.services.clinic import ClinicService

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ClinicService:
    return ClinicService(db)


@router.post("/owners", response_model=OwnerRead, status_code=201)
def create_owner(payload: OwnerCreate, service: ClinicService = Depends(get_service)) -> Owner:
    return service.create_owner(payload)


@router.post("/pets", response_model=PetRead, status_code=201)
def create_pet(payload: PetCreate, service: ClinicService = Depends(get_service)) -> Pet:
    return service.create_pet(payload)


@router.post("/veterinarians", response_model=VeterinarianRead, status_code=201)
def create_veterinarian(payload: VeterinarianCreate, service: ClinicService = Depends(get_service)) -> Veterinarian:
    return service.create_veterinarian(payload)


@router.post("/vaccines", response_model=VaccineRead, status_code=201)
def create_vaccine(payload: VaccineCreate, service: ClinicService = Depends(get_service)) -> Vaccine:
    return service.create_vaccine(payload)


@router.post("/appointments", response_model=AppointmentRead, status_code=201)
def create_appointment(payload: AppointmentCreate, service: ClinicService = Depends(get_service)) -> Appointment:
    return service.create_appointment(payload)


@router.get("/appointments", response_model=list[AppointmentRead])
def list_appointments(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: AppointmentStatus | None = None,
    pet_id: int | None = None,
    veterinarian_id: int | None = None,
    service: ClinicService = Depends(get_service),
) -> list[Appointment]:
    return service.list_appointments(limit, offset, status, pet_id, veterinarian_id)


@router.post("/appointments/{appointment_id}/status", response_model=AppointmentRead)
def transition_appointment(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    service: ClinicService = Depends(get_service),
) -> Appointment:
    return service.transition_appointment(appointment_id, payload.target_status)


@router.post("/appointments/{appointment_id}/medical-record", response_model=MedicalRecordRead, status_code=201)
def create_medical_record(
    appointment_id: int,
    payload: MedicalRecordCreate,
    service: ClinicService = Depends(get_service),
) -> MedicalRecord:
    return service.create_medical_record(appointment_id, payload)


@router.post("/vaccinations", response_model=VaccinationRead, status_code=201)
def create_vaccination(payload: VaccinationCreate, service: ClinicService = Depends(get_service)) -> VaccinationRecord:
    return service.create_vaccination(payload)
