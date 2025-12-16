"""add_new_post_features

Revision ID: defcab73f28d
Revises: 9c45c50bb7ba
Create Date: 2025-11-04 22:46:48.530854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'defcab73f28d'
down_revision: Union[str, None] = '9c45c50bb7ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to posts table
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suggested_titles', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('suggested_subtitles', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('content_analysis', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('forbidden_words_check', sa.JSON(), nullable=True))

    # Add tone_preset to doctor_profiles table
    with op.batch_alter_table('doctor_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tone_preset', sa.String(50), nullable=True))

    # Create writing_requests table
    op.create_table(
        'writing_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('request_text', sa.Text(), nullable=False),
        sa.Column('is_common', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # Drop writing_requests table
    op.drop_table('writing_requests')

    # Remove tone_preset from doctor_profiles
    with op.batch_alter_table('doctor_profiles', schema=None) as batch_op:
        batch_op.drop_column('tone_preset')

    # Remove new columns from posts table
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_column('forbidden_words_check')
        batch_op.drop_column('content_analysis')
        batch_op.drop_column('suggested_subtitles')
        batch_op.drop_column('suggested_titles')
