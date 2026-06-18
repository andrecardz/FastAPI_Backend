from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.clinic import (
    Appointment,
    AppointmentStatus,
    MedicalRecord,
    Owner,
    Pet,
    PetStatus,
    VaccinationRecord,
    Vaccine,
    Veterinarian,
    VeterinarianStatus,
)
from app.repositories.clinic import ClinicRepository
from app.schemas.clinic import (
    AppointmentCreate,
    MedicalRecordCreate,
    OwnerCreate,
    PetCreate,
    VaccinationCreate,
    VaccineCreate,
    VeterinarianCreate,
)


ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: {AppointmentStatus.CHECKED_IN, AppointmentStatus.CANCELED},
    AppointmentStatus.CHECKED_IN: {AppointmentStatus.IN_PROGRESS, AppointmentStatus.CANCELED},
    AppointmentStatus.IN_PROGRESS: {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELED: set(),
}


class ClinicService:
    def __init__(self, db: Session) -> None:
        self.repo = ClinicRepository(db)

    def create_owner(self, payload: OwnerCreate) -> Owner:
        if self.repo.owner_email_exists(payload.email):
            raise BusinessRuleError(
                "OWNER_EMAIL_ALREADY_EXISTS",
                "Ja existe um tutor cadastrado com este e-mail.",
                409,
                {"email": payload.email},
            )
        owner = self.repo.add(Owner(**payload.model_dump()))
        self.repo.commit()
        return owner

    def create_pet(self, payload: PetCreate) -> Pet:
        owner = self.repo.get_owner(payload.owner_id)
        if owner is None:
            raise BusinessRuleError("OWNER_NOT_FOUND", "Tutor nao encontrado.", 404, {"owner_id": payload.owner_id})
        pet = self.repo.add(Pet(**payload.model_dump()))
        self.repo.commit()
        return pet

    def create_veterinarian(self, payload: VeterinarianCreate) -> Veterinarian:
        if self.repo.veterinarian_crmv_exists(payload.crmv):
            raise BusinessRuleError(
                "VETERINARIAN_CRMV_ALREADY_EXISTS",
                "Ja existe um veterinario cadastrado com este CRMV.",
                409,
                {"crmv": payload.crmv},
            )
        veterinarian = self.repo.add(Veterinarian(**payload.model_dump()))
        self.repo.commit()
        return veterinarian

    def create_vaccine(self, payload: VaccineCreate) -> Vaccine:
        if self.repo.vaccine_name_exists(payload.name):
            raise BusinessRuleError(
                "VACCINE_NAME_ALREADY_EXISTS",
                "Ja existe uma vacina cadastrada com este nome.",
                409,
                {"name": payload.name},
            )
        vaccine = self.repo.add(Vaccine(**payload.model_dump()))
        self.repo.commit()
        return vaccine

    def create_appointment(self, payload: AppointmentCreate) -> Appointment:
        pet = self._get_pet_or_fail(payload.pet_id)
        veterinarian = self._get_veterinarian_or_fail(payload.veterinarian_id)
        self._ensure_pet_can_receive_care(pet)
        self._ensure_veterinarian_active(veterinarian)
        conflict = self.repo.find_conflicting_appointment(
            pet_id=payload.pet_id,
            veterinarian_id=payload.veterinarian_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
        )
        if conflict is not None:
            raise BusinessRuleError(
                "APPOINTMENT_CONFLICT",
                "Ja existe uma consulta ativa para este animal ou veterinario no periodo solicitado.",
                409,
                {
                    "conflicting_appointment_id": conflict.id,
                    "period": {"start": conflict.starts_at.isoformat(), "end": conflict.ends_at.isoformat()},
                },
            )
        appointment = self.repo.add(Appointment(**payload.model_dump()))
        self.repo.commit()
        return appointment

    def list_appointments(
        self,
        limit: int,
        offset: int,
        status: AppointmentStatus | None,
        pet_id: int | None,
        veterinarian_id: int | None,
    ) -> list[Appointment]:
        return self.repo.list_appointments(limit, offset, status, pet_id, veterinarian_id)

    def transition_appointment(self, appointment_id: int, target_status: AppointmentStatus) -> Appointment:
        appointment = self._get_appointment_or_fail(appointment_id)
        current_status = appointment.status
        allowed = ALLOWED_TRANSITIONS[current_status]
        if target_status not in allowed:
            raise BusinessRuleError(
                "INVALID_APPOINTMENT_TRANSITION",
                "A transicao de estado solicitada nao e permitida.",
                409,
                {
                    "current_status": current_status.value,
                    "target_status": target_status.value,
                    "allowed": sorted(status.value for status in allowed),
                },
            )
        if target_status == AppointmentStatus.COMPLETED and appointment.medical_record is None:
            raise BusinessRuleError(
                "MEDICAL_RECORD_REQUIRED",
                "A consulta so pode ser concluida depois do prontuario ser registrado.",
                409,
                {"appointment_id": appointment.id},
            )
        appointment.status = target_status
        self.repo.create_audit_event(
            "appointments",
            appointment.id,
            "status_transition",
            {"from": current_status.value, "to": target_status.value},
        )
        self.repo.commit()
        self.repo.refresh(appointment)
        return appointment

    def create_medical_record(self, appointment_id: int, payload: MedicalRecordCreate) -> MedicalRecord:
        appointment = self._get_appointment_or_fail(appointment_id)
        if appointment.status not in {AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS}:
            raise BusinessRuleError(
                "APPOINTMENT_NOT_READY_FOR_RECORD",
                "Prontuario so pode ser registrado para consulta com check-in ou em atendimento.",
                409,
                {"appointment_id": appointment.id, "status": appointment.status.value},
            )
        if self.repo.get_medical_record_by_appointment(appointment_id) is not None:
            raise BusinessRuleError(
                "MEDICAL_RECORD_ALREADY_EXISTS",
                "Ja existe prontuario para esta consulta.",
                409,
                {"appointment_id": appointment_id},
            )
        record = self.repo.add(MedicalRecord(appointment_id=appointment_id, **payload.model_dump()))
        appointment.total_amount = self._calculate_total_amount(appointment, record)
        self.repo.commit()
        self.repo.refresh(record)
        return record

    def create_vaccination(self, payload: VaccinationCreate) -> VaccinationRecord:
        pet = self._get_pet_or_fail(payload.pet_id)
        vaccine = self._get_vaccine_or_fail(payload.vaccine_id)
        appointment = self._get_appointment_or_fail(payload.appointment_id)
        self._ensure_pet_can_receive_care(pet)
        if not vaccine.active:
            raise BusinessRuleError(
                "VACCINE_INACTIVE",
                "Vacina inativa nao pode ser aplicada.",
                409,
                {"vaccine_id": vaccine.id},
            )
        if vaccine.species.lower() != pet.species.lower():
            raise BusinessRuleError(
                "VACCINE_SPECIES_MISMATCH",
                "A vacina nao e indicada para a especie do animal.",
                409,
                {"pet_species": pet.species, "vaccine_species": vaccine.species},
            )
        if appointment.pet_id != pet.id or appointment.status != AppointmentStatus.COMPLETED:
            raise BusinessRuleError(
                "VACCINATION_REQUIRES_COMPLETED_APPOINTMENT",
                "Vacinacao exige consulta concluida para o mesmo animal.",
                409,
                {"appointment_id": appointment.id, "appointment_status": appointment.status.value},
            )
        vaccination = self.repo.add(VaccinationRecord(**payload.model_dump()))
        self.repo.commit()
        return vaccination

    def _get_pet_or_fail(self, pet_id: int) -> Pet:
        pet = self.repo.get_pet(pet_id)
        if pet is None:
            raise BusinessRuleError("PET_NOT_FOUND", "Animal nao encontrado.", 404, {"pet_id": pet_id})
        return pet

    def _get_veterinarian_or_fail(self, veterinarian_id: int) -> Veterinarian:
        veterinarian = self.repo.get_veterinarian(veterinarian_id)
        if veterinarian is None:
            raise BusinessRuleError(
                "VETERINARIAN_NOT_FOUND",
                "Veterinario nao encontrado.",
                404,
                {"veterinarian_id": veterinarian_id},
            )
        return veterinarian

    def _get_vaccine_or_fail(self, vaccine_id: int) -> Vaccine:
        vaccine = self.repo.get_vaccine(vaccine_id)
        if vaccine is None:
            raise BusinessRuleError("VACCINE_NOT_FOUND", "Vacina nao encontrada.", 404, {"vaccine_id": vaccine_id})
        return vaccine

    def _get_appointment_or_fail(self, appointment_id: int) -> Appointment:
        appointment = self.repo.get_appointment(appointment_id)
        if appointment is None:
            raise BusinessRuleError(
                "APPOINTMENT_NOT_FOUND",
                "Consulta nao encontrada.",
                404,
                {"appointment_id": appointment_id},
            )
        return appointment

    def _ensure_pet_can_receive_care(self, pet: Pet) -> None:
        if pet.status in {PetStatus.INACTIVE, PetStatus.DECEASED}:
            raise BusinessRuleError(
                "PET_NOT_ELIGIBLE_FOR_CARE",
                "Animal inativo ou falecido nao pode receber novo atendimento.",
                409,
                {"pet_id": pet.id, "status": pet.status.value},
            )

    def _ensure_veterinarian_active(self, veterinarian: Veterinarian) -> None:
        if veterinarian.status != VeterinarianStatus.ACTIVE:
            raise BusinessRuleError(
                "VETERINARIAN_NOT_AVAILABLE",
                "Veterinario precisa estar ativo para receber consultas.",
                409,
                {"veterinarian_id": veterinarian.id, "status": veterinarian.status.value},
            )

    def _calculate_total_amount(self, appointment: Appointment, record: MedicalRecord) -> Decimal:
        return (
            Decimal(str(appointment.veterinarian.base_consultation_fee))
            + Decimal(str(record.procedure_cost))
            + Decimal(str(record.medication_cost))
        )
