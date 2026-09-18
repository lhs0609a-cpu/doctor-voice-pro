"""Persistent recurring publication policy."""
from alembic import op
from app.models.campaign import AutopilotPolicy

revision = '20260908_autopilot'
down_revision = '20260908_automation_runs'
branch_labels = None
depends_on = None


def upgrade():
    AutopilotPolicy.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Retain automation quotas and execution history during rollback.')
