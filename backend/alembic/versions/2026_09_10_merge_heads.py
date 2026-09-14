"""두 갈래(2025년 스키마 / 2026-09 캠페인·실행기)를 합친다.

두 갈래가 그대로 있으면 컨테이너 시작 명령의 `alembic upgrade head` 가
"Multiple head revisions are present" 로 죽어 서버가 뜨지 않는다.
"""

revision = '20260910_merge_heads'
down_revision = ('b7f3c1d9e2a4', '20260910_agent_sessions')
branch_labels = None
depends_on = None


def upgrade():
    """합류점일 뿐이라 바꿀 것이 없다."""


def downgrade():
    """갈래를 되돌리지 않는다 — 각 마이그레이션을 개별로 내려야 한다."""
