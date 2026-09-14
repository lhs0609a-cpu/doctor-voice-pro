"""홈페이지 ↔ 실행기 자동 연결(1회용 코드 + 기기 키)."""
from alembic import op
import sqlalchemy as sa

revision = '20260910_agent_pairing'
down_revision = '20260910_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('agent_pair_codes'):
        op.create_table('agent_pair_codes',
            sa.Column('code', sa.String(16), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
        )
    if not inspector.has_table('agent_devices'):
        op.create_table('agent_devices',
            sa.Column('device_id', sa.String(64), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=False, index=True),
            sa.Column('secret_hash', sa.String(64), nullable=False),
            sa.Column('label', sa.String(120), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table('agent_devices')
    op.drop_table('agent_pair_codes')
