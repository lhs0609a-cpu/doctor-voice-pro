"""카페 바이럴 스레드 — 질문글 1개 + 댓글 N개를 한 덩어리로 보관한다.

기존 cafe 모델(CafeContent)은 '크롤링해 온 남의 글에 댓글 하나 달기'를 위한 것이라
스레드(글 + 그에 달리는 댓글들)를 담을 자리가 없다. 여기서는 한 덩어리를 통째로 둔다 —
댓글은 서로를 보고 쓴 것이라 따로 떼면 의미가 없기 때문이다.

1단계(2026-09-30 결정)는 원고 생성·검수까지다. 카페에 올리는 것은 사람이 한다.
그래서 게시 관련 칸(계정·예약·URL)은 아직 두지 않는다 — 쓰지 않을 칸을 미리 만들면
나중에 진짜 필요한 모양과 어긋난다.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.db.database import Base


class CafeThread(Base):
    """질문글 1개 + 댓글 N개 한 세트."""
    __tablename__ = "cafe_threads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(36), nullable=False, index=True)      # 어느 병원 것인가

    topic = Column(String(300), nullable=False)                     # 어떤 고민으로 물을 것인가
    cafe_name = Column(String(200), nullable=True)                  # 어느 카페에 올릴 것인가(참고용)

    title = Column(String(300), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    # [{"seq": 1, "persona": "...", "body": "..."}] — 순서가 곧 댓글 순서다.
    comments = Column(JSON, nullable=False, default=list)
    # 몇 번째 댓글에서만 병원 이름을 말하는가(1-based). 고객 확정값은 2.
    promo_index = Column(Integer, nullable=False, default=2)

    # {"ok": bool, "issues": [...]} — 사람이 고칠 때마다 다시 채운다.
    checks = Column(JSON, nullable=False, default=dict)
    approved = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
