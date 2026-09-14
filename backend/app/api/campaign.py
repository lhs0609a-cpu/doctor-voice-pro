"""
캠페인 API — 병원 단위 대량 발행 흐름.

/campaign/clients            병원 CRUD, 블로그 계정, 브리프 프리셋
/campaign/campaigns          캠페인 CRUD + 6단계(키워드/원고/사진/예약/현황)
/campaign/tasks              백그라운드 작업 상태(폴링)
/campaign/agent              발행 실행기(확장·에이전트)용: 잡 클레임/결과/계정 상태
"""
from __future__ import annotations

import base64
import io
import re
import secrets
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import User
from app.models.background_job import BackgroundJob
from app.models.campaign import (
    JOB_ACTIVE, AgentDevice, AgentPairCode, AgentPairRequest, AgentSession, AutopilotPolicy, AutomationRun, Blog, BriefPreset, Campaign, CampaignKeyword, Client, Draft, PublishJob, PublishAttempt, SerpSnapshot,
)
from app.models.media_pool import ImageVariant, PoolCollection, PoolCollectionMember, PoolImage
from app.models.publish_queue import ScheduleMark
from app.services import campaign_crypto as crypto
from app.services import campaign_jobs
from app.services import campaign_writer as writer
from app.services import image_uniquifier as uniq
from app.services import job_worker
from app.services import schedule_engine as se
from app.services import publish_protocol as protocol
from app.services.autopilot import PolicyConfig

router = APIRouter()


class AutopilotIn(PolicyConfig):
    enabled: bool = True


@router.get('/campaigns/{campaign_id}/autopilot')
async def get_autopilot(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.campaign import AutopilotPolicy
    campaign = await _owned(db, Campaign, campaign_id, current_user, '캠페인')
    policy = await db.get(AutopilotPolicy, campaign_id)
    task = await db.get(BackgroundJob, policy.last_job_id) if policy and policy.last_job_id else None
    return {'enabled': bool(policy and policy.enabled),
            'config': PolicyConfig.model_validate(policy.config if policy else (campaign.settings or {}).get('landing', {})).model_dump(),
            'message': policy.message if policy else '운영 기준을 저장하면 키워드 발굴부터 시작합니다',
            'next_run_at': policy.next_run_at.isoformat() + 'Z' if policy else None,
            'reserved_today': policy.reserved_today if policy and policy.quota_day == se.kst_now().date().isoformat() else 0,
            'task': _task_out(task) if task else None}


@router.put('/campaigns/{campaign_id}/autopilot')
async def configure_autopilot(campaign_id: str, body: AutopilotIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.campaign import AutopilotPolicy
    from app.services.autopilot import preflight, tick
    campaign = await _owned(db, Campaign, campaign_id, current_user, '캠페인')
    uid = _uid(current_user)
    config = PolicyConfig.model_validate(body.model_dump())
    if body.enabled:
        issues = await preflight(db, campaign, config)
        if issues:
            raise HTTPException(status_code=400, detail={'message': '자동 운영 준비가 필요합니다', 'issues': issues})
    await db.execute(update(AutopilotPolicy).where(AutopilotPolicy.campaign_id == campaign_id).values(updated_at=datetime.utcnow()))
    await db.execute(update(Campaign).where(Campaign.id == campaign_id).values(updated_at=datetime.utcnow()))
    policy = await db.get(AutopilotPolicy, campaign_id, populate_existing=True)
    if not policy:
        policy = AutopilotPolicy(campaign_id=campaign_id, user_id=uid, reserved_today=0)
        db.add(policy)
    policy.config, policy.enabled = config.model_dump(), body.enabled
    campaign.settings = {**(campaign.settings or {}), 'landing': {
        key: value for key, value in config.model_dump().items() if key.startswith('landing_')}}
    policy.next_run_at = datetime.utcnow()
    policy.message = '자동 운영 시작' if body.enabled else '일시정지 — 이미 네이버에 등록된 예약은 유지됩니다'
    if not body.enabled:
        active = await db.get(AutomationRun, campaign_id)
        if active:
            await db.execute(update(BackgroundJob).where(BackgroundJob.id == active.job_id,
                BackgroundJob.status.in_(['pending', 'running'])).values(status='cancelled', finished_at=datetime.utcnow()))
    await db.commit()
    if body.enabled:
        await tick(db, campaign_id)
    return await get_autopilot(campaign_id, current_user, db)


@router.put('/campaigns/{campaign_id}/landing')
async def configure_landing(campaign_id: str, body: PolicyConfig, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.campaign import AutopilotPolicy
    campaign = await _owned(db, Campaign, campaign_id, current_user, '캠페인')
    await db.execute(update(AutopilotPolicy).where(AutopilotPolicy.campaign_id == campaign_id).values(updated_at=datetime.utcnow()))
    await db.execute(update(Campaign).where(Campaign.id == campaign_id).values(updated_at=datetime.utcnow()))
    await db.refresh(campaign)
    landing = {key: value for key, value in body.model_dump().items() if key.startswith('landing_')}
    campaign.settings = {**(campaign.settings or {}), 'landing': landing}
    policy = await db.get(AutopilotPolicy, campaign_id, populate_existing=True)
    if policy:
        policy.config = {**policy.config, **landing}
    await db.commit()
    return landing


def _uid(user: User) -> str:
    identity = inspect(user).identity
    return str(identity[0]) if identity else str(user.id)


async def _owned(db: AsyncSession, model, obj_id: str, user: User, what: str = "항목"):
    obj = await db.get(model, obj_id)
    if not obj or str(getattr(obj, "user_id", "")) != _uid(user):
        raise HTTPException(status_code=404, detail=f"{what}을(를) 찾을 수 없습니다")
    return obj


# ======================================================================
# 병원(Client)
# ======================================================================
class ClientIn(BaseModel):
    name: str
    short_name: Optional[str] = None
    specialty: Optional[str] = None
    diseases: List[str] = []
    treatments: List[str] = []
    regions: List[str] = []
    region_expand_level: int = 1
    suffixes: List[str] = []
    min_volume_region: int = 20
    min_volume_national: int = 100
    forbidden_words: List[str] = []
    tone: Optional[str] = None
    facts: Optional[str] = None
    default_collection_id: Optional[str] = None
    sheet_url: Optional[str] = None
    sheet_blog_tab: Optional[str] = "블로그"
    sheet_cafe_tab: Optional[str] = "카페"


class BlogOut(BaseModel):
    id: str
    client_id: str
    blog_id: str
    label: Optional[str] = None
    login_id: Optional[str] = None
    has_password: bool = False
    daily_limit: int = 3
    window_start: str = "09:00"
    window_end: str = "21:00"
    min_gap_minutes: int = 120
    default_category: Optional[str] = None
    open_type: str = "public"
    status: str = "active"
    status_reason: Optional[str] = None
    last_published_at: Optional[datetime] = None


class BriefOut(BaseModel):
    id: str
    client_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    flow: List[Dict[str, Any]] = []
    rules: Optional[str] = None
    must_include: List[str] = []
    avoid: List[str] = []
    source_text: Optional[str] = None
    target_chars: int = 2000
    heading_count: int = 4
    keyword_count: int = 6
    is_default: bool = False


class ClientOut(ClientIn):
    id: str
    active: bool = True
    created_at: Optional[datetime] = None
    blogs: List[BlogOut] = []
    briefs: List[BriefOut] = []


def _blog_out(b: Blog) -> BlogOut:
    return BlogOut(
        id=b.id, client_id=b.client_id, blog_id=b.blog_id, label=b.label, login_id=b.login_id,
        has_password=bool(b.login_pw_enc), daily_limit=b.daily_limit or 3,
        window_start=b.window_start or "09:00", window_end=b.window_end or "21:00",
        min_gap_minutes=b.min_gap_minutes or 120, default_category=b.default_category,
        open_type=b.open_type or "public", status=b.status or "active", status_reason=b.status_reason,
        last_published_at=b.last_published_at,
    )


def _brief_out(b: BriefPreset) -> BriefOut:
    return BriefOut(
        id=b.id, client_id=b.client_id, name=b.name, description=b.description, flow=b.flow or [],
        rules=b.rules, must_include=b.must_include or [], avoid=b.avoid or [], source_text=b.source_text,
        target_chars=b.target_chars or 2000, heading_count=b.heading_count or 4,
        keyword_count=b.keyword_count or 6, is_default=bool(b.is_default),
    )


async def _client_out(db: AsyncSession, c: Client) -> ClientOut:
    blogs = (await db.execute(select(Blog).where(Blog.client_id == c.id).order_by(Blog.created_at))).scalars().all()
    briefs = (await db.execute(select(BriefPreset).where(BriefPreset.client_id == c.id).order_by(BriefPreset.created_at))).scalars().all()
    return ClientOut(
        id=c.id, name=c.name, short_name=c.short_name, specialty=c.specialty,
        diseases=c.diseases or [], treatments=c.treatments or [], regions=c.regions or [],
        region_expand_level=c.region_expand_level or 1, suffixes=c.suffixes or [],
        min_volume_region=c.min_volume_region or 20, min_volume_national=c.min_volume_national or 100,
        forbidden_words=c.forbidden_words or [], tone=c.tone, facts=c.facts,
        default_collection_id=c.default_collection_id, sheet_url=c.sheet_url,
        sheet_blog_tab=c.sheet_blog_tab, sheet_cafe_tab=c.sheet_cafe_tab,
        active=bool(c.active), created_at=c.created_at,
        blogs=[_blog_out(b) for b in blogs], briefs=[_brief_out(b) for b in briefs],
    )


@router.get("/clients", response_model=List[ClientOut])
async def list_clients(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Client).where(Client.user_id == _uid(current_user), Client.active == True).order_by(Client.created_at))).scalars().all()  # noqa: E712
    return [await _client_out(db, c) for c in rows]


@router.post("/clients", response_model=ClientOut)
async def create_client(body: ClientIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = Client(user_id=_uid(current_user), **body.model_dump())
    db.add(c)
    await db.commit()
    return await _client_out(db, c)


@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(client_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Client, client_id, current_user, "병원")
    return await _client_out(db, c)


@router.put("/clients/{client_id}", response_model=ClientOut)
async def update_client(client_id: str, body: ClientIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Client, client_id, current_user, "병원")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    await db.commit()
    return await _client_out(db, c)


@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Client, client_id, current_user, "병원")
    c.active = False
    await db.commit()
    return {"success": True}


# 인터뷰에 나온 병원들을 예시로 넣어 주는 시드(초보자 온보딩)
SEED_CLIENTS = [
    {"name": "로담한의원", "specialty": "한의원", "diseases": ["여드름흉터", "수두자국", "대상포진"], "regions": ["강남"]},
    {"name": "소잠한의원", "specialty": "한의원", "diseases": ["건선", "습진", "한포진", "주부습진", "아토피", "가려움"], "regions": ["강남"]},
    {"name": "위례한의원", "specialty": "한의원", "diseases": ["다이어트", "다한증"], "regions": ["위례"]},
    {"name": "다은의원", "specialty": "피부과/가정의학과/이비인후과/내과", "diseases": ["피부과", "가정의학과", "이비인후과", "내과"], "regions": ["강남"]},
    {"name": "키네스센터", "specialty": "키성장", "diseases": ["키성장", "성장클리닉", "성장검사"], "regions": ["강남"]},
]


@router.post("/clients/seed-examples", response_model=List[ClientOut])
async def seed_example_clients(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """예시 병원 5곳(인터뷰 기준)을 넣는다. 이미 같은 이름이 있으면 건너뛴다."""
    existing = {c.name for c in (await db.execute(select(Client).where(Client.user_id == _uid(current_user)))).scalars().all()}
    created: List[Client] = []
    for seed in SEED_CLIENTS:
        if seed["name"] in existing:
            continue
        c = Client(user_id=_uid(current_user), **seed)
        db.add(c)
        created.append(c)
    await db.flush()
    # 키네스에는 기본 브리프를 붙인다
    for c in created:
        if c.name.startswith("키네스"):
            db.add(BriefPreset(user_id=_uid(current_user), client_id=c.id, is_default=True, **BUILTIN_BRIEFS[0]["preset"]))
    await db.commit()
    rows = (await db.execute(select(Client).where(Client.user_id == _uid(current_user), Client.active == True).order_by(Client.created_at))).scalars().all()  # noqa: E712
    return [await _client_out(db, c) for c in rows]


# ======================================================================
# 블로그 계정
# ======================================================================
class BlogIn(BaseModel):
    blog_id: str
    label: Optional[str] = None
    login_id: Optional[str] = None
    login_pw: Optional[str] = None            # 저장 시 암호화. 비우면 기존 값 유지
    daily_limit: int = 3
    window_start: str = "09:00"
    window_end: str = "21:00"
    min_gap_minutes: int = 120
    default_category: Optional[str] = None
    open_type: str = "public"


def _clean_blog_id(raw: str) -> str:
    """주소를 통째로 붙여 넣어도 아이디만 남긴다(https://blog.naver.com/abc123 → abc123).
    그대로 저장하면 실행기가 없는 블로그 주소로 가서 발행이 실패하므로, 모양이 틀린 값은 여기서 막는다."""
    import re
    from app.blogindex import normalize_blog_id
    bid = normalize_blog_id(raw)
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,50}", bid):
        raise HTTPException(status_code=400, detail="네이버 블로그 아이디는 blog.naver.com/ 뒤의 영어·숫자 부분입니다 (예: abc123)")
    return bid


@router.post("/clients/{client_id}/blogs", response_model=BlogOut)
async def add_blog(client_id: str, body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _owned(db, Client, client_id, current_user, "병원")
    b = Blog(
        user_id=_uid(current_user), client_id=client_id, blog_id=_clean_blog_id(body.blog_id), label=body.label,
        login_id=body.login_id, login_pw_enc=crypto.encrypt(body.login_pw), daily_limit=body.daily_limit,
        window_start=body.window_start, window_end=body.window_end, min_gap_minutes=body.min_gap_minutes,
        default_category=body.default_category, open_type=body.open_type,
    )
    db.add(b)
    await db.commit()
    return _blog_out(b)


@router.put("/blogs/{blog_ref_id}", response_model=BlogOut)
async def update_blog(blog_ref_id: str, body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    b.blog_id = _clean_blog_id(body.blog_id)
    b.label, b.login_id = body.label, body.login_id
    if body.login_pw:
        b.login_pw_enc = crypto.encrypt(body.login_pw)
    b.daily_limit, b.window_start, b.window_end = body.daily_limit, body.window_start, body.window_end
    b.min_gap_minutes, b.default_category, b.open_type = body.min_gap_minutes, body.default_category, body.open_type
    await db.commit()
    return _blog_out(b)


class BlogStatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


@router.post("/blogs/{blog_ref_id}/status", response_model=BlogOut)
async def set_blog_status(blog_ref_id: str, body: BlogStatusIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    if body.status not in ("active", "paused", "captcha", "login_required", "disabled"):
        raise HTTPException(status_code=400, detail="상태 값이 올바르지 않습니다")
    b.status, b.status_reason, b.status_changed_at = body.status, body.reason, datetime.utcnow()
    await db.commit()
    return _blog_out(b)


@router.delete("/blogs/{blog_ref_id}")
async def delete_blog(blog_ref_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    active = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.blog_ref_id == b.id, PublishJob.status.in_(list(JOB_ACTIVE))))).scalar() or 0
    if active:
        raise HTTPException(status_code=400, detail=f"이 블로그에 진행 중인 발행 {active}건이 있어 삭제할 수 없습니다. 먼저 예약을 취소하세요.")
    await db.delete(b)
    await db.commit()
    return {"success": True}


# ======================================================================
# 브리프 프리셋
# ======================================================================
BUILTIN_BRIEFS = [
    {
        "key": "kines",
        "label": "키네스 키성장 원고 (5단 흐름)",
        "preset": {
            "name": "키네스 키성장 원고",
            "description": "키네스센터 요청 흐름: 부모 공감 → 키성장 정보 → 정밀검사 필요성 → 키네스 검사 프로세스 → 프로그램 → 마무리",
            "flow": [
                {"title": "부모의 걱정에 공감", "goal": "아이 키가 또래보다 작아 걱정하는 부모 마음에 공감하며 시작. 질문형 도입 1~2문장.", "min_chars": 250},
                {"title": "키성장에 관한 정보", "goal": "성장판, 성장 속도, 사춘기 시기, 유전 외 요인 등 부모가 알아야 할 기본 정보를 쉽게.", "min_chars": 400},
                {"title": "아이마다 정밀 검사가 중요한 이유", "goal": "같은 키라도 원인이 다르다. 성장판 상태·골연령·호르몬·생활습관에 따라 접근이 달라져 개별 검사가 필요함을 설명.", "min_chars": 350},
                {"title": "키네스의 정밀 검사 프로세스", "goal": "원본 원고에 있는 검사 항목과 순서만 사용해 상담→검사→분석→설명 과정을 구체적으로.", "min_chars": 400},
                {"title": "키네스 프로그램", "goal": "검사 결과에 따라 맞춤 구성되는 프로그램을 원본 원고 범위 안에서 소개. 효과 단정 표현 금지.", "min_chars": 350},
                {"title": "마무리", "goal": "골든타임을 놓치지 않도록 상담 권유. 부담 없는 톤. 과장·확정 표현 없이.", "min_chars": 150},
            ],
            "rules": "부모(주로 엄마)에게 설명하는 정중한 말투. 의학 용어는 한 번 풀어서 쓴다. '반드시 큰다', '최고', '유일' 같은 단정·최상급 금지. 가격·이벤트 언급 금지. 흐름의 순서를 바꾸지 않는다.",
            "must_include": ["키네스", "정밀 검사", "성장판"],
            "avoid": ["100%", "완치", "보장", "무조건", "최고", "유일", "부작용 없음"],
            "target_chars": 2200,
            "heading_count": 5,
            "keyword_count": 6,
        },
    },
    {
        "key": "skin",
        "label": "피부질환 정보형 (공감→원인→치료→마무리)",
        "preset": {
            "name": "피부질환 정보형",
            "description": "건선·습진·아토피 등 피부질환 블로그의 기본 흐름",
            "flow": [
                {"title": "증상 공감", "goal": "가려움·재발로 힘든 환자 상황에 공감하며 시작.", "min_chars": 200},
                {"title": "원인과 특징", "goal": "질환의 원인·유형·악화 요인을 쉽게 설명.", "min_chars": 400},
                {"title": "치료 접근", "goal": "병원의 치료 방향을 사실 소스 안에서 설명. 효과 단정 금지.", "min_chars": 450},
                {"title": "생활 관리", "goal": "집에서 할 수 있는 관리 팁 3~4개.", "min_chars": 300},
                {"title": "마무리", "goal": "상담 권유. 과장 없이.", "min_chars": 150},
            ],
            "rules": "환자에게 설명하듯 정중하고 쉽게. 최상급·단정 표현 금지.",
            "must_include": [],
            "avoid": ["완치", "100%", "부작용 없음", "최고"],
            "target_chars": 2000, "heading_count": 4, "keyword_count": 6,
        },
    },
]


class BriefIn(BaseModel):
    client_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    flow: List[Dict[str, Any]] = []
    rules: Optional[str] = None
    must_include: List[str] = []
    avoid: List[str] = []
    source_text: Optional[str] = None
    target_chars: int = 2000
    heading_count: int = 4
    keyword_count: int = 6
    is_default: bool = False


@router.get("/briefs/builtin")
async def builtin_briefs(current_user: User = Depends(get_current_user)):
    return [{"key": b["key"], "label": b["label"], "preset": b["preset"]} for b in BUILTIN_BRIEFS]


@router.get("/briefs", response_model=List[BriefOut])
async def list_briefs(client_id: Optional[str] = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(BriefPreset).where(BriefPreset.user_id == _uid(current_user))
    if client_id:
        q = q.where((BriefPreset.client_id == client_id) | (BriefPreset.client_id.is_(None)))
    rows = (await db.execute(q.order_by(BriefPreset.created_at))).scalars().all()
    return [_brief_out(b) for b in rows]


@router.post("/briefs", response_model=BriefOut)
async def create_brief(body: BriefIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.client_id:
        await _owned(db, Client, body.client_id, current_user, "병원")
    b = BriefPreset(user_id=_uid(current_user), **body.model_dump())
    db.add(b)
    await db.commit()
    return _brief_out(b)


@router.put("/briefs/{brief_id}", response_model=BriefOut)
async def update_brief(brief_id: str, body: BriefIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, BriefPreset, brief_id, current_user, "브리프")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    await db.commit()
    return _brief_out(b)


@router.delete("/briefs/{brief_id}")
async def delete_brief(brief_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, BriefPreset, brief_id, current_user, "브리프")
    await db.delete(b)
    await db.commit()
    return {"success": True}


# ======================================================================
# 백그라운드 작업 상태
# ======================================================================
class TaskOut(BaseModel):
    id: str
    type: str
    status: str
    progress: int = 0
    total: int = 0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


def _task_out(j: BackgroundJob) -> TaskOut:
    return TaskOut(id=j.id, type=j.type, status=j.status, progress=j.progress or 0, total=j.total or 0,
                   message=j.message, result=j.result, error=j.error, created_at=j.created_at, finished_at=j.finished_at)


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await db.get(BackgroundJob, task_id)
    if not j or (j.user_id and j.user_id != _uid(current_user)):
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return _task_out(j)


@router.get("/tasks", response_model=List[TaskOut])
async def list_tasks(campaign_id: Optional[str] = None, active_only: bool = False, limit: int = 20,
                     current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(BackgroundJob).where(BackgroundJob.user_id == _uid(current_user))
    if active_only:
        q = q.where(BackgroundJob.status.in_(["pending", "running"]))
    rows = (await db.execute(q.order_by(BackgroundJob.created_at.desc()).limit(200))).scalars().all()
    if campaign_id:
        rows = [r for r in rows if (r.payload or {}).get("campaign_id") == campaign_id]
    return [_task_out(r) for r in rows[:limit]]


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ok = await job_worker.cancel(db, task_id, _uid(current_user))
    return {"success": ok}


# ======================================================================
# 캠페인
# ======================================================================
class CampaignIn(BaseModel):
    client_id: str
    name: Optional[str] = None


class CampaignPatch(BaseModel):
    name: Optional[str] = None
    step: Optional[int] = None
    blog_ids: Optional[List[str]] = None
    brief_id: Optional[str] = None
    collection_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class CampaignOut(BaseModel):
    id: str
    client_id: str
    client_name: Optional[str] = None
    name: str
    step: int
    status: str
    blog_ids: List[str] = []
    brief_id: Optional[str] = None
    collection_id: Optional[str] = None
    settings: Dict[str, Any] = {}
    stats: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


async def _campaign_out(db: AsyncSession, c: Campaign) -> CampaignOut:
    client = await db.get(Client, c.client_id)
    return CampaignOut(
        id=c.id, client_id=c.client_id, client_name=client.name if client else None, name=c.name, step=c.step or 1,
        status=c.status or "draft", blog_ids=c.blog_ids or [], brief_id=c.brief_id, collection_id=c.collection_id,
        settings=c.settings or {}, stats=c.stats or {}, created_at=c.created_at, updated_at=c.updated_at,
    )


@router.get("/campaigns", response_model=List[CampaignOut])
async def list_campaigns(client_id: Optional[str] = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(Campaign).where(Campaign.user_id == _uid(current_user))
    if client_id:
        q = q.where(Campaign.client_id == client_id)
    rows = (await db.execute(q.order_by(Campaign.updated_at.desc()))).scalars().all()
    return [await _campaign_out(db, c) for c in rows]


@router.post("/campaigns", response_model=CampaignOut)
async def create_campaign(body: CampaignIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    client = await _owned(db, Client, body.client_id, current_user, "병원")
    blogs = (await db.execute(select(Blog.id).where(Blog.client_id == client.id, Blog.status == "active"))).all()
    default_brief = (await db.execute(select(BriefPreset.id).where(BriefPreset.client_id == client.id, BriefPreset.is_default == True))).scalar_one_or_none()  # noqa: E712
    name = body.name or f"{client.name} {date.today().strftime('%m/%d')} 캠페인"
    c = Campaign(
        user_id=_uid(current_user), client_id=client.id, name=name, step=1, status="draft",
        blog_ids=[b for (b,) in blogs], brief_id=default_brief, collection_id=client.default_collection_id,
        settings={}, stats={},
    )
    db.add(c)
    await db.commit()
    return await _campaign_out(db, c)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    return await _campaign_out(db, c)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignOut)
async def patch_campaign(campaign_id: str, body: CampaignPatch, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "settings":
            merged = dict(c.settings or {})
            merged.update(v)
            c.settings = merged
        else:
            setattr(c, k, v)
    await db.commit()
    return await _campaign_out(db, c)


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    active = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.campaign_id == c.id, PublishJob.status.in_(["assigned", "publishing"])))).scalar() or 0
    if active:
        raise HTTPException(status_code=400, detail="발행 진행 중인 건이 있어 삭제할 수 없습니다. 먼저 예약을 취소하세요.")
    for model in (PublishJob, Draft, CampaignKeyword):
        for row in (await db.execute(select(model).where(model.campaign_id == c.id))).scalars().all():
            await db.delete(row)
    await db.delete(c)
    await db.commit()
    return {"success": True}


# ─────────────────────────────── 2단계: 키워드 ───────────────────────────────
class ExpandIn(BaseModel):
    seeds: List[str] = []
    regions: Optional[List[str]] = None
    diseases: Optional[List[str]] = None
    level: Optional[int] = None
    min_volume_region: Optional[int] = None
    min_volume_national: Optional[int] = None
    include_related: bool = True
    analyze_after: bool = False       # 확장 후 통검 분석까지 이어서


class KeywordOut(BaseModel):
    id: str
    keyword: str
    region: Optional[str] = None
    disease: Optional[str] = None
    source: str = "manual"
    scope: str = "region"
    monthly_mobile: int = 0
    monthly_pc: int = 0
    total_volume: int = 0
    competition: str = "mid"
    verdict: str = "unknown"
    verdict_reason: Optional[str] = None
    serp_summary: Optional[Dict[str, Any]] = None
    in_sheet: bool = False
    sheet_note: Optional[str] = None
    selected: bool = False
    passes_filter: bool = True
    has_draft: bool = False
    my_blog_id: Optional[str] = None
    my_verdict: Optional[str] = None
    my_probability: Optional[float] = None
    my_verdict_result: Optional[Dict[str, Any]] = None
    my_verdict_at: Optional[datetime] = None


def _kw_out(k: CampaignKeyword, has_draft: bool = False) -> KeywordOut:
    return KeywordOut(
        id=k.id, keyword=k.keyword, region=k.region, disease=k.disease, source=k.source or "manual", scope=k.scope or "region",
        monthly_mobile=k.monthly_mobile or 0, monthly_pc=k.monthly_pc or 0, total_volume=k.total_volume or 0,
        competition=k.competition or "mid", verdict=k.verdict or "unknown", verdict_reason=k.verdict_reason,
        serp_summary=k.serp_summary, in_sheet=bool(k.in_sheet), sheet_note=k.sheet_note,
        selected=bool(k.selected), passes_filter=bool(k.passes_filter), has_draft=has_draft,
        my_blog_id=k.my_blog_id, my_verdict=k.my_verdict, my_probability=k.my_probability,
        my_verdict_result=k.my_verdict_result, my_verdict_at=k.my_verdict_at,
    )


@router.post("/campaigns/{campaign_id}/keywords/expand", response_model=TaskOut)
async def expand_keywords(campaign_id: str, body: ExpandIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    payload = {"campaign_id": c.id, **body.model_dump(exclude_none=True)}
    job = await job_worker.enqueue(db, "keyword_expand", payload, _uid(current_user), dedupe_key=f"expand:{c.id}")
    if body.analyze_after:
        await job_worker.enqueue(db, "serp_analyze", {"campaign_id": c.id}, _uid(current_user), dedupe_key=f"serp:{c.id}", run_after=datetime.utcnow() + timedelta(seconds=1))
    return _task_out(job)


class ManualKeywordsIn(BaseModel):
    keywords: List[str]
    fetch_volume: bool = True


@router.post("/campaigns/{campaign_id}/keywords", response_model=List[KeywordOut])
async def add_keywords(campaign_id: str, body: ManualKeywordsIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    from app.services import keyword_expander as ke, search_volume_service as svs
    existing = {ke._norm(k.keyword): k for k in (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()}
    clean = [k.strip() for k in body.keywords if k and k.strip()]
    new_rows: List[CampaignKeyword] = []
    for kw in clean:
        if ke._norm(kw) in existing:
            continue
        row = CampaignKeyword(user_id=_uid(current_user), campaign_id=c.id, client_id=c.client_id, keyword=kw, source="manual", selected=True)
        db.add(row)
        existing[ke._norm(kw)] = row
        new_rows.append(row)
    if body.fetch_volume and new_rows and svs.is_configured():
        metrics = await svs.get_keyword_metrics(db, [r.keyword for r in new_rows])
        by = {svs._normalize(m["keyword"]): m for m in metrics}
        client = await db.get(Client, c.client_id)
        for r in new_rows:
            m = by.get(ke._norm(r.keyword))
            if m:
                r.monthly_mobile, r.monthly_pc = m["monthly_mobile"], m["monthly_pc"]
                r.total_volume, r.competition = m["total_volume"], m["competition"]
                r.volume_fetched_at = datetime.utcnow()
                r.scope = ke.guess_scope(r.keyword, client.regions if client else [])
                thr = (client.min_volume_region if r.scope == "region" else client.min_volume_national) if client else 20
                r.passes_filter = r.monthly_mobile >= thr
    await db.commit()
    return [_kw_out(r) for r in new_rows]


@router.get("/campaigns/{campaign_id}/keywords", response_model=List[KeywordOut])
async def list_keywords(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    rows = (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()
    drafted = {r for (r,) in (await db.execute(select(Draft.keyword_id).where(Draft.campaign_id == c.id, Draft.keyword_id.isnot(None)))).all()}
    rows.sort(key=lambda k: (not k.selected, not k.passes_filter, -(k.monthly_mobile or 0), k.keyword))
    return [_kw_out(k, k.id in drafted) for k in rows]


class SelectIn(BaseModel):
    ids: List[str]
    selected: bool


@router.patch("/campaigns/{campaign_id}/keywords/select")
async def select_keywords(campaign_id: str, body: SelectIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    await db.execute(update(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id, CampaignKeyword.id.in_(body.ids)).values(selected=body.selected))
    await db.commit()
    return {"success": True, "count": len(body.ids)}


@router.delete("/campaigns/{campaign_id}/keywords/{keyword_id}")
async def delete_keyword(campaign_id: str, keyword_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    k = await db.get(CampaignKeyword, keyword_id)
    if k and k.campaign_id == c.id:
        await db.delete(k)
        await db.commit()
    return {"success": True}


class AnalyzeIn(BaseModel):
    keyword_ids: Optional[List[str]] = None
    limit: int = 60


@router.post("/campaigns/{campaign_id}/keywords/analyze", response_model=TaskOut)
async def analyze_keywords(campaign_id: str, body: AnalyzeIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    payload = {"campaign_id": c.id, "limit": body.limit}
    if body.keyword_ids:
        payload["keyword_ids"] = body.keyword_ids
    job = await job_worker.enqueue(db, "serp_analyze", payload, _uid(current_user), dedupe_key=f"serp:{c.id}")
    return _task_out(job)


@router.post("/campaigns/{campaign_id}/keywords/sheet-check", response_model=TaskOut)
async def sheet_check(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    job = await job_worker.enqueue(db, "sheet_check", {"campaign_id": c.id}, _uid(current_user), dedupe_key=f"sheet:{c.id}")
    return _task_out(job)


@router.get("/campaigns/{campaign_id}/keywords/{keyword_id}/serp")
async def keyword_serp_detail(campaign_id: str, keyword_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    k = await db.get(CampaignKeyword, keyword_id)
    if not k or k.campaign_id != c.id:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")
    from app.services import serp_analyzer as sa
    snap = (await db.execute(select(SerpSnapshot).where(SerpSnapshot.keyword_norm == sa.normalize_keyword(k.keyword)).order_by(SerpSnapshot.fetched_at.desc()).limit(1))).scalar_one_or_none()
    if not snap:
        return {"keyword": k.keyword, "posts": [], "summary": None}
    return {"keyword": k.keyword, "fetched_at": snap.fetched_at, "posts": snap.posts, "summary": snap.summary, "verdict": snap.verdict, "verdict_reason": snap.verdict_reason, "error": snap.error}


# ─────────────────────────────── 3단계: 원고 ───────────────────────────────
class DraftOut(BaseModel):
    id: str
    campaign_id: Optional[str] = None
    keyword_id: Optional[str] = None
    keyword: Optional[str] = None
    source: str
    parent_draft_id: Optional[str] = None
    title: str
    body: Optional[str] = None
    char_count: int = 0
    status: str
    checks: Dict[str, Any] = {}
    image_plan: List[Dict[str, Any]] = []
    image_count_target: int = 0
    tags: List[str] = []
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _draft_out(d: Draft, with_body: bool = True) -> DraftOut:
    return DraftOut(
        id=d.id, campaign_id=d.campaign_id, keyword_id=d.keyword_id, keyword=d.keyword, source=d.source or "manual",
        parent_draft_id=d.parent_draft_id, title=d.title or "", body=(d.body if with_body else None),
        char_count=d.char_count or 0, status=d.status or "ready", checks=d.checks or {}, image_plan=d.image_plan or [],
        image_count_target=d.image_count_target or 0, tags=d.tags or [], error=d.error, created_at=d.created_at, updated_at=d.updated_at,
    )


class GenerateIn(BaseModel):
    keyword_ids: Optional[List[str]] = None
    brief_id: Optional[str] = None
    target_chars: Optional[int] = None
    heading_count: Optional[int] = None
    keyword_count: Optional[int] = None
    image_count: Optional[int] = None
    instructions: Optional[str] = None
    force: bool = False


@router.post("/campaigns/{campaign_id}/drafts/generate", response_model=TaskOut)
async def generate_drafts(campaign_id: str, body: GenerateIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    if body.brief_id:
        c.brief_id = body.brief_id
        await db.commit()
    payload = {"campaign_id": c.id, **body.model_dump(exclude_none=True)}
    job = await job_worker.enqueue(db, "draft_generate", payload, _uid(current_user), dedupe_key=f"gen:{c.id}", total=0)
    return _task_out(job)


class VariantsIn(BaseModel):
    source_text: str
    count: int = 3
    keyword: Optional[str] = None
    title: Optional[str] = None
    target_chars: Optional[int] = None


@router.post("/campaigns/{campaign_id}/drafts/variants", response_model=TaskOut)
async def make_variants(campaign_id: str, body: VariantsIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    payload = {"campaign_id": c.id, "client_id": c.client_id, **body.model_dump(exclude_none=True)}
    job = await job_worker.enqueue(db, "draft_variants", payload, _uid(current_user))
    return _task_out(job)


def _parse_upload(name: str, data: bytes) -> tuple[str, str]:
    """txt/md/docx → (제목, 본문). 제목 = 첫 줄(없으면 파일명)."""
    lower = name.lower()
    text = ""
    if lower.endswith(".docx"):
        try:
            import docx  # python-docx
            doc = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"{name}: 워드 파일을 읽지 못했습니다 ({e})")
    else:
        for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                text = data.decode(enc)
                break
            except Exception:  # noqa: BLE001
                continue
        if not text:
            raise HTTPException(status_code=400, detail=f"{name}: 텍스트 인코딩을 알 수 없습니다")
    text = text.replace("\r\n", "\n").strip()
    lines = [ln for ln in text.split("\n")]
    first = next((ln.strip() for ln in lines if ln.strip()), "")
    stem = re.sub(r"\.(txt|md|docx)$", "", name, flags=re.I)
    # 첫 줄이 짧으면 제목으로, 길면 파일명을 제목으로
    if first and len(first) <= 60:
        idx = lines.index(next(ln for ln in lines if ln.strip()))
        body = "\n".join(lines[idx + 1 :]).strip()
        return first, body or text
    return stem, text


@router.post("/campaigns/{campaign_id}/drafts/upload", response_model=List[DraftOut])
async def upload_drafts(campaign_id: str, files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    client = await db.get(Client, c.client_id)
    kws = (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()
    out: List[Draft] = []
    for f in files[:200]:
        data = await f.read()
        title, body = _parse_upload(f.filename or "원고.txt", data)
        body = writer.reflow(body)
        # 키워드 자동 매칭: 제목/본문에 들어 있는 캠페인 키워드 중 가장 긴 것
        matched = None
        hay = (title + "\n" + body).replace(" ", "")
        for k in sorted(kws, key=lambda x: -len(x.keyword)):
            if k.keyword.replace(" ", "") in hay:
                matched = k
                break
        checks = writer.run_static_checks(title, body, client.forbidden_words if client else [])
        d = Draft(
            user_id=_uid(current_user), client_id=c.client_id, campaign_id=c.id,
            keyword_id=matched.id if matched else None, keyword=matched.keyword if matched else None,
            source="upload", title=title[:200], body=body, char_count=writer.count_chars(body),
            status="ready" if checks["ok"] else "needs_review", checks=checks,
            tags=[matched.keyword] if matched else [], emphasize=[matched.keyword] if matched else [],
        )
        db.add(d)
        out.append(d)
    await db.commit()
    return [_draft_out(d, with_body=False) for d in out]


class DraftTextIn(BaseModel):
    title: str
    body: str
    keyword: Optional[str] = None


@router.post("/campaigns/{campaign_id}/drafts", response_model=DraftOut)
async def add_draft_text(campaign_id: str, body: DraftTextIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    client = await db.get(Client, c.client_id)
    text = writer.reflow(body.body)
    checks = writer.run_static_checks(body.title, text, client.forbidden_words if client else [])
    d = Draft(user_id=_uid(current_user), client_id=c.client_id, campaign_id=c.id, keyword=body.keyword, source="manual",
              title=body.title[:200], body=text, char_count=writer.count_chars(text), status="ready" if checks["ok"] else "needs_review",
              checks=checks, tags=[body.keyword] if body.keyword else [], emphasize=[body.keyword] if body.keyword else [])
    db.add(d)
    await db.commit()
    return _draft_out(d)


@router.get("/campaigns/{campaign_id}/drafts", response_model=List[DraftOut])
async def list_drafts(campaign_id: str, with_body: bool = False, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    rows = (await db.execute(select(Draft).where(Draft.campaign_id == c.id).order_by(Draft.created_at.asc()))).scalars().all()
    return [_draft_out(d, with_body=with_body) for d in rows]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
async def get_draft(draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    return _draft_out(d)


class DraftPatch(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    keyword: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


@router.put("/drafts/{draft_id}", response_model=DraftOut)
async def update_draft(draft_id: str, body: DraftPatch, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    if d.status == "generating":
        raise HTTPException(status_code=409, detail="생성이 끝난 뒤 원고를 수정하세요")
    locked = (await db.execute(select(PublishJob.id).where(PublishJob.draft_id == d.id, PublishJob.status.in_(["assigned", "publishing", "submitted", "uncertain"])).limit(1))).scalar_one_or_none()
    if locked:
        raise HTTPException(status_code=409, detail="실행 중이거나 등록된 원고는 수정할 수 없습니다")
    if body.title is not None:
        d.title = body.title[:200]
    if body.body is not None:
        d.body = writer.reflow(body.body)
        d.char_count = writer.count_chars(d.body)
        client = await db.get(Client, d.client_id) if d.client_id else None
        checks = dict(d.checks or {})
        checks.update(writer.run_static_checks(d.title, d.body, client.forbidden_words if client else []))
        d.checks = checks
        if d.status in ("needs_review", "failed"):
            d.status = "ready" if checks.get("ok") else "needs_review"
    if body.keyword is not None:
        d.keyword = body.keyword
    if body.tags is not None:
        d.tags = body.tags
    if body.status in ("ready", "needs_review"):
        d.status = body.status
    if body.title is not None or body.body is not None or body.status == "ready":
        client = await db.get(Client, d.client_id) if d.client_id else None
        checks = writer.run_static_checks(d.title, d.body, client.forbidden_words if client else [])
        previous_checks = d.checks or {}
        if previous_checks.get('landing'):
            checks['landing'] = previous_checks['landing']
            checks['ok'] = checks['ok'] and d.body.count(checks['landing']['url']) == 1
        if previous_checks.get('editorial'):
            from app.services.editorial_quality import fingerprint
            editorial = dict(previous_checks['editorial'])
            editorial['approved'] = editorial.get('approved') is True and editorial.get('content_hash') == fingerprint(d.title, d.body)
            checks['editorial'] = editorial
            checks['ok'] = checks['ok'] and editorial['approved']
        d.checks = checks
        d.status = "ready" if checks["ok"] and body.status != "needs_review" else "needs_review"
        await db.execute(update(PublishJob).where(PublishJob.draft_id == d.id, PublishJob.status == "queued").values(images_ready=False))
    await db.commit()
    return _draft_out(d)


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    active = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.draft_id == d.id, PublishJob.status.in_(list(JOB_ACTIVE))))).scalar() or 0
    if active:
        raise HTTPException(status_code=400, detail="예약이 걸린 원고는 삭제할 수 없습니다. 예약을 먼저 취소하세요.")
    await db.delete(d)
    await db.commit()
    return {"success": True}


# ─────────────────────────────── 4단계: 사진 ───────────────────────────────
class PlanIn(BaseModel):
    collection_id: Optional[str] = None
    image_count: Optional[int] = None
    draft_ids: Optional[List[str]] = None


@router.post("/campaigns/{campaign_id}/photos/plan", response_model=TaskOut)
async def plan_photos(campaign_id: str, body: PlanIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    if body.collection_id:
        c.collection_id = body.collection_id
        await db.commit()
    payload = {"campaign_id": c.id, **body.model_dump(exclude_none=True)}
    job = await job_worker.enqueue(db, "image_plan", payload, _uid(current_user), dedupe_key=f"plan:{c.id}")
    return _task_out(job)


class TagIn(BaseModel):
    collection_id: Optional[str] = None


@router.post("/photos/tag", response_model=TaskOut)
async def tag_photos(body: TagIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await job_worker.enqueue(db, "photo_tag", {"collection_id": body.collection_id}, _uid(current_user), dedupe_key=f"tag:{_uid(current_user)}:{body.collection_id or 'all'}")
    return _task_out(job)


class PhotoMeta(BaseModel):
    id: str
    thumbnail: Optional[str] = None
    scene: Optional[str] = None
    tags: List[str] = []
    caption: Optional[str] = None
    has_text: Optional[bool] = None
    suitable_for: List[str] = []
    use_count: int = 0
    tagged: bool = False


@router.get("/photos", response_model=List[PhotoMeta])
async def list_photos(collection_id: Optional[str] = None, limit: int = 300, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """사진 메타(썸네일 포함, 원본 BLOB 제외). 4단계 교체 후보 목록·태깅 현황용."""
    cols = (PoolImage.id, PoolImage.thumbnail, PoolImage.scene, PoolImage.tags, PoolImage.caption, PoolImage.has_text, PoolImage.suitable_for, PoolImage.use_count, PoolImage.tagged_at)
    q = select(*cols).where(PoolImage.user_id == _uid(current_user), PoolImage.active == True)  # noqa: E712
    if collection_id:
        q = q.join(PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id).where(PoolCollectionMember.collection_id == collection_id)
    rows = (await db.execute(q.order_by(PoolImage.created_at.desc()).limit(limit))).all()
    return [PhotoMeta(id=r.id, thumbnail=r.thumbnail, scene=r.scene, tags=list(r.tags or []), caption=r.caption, has_text=r.has_text,
                      suitable_for=list(r.suitable_for or []), use_count=r.use_count or 0, tagged=bool(r.tagged_at)) for r in rows]


class PhotoTagPatch(BaseModel):
    scene: Optional[str] = None
    tags: Optional[List[str]] = None
    caption: Optional[str] = None
    suitable_for: Optional[List[str]] = None


@router.put("/photos/{image_id}/tags", response_model=PhotoMeta)
async def edit_photo_tags(image_id: str, body: PhotoTagPatch, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    img = await db.get(PoolImage, image_id)
    if not img or img.user_id != _uid(current_user):
        raise HTTPException(status_code=404, detail="사진을 찾을 수 없습니다")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(img, k, v)
    img.tagged_at = img.tagged_at or datetime.utcnow()
    await db.commit()
    return PhotoMeta(id=img.id, thumbnail=img.thumbnail, scene=img.scene, tags=list(img.tags or []), caption=img.caption, has_text=img.has_text,
                     suitable_for=list(img.suitable_for or []), use_count=img.use_count or 0, tagged=bool(img.tagged_at))


class ImagePlanIn(BaseModel):
    slots: List[Dict[str, Any]]      # [{slot, pool_image_id, after_paragraph?}]


@router.put("/drafts/{draft_id}/image-plan", response_model=DraftOut)
async def set_image_plan(draft_id: str, body: ImagePlanIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    locked = (await db.execute(select(PublishJob.id).where(PublishJob.draft_id == d.id, PublishJob.status.in_(["assigned", "publishing", "submitted", "uncertain"])).limit(1))).scalar_one_or_none()
    if locked:
        raise HTTPException(status_code=409, detail="실행 중이거나 등록된 원고의 사진은 수정할 수 없습니다")
    ids = {s['pool_image_id'] for s in body.slots if s.get('pool_image_id')}
    owned_ids = set((await db.execute(select(PoolImage.id).where(PoolImage.id.in_(ids), PoolImage.user_id == _uid(current_user)))).scalars().all())
    if ids != owned_ids:
        raise HTTPException(status_code=400, detail="사용할 수 없는 사진이 포함되어 있습니다")
    current = {s.get("slot"): dict(s) for s in (d.image_plan or [])}
    for s in body.slots:
        idx = s.get("slot")
        cur = current.get(idx, {"slot": idx, "after_paragraph": s.get("after_paragraph", 0)})
        if "pool_image_id" in s:
            cur["pool_image_id"] = s["pool_image_id"]
            cur["reason"] = "직접 선택"
        if "after_paragraph" in s:
            cur["after_paragraph"] = int(s["after_paragraph"])
        current[idx] = cur
    plan = sorted(current.values(), key=lambda x: (x.get("after_paragraph", 0), x.get("slot", 0)))
    for i, s in enumerate(plan):
        s["slot"] = i
    d.image_plan = plan
    d.image_count_target = len(plan)
    # 이미 잡힌 발행건이 있으면 사진을 다시 준비해야 한다
    await db.execute(update(PublishJob).where(PublishJob.draft_id == d.id, PublishJob.status.in_(["queued", "assigned"])).values(images_ready=False))
    await db.commit()
    return _draft_out(d)


# ─────────────────────────────── 5단계: 예약 ───────────────────────────────
class ScheduleIn(BaseModel):
    start_date: date
    days: int = 14
    blog_ids: Optional[List[str]] = None
    per_day: Optional[int] = None            # 지정 시 블로그별 하루 한도를 이 값으로 덮어쓴다(이번 캠페인만)
    draft_ids: Optional[List[str]] = None    # 비우면 ready 원고 전부
    include_needs_review: bool = False
    seed: Optional[int] = None


class ScheduleItem(BaseModel):
    draft_id: str
    title: str
    blog_ref_id: str
    blog_label: str
    scheduled_at: str


class SchedulePreview(BaseModel):
    total: int
    assigned: List[ScheduleItem]
    unassigned: int
    calendar: List[Dict[str, Any]]
    warnings: List[str] = []


async def _schedule_inputs(db: AsyncSession, c: Campaign, body: ScheduleIn, user: User):
    blog_ids = body.blog_ids or c.blog_ids or []
    blogs = (await db.execute(select(Blog).where(Blog.id.in_(blog_ids), Blog.user_id == _uid(user)))).scalars().all() if blog_ids else []
    warnings: List[str] = []
    usable = []
    for b in blogs:
        if b.status != "active":
            warnings.append(f"{b.label or b.blog_id}: 상태가 '{b.status}'라 제외했습니다. {b.status_reason or ''}".strip())
            continue
        usable.append(b)
    if not usable:
        raise HTTPException(status_code=400, detail="발행할 수 있는 블로그가 없습니다. 병원 설정에서 블로그를 추가하거나 상태를 '정상'으로 바꾸세요.")
    q = select(Draft).where(Draft.campaign_id == c.id, Draft.source != "upload")
    statuses = ["ready"] + (["needs_review"] if body.include_needs_review else [])
    q = q.where(Draft.status.in_(statuses))
    if body.draft_ids:
        q = q.where(Draft.id.in_(body.draft_ids))
    drafts = (await db.execute(q.order_by(Draft.created_at.asc()))).scalars().all()
    parent_ids = {d.parent_draft_id for d in drafts if d.parent_draft_id}
    drafts = [d for d in drafts if d.id not in parent_ids]
    # 이미 활성 발행건이 있는 원고는 제외
    busy = {r for (r,) in (await db.execute(select(PublishJob.draft_id).where(PublishJob.campaign_id == c.id, PublishJob.status.in_(list(JOB_ACTIVE))))).all()}
    skipped = [d for d in drafts if d.id in busy]
    if skipped:
        warnings.append(f"이미 예약된 원고 {len(skipped)}건은 제외했습니다.")
    drafts = [d for d in drafts if d.id not in busy]
    if not drafts:
        raise HTTPException(status_code=400, detail="예약할 원고가 없습니다. 3단계에서 원고를 준비하세요(검수 통과 상태만 예약됩니다).")
    plans = [se.blog_plan_from_model(b) for b in usable]
    if body.per_day:
        for p in plans:
            p.daily_limit = max(1, min(20, body.per_day))
    await se.load_taken_slots(db, _uid(user), plans)
    return usable, drafts, plans, warnings


def _preview(drafts: List[Draft], blogs: List[Blog], assigned, remaining, warnings) -> SchedulePreview:
    label = {b.id: (b.label or b.blog_id) for b in blogs}
    items = []
    for d, (ref, at) in zip(drafts, assigned):
        items.append(ScheduleItem(draft_id=d.id, title=d.title, blog_ref_id=ref, blog_label=label.get(ref, ref), scheduled_at=at.isoformat(timespec="minutes")))
    if remaining:
        warnings = warnings + [f"자리가 모자라 {remaining}건을 배정하지 못했습니다. 기간을 늘리거나 하루 건수를 올리세요."]
    return SchedulePreview(total=len(drafts), assigned=items, unassigned=remaining, calendar=se.calendar_view(assigned, label), warnings=warnings)


@router.post("/campaigns/{campaign_id}/schedule/preview", response_model=SchedulePreview)
async def schedule_preview(campaign_id: str, body: ScheduleIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    blogs, drafts, plans, warnings = await _schedule_inputs(db, c, body, current_user)
    seed = body.seed if body.seed is not None else int(c.created_at.timestamp()) if c.created_at else 0
    assigned, remaining = se.allocate(len(drafts), plans, body.start_date, body.days, seed=seed)
    return _preview(drafts, blogs, assigned, remaining, warnings)


@router.post("/campaigns/{campaign_id}/schedule/commit", response_model=SchedulePreview)
async def schedule_commit(campaign_id: str, body: ScheduleIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    await db.execute(update(Campaign).where(Campaign.id == c.id).values(updated_at=datetime.utcnow()))
    blogs, drafts, plans, warnings = await _schedule_inputs(db, c, body, current_user)
    seed = body.seed if body.seed is not None else int(c.created_at.timestamp()) if c.created_at else 0
    assigned, remaining = se.allocate(len(drafts), plans, body.start_date, body.days, seed=seed)
    by_ref = {b.id: b for b in blogs}
    for d, (ref, at) in zip(drafts, assigned):
        b = by_ref[ref]
        db.add(PublishJob(
            user_id=_uid(current_user), campaign_id=c.id, draft_id=d.id, blog_ref_id=ref, naver_blog_id=b.blog_id,
            scheduled_at=at, status="queued", open_type=b.open_type or "public", category=b.default_category,
        ))
        # 예약 자리 기록(다른 경로의 간격 예약과 공유)
        db.add(ScheduleMark(user_id=_uid(current_user), blog_id=b.blog_id, scheduled_at=at, title=d.title[:200], source="campaign"))
    c.status = "scheduled"
    c.step = 6
    merged = dict(c.settings or {})
    merged["schedule"] = {"start_date": body.start_date.isoformat(), "days": body.days, "per_day": body.per_day, "blog_ids": [b.id for b in blogs]}
    c.settings = merged
    try:
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"예약 저장 실패(같은 시각이 이미 있을 수 있습니다): {e}")
    # 사진 사전 유니크화
    await job_worker.enqueue(db, "prepare_images", {"campaign_id": c.id}, _uid(current_user), dedupe_key=f"prep:{c.id}")
    await campaign_jobs._bump_stats(job_worker.JobContext(db=db, job=BackgroundJob()), c.id)
    return _preview(drafts, blogs, assigned, remaining, warnings)


@router.delete("/campaigns/{campaign_id}/schedule")
async def schedule_cancel(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """아직 발행되지 않은 예약을 전부 취소한다(발행중인 건은 남긴다)."""
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    jobs = (await db.execute(select(PublishJob).where(PublishJob.campaign_id == c.id, PublishJob.status.in_(["queued", "failed", "dry_run"])))).scalars().all()
    n = 0
    for j in jobs:
        changed = await db.execute(update(PublishJob).where(PublishJob.id == j.id, PublishJob.status.in_(["queued", "failed", "dry_run"])).values(status="cancelled"))
        if changed.rowcount != 1:
            continue
        b = await db.get(Blog, j.blog_ref_id)
        if b:
            mark = (await db.execute(select(ScheduleMark).where(ScheduleMark.user_id == _uid(current_user), ScheduleMark.blog_id == b.blog_id, ScheduleMark.scheduled_at == j.scheduled_at))).scalar_one_or_none()
            if mark:
                await db.delete(mark)
        n += 1
    c.status = "draft"
    c.step = 5
    await db.commit()
    return {"success": True, "cancelled": n}


# ─────────────────────────────── 6단계: 현황 ───────────────────────────────
class JobOut(BaseModel):
    id: str
    draft_id: str
    title: str
    keyword: Optional[str] = None
    blog_ref_id: str
    blog_label: str
    naver_blog_id: Optional[str] = None
    scheduled_at: str
    status: str
    attempts: int = 0
    result_url: Optional[str] = None
    error: Optional[str] = None
    images_ready: bool = False
    image_count: int = 0
    published_at: Optional[datetime] = None


async def _jobs_out(db: AsyncSession, jobs: List[PublishJob]) -> List[JobOut]:
    if not jobs:
        return []
    drafts = {d.id: d for d in (await db.execute(select(Draft).where(Draft.id.in_({j.draft_id for j in jobs})))).scalars().all()}
    blogs = {b.id: b for b in (await db.execute(select(Blog).where(Blog.id.in_({j.blog_ref_id for j in jobs})))).scalars().all()}
    out = []
    for j in jobs:
        d = drafts.get(j.draft_id)
        b = blogs.get(j.blog_ref_id)
        out.append(JobOut(
            id=j.id, draft_id=j.draft_id, title=d.title if d else "(삭제된 원고)", keyword=d.keyword if d else None,
            blog_ref_id=j.blog_ref_id, blog_label=(b.label or b.blog_id) if b else "?", naver_blog_id=j.naver_blog_id,
            scheduled_at=j.scheduled_at.isoformat(timespec="minutes"), status=j.status, attempts=j.attempts or 0,
            result_url=j.result_url, error=j.error, images_ready=bool(j.images_ready),
            image_count=len(d.image_plan or []) if d else 0, published_at=j.published_at,
        ))
    return out


@router.get("/campaigns/{campaign_id}/jobs", response_model=List[JobOut])
async def list_jobs(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await protocol.recover_expired(db, _uid(current_user))
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    jobs = (await db.execute(select(PublishJob).where(PublishJob.campaign_id == c.id).order_by(PublishJob.scheduled_at.asc()))).scalars().all()
    return await _jobs_out(db, jobs)


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.status not in ("failed", "cancelled", "dry_run"):
        raise HTTPException(status_code=400, detail="확인 필요 건은 네이버 예약 목록을 대조한 뒤 처리하세요")
    changed = await db.execute(update(PublishJob).where(PublishJob.id == j.id, PublishJob.status == j.status).values(
        status="queued", error=None, lock_token=None, lock_expires_at=None, next_retry_at=None))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="작업 상태가 변경되었습니다. 새로고침하세요")
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.status not in ("queued", "failed", "dry_run"):
        raise HTTPException(status_code=400, detail="발행됐거나 발행 중인 건은 취소할 수 없습니다")
    changed = await db.execute(update(PublishJob).where(PublishJob.id == j.id, PublishJob.status == j.status).values(status="cancelled"))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="실행이 시작되어 취소할 수 없습니다")
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


class MarkPublishedIn(BaseModel):
    result_url: str = Field(min_length=10, max_length=500)


@router.post("/jobs/{job_id}/mark-published", response_model=JobOut)
async def mark_published(job_id: str, body: MarkPublishedIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """'확인 필요' 건을 사람이 네이버에서 확인한 뒤 발행됨으로 표시."""
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    from urllib.parse import urlparse
    url = urlparse(body.result_url)
    if url.scheme != "https" or url.hostname != "blog.naver.com" or not re.fullmatch(rf"/{re.escape(j.naver_blog_id or '')}/[0-9]+/?", url.path):
        raise HTTPException(status_code=400, detail="해당 블로그의 공개 게시물 URL을 입력하세요")
    if j.status not in ("uncertain", "submitted"):
        raise HTTPException(status_code=409, detail="확인 필요 또는 예약 등록 상태만 확인할 수 있습니다")
    if j.lock_expires_at and j.lock_expires_at > datetime.utcnow():
        raise HTTPException(status_code=409, detail="실행기가 아직 작업 중입니다")
    changed = await db.execute(update(PublishJob).where(PublishJob.id == j.id, PublishJob.status == j.status).values(
        status="published", result_url=body.result_url, published_at=datetime.utcnow()))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="작업 상태가 변경되었습니다")
    await db.execute(update(PublishAttempt).where(PublishAttempt.job_id == j.id).values(active_blog_id=None))
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


class AutomationIn(BaseModel):
    max_keywords: int = Field(default=10, ge=1, le=50)
    image_count: int = Field(default=5, ge=0, le=20)
    auto_schedule: bool = False
    start_date: date
    days: int = Field(default=14, ge=1, le=90)
    discover_keywords: bool = False
    quality: PolicyConfig = Field(default_factory=PolicyConfig)


@router.post("/campaigns/{campaign_id}/automation", response_model=TaskOut)
async def start_automation(campaign_id: str, body: AutomationIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    uid = _uid(current_user)
    if body.discover_keywords:
        # Use the same lock order as recurring replenishment.
        await db.execute(update(AutopilotPolicy).where(AutopilotPolicy.campaign_id == campaign_id).values(updated_at=datetime.utcnow()))
        policy = await db.get(AutopilotPolicy, campaign_id, populate_existing=True)
        if policy and policy.enabled:
            raise HTTPException(status_code=409, detail="매일 자동 운영을 일시정지한 뒤 대량 작업을 시작하세요")
    await db.execute(update(Campaign).where(Campaign.id == campaign_id).values(updated_at=datetime.utcnow()))
    active = await db.get(AutomationRun, campaign_id)
    previous = active.job_id if active else None
    if previous:
        old = await db.get(BackgroundJob, previous)
        if old and old.status in ("pending", "running"):
            return _task_out(old)
        if old and old.status == "cancelled" and old.locked_at and old.updated_at and datetime.utcnow() - old.updated_at < timedelta(minutes=30):
            raise HTTPException(status_code=409, detail="이전 자동화가 취소 처리 중입니다. 잠시 후 다시 시작하세요")
    keyword_ids = [] if body.discover_keywords else list((await db.execute(select(CampaignKeyword.id).where(
        CampaignKeyword.campaign_id == campaign_id, CampaignKeyword.selected == True,
    ).order_by(CampaignKeyword.created_at).limit(body.max_keywords))).scalars().all())
    if not keyword_ids and not body.discover_keywords:
        raise HTTPException(status_code=400, detail="2단계에서 자동화할 키워드를 선택하세요")
    payload = {**body.model_dump(mode="json"), "campaign_id": campaign_id, "keyword_ids": keyword_ids}
    if body.discover_keywords:
        from app.services.autopilot import preflight
        issues = await preflight(db, campaign, body.quality)
        if issues:
            raise HTTPException(status_code=400, detail={"issues": issues})
        client = await db.get(Client, campaign.client_id)
        payload.update({**body.quality.model_dump(), "keyword_ids": [], "strict_quality": True,
                        "auto_schedule": True, "collection_id": campaign.collection_id or client.default_collection_id})
        campaign.settings = {**(campaign.settings or {}), "landing": body.quality.model_dump()}
        if policy:
            policy.config = body.quality.model_dump()
    job = BackgroundJob(user_id=uid, type="automation_pipeline", status="pending",
                        payload=payload,
                        result={"requested": body.max_keywords} if body.discover_keywords else None,
                        max_attempts=2, total=4, run_after=datetime.utcnow())
    db.add(job)
    await db.flush()
    if active:
        changed = await db.execute(update(AutomationRun).where(AutomationRun.campaign_id == campaign_id, AutomationRun.job_id == previous).values(job_id=job.id))
        if changed.rowcount != 1:
            await db.rollback()
            active = await db.get(AutomationRun, campaign_id)
            return _task_out(await db.get(BackgroundJob, active.job_id))
    else:
        db.add(AutomationRun(campaign_id=campaign_id, user_id=uid, job_id=job.id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        active = await db.get(AutomationRun, campaign_id)
        if not active:
            raise
        return _task_out(await db.get(BackgroundJob, active.job_id))
    return _task_out(job)


# ======================================================================
# 발행 실행기(확장/에이전트) API
# ======================================================================
class ClaimIn(BaseModel):
    blog_ref_id: Optional[str] = None      # 특정 블로그 것만
    naver_blog_id: Optional[str] = None    # 확장이 현재 로그인된 블로그로 필터할 때
    limit: int = Field(default=1, ge=1, le=20)
    include_images: bool = True
    mode: str = Field(default="live", pattern="^(live|dry_run)$")
    protocol_version: int = 1
    capabilities: List[str] = Field(default_factory=list, max_length=20)


class JobBlock(BaseModel):
    type: str
    content: Optional[str] = None
    image: Optional[str] = None


class ClaimedJob(BaseModel):
    id: str
    lock_token: str
    title: str
    content: str
    blocks: List[JobBlock]
    tags: List[str] = []
    emphasize: List[str] = []
    finalAction: str = "schedule"
    schedule: Dict[str, Any]
    options: Dict[str, Any]
    expectedBlogId: Optional[str] = None
    blog_ref_id: str
    draft_id: str
    protocol_version: int = 2
    lease_seconds: int = protocol.LEASE_SECONDS


def _assemble_blocks(draft: Draft, variants: List[Dict[str, Any]], include_images: bool) -> List[JobBlock]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", draft.body or "") if p.strip()]
    by_para: Dict[int, List[Dict[str, Any]]] = {}
    for v in variants:
        by_para.setdefault(int(v.get("after_paragraph", 0)), []).append(v)
    blocks: List[JobBlock] = []
    # 문단은 '두 문장마다 빈 줄' 규칙으로 이미 잘게 나뉘어 있으므로, 사진 사이 텍스트는 합쳐서 하나의 블록으로
    buf: List[str] = []
    for i, p in enumerate(paragraphs):
        buf.append(p)
        if i in by_para:
            blocks.append(JobBlock(type="text", content="\n\n".join(buf)))
            buf = []
            if include_images:
                for v in sorted(by_para[i], key=lambda x: x.get("slot", 0)):
                    data_url = campaign_jobs.image_as_data_url(v.get("path", ""))
                    if data_url:
                        blocks.append(JobBlock(type="image", image=data_url))
    if buf:
        blocks.append(JobBlock(type="text", content="\n\n".join(buf)))
    return blocks


@router.post("/agent/claim", response_model=List[ClaimedJob])
async def agent_claim(body: ClaimIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.protocol_version != 2:
        raise HTTPException(status_code=426, detail="실행기와 확장프로그램을 새 버전으로 업데이트하세요")
    await protocol.recover_expired(db, _uid(current_user))
    q = select(PublishJob).where(PublishJob.user_id == _uid(current_user), protocol.eligible(datetime.utcnow()))
    if body.blog_ref_id:
        q = q.where(PublishJob.blog_ref_id == body.blog_ref_id)
    if body.naver_blog_id:
        q = q.where(PublishJob.naver_blog_id == body.naver_blog_id)
    rows = (await db.execute(q.order_by(PublishJob.scheduled_at).limit(60))).scalars().all()
    candidates = [(j.id, j.blog_ref_id) for j in rows]
    for job_id, blog_id in candidates:
        from app.models.campaign import AutopilotPolicy
        candidate = await db.get(PublishJob, job_id)
        candidate_draft = await db.get(Draft, candidate.draft_id)
        if candidate_draft and (candidate_draft.checks or {}).get('landing') and 'landing_links_v1' not in body.capabilities:
            raise HTTPException(status_code=426, detail='랜딩 링크 검증을 지원하는 최신 실행기로 업데이트하세요')
        policy = await db.get(AutopilotPolicy, candidate.campaign_id)
        bulk_publication = (candidate_draft.checks or {}).get('bulk_publication') if candidate_draft else None
        if policy and not policy.enabled and not bulk_publication:
            continue
        blog = await db.get(Blog, blog_id)
        if not blog or blog.user_id != _uid(current_user) or blog.status != "active":
            continue
        token = await protocol.claim(db, job_id, _uid(current_user), blog_id, body.mode)
        if not token:
            continue
        try:
            j = await db.get(PublishJob, job_id, populate_existing=True)
            if j.scheduled_at <= se.kst_now() + timedelta(minutes=15):
                raise ValueError("예약 시각이 임박했습니다. 새 시각으로 예약하세요")
            draft = await db.get(Draft, j.draft_id)
            if not draft or draft.user_id != _uid(current_user):
                raise ValueError("원고를 찾을 수 없습니다")
            if draft.status != "ready":
                raise ValueError("검수가 끝난 원고만 발행할 수 있습니다")
            from app.services.editorial_quality import approved
            policy = await db.get(AutopilotPolicy, j.campaign_id)
            bulk_publication = (draft.checks or {}).get('bulk_publication')
            if policy or bulk_publication:
                if policy and not policy.enabled and not bulk_publication:
                    raise ValueError('자동 운영이 일시정지되어 발행을 보류합니다')
                if not approved(draft):
                    raise ValueError('근거·품질 검수 승인과 현재 원고가 일치하지 않습니다')
                required_images = bulk_publication['image_count'] if bulk_publication else policy.config.get('image_count', 0)
                if required_images and (not body.include_images or
                        len(draft.image_plan or []) < required_images):
                    raise ValueError('자동 운영에 필요한 이미지가 누락되었습니다')
            if j.images_ready and any(not Path(v.get("path", "")).is_file() for v in (j.image_variants or [])):
                j.images_ready = False
            if body.include_images and not j.images_ready and draft.image_plan:
                j.image_variants = await campaign_jobs.prepare_job_images(db, j, draft)
                j.images_ready = True
            blocks = _assemble_blocks(draft, j.image_variants or [], body.include_images)
            if body.include_images and draft.image_plan and sum(b.type == "image" for b in blocks) != len(draft.image_plan):
                raise ValueError("필수 이미지가 누락되었습니다")
            payload = ClaimedJob(
                id=j.id, lock_token=token, title=draft.title,
                content="\n\n".join(b.content for b in blocks if b.type == "text" and b.content),
                blocks=blocks, tags=(draft.tags or [])[:10], emphasize=draft.emphasize or [],
                schedule={"datetime": j.scheduled_at.isoformat(timespec="minutes") + "+09:00"},
                options={"openType": j.open_type or "public", "search": True, "category": j.category,
                         "requiredLinks": [draft.checks['landing']['url']] if (draft.checks or {}).get('landing') else []},
                expectedBlogId=j.naver_blog_id, blog_ref_id=j.blog_ref_id, draft_id=j.draft_id,
            )
            attempt = await db.get(PublishAttempt, token)
            attempt.payload = payload.model_dump()
            j.lock_expires_at = datetime.utcnow() + timedelta(seconds=protocol.LEASE_SECONDS)
            await db.commit()
            return [payload]
        except Exception as exc:
            await db.rollback()
            await protocol.result(db, job_id, _uid(current_user), token,
                                  {"ok": False, "message": str(exc)[:500]})
    return []


class ResultIn(BaseModel):
    lock_token: Optional[str] = None
    ok: bool
    uncertain: bool = False
    message: Optional[str] = None
    url: Optional[str] = None
    need_login: bool = False
    captcha: bool = False
    receipt_id: Optional[str] = None
    release: bool = False       # 실행기가 시작도 못 했을 때(확장 미연결 등): 시도 횟수 없이 대기로 되돌림


@router.post("/agent/jobs/{job_id}/result")
async def agent_result(job_id: str, body: ResultIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        ack = await protocol.result(db, job_id, _uid(current_user), body.lock_token, body.model_dump(exclude={"lock_token"}))
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if body.need_login or body.captcha:
        j = await _owned(db, PublishJob, job_id, current_user, "발행건")
        b = await db.get(Blog, j.blog_ref_id)
        if b:
            b.status = "captcha" if body.captcha else "login_required"
            b.status_reason = body.message
            await db.commit()
    return ack


class CheckpointIn(BaseModel):
    lock_token: str = Field(min_length=1, max_length=64)
    stage: str = Field(default="heartbeat", pattern="^(heartbeat|editing|finalizing)$")


async def execution_grant(job_id: str, authorization: str, db: AsyncSession):
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    attempt = await db.get(PublishAttempt, token) if token else None
    if not attempt or attempt.job_id != job_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 작업 권한입니다")
    return attempt


@router.get("/execution/{job_id}/payload")
async def execution_payload(job_id: str, authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    attempt = await execution_grant(job_id, authorization, db)
    j = await db.get(PublishJob, job_id)
    if attempt.result or not j or j.lock_token != attempt.token or j.status != "assigned" or not j.lock_expires_at or j.lock_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=409, detail="만료되었거나 종료된 작업입니다")
    return attempt.payload


@router.post("/execution/{job_id}/checkpoint")
async def execution_checkpoint(job_id: str, body: CheckpointIn, authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    attempt = await execution_grant(job_id, authorization, db)
    if body.lock_token != attempt.token:
        raise HTTPException(status_code=409, detail="작업 권한이 일치하지 않습니다")
    try:
        return await protocol.checkpoint(db, job_id, attempt.user_id, attempt.token, body.stage)
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/execution/{job_id}/result")
async def execution_result(job_id: str, body: ResultIn, authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    attempt = await execution_grant(job_id, authorization, db)
    if body.lock_token != attempt.token:
        raise HTTPException(status_code=409, detail="작업 권한이 일치하지 않습니다")
    try:
        return await protocol.result(db, job_id, attempt.user_id, attempt.token, body.model_dump(exclude={"lock_token"}))
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/agent/jobs/{job_id}/checkpoint")
async def agent_checkpoint(job_id: str, body: CheckpointIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await protocol.checkpoint(db, job_id, _uid(current_user), body.lock_token, body.stage)
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class ReconcileIn(BaseModel):
    outcome: str = Field(pattern="^(registered|not_registered)$")
    evidence: str = Field(min_length=5, max_length=1000)


@router.post("/jobs/{job_id}/reconcile", response_model=JobOut)
async def reconcile_job(job_id: str, body: ReconcileIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.status != "uncertain":
        raise HTTPException(status_code=409, detail="확인 필요 상태만 대조할 수 있습니다")
    if j.lock_expires_at and j.lock_expires_at > datetime.utcnow():
        raise HTTPException(status_code=409, detail="실행기가 아직 작업 중입니다. 종료 후 확인하세요")
    changed = await db.execute(update(PublishJob).where(PublishJob.id == j.id, PublishJob.status == "uncertain").values(
        status="submitted" if body.outcome == "registered" else "cancelled", error="사용자 대조: " + body.evidence))
    if changed.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="작업 상태가 변경되었습니다")
    await db.execute(update(PublishAttempt).where(PublishAttempt.job_id == j.id).values(active_blog_id=None))
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


class AgentBlogSummary(BaseModel):
    blog_ref_id: str
    naver_blog_id: str
    label: str
    status: str
    status_reason: Optional[str] = None
    pending: int = 0
    next_at: Optional[str] = None
    login_id: Optional[str] = None


@router.get("/agent/summary", response_model=List[AgentBlogSummary])
async def agent_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    blogs = (await db.execute(select(Blog).where(Blog.user_id == _uid(current_user)).order_by(Blog.created_at))).scalars().all()
    out = []
    for b in blogs:
        rows = (await db.execute(select(PublishJob.scheduled_at).where(PublishJob.blog_ref_id == b.id, PublishJob.status.in_(["queued", "assigned", "failed"])).order_by(PublishJob.scheduled_at.asc()))).all()
        out.append(AgentBlogSummary(blog_ref_id=b.id, naver_blog_id=b.blog_id, label=b.label or b.blog_id, status=b.status or "active", status_reason=b.status_reason,
                                    pending=len(rows), next_at=rows[0][0].isoformat(timespec="minutes") if rows else None, login_id=b.login_id))
    return out


# ─────────────────────── 실행기 하트비트(웹 신호등) ───────────────────────
# 실행기는 브라우저 밖에 있어 웹이 직접 물어볼 수 없다. 실행기가 주기적으로 자기 상태를
# 남기고, 웹은 그걸 읽어 신호등을 켠다. ONLINE_SECONDS 안에 소식이 없으면 꺼진 것으로 본다.
ONLINE_SECONDS = 150


class AgentHeartbeatIn(BaseModel):
    device_id: str
    version: Optional[str] = None
    running: bool = False
    label: Optional[str] = None
    note: Optional[str] = None


class AgentDeviceOut(BaseModel):
    device_id: str
    version: Optional[str] = None
    running: bool = False
    label: Optional[str] = None
    note: Optional[str] = None
    last_seen_at: str
    seconds_ago: int


class AgentStatusOut(BaseModel):
    online: bool = False
    running: bool = False
    version: Optional[str] = None          # 살아 있는 기기 중 가장 최근 것
    devices: List[AgentDeviceOut] = []


@router.post("/agent/heartbeat", response_model=AgentStatusOut)
async def agent_heartbeat(body: AgentHeartbeatIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """실행기가 살아 있음을 알린다. 같은 기기는 한 줄을 계속 갱신한다."""
    device_id = (body.device_id or "").strip()[:64]
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 가 필요합니다")
    row = await db.get(AgentSession, device_id)
    if row and row.user_id != _uid(current_user):
        raise HTTPException(status_code=403, detail="다른 계정의 기기입니다")
    if not row:
        row = AgentSession(device_id=device_id, user_id=_uid(current_user))
        db.add(row)
    row.version = (body.version or "")[:20] or None
    row.running = bool(body.running)
    row.label = (body.label or "")[:120] or None
    row.note = (body.note or "")[:300] or None
    row.last_seen_at = datetime.utcnow()
    await db.commit()
    return await _agent_status(db, _uid(current_user))


@router.get("/agent/status", response_model=AgentStatusOut)
async def agent_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """웹 신호등용. 실행기가 켜져 있는지, 어떤 버전인지, 지금 발행 중인지."""
    return await _agent_status(db, _uid(current_user))


async def _agent_status(db: AsyncSession, user_id: str) -> AgentStatusOut:
    rows = (await db.execute(select(AgentSession).where(AgentSession.user_id == user_id)
                             .order_by(AgentSession.last_seen_at.desc()))).scalars().all()
    now = datetime.utcnow()
    devices = []
    for r in rows:
        seconds = max(0, int((now - (r.last_seen_at or now)).total_seconds()))
        devices.append(AgentDeviceOut(device_id=r.device_id, version=r.version, running=bool(r.running),
                                      label=r.label, note=r.note,
                                      last_seen_at=(r.last_seen_at or now).isoformat(timespec="seconds"),
                                      seconds_ago=seconds))
    live = [d for d in devices if d.seconds_ago <= ONLINE_SECONDS]
    return AgentStatusOut(online=bool(live), running=any(d.running for d in live),
                          version=live[0].version if live else None, devices=devices[:5])


# ─────────────────────── 홈페이지 ↔ 실행기 자동 연결 ───────────────────────
# 로그인된 홈페이지가 1회용 코드를 받아 같은 PC의 실행기(127.0.0.1)에 건넨다. 실행기는 그 코드로
# 이 기기 전용 키를 받고, 키로 필요할 때마다 로그인 토큰을 새로 받는다. 비밀번호는 오가지 않는다.
PAIR_CODE_SECONDS = 600
PAIR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 헷갈리는 0/O, 1/I 제외


def _secret_hash(secret: str) -> str:
    import hashlib
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class PairCodeOut(BaseModel):
    code: str
    expires_in: int


class PairClaimIn(BaseModel):
    code: str
    device_id: str
    label: Optional[str] = None


class PairClaimOut(BaseModel):
    device_secret: str
    email: Optional[str] = None


class DeviceTokenIn(BaseModel):
    device_id: str
    device_secret: str


class DeviceTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: Optional[str] = None


async def _user_email(db: AsyncSession, user_id: str) -> Optional[str]:
    """실행기 화면에 '어느 계정에 연결됐는지' 보여주기 위한 값. 못 찾으면 None — 연결은 계속된다."""
    from uuid import UUID
    try:
        user = await db.get(User, UUID(str(user_id)))
    except Exception:  # noqa: BLE001  잘못된 id·조회 실패 모두 표시만 생략한다
        return None
    return getattr(user, "email", None) if user else None


@router.post("/agent/pair", response_model=PairCodeOut)
async def agent_pair_code(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """로그인된 홈페이지가 부른다. 10분 동안 한 번 쓸 수 있는 연결 코드."""
    import secrets
    now = datetime.utcnow()
    uid = _uid(current_user)
    # 지난 코드는 정리한다 — 쌓아 둘 이유가 없다.
    for old in (await db.execute(select(AgentPairCode).where(AgentPairCode.user_id == uid))).scalars().all():
        if old.used_at or old.expires_at <= now:
            await db.delete(old)
    code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(8))
    db.add(AgentPairCode(code=code, user_id=uid, created_at=now, expires_at=now + timedelta(seconds=PAIR_CODE_SECONDS)))
    await db.commit()
    return PairCodeOut(code=code, expires_in=PAIR_CODE_SECONDS)


async def _issue_device_secret(db: AsyncSession, user_id: str, device_id: str, label: Optional[str]) -> str:
    """이 PC를 그 계정에 묶고 기기 전용 키를 새로 발급한다(커밋은 부르는 쪽에서)."""
    import secrets
    now = datetime.utcnow()
    secret = secrets.token_urlsafe(32)
    device = await db.get(AgentDevice, device_id)
    if device and device.user_id != user_id:
        # PC가 다른 계정으로 옮겨 간다 — 예전 계정의 신호등 기록은 지운다.
        session = await db.get(AgentSession, device_id)
        if session:
            await db.delete(session)
    if not device:
        device = AgentDevice(device_id=device_id, user_id=user_id, created_at=now)
        db.add(device)
    device.user_id = user_id
    device.secret_hash = _secret_hash(secret)
    device.label = (label or "")[:120] or None
    device.revoked_at = None
    device.last_used_at = now
    return secret


@router.post("/agent/pair/claim", response_model=PairClaimOut)
async def agent_pair_claim(body: PairClaimIn, db: AsyncSession = Depends(get_db)):
    """실행기가 부른다(로그인 없음). 코드는 한 번만 통하고, 성공하면 이 기기 전용 키를 준다."""
    now = datetime.utcnow()
    code = (body.code or "").strip().upper().replace("-", "")
    device_id = (body.device_id or "").strip()[:64]
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 가 필요합니다")
    row = await db.get(AgentPairCode, code) if code else None
    if not row or row.used_at or row.expires_at <= now:
        raise HTTPException(status_code=400, detail="연결 코드가 만료되었거나 이미 사용되었습니다. 홈페이지를 새로고침하세요")
    row.used_at = now
    secret = await _issue_device_secret(db, row.user_id, device_id, body.label)
    await db.commit()
    return PairClaimOut(device_secret=secret, email=await _user_email(db, row.user_id))


# --------------------------------------------- 실행기가 먼저 손을 드는 연결(켜면 브라우저가 열린다)
# 위의 코드 방식은 홈페이지가 이 PC의 127.0.0.1 창구에 닿아야 한다. 브라우저가 로컬 접근을 막으면 그 길이 끊긴다.
# 그래서 반대 방향도 둔다: 실행기가 요청을 만들고 브라우저를 열면, 로그인돼 있는 홈페이지가 승인한다.

PAIR_REQUEST_SECONDS = 600


class PairRequestIn(BaseModel):
    device_id: str
    label: Optional[str] = None


class PairRequestOut(BaseModel):
    request_id: str
    expires_in: int


class PairRequestInfoOut(BaseModel):
    device_id: str
    label: Optional[str] = None
    approved: bool
    mine: bool           # 이미 내 계정이 승인한 요청인가


class PairApproveIn(BaseModel):
    request_id: str


class PairPollIn(BaseModel):
    request_id: str
    device_id: str


class PairPollOut(BaseModel):
    status: str                         # waiting | ok
    device_secret: Optional[str] = None
    email: Optional[str] = None


async def _live_request(db: AsyncSession, request_id: str) -> AgentPairRequest:
    row = await db.get(AgentPairRequest, (request_id or "").strip()[:64]) if request_id else None
    if not row or row.picked_at or row.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=404, detail="연결 요청을 찾을 수 없습니다. 실행기에서 [지금 연결하기]를 다시 누르세요")
    return row


@router.post("/agent/pair/request", response_model=PairRequestOut)
async def agent_pair_request(body: PairRequestIn, db: AsyncSession = Depends(get_db)):
    """실행기가 부른다(로그인 없음). 10분짜리 연결 요청을 만들고 그 열쇠(request_id)를 돌려준다."""
    import secrets
    now = datetime.utcnow()
    device_id = (body.device_id or "").strip()[:64]
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 가 필요합니다")
    # 같은 PC가 다시 켜지면 예전 요청은 의미가 없다. 만료된 것들과 함께 지운다.
    for old in (await db.execute(select(AgentPairRequest).where(
            (AgentPairRequest.device_id == device_id) | (AgentPairRequest.expires_at <= now)))).scalars().all():
        await db.delete(old)
    request_id = secrets.token_urlsafe(32)[:64]
    db.add(AgentPairRequest(request_id=request_id, device_id=device_id, label=(body.label or "")[:120] or None,
                            created_at=now, expires_at=now + timedelta(seconds=PAIR_REQUEST_SECONDS)))
    await db.commit()
    return PairRequestOut(request_id=request_id, expires_in=PAIR_REQUEST_SECONDS)


@router.get("/agent/pair/request/{request_id}", response_model=PairRequestInfoOut)
async def agent_pair_request_info(request_id: str, current_user: User = Depends(get_current_user),
                                  db: AsyncSession = Depends(get_db)):
    """홈페이지가 승인 화면에 '어느 PC인지' 보여주려고 읽는다."""
    row = await _live_request(db, request_id)
    return PairRequestInfoOut(device_id=row.device_id, label=row.label, approved=bool(row.approved_at),
                              mine=row.user_id == _uid(current_user))


@router.post("/agent/pair/approve")
async def agent_pair_approve(body: PairApproveIn, current_user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    """로그인된 홈페이지가 이 PC를 내 계정에 연결하겠다고 승인한다."""
    row = await _live_request(db, body.request_id)
    row.user_id = _uid(current_user)
    row.approved_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "device_id": row.device_id}


@router.post("/agent/pair/poll", response_model=PairPollOut)
async def agent_pair_poll(body: PairPollIn, db: AsyncSession = Depends(get_db)):
    """실행기가 부른다(로그인 없음). 승인되면 기기 키를 한 번만 내준다."""
    row = await _live_request(db, body.request_id)
    device_id = (body.device_id or "").strip()[:64]
    if not device_id or device_id != row.device_id:
        # 요청을 만든 PC만 가져갈 수 있다.
        raise HTTPException(status_code=404, detail="연결 요청을 찾을 수 없습니다")
    if not row.approved_at or not row.user_id:
        return PairPollOut(status="waiting")
    row.picked_at = datetime.utcnow()
    secret = await _issue_device_secret(db, row.user_id, device_id, row.label)
    await db.commit()
    return PairPollOut(status="ok", device_secret=secret, email=await _user_email(db, row.user_id))


@router.post("/agent/device-token", response_model=DeviceTokenOut)
async def agent_device_token(body: DeviceTokenIn, db: AsyncSession = Depends(get_db)):
    """실행기가 부른다(로그인 없음). 기기 키로 새 로그인 토큰을 받는다."""
    import hmac
    from app.core.security import create_access_token
    device = await db.get(AgentDevice, (body.device_id or "").strip()[:64])
    if (not device or device.revoked_at
            or not hmac.compare_digest(device.secret_hash, _secret_hash(body.device_secret or ""))):
        raise HTTPException(status_code=401, detail="이 PC의 연결이 해제되었습니다. 홈페이지를 열면 다시 연결됩니다")
    device.last_used_at = datetime.utcnow()
    await db.commit()
    return DeviceTokenOut(access_token=create_access_token(subject=device.user_id),
                          email=await _user_email(db, device.user_id))


@router.delete("/agent/devices/{device_id}")
async def agent_device_revoke(device_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """홈페이지에서 이 PC의 연결을 끊는다. 실행기는 다음 토큰 요청부터 거절된다."""
    device = await db.get(AgentDevice, device_id)
    if not device or device.user_id != _uid(current_user):
        raise HTTPException(status_code=404, detail="연결된 기기를 찾을 수 없습니다")
    device.revoked_at = datetime.utcnow()
    session = await db.get(AgentSession, device_id)
    if session:
        await db.delete(session)
    await db.commit()
    return {"success": True}


@router.get("/agent/blogs/{blog_ref_id}/credential")
async def agent_credential(blog_ref_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """에이전트 자동 로그인용. 앱 화면에서는 쓰지 않는다."""
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    return {"login_id": b.login_id, "login_pw": crypto.decrypt(b.login_pw_enc), "naver_blog_id": b.blog_id}
