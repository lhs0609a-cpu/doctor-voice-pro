"""
키워드 실검색량 캐시 모델.
- 네이버 검색광고 API(keywordstool)는 일일 호출 제한이 있고 데이터도 하루 단위로만 갱신된다.
- 그래서 키워드별 검색량을 날짜 단위로 캐시한다. fetched_date == 오늘이면 API 재호출 없이 재사용.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Date, DateTime, JSON

from app.db.database import Base


class KeywordVolumeCache(Base):
    """키워드 1개의 하루치 검색량 스냅샷."""
    __tablename__ = "keyword_volume_cache"

    # 키워드는 네이버가 공백 없는 대문자로 정규화해 돌려주므로 그 형태를 PK로 쓴다.
    keyword = Column(String(200), primary_key=True)
    monthly_pc = Column(Integer, default=0)          # 월간 PC 검색수
    monthly_mobile = Column(Integer, default=0)      # 월간 모바일 검색수
    total_volume = Column(Integer, default=0)        # pc + mobile
    competition = Column(String(10), default="mid")  # low | mid | high (compIdx 매핑)
    comp_idx_raw = Column(String(20))                # 원본 '낮음/중간/높음'
    est_cpc = Column(Integer, default=0)             # 추정 CPC(원)
    raw = Column(JSON)                               # 원본 응답 항목(디버깅/확장용)

    fetched_date = Column(Date, index=True)          # 캐시 기준 날짜(오늘이면 히트)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
