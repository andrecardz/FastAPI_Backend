"""add overlap indexes for scheduling rule

Revision ID: 002_add_overlap_indexes
Revises: 001_initial_clinic_structure
Create Date: 2026-06-17 00:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002_add_overlap_indexes"
down_revision: str | None = "001_initial_clinic_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_appointments_vet_status_start_end",
        "appointments",
        ["veterinarian_id", "status", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_appointments_pet_status_start_end",
        "appointments",
        ["pet_id", "status", "starts_at", "ends_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_pet_status_start_end", table_name="appointments")
    op.drop_index("ix_appointments_vet_status_start_end", table_name="appointments")
