"""실행기가 먼저 손을 드는 연결 요청(켜면 브라우저가 열리고 홈페이지가 승인한다)."""
from alembic import op
import sqlalchemy as sa

revision = '20260915_agent_pair_requests'
down_revision = '20260910_agent_pairing'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('agent_pair_requests'):
        op.create_table('agent_pair_requests',
            sa.Column('request_id', sa.String(64), primary_key=True),
            sa.Column('device_id', sa.String(64), nullable=False, index=True),
            sa.Column('label', sa.String(120), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('user_id', sa.String(36), nullable=True, index=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('picked_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table('agent_pair_requests')
