"""
DB 기반 작업 큐.

긴 작업(검색량 조회·통검 분석·원고 생성·사진 태깅·유니크화)은 HTTP 요청 안에서
돌리지 않고 여기 적재한 뒤 워커(app/services/job_worker.py)가 꺼내 처리한다.
재배포·재시작에도 작업이 남고, 진행률은 행에 기록되어 화면이 폴링으로 본다.

Redis 없이 SQLite/Postgres 어느 쪽에서도 동작하도록 행 잠금은
'locked_at + 만료' 방식으로 한다(단일 워커 전제, 여러 워커면 Postgres SKIP LOCKED 로 교체).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, Index

from app.db.database import Base


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (Index("ix_background_jobs_status_run", "status", "run_after"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    # keyword_expand | serp_analyze | draft_generate | draft_variants | photo_tag
    # image_plan | prepare_images | sheet_sync | campaign_schedule
    type = Column(String(40), nullable=False, index=True)
    payload = Column(JSON, default=dict)
    # pending | running | done | failed | cancelled
    status = Column(String(20), default="pending", index=True)
    progress = Column(Integer, default=0)
    total = Column(Integer, default=0)
    message = Column(String(300), nullable=True)      # 화면에 보여줄 한 줄 상태
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=2)
    run_after = Column(DateTime, default=datetime.utcnow, index=True)
    locked_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    # 같은 대상에 대한 중복 적재 방지용 키(예: "serp:campaign_id")
    dedupe_key = Column(String(200), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
