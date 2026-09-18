"""
블로그 지수 / 상위노출 가능성 판정 — 캐시·표본 테이블.

원본 로직 문서: D:/developer/blog-index-analyzer/블로그지수_상위노출_로직_전체추출.txt
SCORING_VERSION=6, DIFFICULTY_VERSION=2, verdict model v1-heuristic.

정직성 규칙(14-3): 측정 못 한 값은 지어내지 않는다. 채점 실패는 캐시하지 않는다.
버전이 바뀌면 이전 버전 표본은 모집단에서 제외한다.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text

from app.db.database import Base


def _uid() -> str:
    return str(uuid.uuid4())


class BlogIndexSnapshot(Base):
    """블로그 지수 분석 결과(전체 스키마 14-5). 1시간 캐시 + 시계열."""
    __tablename__ = "blog_index_snapshots"
    __table_args__ = (Index("ix_blog_index_blog_created", "blog_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=_uid)
    blog_id = Column(String(100), nullable=False, index=True)
    keyword_category = Column(String(30), default="default")
    scoring_version = Column(Integer, default=6)
    total_score = Column(Float, nullable=True)
    level = Column(Integer, nullable=True)
    grade = Column(String(20), nullable=True)
    measurement_complete = Column(Boolean, default=False)
    success = Column(Boolean, default=True)
    result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PostAnalysisCache(Base):
    """글 1개 풀파싱 결과. 발행된 글은 변하지 않으므로 URL 키 영구 캐시(1-4)."""
    __tablename__ = "blog_post_analysis_cache"

    post_url = Column(String(500), primary_key=True)
    blog_id = Column(String(100), index=True)
    post_no = Column(String(30), nullable=True)
    data = Column(JSON, default=dict)
    fetch_method = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SerpCache(Base):
    """블로그탭/VIEW탭/OpenAPI 검색 결과 캐시. 키워드 단위 공용(10-3: 6h)."""
    __tablename__ = "blog_serp_cache"
    __table_args__ = (Index("ix_blog_serp_kw_tab", "keyword_norm", "tab"),)

    id = Column(String(36), primary_key=True, default=_uid)
    keyword_norm = Column(String(200), nullable=False)
    keyword = Column(String(200), nullable=False)
    tab = Column(String(20), default="blog")          # blog | view | openapi | mobile_blog
    rows = Column(JSON, default=list)                  # [{rank, blog_id, post_no, post_url, title}]
    source = Column(String(30), nullable=True)         # http | http_regex | playwright | openapi
    parse_mode = Column(String(20), nullable=True)     # list | regex
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)


class BlogScoreSample(Base):
    """백분위 모집단(4-1). 같은 SCORING_VERSION, is_seed=0 만 모집단. 300개 미만이면 절대 기준표."""
    __tablename__ = "blog_score_samples"

    id = Column(String(36), primary_key=True, default=_uid)
    blog_id = Column(String(100), nullable=False, index=True)
    score = Column(Float, nullable=False)
    scoring_version = Column(Integer, default=6, index=True)
    is_seed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompetitorScore(Base):
    """경쟁자 점수 디스크 캐시(10-3: 6h). 채점 실패는 저장하지 않는다."""
    __tablename__ = "blog_competitor_scores"

    blog_id = Column(String(100), primary_key=True)
    blog_name = Column(String(200), nullable=True)
    score = Column(Float, nullable=False)
    level = Column(Integer, nullable=True)
    grade = Column(String(20), nullable=True)
    recent_activity_days = Column(Integer, nullable=True)
    scoring_version = Column(Integer, default=6)
    measured_at = Column(DateTime, default=datetime.utcnow, index=True)


class CeilingCache(Base):
    """노출 천장(7장) 24h 캐시."""
    __tablename__ = "blog_ceiling_cache"

    blog_id = Column(String(100), primary_key=True)
    result = Column(JSON, default=dict)
    measured_at = Column(DateTime, default=datetime.utcnow)


class VerdictResult(Base):
    """키워드 판정 v2 결과 기록(사용자별). 정답지 축적용."""
    __tablename__ = "blog_verdict_results"
    __table_args__ = (Index("ix_blog_verdict_user_blog_kw", "user_id", "blog_id", "keyword_norm"),)

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), nullable=True)
    blog_id = Column(String(100), nullable=False)
    keyword = Column(String(200), nullable=False)
    keyword_norm = Column(String(200), nullable=False)
    verdict = Column(String(20), nullable=True)       # likely | contested | unlikely | unknown | already_ranked
    probability = Column(Float, nullable=True)
    my_score = Column(Float, nullable=True)
    cut_line = Column(Float, nullable=True)
    model_version = Column(String(30), nullable=True)
    result = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
