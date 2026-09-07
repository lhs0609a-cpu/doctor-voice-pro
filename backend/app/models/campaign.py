"""
캠페인(병원 단위 대량 발행) 모델.

설계 문서(2026-09-03 '닥터보이스 대량발행 설계안') 기준:
  Client(병원) → Blog(계정) / BriefPreset(원고 브리프)
  Campaign → CampaignKeyword → Draft → PublishJob
  SerpSnapshot: 키워드별 통합검색 분석 결과(24시간 캐시)

원칙
- 글·사진 배치·예약 상태는 전부 서버에 둔다(브라우저 localStorage 금지).
- 예약 시각(scheduled_at)은 타임존 없는 한국 현지시각 그대로 보관한다.
  네이버 화면에 입력하는 값과 같아야 하므로 서버가 변환하지 않는다.
- id 는 String(36) uuid (기존 media_pool / publish_queue 와 같은 방식).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uid() -> str:
    return str(uuid.uuid4())


class Client(Base):
    """병원(광고주). 캠페인의 기준 단위."""
    __tablename__ = "campaign_clients"

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)               # 예: 소잠한의원
    short_name = Column(String(100), nullable=True)          # 글 안에서 부르는 이름
    specialty = Column(String(100), nullable=True)           # 한의원/피부과/…
    diseases = Column(JSON, default=list)                    # ["건선", "습진", ...] 중점 질환
    treatments = Column(JSON, default=list)                  # ["다이어트", ...] 시술/프로그램
    regions = Column(JSON, default=list)                     # ["강남", "역삼"] 기준 지역
    region_expand_level = Column(Integer, default=1)         # 0=입력만 1=인접동/역 2=인접구까지
    suffixes = Column(JSON, default=list)                    # 조합 접미어. 비면 기본값 사용
    min_volume_region = Column(Integer, default=20)          # 지역 키워드 모바일 검색량 하한
    min_volume_national = Column(Integer, default=100)       # 전국 키워드 하한
    forbidden_words = Column(JSON, default=list)             # 병원별 금칙어
    tone = Column(Text, nullable=True)                       # 문체 지침(자유 서술)
    facts = Column(Text, nullable=True)                      # 병원 고정 사실(주소/원장/장비 등)
    default_collection_id = Column(String(36), nullable=True)  # 기본 사진 세트(pool_collections.id)
    sheet_url = Column(String(500), nullable=True)           # 구글시트 URL
    sheet_blog_tab = Column(String(100), default="블로그")
    sheet_cafe_tab = Column(String(100), default="카페")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    blogs = relationship("Blog", back_populates="client", cascade="all, delete-orphan")
    briefs = relationship("BriefPreset", back_populates="client", cascade="all, delete-orphan")


class Blog(Base):
    """네이버 블로그 계정. 병원 하나에 여러 개."""
    __tablename__ = "campaign_blogs"
    __table_args__ = (Index("ix_campaign_blogs_user_blog", "user_id", "blog_id"),)

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("campaign_clients.id"), nullable=False, index=True)
    blog_id = Column(String(100), nullable=False)            # 네이버 블로그 ID (URL 의 아이디)
    label = Column(String(100), nullable=True)               # 화면 표시용 별칭
    login_id = Column(String(100), nullable=True)            # 네이버 로그인 ID (에이전트 자동로그인용)
    login_pw_enc = Column(Text, nullable=True)               # Fernet 암호화 비밀번호
    daily_limit = Column(Integer, default=3)                 # 하루 발행 한도
    window_start = Column(String(5), default="09:00")        # 발행 시간대 시작(HH:MM, KST)
    window_end = Column(String(5), default="21:00")
    min_gap_minutes = Column(Integer, default=120)           # 같은 블로그 글 사이 최소 간격
    default_category = Column(String(100), nullable=True)    # 네이버 카테고리 번호
    open_type = Column(String(20), default="public")
    # active | paused | captcha | login_required | disabled
    status = Column(String(30), default="active")
    status_reason = Column(Text, nullable=True)
    status_changed_at = Column(DateTime, nullable=True)
    device_profile = Column(String(100), nullable=True)      # 에이전트 브라우저 프로필 키
    last_published_at = Column(DateTime, nullable=True)
    # 블로그 지수(SCORING_VERSION 6) 최근 결과
    index_score = Column(Float, nullable=True)
    index_level = Column(Integer, nullable=True)
    index_grade = Column(String(20), nullable=True)
    index_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="blogs")


class BriefPreset(Base):
    """원고 브리프 프리셋. 글의 흐름·규칙·고정 사실을 담는다.

    flow 예시(키네스):
      [{"title": "부모의 걱정 공감", "goal": "...", "min_chars": 250}, ...]
    """
    __tablename__ = "campaign_briefs"

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("campaign_clients.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    flow = Column(JSON, default=list)                        # 단락 흐름
    rules = Column(Text, nullable=True)                      # 자유 서술 규칙(문체/금기)
    must_include = Column(JSON, default=list)                # 반드시 들어갈 사실/문구
    avoid = Column(JSON, default=list)                       # 피할 표현
    source_text = Column(Text, nullable=True)                # 원본 원고(사실 소스)
    target_chars = Column(Integer, default=2000)
    heading_count = Column(Integer, default=4)
    keyword_count = Column(Integer, default=6)               # 본문 키워드 등장 목표
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="briefs")


class Campaign(Base):
    """병원 하나에 대한 한 묶음의 발행. 6단계 마법사의 저장 단위."""
    __tablename__ = "campaigns"

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("campaign_clients.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    step = Column(Integer, default=1)                        # 마지막으로 머문 단계 1~6
    # draft(준비중) | scheduled(예약 걸림) | running(발행 진행) | done | cancelled
    status = Column(String(20), default="draft", index=True)
    blog_ids = Column(JSON, default=list)                    # 이 캠페인이 쓰는 블로그(campaign_blogs.id)
    brief_id = Column(String(36), nullable=True)
    collection_id = Column(String(36), nullable=True)        # 사진 세트
    settings = Column(JSON, default=dict)                    # 단계별 선택값 스냅샷
    stats = Column(JSON, default=dict)                       # {keywords, drafts, jobs, published, failed}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CampaignKeyword(Base):
    """캠페인 후보 키워드 1개. 검색량·통검 판정·시트 중복 여부까지 한 행에."""
    __tablename__ = "campaign_keywords"
    __table_args__ = (Index("ix_campaign_keywords_campaign_kw", "campaign_id", "keyword"),)

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    client_id = Column(String(36), nullable=True, index=True)
    keyword = Column(String(200), nullable=False)
    region = Column(String(100), nullable=True)
    disease = Column(String(100), nullable=True)
    # manual(직접입력) | combo(지역×질환 조합) | related(검색광고 연관어) | seed(원장 제안)
    source = Column(String(20), default="manual")
    scope = Column(String(10), default="region")             # region | national
    monthly_mobile = Column(Integer, default=0)
    monthly_pc = Column(Integer, default=0)
    total_volume = Column(Integer, default=0)
    competition = Column(String(10), default="mid")
    volume_fetched_at = Column(DateTime, nullable=True)
    # 통검 판정: possible(가능) | contested(경쟁) | avoid(비추천) | unknown(미분석)
    verdict = Column(String(20), default="unknown")
    verdict_reason = Column(Text, nullable=True)
    serp_summary = Column(JSON, nullable=True)               # SerpSnapshot.summary 복사본
    in_sheet = Column(Boolean, default=False)                # 구글시트에 이미 있음
    sheet_note = Column(String(200), nullable=True)
    selected = Column(Boolean, default=False)                # 사용자가 체크
    passes_filter = Column(Boolean, default=True)            # 검색량 하한 통과
    # 내 블로그 기준 상위노출 판정(v2, 컷라인 로지스틱). my_probability 는 0~1
    my_blog_id = Column(String(100), nullable=True)
    my_verdict = Column(String(20), nullable=True)           # likely|contested|unlikely|unknown|already_ranked
    my_probability = Column(Float, nullable=True)
    my_verdict_result = Column(JSON, nullable=True)
    my_verdict_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SerpSnapshot(Base):
    """키워드 통합검색 분석 결과. 매번 새로 수집하되 24시간 안에는 재사용."""
    __tablename__ = "serp_snapshots"

    id = Column(String(36), primary_key=True, default=_uid)
    keyword_norm = Column(String(200), nullable=False, index=True)
    keyword = Column(String(200), nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)
    device = Column(String(10), default="mobile")
    posts = Column(JSON, default=list)      # [{url, title, blog_id, blog_type, section, kw_count, image_count, chars, headings, published_at}]
    summary = Column(JSON, default=dict)    # {exposed_count, hospital_ratio, has_influencer, avg_kw, avg_images, avg_chars, ...}
    verdict = Column(String(20), default="unknown")
    verdict_reason = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


class Draft(Base):
    """완성 원고 1건(생성/변형/업로드 모두 여기). 사진 배치 계획 포함."""
    __tablename__ = "campaign_drafts"

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(36), nullable=True, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id"), nullable=True, index=True)
    keyword_id = Column(String(36), nullable=True)
    keyword = Column(String(200), nullable=True)
    # generated(키워드 자동작성) | variant(원본 변형) | upload(파일) | manual(직접입력)
    source = Column(String(20), default="manual")
    parent_draft_id = Column(String(36), nullable=True)      # 변형의 원본
    brief_id = Column(String(36), nullable=True)
    title = Column(String(500), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    char_count = Column(Integer, default=0)
    # generating | ready | needs_review | failed
    status = Column(String(20), default="ready", index=True)
    checks = Column(JSON, default=dict)      # {medical_law: [...], forbidden: [...], flow_ok: bool, facts_ok: bool, similarity: 0.xx}
    image_plan = Column(JSON, default=list)  # [{slot, after_paragraph, need, pool_image_id, reason, score}]
    image_count_target = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    emphasize = Column(JSON, default=list)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishJob(Base):
    """발행 1건. 상태머신:
       queued → assigned → publishing → published | failed | uncertain
       failed → assigned(자동 재시도)  /  uncertain → published|assigned(예약목록 대조)
       assigned → queued(잠금 만료: 에이전트 죽음)
    """
    __tablename__ = "campaign_publish_jobs"
    __table_args__ = (Index("ix_campaign_jobs_blog_sched", "blog_ref_id", "scheduled_at"),)

    id = Column(String(36), primary_key=True, default=_uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    draft_id = Column(String(36), ForeignKey("campaign_drafts.id"), nullable=False, index=True)
    blog_ref_id = Column(String(36), ForeignKey("campaign_blogs.id"), nullable=False, index=True)
    naver_blog_id = Column(String(100), nullable=True)       # 발행 시 대조용(expectedBlogId)
    scheduled_at = Column(DateTime, nullable=False, index=True)   # KST naive
    status = Column(String(20), default="queued", index=True)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    lock_token = Column(String(64), nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)
    result_url = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)
    open_type = Column(String(20), default="public")
    category = Column(String(100), nullable=True)
    images_ready = Column(Boolean, default=False)            # 유니크화 사전 처리 완료
    image_variants = Column(JSON, default=list)              # [{slot, pool_image_id, variant_id, path}]
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


JOB_TERMINAL = {"published", "cancelled"}
JOB_ACTIVE = {"queued", "assigned", "publishing", "failed", "uncertain"}
