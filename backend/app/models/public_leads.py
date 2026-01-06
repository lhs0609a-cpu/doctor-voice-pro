"""공공데이터 기반 리드 수집 모델"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class BusinessCategory(str, Enum):
    """업종 카테고리"""
    RESTAURANT = "음식점"
    CAFE = "카페"
    HOSPITAL = "병원"
    CLINIC = "의원"
    DENTAL = "치과"
    PHARMACY = "약국"
    ACADEMY = "학원"
    BEAUTY = "미용실"
    GYM = "헬스장"
    RETAIL = "소매업"
    REAL_ESTATE = "부동산"
    LAUNDRY = "세탁소"
    PET = "반려동물"
    AUTO = "자동차"
    OTHER = "기타"


class LeadStatus(str, Enum):
    """리드 상태"""
    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"


# ============ SQLAlchemy Model ============
class PublicLeadDB(Base):
    """공공데이터 기반 리드 (DB 모델)"""
    __tablename__ = "public_leads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)

    # 기본 정보
    business_name = Column(String(200), nullable=False)
    category = Column(String(100))
    sub_category = Column(String(100))

    # 위치 정보
    address = Column(Text)
    road_address = Column(Text)
    sido = Column(String(50), index=True)
    sigungu = Column(String(50), index=True)
    dong = Column(String(50))

    # 연락처 정보
    phone = Column(String(50))
    email = Column(String(200))
    website = Column(String(500))

    # 사업자 정보
    business_number = Column(String(50))
    owner_name = Column(String(100))
    open_date = Column(String(50))

    # 상태 및 메타
    status = Column(String(20), default="new", index=True)
    score = Column(Integer, default=0)
    notes = Column(Text)
    tags = Column(JSON, default=[])

    # 수집 정보
    source = Column(String(100), default="public_data")
    collected_at = Column(DateTime)
    last_contacted_at = Column(DateTime)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "business_name": self.business_name,
            "category": self.category,
            "sub_category": self.sub_category,
            "address": self.address,
            "road_address": self.road_address,
            "sido": self.sido,
            "sigungu": self.sigungu,
            "dong": self.dong,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "business_number": self.business_number,
            "owner_name": self.owner_name,
            "open_date": self.open_date,
            "status": self.status,
            "score": self.score,
            "notes": self.notes,
            "tags": self.tags or [],
            "source": self.source,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "last_contacted_at": self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============ Pydantic Models ============
class PublicLead(BaseModel):
    """공공데이터 기반 리드"""
    id: Optional[str] = None
    user_id: Optional[str] = None

    # 기본 정보
    business_name: str  # 상호명
    category: str  # 업종
    sub_category: Optional[str] = None  # 세부업종

    # 위치 정보
    address: str  # 주소
    road_address: Optional[str] = None  # 도로명주소
    sido: str  # 시도
    sigungu: str  # 시군구
    dong: Optional[str] = None  # 동

    # 연락처 정보
    phone: Optional[str] = None  # 전화번호
    email: Optional[str] = None  # 이메일 (추출된)
    website: Optional[str] = None  # 웹사이트

    # 사업자 정보
    business_number: Optional[str] = None  # 사업자등록번호
    owner_name: Optional[str] = None  # 대표자명
    open_date: Optional[str] = None  # 개업일

    # 상태 및 메타
    status: LeadStatus = LeadStatus.NEW
    score: int = 0  # 리드 스코어 (0-100)
    notes: Optional[str] = None
    tags: List[str] = []

    # 수집 정보
    source: str = "public_data"  # 데이터 출처
    collected_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LeadSearchRequest(BaseModel):
    """리드 검색 요청"""
    sido: str  # 시도 (필수)
    sigungu: Optional[str] = None  # 시군구
    dong: Optional[str] = None  # 동
    category: Optional[str] = None  # 업종
    keyword: Optional[str] = None  # 키워드
    limit: int = 100  # 최대 수집 수


class LeadSearchResponse(BaseModel):
    """리드 검색 응답"""
    success: bool
    total: int
    leads: List[PublicLead]
    message: Optional[str] = None


class LeadStats(BaseModel):
    """리드 통계"""
    total: int
    by_status: dict
    by_category: dict
    by_region: dict
    recent_collected: int
    contacted_today: int


# 시도 목록
SIDO_LIST = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시",
    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
    "경기도", "강원도", "충청북도", "충청남도",
    "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
]

# 업종 목록
CATEGORY_LIST = [
    {"code": "I", "name": "음식점", "sub": ["한식", "중식", "일식", "양식", "분식", "치킨", "피자", "카페"]},
    {"code": "Q", "name": "의료", "sub": ["병원", "의원", "치과", "한의원", "약국"]},
    {"code": "P", "name": "교육", "sub": ["학원", "교습소", "어린이집"]},
    {"code": "S", "name": "서비스", "sub": ["미용실", "네일샵", "피부관리", "헬스장", "세탁소"]},
    {"code": "G", "name": "소매", "sub": ["편의점", "마트", "의류", "화장품", "꽃집"]},
    {"code": "L", "name": "부동산", "sub": ["공인중개사"]},
    {"code": "R", "name": "반려동물", "sub": ["동물병원", "애견샵", "펫호텔"]},
    {"code": "H", "name": "자동차", "sub": ["정비소", "세차장", "주유소"]},
]
