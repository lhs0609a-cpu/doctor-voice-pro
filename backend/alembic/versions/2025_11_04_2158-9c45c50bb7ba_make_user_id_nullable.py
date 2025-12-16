"""make_user_id_nullable

Revision ID: 9c45c50bb7ba
Revises: 2bd23bba19a5
Create Date: 2025-11-04 21:58:25.373772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c45c50bb7ba'
down_revision: Union[str, None] = '2bd23bba19a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make user_id nullable in posts table
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.alter_column('user_id',
                              existing_type=sa.UUID(),
                              nullable=True)

    # Add scheduled_at and is_favorited columns if they don't exist
    with op.batch_alter_table('posts', schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column('scheduled_at', sa.DateTime(), nullable=True))
        except:
            pass  # Column already exists

        try:
            batch_op.add_column(sa.Column('is_favorited', sa.Boolean(), nullable=False, server_default='0'))
        except:
            pass  # Column already exists


def downgrade() -> None:
    # Revert user_id to NOT NULL (this will fail if there are NULL values)
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.alter_column('user_id',
                              existing_type=sa.UUID(),
                              nullable=False)

    # Remove added columns
    with op.batch_alter_table('posts', schema=None) as batch_op:
        try:
            batch_op.drop_column('is_favorited')
        except:
            pass

        try:
            batch_op.drop_column('scheduled_at')
        except:
            pass
