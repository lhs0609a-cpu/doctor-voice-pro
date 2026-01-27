"""add_industry_type_to_users

Revision ID: a1b2c3d4e5f6
Revises: defcab73f28d
Create Date: 2025-01-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'defcab73f28d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add industry_type column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'industry_type',
                sa.Enum(
                    'medical', 'legal', 'restaurant', 'beauty',
                    'fitness', 'education', 'realestate', 'other',
                    name='industrytype'
                ),
                nullable=False,
                server_default='medical'
            )
        )
        batch_op.add_column(
            sa.Column('business_name', sa.String(200), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('business_name')
        batch_op.drop_column('industry_type')

    # Drop the enum type
    sa.Enum(name='industrytype').drop(op.get_bind(), checkfirst=True)
