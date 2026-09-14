"""Durable publication attempts (additive, existing application tables preserved)."""
from alembic import op
import sqlalchemy as sa

revision = '20260908_publish_attempts'
down_revision = '2bd23bba19a5'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('campaign_publish_attempts'):
        return
    op.create_table('campaign_publish_attempts',
        sa.Column('token', sa.String(64), primary_key=True),
        sa.Column('job_id', sa.String(36), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('active_blog_id', sa.String(36), nullable=True, unique=True),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    raise RuntimeError('Publication receipts must be retained for reconciliation; roll back executors without dropping this table.')
