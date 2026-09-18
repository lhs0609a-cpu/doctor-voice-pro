"""store post-publication search evidence"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_job_verification"
down_revision = "6f1a2c3d4e5f"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("campaign_publish_jobs", sa.Column("verification", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("campaign_publish_jobs", "verification")
