"""블로그별 고정 프록시(암호화 저장)."""
from alembic import op
import sqlalchemy as sa

revision = '20260916_blog_proxy'
down_revision = '20260915_agent_pair_requests'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('campaign_blogs'):
        columns = {c['name'] for c in inspector.get_columns('campaign_blogs')}
        if 'proxy_enc' not in columns:
            op.add_column('campaign_blogs', sa.Column('proxy_enc', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('campaign_blogs', 'proxy_enc')
