"""initial clinic structure

Revision ID: 001_initial_clinic_structure
Revises:
Create Date: 2026-06-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_clinic_structure"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

pet_status = sa.Enum("active", "in_treatment", "inactive", "deceased", name="pet_status")
veterinarian_status = sa.Enum("active", "on_leave", "inactive", name="veterinarian_status")
appointment_status = sa.Enum("scheduled", "checked_in", "in_progress", "completed", "canceled", name="appointment_status")


def upgrade() -> None:
    bind = op.get_bind()
    pet_status.create(bind, checkfirst=True)
    veterinarian_status.create(bind, checkfirst=True)
    appointment_status.create(bind, checkfirst=True)

    op.create_table(
        "owners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_owners_email", "owners", ["email"])

    op.create_table(
        "pets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("species", sa.String(length=60), nullable=False),
        sa.Column("breed", sa.String(length=80), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("status", pet_status, nullable=False),
    )
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"])

    op.create_table(
        "veterinarians",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("crmv", sa.String(length=30), nullable=False),
        sa.Column("specialty", sa.String(length=90), nullable=False),
        sa.Column("base_consultation_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", veterinarian_status, nullable=False),
        sa.UniqueConstraint("crmv"),
    )

    op.create_table(
        "vaccines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("species", sa.String(length=60), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id"), nullable=False),
        sa.Column("veterinarian_id", sa.Integer(), sa.ForeignKey("veterinarians.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("status", appointment_status, nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointments_pet_id", "appointments", ["pet_id"])
    op.create_index("ix_appointments_veterinarian_id", "appointments", ["veterinarian_id"])

    op.create_table(
        "medical_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=False),
        sa.Column("treatment", sa.Text(), nullable=False),
        sa.Column("procedure_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("medication_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("appointment_id"),
    )

    op.create_table(
        "vaccination_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id"), nullable=False),
        sa.Column("vaccine_id", sa.Integer(), sa.ForeignKey("vaccines.id"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booster_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("batch_number", sa.String(length=80), nullable=False),
        sa.UniqueConstraint("pet_id", "vaccine_id", "applied_at", name="uq_pet_vaccine_applied_at"),
    )
    op.create_index("ix_vaccination_records_pet_id", "vaccination_records", ["pet_id"])
    op.create_index("ix_vaccination_records_vaccine_id", "vaccination_records", ["vaccine_id"])
    op.create_index("ix_vaccination_records_appointment_id", "vaccination_records", ["appointment_id"])


def downgrade() -> None:
    op.drop_index("ix_vaccination_records_appointment_id", table_name="vaccination_records")
    op.drop_index("ix_vaccination_records_vaccine_id", table_name="vaccination_records")
    op.drop_index("ix_vaccination_records_pet_id", table_name="vaccination_records")
    op.drop_table("vaccination_records")
    op.drop_table("medical_records")
    op.drop_index("ix_appointments_veterinarian_id", table_name="appointments")
    op.drop_index("ix_appointments_pet_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("vaccines")
    op.drop_table("veterinarians")
    op.drop_index("ix_pets_owner_id", table_name="pets")
    op.drop_table("pets")
    op.drop_index("ix_owners_email", table_name="owners")
    op.drop_table("owners")

    bind = op.get_bind()
    appointment_status.drop(bind, checkfirst=True)
    veterinarian_status.drop(bind, checkfirst=True)
    pet_status.drop(bind, checkfirst=True)
