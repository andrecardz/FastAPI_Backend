from collections.abc import Generator
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import create_app

_ids = count(1)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def seed_clinic(
    client: TestClient,
    pet_status: str = "active",
    veterinarian_status: str = "active",
    pet_species: str = "canine",
    vaccine_species: str = "canine",
) -> dict[str, int]:
    suffix = next(_ids)
    owner = client.post(
        "/owners",
        json={"name": "Ana Silva", "email": f"ana{suffix}@example.com", "phone": "11999990000"},
    ).json()
    pet = client.post(
        "/pets",
        json={
            "owner_id": owner["id"],
            "name": "Luna",
            "species": pet_species,
            "breed": "SRD",
            "birth_date": "2020-01-01",
            "weight_kg": 8.5,
            "status": pet_status,
        },
    ).json()
    veterinarian = client.post(
        "/veterinarians",
        json={
            "name": "Dr. Bruno",
            "crmv": f"CRMV-{suffix}",
            "specialty": "Clinica geral",
            "base_consultation_fee": 120,
            "status": veterinarian_status,
        },
    ).json()
    vaccine = client.post(
        "/vaccines",
        json={"name": f"V10-{suffix}", "species": vaccine_species, "validity_days": 365, "active": True},
    ).json()
    return {"owner_id": owner["id"], "pet_id": pet["id"], "veterinarian_id": veterinarian["id"], "vaccine_id": vaccine["id"]}


def appointment_payload(ids: dict[str, int], start: str = "2030-01-01T10:00:00", end: str = "2030-01-01T10:30:00") -> dict[str, object]:
    return {
        "pet_id": ids["pet_id"],
        "veterinarian_id": ids["veterinarian_id"],
        "starts_at": start,
        "ends_at": end,
        "reason": "Consulta preventiva",
    }
