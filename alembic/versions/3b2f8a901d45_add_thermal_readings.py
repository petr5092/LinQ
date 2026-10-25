"""add thermal readings history

Revision ID: 3b2f8a901d45
Revises: fa9e794bca03
Create Date: 2026-10-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3b2f8a901d45"
down_revision: Union[str, Sequence[str], None] = "fa9e794bca03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cameras") as batch_op:
        batch_op.add_column(sa.Column("camera_type", sa.String(length=20), server_default="visible", nullable=False))
    op.create_table(
        "thermal_readings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(length=50), nullable=False),
        sa.Column("zone_id", sa.String(length=100), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("min_temperature_c", sa.Float(), nullable=False),
        sa.Column("mean_temperature_c", sa.Float(), nullable=False),
        sa.Column("max_temperature_c", sa.Float(), nullable=False),
        sa.Column("threshold_c", sa.Float(), nullable=False),
        sa.Column("hot_pixels", sa.Integer(), nullable=False),
        sa.Column("alarm", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_thermal_readings_captured_at", "thermal_readings", ["captured_at"])
    op.create_index(
        "ix_thermal_reading_camera_zone_time", "thermal_readings",
        ["camera_id", "zone_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_thermal_reading_camera_zone_time", table_name="thermal_readings")
    op.drop_index("ix_thermal_readings_captured_at", table_name="thermal_readings")
    op.drop_table("thermal_readings")
    with op.batch_alter_table("cameras") as batch_op:
        batch_op.drop_column("camera_type")
