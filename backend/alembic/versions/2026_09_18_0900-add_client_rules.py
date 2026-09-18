"""add client-specific writing rules

Revision ID: 6f1a2c3d4e5f
Revises: b7f3c1d9e2a4
"""
from alembic import op
import sqlalchemy as sa


revision = "6f1a2c3d4e5f"
down_revision = "b7f3c1d9e2a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("doctor_profiles", sa.Column("client_rules", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("doctor_profiles", "client_rules")
