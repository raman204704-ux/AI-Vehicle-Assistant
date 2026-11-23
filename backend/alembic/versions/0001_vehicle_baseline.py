"""Baseline schema for the existing vehicles table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_vehicle"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vehicle_name", sa.String(length=100), nullable=False),
        sa.Column("manufacturer", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(length=30), nullable=False),
        sa.Column("registration_number", sa.String(length=30), nullable=False),
        sa.Column("current_odometer", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_id", "vehicles", ["id"], unique=False)
    op.create_index(
        "ix_vehicles_registration_number",
        "vehicles",
        ["registration_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicles_registration_number", table_name="vehicles")
    op.drop_index("ix_vehicles_id", table_name="vehicles")
    op.drop_table("vehicles")
