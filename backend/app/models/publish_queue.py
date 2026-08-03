"""
대량 자동발행 큐 모델.
- 붙여넣기 글을 자동 포맷(글-이미지 인터리브)해 큐에 저장
- 각 글에 예약시각(시작시각 + 간격*순번)을 배정
- 확장 프로그램이 큐를 가져가 네이버 '예약발행'으로 일괄 등록
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON,
    UniqueConstraint
)
from app.db.database import Base


class NaverCategoryCache(Base):
    """확장이 네이버 에디터에서 읽어온 카테고리 목록(사용자별).

    카테고리는 네이버 에디터 DOM 안에만 존재해서 서버가 스스로 알 수 없다.
    확장이 발행/동기화 때 읽어 보내주면 여기 캐시해두고 앱 드롭다운을 채운다.
    """
    __tablename__ = "naver_category_cache"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    categories = Column(JSON)      # [{"id": "24", "name": "대표작성 칼럼(노하우,생각)"}]
    updated_at = Column(DateTime, default=datetime.utcnow)


class PublishBatch(Base):
    """한 번의 대량 등록 묶음(간격/시작시각 등 설정 보관)"""
    __tablename__ = "publish_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200))
    start_at = Column(DateTime, nullable=False)
    interval_minutes = Column(Integer, default=120)     # 글 사이 간격(분)
    images_per_post = Column(Integer, default=0)         # 0=포맷이 정한 슬롯 수 사용
    open_type = Column(String(20), default="public")
    # 네이버 카테고리 번호(예: "24"). 이름도 되지만 번호가 안정적이다. None = 네이버 기본 카테고리
    category = Column(String(100), nullable=True)
    total = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class QueuedPost(Base):
    """큐에 저장된 개별 글(예약 1건)"""
    __tablename__ = "queued_posts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("publish_batches.id"), nullable=True, index=True)

    title = Column(String(500))
    blocks = Column(JSON)               # [{type:'text', content, keyword} | {type:'image'}]
    keywords = Column(JSON)             # ["임플란트", ...]
    hashtags = Column(JSON)             # ["#임플란트", ...]
    image_pool_ids = Column(JSON)       # 배정된 pool_image id 목록(순서대로), 없으면 fetch 시 배정
    image_slots = Column(Integer, default=0)

    scheduled_at = Column(DateTime, nullable=False, index=True)
    open_type = Column(String(20), default="public")
    search = Column(Boolean, default=True)
    # 네이버 카테고리 번호(예: "24"). None = 네이버 기본 카테고리로 발행
    category = Column(String(100), nullable=True)

    # queued: 대기 / registered: 확장이 네이버 예약등록 완료 / failed / published
    status = Column(String(20), default="queued", index=True)
    naver_result = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    registered_at = Column(DateTime, nullable=True)


class ScheduleMark(Base):
    """네이버에 실제로 걸어둔 예약 1건의 '자리 표시'.

    간격 예약은 '아는 가장 늦은 예약 + N시간'으로 다음 자리를 잡는데, 그 기준이
    브라우저 localStorage 에만 있었다. 다른 PC 로 옮기거나 캐시를 지우면 기준이
    사라져 '지금'부터 다시 계산 → 이미 걸어둔 예약 위에 그대로 겹쳐 잡혔다.
    그래서 예약이 성사될 때마다 여기에 남겨 계정 단위로 기준을 공유한다.

    scheduled_at 은 UTC 가 아니라 '네이버 화면에 입력한 현지시각(KST)' 그대로다.
    앱이 예약 시각을 타임존 없이(toLocalInput) 다루므로 여기서도 변환하지 않는다.
    비교는 항상 클라이언트의 현지 시각 기준으로 한다.
    """
    __tablename__ = "schedule_marks"
    __table_args__ = (
        # 같은 블로그의 같은 시각은 한 자리뿐이다. 중복 기록/중복 예약을 DB 에서도 막는다.
        UniqueConstraint("user_id", "blog_id", "scheduled_at", name="uq_schedule_mark_slot"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 네이버 블로그 ID. 한 계정이 여러 블로그를 쓰면 기준도 블로그별로 갈라야 한다.
    blog_id = Column(String(100), nullable=True, index=True)

    scheduled_at = Column(DateTime, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    # single: 단건 발행 / batch: 준비함 일괄 / bulk: 대량 큐
    source = Column(String(20), default="single")
    created_at = Column(DateTime, default=datetime.utcnow)
