"""Campaign pipeline concurrency guard."""
from alembic import op
import sqlalchemy as sa

revision = '20260908_automation_runs'
down_revision = '20260908_publish_attempts'
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('campaign_automation_runs'):
        op.create_table('campaign_automation_runs',
            sa.Column('campaign_id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=False),
            sa.Column('job_id', sa.String(36), nullable=False),
        )


def downgrade():
    raise RuntimeError('Retain pipeline ownership records during rollback.')
