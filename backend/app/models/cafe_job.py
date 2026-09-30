"""카페에 글을 올리는 일감 하나.

2-a(2026-09-30 결정): 실행기는 **질문글 하나만** 올린다. 댓글은 사람이 단다.
계정이 1~2개뿐인 동안에는 댓글 6개를 다른 사람처럼 달 수 없고, 같은 계정이 두 번 달면
그게 바로 광고 티이기 때문이다.

잠금은 **계정 단위**다. 블로그는 '블로그 하나에 미해결 발행 하나'였지만 카페는 '계정 하나가
동시에 두 곳에 글을 쓸 수 없다'가 맞는 단위다. 그래서 블로그 쪽 구조를 건드리지 않고
따로 둔다(사용자 결정) — 블로그 잠금은 운영 사고를 거치며 다듬은 것이라 흔들면 안 된다.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.database import Base

#: 아직 끝나지 않은 상태들. 이 안에 있으면 그 계정은 다른 일감을 받지 않는다.
CAFE_JOB_ACTIVE = ("queued", "assigned", "posting", "uncertain")


class CafeJob(Base):
    """스레드 하나를 카페에 올리는 일감. 지금은 '질문글 올리기' 한 종류뿐이다."""
    __tablename__ = "cafe_jobs"
    __table_args__ = (
        # 한 계정이 동시에 두 일감을 쥐지 못하게 한다. 잠금을 쥔 동안에만 값이 들어간다.
        UniqueConstraint("busy_account_id", name="uq_cafe_jobs_busy_account"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(String(36), nullable=False, index=True)   # cafe_threads.id
    account_id = Column(String(36), nullable=False)              # naver_accounts.id — 누가 올리는가
    cafe_url = Column(String(500), nullable=False)               # 어느 카페에 올리는가
    board_name = Column(String(200), nullable=True)              # 게시판 이름(있으면 실행기가 고른다)

    scheduled_at = Column(DateTime, nullable=False, index=True)  # 이 시각 이후에 올린다(KST naive)
    # queued | assigned | posting | submitted | uncertain | failed | cancelled
    status = Column(String(20), nullable=False, default="queued", index=True)
    lock_token = Column(String(64), nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)
    # 잠금을 쥔 동안에만 account_id 가 복사된다. 유니크 제약이 '한 계정 한 일감'을 지킨다.
    busy_account_id = Column(String(36), nullable=True)

    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    result_url = Column(String(500), nullable=True)              # 올라간 글 주소
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
