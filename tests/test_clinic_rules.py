from fastapi.testclient import TestClient

from tests.conftest import appointment_payload, seed_clinic


def create_appointment(client: TestClient, ids: dict[str, int]) -> dict[str, object]:
    response = client.post("/appointments", json=appointment_payload(ids))
    assert response.status_code == 201
    return response.json()


def move_to_in_progress(client: TestClient, appointment_id: int) -> None:
    assert client.post(f"/appointments/{appointment_id}/status", json={"target_status": "checked_in"}).status_code == 200
    assert client.post(f"/appointments/{appointment_id}/status", json={"target_status": "in_progress"}).status_code == 200


def complete_with_record(client: TestClient, appointment_id: int) -> dict[str, object]:
    move_to_in_progress(client, appointment_id)
    record_response = client.post(
        f"/appointments/{appointment_id}/medical-record",
        json={"diagnosis": "Saudavel", "treatment": "Acompanhamento anual", "procedure_cost": 30, "medication_cost": 20},
    )
    assert record_response.status_code == 201
    response = client.post(f"/appointments/{appointment_id}/status", json={"target_status": "completed"})
    assert response.status_code == 200
    return response.json()


def test_create_appointment_and_filter_with_pagination(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)

    response = client.get("/appointments", params={"limit": 10, "offset": 0, "status": "scheduled", "pet_id": ids["pet_id"]})

    assert response.status_code == 200
    assert response.json()[0]["id"] == appointment["id"]


def test_reject_overlapping_appointment_for_same_pet_or_vet(client: TestClient) -> None:
    ids = seed_clinic(client)
    create_appointment(client, ids)

    response = client.post(
        "/appointments",
        json=appointment_payload(ids, "2030-01-01T10:15:00", "2030-01-01T10:45:00"),
    )

    assert response.status_code == 409
    assert response.json()["error"] == "APPOINTMENT_CONFLICT"


def test_allow_non_overlapping_appointment(client: TestClient) -> None:
    ids = seed_clinic(client)
    create_appointment(client, ids)

    response = client.post(
        "/appointments",
        json=appointment_payload(ids, "2030-01-01T10:30:00", "2030-01-01T11:00:00"),
    )

    assert response.status_code == 201


def test_reject_appointment_for_deceased_pet(client: TestClient) -> None:
    ids = seed_clinic(client, pet_status="deceased")

    response = client.post("/appointments", json=appointment_payload(ids))

    assert response.status_code == 409
    assert response.json()["error"] == "PET_NOT_ELIGIBLE_FOR_CARE"


def test_reject_appointment_for_veterinarian_on_leave(client: TestClient) -> None:
    ids = seed_clinic(client, veterinarian_status="on_leave")

    response = client.post("/appointments", json=appointment_payload(ids))

    assert response.status_code == 409
    assert response.json()["error"] == "VETERINARIAN_NOT_AVAILABLE"


def test_reject_invalid_appointment_period_in_schema(client: TestClient) -> None:
    ids = seed_clinic(client)

    response = client.post(
        "/appointments",
        json=appointment_payload(ids, "2030-01-01T11:00:00", "2030-01-01T10:00:00"),
    )

    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_reject_invalid_state_transition(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)

    response = client.post(f"/appointments/{appointment['id']}/status", json={"target_status": "completed"})

    assert response.status_code == 409
    assert response.json()["error"] == "INVALID_APPOINTMENT_TRANSITION"


def test_terminal_canceled_appointment_cannot_return_to_flow(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)
    assert client.post(f"/appointments/{appointment['id']}/status", json={"target_status": "canceled"}).status_code == 200

    response = client.post(f"/appointments/{appointment['id']}/status", json={"target_status": "checked_in"})

    assert response.status_code == 409
    assert response.json()["details"]["allowed"] == []


def test_medical_record_requires_checked_in_or_in_progress(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)

    response = client.post(
        f"/appointments/{appointment['id']}/medical-record",
        json={"diagnosis": "Otite", "treatment": "Limpeza", "procedure_cost": 10, "medication_cost": 5},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "APPOINTMENT_NOT_READY_FOR_RECORD"


def test_completion_requires_medical_record(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)
    move_to_in_progress(client, int(appointment["id"]))

    response = client.post(f"/appointments/{appointment['id']}/status", json={"target_status": "completed"})

    assert response.status_code == 409
    assert response.json()["error"] == "MEDICAL_RECORD_REQUIRED"


def test_medical_record_calculates_total_and_allows_completion(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)

    completed = complete_with_record(client, int(appointment["id"]))

    assert completed["status"] == "completed"
    assert completed["total_amount"] == 170


def test_vaccination_requires_completed_appointment_for_same_pet(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)

    response = client.post(
        "/vaccinations",
        json={
            "pet_id": ids["pet_id"],
            "vaccine_id": ids["vaccine_id"],
            "appointment_id": appointment["id"],
            "applied_at": "2030-01-01T11:00:00",
            "booster_due_at": "2031-01-01T11:00:00",
            "batch_number": "L123",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "VACCINATION_REQUIRES_COMPLETED_APPOINTMENT"


def test_vaccination_rejects_species_mismatch(client: TestClient) -> None:
    ids = seed_clinic(client, vaccine_species="feline")
    appointment = create_appointment(client, ids)
    complete_with_record(client, int(appointment["id"]))

    response = client.post(
        "/vaccinations",
        json={
            "pet_id": ids["pet_id"],
            "vaccine_id": ids["vaccine_id"],
            "appointment_id": appointment["id"],
            "applied_at": "2030-01-01T11:00:00",
            "booster_due_at": "2031-01-01T11:00:00",
            "batch_number": "L123",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "VACCINE_SPECIES_MISMATCH"


def test_vaccination_success_after_completed_appointment(client: TestClient) -> None:
    ids = seed_clinic(client)
    appointment = create_appointment(client, ids)
    complete_with_record(client, int(appointment["id"]))

    response = client.post(
        "/vaccinations",
        json={
            "pet_id": ids["pet_id"],
            "vaccine_id": ids["vaccine_id"],
            "appointment_id": appointment["id"],
            "applied_at": "2030-01-01T11:00:00",
            "booster_due_at": "2031-01-01T11:00:00",
            "batch_number": "L123",
        },
    )

    assert response.status_code == 201
    assert response.json()["pet_id"] == ids["pet_id"]
