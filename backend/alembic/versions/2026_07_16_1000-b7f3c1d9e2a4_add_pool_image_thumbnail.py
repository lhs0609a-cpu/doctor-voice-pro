"""add thumbnail column to pool_images

목록 조회(list_pool)가 원본 BLOB(data)을 전부 메모리로 올려 OOM 이 나던 문제를 막기 위해,
조회 전용 썸네일을 미리 만들어 보관한다.

Revision ID: b7f3c1d9e2a4
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b7f3c1d9e2a4'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pool_images_columns() -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'pool_images' not in insp.get_table_names():
        return set()
    return {c['name'] for c in insp.get_columns('pool_images')}


def upgrade() -> None:
    # pool_images 는 alembic 이 아니라 create_all 로 만들어진 테이블이라
    # 환경에 따라 이미 컬럼이 있거나 테이블 자체가 없을 수 있다.
    # 부팅 시 alembic upgrade 가 실패하면 서버가 안 뜨므로 방어적으로 처리한다.
    cols = _pool_images_columns()
    if not cols or 'thumbnail' in cols:
        return
    op.add_column('pool_images', sa.Column('thumbnail', sa.Text(), nullable=True))


def downgrade() -> None:
    cols = _pool_images_columns()
    if 'thumbnail' not in cols:
        return
    op.drop_column('pool_images', 'thumbnail')
