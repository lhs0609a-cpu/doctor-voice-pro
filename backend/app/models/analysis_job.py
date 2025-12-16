"""
대량 분석 작업 모델
카테고리별 상위글 대량 분석 작업을 관리
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Text,
    Index,
    JSON,
)
from datetime import datetime
import uuid

from app.db.database import Base


class AnalysisJob(Base):
    """대량 분석 작업 테이블"""
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(50), nullable=False, index=True)
    target_count = Column(Integer, nullable=False)  # 목표 분석 수 (100, 500, 1000)

    # 작업 상태
    status = Column(String(20), default='pending', index=True)  # pending, running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100 진행률

    # 수집 현황
    keywords_collected = Column(Integer, default=0)  # 수집된 키워드 수
    keywords_total = Column(Integer, default=0)  # 목표 키워드 수
    posts_analyzed = Column(Integer, default=0)  # 분석 완료된 글 수
    posts_failed = Column(Integer, default=0)  # 분석 실패한 글 수

    # 수집된 키워드 목록
    keywords = Column(JSON, default=list)  # ["키워드1", "키워드2", ...]

    # 오류 정보
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)  # 상세 에러 로그

    # 결과 요약
    result_summary = Column(JSON, nullable=True)  # 분석 결과 요약

    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)  # 실제 분석 시작 시간
    completed_at = Column(DateTime, nullable=True)

    # 인덱스
    __table_args__ = (
        Index('idx_job_status_category', 'status', 'category'),
        Index('idx_job_created', 'created_at'),
    )


class CollectedKeyword(Base):
    """수집된 키워드 테이블"""
    __tablename__ = "collected_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False, index=True)
    keyword = Column(String(200), nullable=False)
    source = Column(String(50), default='seed')  # seed, related, autocomplete

    # 분석 상태
    is_analyzed = Column(Integer, default=0)  # 0: 미분석, 1: 분석완료
    analysis_count = Column(Integer, default=0)  # 이 키워드로 분석한 글 수
    last_analyzed_at = Column(DateTime, nullable=True)

    # 메타 정보
    search_volume = Column(Integer, nullable=True)  # 검색량 (추후 확장)
    competition = Column(String(20), nullable=True)  # 경쟁도 (low, medium, high)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 복합 유니크 인덱스
    __table_args__ = (
        Index('idx_keyword_category_unique', 'category', 'keyword', unique=True),
        Index('idx_keyword_analyzed', 'is_analyzed'),
    )
