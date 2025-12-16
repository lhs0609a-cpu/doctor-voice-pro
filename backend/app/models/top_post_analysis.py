"""
상위 글 분석 모델
네이버 블로그 검색 결과 상위 1~3위 글들의 패턴을 분석하여 저장
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    Text,
    Boolean,
    Index,
)
from datetime import datetime

from app.db.database import Base


class TopPostAnalysis(Base):
    """상위 글 분석 결과 테이블"""
    __tablename__ = "top_post_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(200), nullable=False, index=True)  # 검색 키워드
    rank = Column(Integer, nullable=False)  # 검색 순위 (1, 2, 3)
    blog_id = Column(String(100), nullable=False)  # 블로그 ID
    post_url = Column(String(500), nullable=False)  # 포스트 URL

    # 제목 분석
    title = Column(String(500))  # 제목 텍스트
    title_length = Column(Integer, default=0)  # 제목 글자 수
    title_has_keyword = Column(Boolean, default=False)  # 제목에 키워드 포함 여부
    title_keyword_position = Column(Integer, default=-1)  # 키워드 위치 (0=앞, 1=중간, 2=끝, -1=없음)

    # 본문 분석
    content_length = Column(Integer, default=0)  # 본문 글자 수
    image_count = Column(Integer, default=0)  # 이미지 개수
    video_count = Column(Integer, default=0)  # 동영상 개수
    heading_count = Column(Integer, default=0)  # 소제목 개수
    paragraph_count = Column(Integer, default=0)  # 문단 개수

    # 키워드 분석
    keyword_count = Column(Integer, default=0)  # 키워드 등장 횟수
    keyword_density = Column(Float, default=0.0)  # 키워드 밀도 (1000자당)

    # 추가 요소
    has_map = Column(Boolean, default=False)  # 지도 포함 여부
    has_link = Column(Boolean, default=False)  # 외부 링크 포함 여부
    has_quote = Column(Boolean, default=False)  # 인용구 포함 여부
    has_list = Column(Boolean, default=False)  # 목록 포함 여부
    like_count = Column(Integer, default=0)  # 공감 수
    comment_count = Column(Integer, default=0)  # 댓글 수
    post_date = Column(DateTime, nullable=True)  # 글 작성일
    post_age_days = Column(Integer, nullable=True)  # 작성 후 경과 일수

    # 메타 정보
    category = Column(String(50), index=True)  # 카테고리
    data_quality = Column(String(20), default='low')  # 데이터 품질 (low, medium, high)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # 복합 인덱스
    __table_args__ = (
        Index('idx_keyword_url', 'keyword', 'post_url', unique=True),
        Index('idx_category_rank', 'category', 'rank'),
    )


class AggregatedPattern(Base):
    """집계 패턴 테이블 - 카테고리별 상위글 패턴 평균"""
    __tablename__ = "aggregated_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False, unique=True, index=True)  # 카테고리
    sample_count = Column(Integer, default=0)  # 분석 샘플 수

    # 평균 값
    avg_title_length = Column(Float, default=0.0)
    avg_content_length = Column(Float, default=0.0)
    avg_image_count = Column(Float, default=0.0)
    avg_video_count = Column(Float, default=0.0)
    avg_heading_count = Column(Float, default=0.0)
    avg_paragraph_count = Column(Float, default=0.0)
    avg_keyword_count = Column(Float, default=0.0)
    avg_keyword_density = Column(Float, default=0.0)

    # 최소/최대 값
    min_content_length = Column(Integer, default=0)
    max_content_length = Column(Integer, default=0)
    min_image_count = Column(Integer, default=0)
    max_image_count = Column(Integer, default=0)

    # 비율 통계
    title_keyword_rate = Column(Float, default=0.0)  # 제목에 키워드 포함 비율
    map_usage_rate = Column(Float, default=0.0)  # 지도 사용 비율
    link_usage_rate = Column(Float, default=0.0)  # 외부 링크 사용 비율
    video_usage_rate = Column(Float, default=0.0)  # 동영상 사용 비율
    quote_usage_rate = Column(Float, default=0.0)  # 인용구 사용 비율
    list_usage_rate = Column(Float, default=0.0)  # 목록 사용 비율

    # 키워드 위치 분포
    keyword_position_front = Column(Float, default=0.0)  # 앞부분 비율
    keyword_position_middle = Column(Float, default=0.0)  # 중간 비율
    keyword_position_end = Column(Float, default=0.0)  # 끝부분 비율

    # 최적 범위 (25~75 percentile)
    optimal_content_min = Column(Integer, default=0)
    optimal_content_max = Column(Integer, default=0)
    optimal_image_min = Column(Integer, default=0)
    optimal_image_max = Column(Integer, default=0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
