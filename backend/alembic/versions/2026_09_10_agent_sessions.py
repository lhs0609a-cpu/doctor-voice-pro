"""PC 실행기 하트비트(웹 신호등·버전 표시용)."""
from alembic import op
import sqlalchemy as sa

revision = '20260910_agent_sessions'
down_revision = '20260910_queue_blog_ref'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('agent_sessions'):
        return
    # 인덱스는 컬럼의 index=True 로 함께 만들어진다(따로 create_index 하면 중복이라 깨진다).
    op.create_table('agent_sessions',
        sa.Column('device_id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('version', sa.String(20), nullable=True),
        sa.Column('running', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('label', sa.String(120), nullable=True),
        sa.Column('note', sa.String(300), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade():
    op.drop_table('agent_sessions')
