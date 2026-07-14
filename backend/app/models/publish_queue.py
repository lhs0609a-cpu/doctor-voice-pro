"""
대량 자동발행 큐 모델.
- 붙여넣기 글을 자동 포맷(글-이미지 인터리브)해 큐에 저장
- 각 글에 예약시각(시작시각 + 간격*순번)을 배정
- 확장 프로그램이 큐를 가져가 네이버 '예약발행'으로 일괄 등록
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
)
from app.db.database import Base


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

    # queued: 대기 / registered: 확장이 네이버 예약등록 완료 / failed / published
    status = Column(String(20), default="queued", index=True)
    naver_result = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    registered_at = Column(DateTime, nullable=True)
