"""발행 큐의 글에 대상 블로그를 붙인다(확장 제거: PC 실행기가 블로그별로 가져가야 한다)."""
from alembic import op
import sqlalchemy as sa

revision = '20260910_queue_blog_ref'
down_revision = '20260908_autopilot'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('queued_posts'):
        return
    columns = {c['name'] for c in inspector.get_columns('queued_posts')}
    if 'blog_ref_id' not in columns:
        op.add_column('queued_posts', sa.Column('blog_ref_id', sa.String(36), nullable=True))
        op.create_index('ix_queued_posts_blog_ref_id', 'queued_posts', ['blog_ref_id'])
    if 'final_action' not in columns:
        op.add_column('queued_posts', sa.Column('final_action', sa.String(20), nullable=True,
                                                server_default='schedule'))


def downgrade():
    op.drop_column('queued_posts', 'final_action')
    op.drop_index('ix_queued_posts_blog_ref_id', table_name='queued_posts')
    op.drop_column('queued_posts', 'blog_ref_id')
