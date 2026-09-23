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
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, inspect, select, update
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
from app.services import docx_import
from app.services.point_formatting import PointFormatting, apply_points
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
    proxy_label: Optional[str] = None         # 화면 표시용. 비밀번호는 지운 주소만 보낸다.
    # 이 아이디로 올리는 글 끝에 늘 붙는 것들
    footer_link_url: Optional[str] = None
    footer_link_label: Optional[str] = None
    place_url: Optional[str] = None
    place_label: Optional[str] = None


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


def _proxy_label(proxy_enc: Optional[str]) -> Optional[str]:
    """화면에는 host:port 만 보여 준다 — 프록시 비밀번호를 브라우저로 돌려보내지 않는다."""
    raw = crypto.decrypt(proxy_enc) if proxy_enc else None
    if not raw:
        return None
    from urllib.parse import urlparse
    try:
        parsed = urlparse(raw if "://" in raw else "http://" + raw)
        host = parsed.hostname or ""
        return f"{host}:{parsed.port}" if parsed.port else host
    except ValueError:
        return "설정됨"


def _blog_out(b: Blog) -> BlogOut:
    return BlogOut(
        id=b.id, client_id=b.client_id, blog_id=b.blog_id, label=b.label, login_id=b.login_id,
        has_password=bool(b.login_pw_enc), daily_limit=b.daily_limit or 3,
        window_start=b.window_start or "09:00", window_end=b.window_end or "21:00",
        min_gap_minutes=b.min_gap_minutes or 120, default_category=b.default_category,
        open_type=b.open_type or "public", status=b.status or "active", status_reason=b.status_reason,
        last_published_at=b.last_published_at, proxy_label=_proxy_label(b.proxy_enc),
        footer_link_url=b.footer_link_url, footer_link_label=b.footer_link_label,
        place_url=b.place_url, place_label=b.place_label,
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
    # 이 블로그만 쓸 고정 프록시. 비우면 기존 값 유지, "-" 하나면 지운다(= 프록시 없이 발행).
    proxy_url: Optional[str] = None
    daily_limit: int = 3
    window_start: str = "09:00"
    window_end: str = "21:00"
    min_gap_minutes: int = 120
    default_category: Optional[str] = None
    open_type: str = "public"
    # 이 아이디로 올리는 글 끝에 늘 붙일 것들. 한 번 저장해 두면 매번 안 넣어도 된다.
    footer_link_url: Optional[str] = None
    footer_link_label: Optional[str] = None
    place_url: Optional[str] = None
    place_label: Optional[str] = None


def _clean_footer_url(raw: Optional[str]) -> Optional[str]:
    """글 끝에 붙일 주소. 빈 값이면 지우고, 모양이 틀리면 거절한다.

    네이버는 한 줄짜리 https 주소를 링크 카드(플레이스면 지도 카드)로 바꿔 준다.
    그래서 저장해 두는 것도, 글에 넣는 것도 '주소 한 줄'이면 충분하다."""
    value = (raw or "").strip()
    if not value or value == "-":
        return None
    from app.services import landing_links
    try:
        return landing_links.validate_url(value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _clean_proxy(raw: Optional[str]) -> Optional[str]:
    """host:port 또는 scheme://user:pw@host:port 를 받아 정규화한다. 모양이 틀리면 거절한다.

    틀린 주소를 저장하면 발행할 때 브라우저가 아예 뜨지 않아 원인을 찾기 어렵다."""
    from urllib.parse import urlparse
    value = (raw or "").strip()
    if not value or value == "-":
        return None
    if "://" not in value:
        value = "http://" + value
    try:
        parsed = urlparse(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="프록시 주소 형식이 올바르지 않습니다")
    if parsed.scheme not in ("http", "https", "socks5", "socks5h"):
        raise HTTPException(status_code=400, detail="프록시는 http, https, socks5 만 됩니다")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="프록시 주소에 서버가 없습니다 (예: 123.45.67.89:8080)")
    try:
        if parsed.port is None:
            raise HTTPException(status_code=400, detail="프록시 주소에 포트가 필요합니다 (예: 123.45.67.89:8080)")
    except ValueError:
        raise HTTPException(status_code=400, detail="프록시 포트가 숫자가 아닙니다")
    return value


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
        proxy_enc=crypto.encrypt(_clean_proxy(body.proxy_url)),
        footer_link_url=_clean_footer_url(body.footer_link_url),
        footer_link_label=(body.footer_link_label or "").strip()[:100] or None,
        place_url=_clean_footer_url(body.place_url),
        place_label=(body.place_label or "").strip()[:100] or None,
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
    if body.proxy_url is not None and body.proxy_url.strip():
        b.proxy_enc = None if body.proxy_url.strip() == "-" else crypto.encrypt(_clean_proxy(body.proxy_url))
    b.daily_limit, b.window_start, b.window_end = body.daily_limit, body.window_start, body.window_end
    b.min_gap_minutes, b.default_category, b.open_type = body.min_gap_minutes, body.default_category, body.open_type
    b.footer_link_url = _clean_footer_url(body.footer_link_url)
    b.footer_link_label = (body.footer_link_label or "").strip()[:100] or None
    b.place_url = _clean_footer_url(body.place_url)
    b.place_label = (body.place_label or "").strip()[:100] or None
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
            "description": "키네스 지점 요청 흐름: 부모의 한 가지 걱정 → 함께 살펴볼 핵심 항목 → 그 이유 → 실제 관리 내용 → 관련 사례·자료 → 마무리",
            "flow": [
                {"title": "부모의 걱정에 공감", "goal": "아이 키가 또래보다 작아 걱정하는 부모 마음에 공감하며 시작. 질문형 도입 1~2문장.", "min_chars": 250},
                {"title": "함께 살펴볼 핵심 항목", "goal": "이번 글의 걱정을 이해하는 데 필요한 항목 한 가지와 보조 항목 한 가지만 쉬운 말로 설명.", "min_chars": 350},
                {"title": "왜 함께 살펴봐야 할까요", "goal": "앞 문단의 항목이 아이의 성장·체력 관리와 어떤 관련이 있는지 설명. 새로운 주제를 추가하지 않음.", "min_chars": 300},
                {"title": "키네스의 관리 방법", "goal": "제공된 병원 사실과 근거 자료 안에서 상담·운동·생활 관리 등 실제 내용을 소개. 검사 시행을 암시하지 않음.", "min_chars": 400},
                {"title": "관련 사례와 기록", "goal": "첨부된 사례 자료에서 이번 주제와 직접 관련된 상황·관리·기록만 사용. 수치와 인과관계를 만들지 않음.", "min_chars": 350},
                {"title": "마무리", "goal": "골든타임을 놓치지 않도록 상담 권유. 부담 없는 톤. 과장·확정 표현 없이.", "min_chars": 150},
            ],
            "rules": "부모(주로 엄마)에게 설명하는 정중한 말투. 의학 용어는 한 번 풀어서 쓴다. '반드시 큰다', '최고', '유일' 같은 단정·최상급 금지. 가격·이벤트 언급 금지. 흐름의 순서를 바꾸지 않는다.",
            "must_include": ["키네스"],
            "avoid": ["100%", "완치", "보장", "무조건", "최고", "유일", "부작용 없음", "뼈나이 검사", "골연령 검사", "성장판 검사", "성장판을 검사"],
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


@router.get("/campaigns/{campaign_id}/formatting", response_model=PointFormatting)
async def get_point_formatting(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    return PointFormatting.model_validate((c.settings or {}).get('formatting') or {})


@router.put("/campaigns/{campaign_id}/formatting", response_model=PointFormatting)
async def save_point_formatting(campaign_id: str, body: PointFormatting, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    c.settings = {**(c.settings or {}), 'formatting': body.model_dump()}
    await db.commit()
    return body


@router.post("/drafts/{draft_id}/formatting-preview")
async def preview_point_formatting(draft_id: str, body: PointFormatting, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    blocks = d.blocks or [{'type':'text','content':p} for p in re.split(r'\n\s*\n', d.body or '') if p]
    styled = apply_points(blocks, body.model_dump(), [d.keyword or '', *(d.emphasize or [])])
    # Keep image bytes and pool identifiers out of the text preview.
    return {'title': d.title, 'blocks': [b if b.get('type') != 'image' else {'type':'image'} for b in styled]}


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
    category: Optional[str] = None
    intent_score: int = 0              # 간절함(내원 의도) 0~100
    intent_reason: Optional[str] = None
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
        id=k.id, keyword=k.keyword, region=k.region, disease=k.disease, category=k.category,
        intent_score=int(k.intent_score or 0), intent_reason=k.intent_reason,
        source=k.source or "manual", scope=k.scope or "region",
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


class HuntIn(BaseModel):
    """키워드 발굴: 씨앗 확장 → 통합검색 자리 확인 → 내 블로그로 뚫리는지 판정."""
    target: int = Field(100, ge=10, le=500)          # 최종으로 쓰고 싶은 키워드 수
    blog_id: Optional[str] = None                     # 판정 기준 블로그(비우면 캠페인의 정상 블로그)
    screen_limit: Optional[int] = Field(None, ge=10, le=1000)   # ② 통검을 볼 최대 개수
    verdict_limit: Optional[int] = Field(None, ge=0, le=500)    # ③ 내 블로그 판정 최대 개수
    # 직접 찾고 싶은 키워드. 주면 진료 항목 대신 이것만 파고, 연관어도 이 기준으로 살린다.
    seeds: Optional[List[str]] = Field(None, max_length=20)
    # 질환별 개수 {"건선": 30, "습진": 20}. 합이 target 을 넘으면 비율로 보고 줄인다.
    disease_quota: Optional[Dict[str, int]] = None
    # 글 성격 비율 {"증상": 20, "치료": 25, ...}. 후보가 모자란 칸은 다른 성격으로 메운다.
    category_ratio: Optional[Dict[str, int]] = None
    # 새로 찾을 때 이 캠페인의 지난 키워드를 비운다(기본). 이어 붙이려면 false.
    replace: bool = True


@router.get("/keyword-categories")
async def keyword_categories(current_user: User = Depends(get_current_user)):
    """화면이 비율 입력칸을 그릴 때 쓰는 카테고리 목록과 기본 비율."""
    from app.services import keyword_taxonomy as tx
    return {"categories": [{"key": c, "label": tx.CATEGORY_LABELS[c],
                            "default_ratio": tx.DEFAULT_RATIO.get(c, 0)} for c in tx.CATEGORIES]}


@router.post("/campaigns/{campaign_id}/keywords/hunt", response_model=TaskOut)
async def hunt_keywords(campaign_id: str, body: HuntIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    payload = {"campaign_id": c.id, **body.model_dump(exclude_none=True)}
    job = await job_worker.enqueue(db, "keyword_hunt", payload, _uid(current_user), dedupe_key=f"hunt:{c.id}")
    return _task_out(job)


class ManualKeywordsIn(BaseModel):
    keywords: List[str]
    fetch_volume: bool = True


@router.post("/campaigns/{campaign_id}/keywords", response_model=List[KeywordOut])
async def add_keywords(campaign_id: str, body: ManualKeywordsIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    from app.services import keyword_expander as ke, keyword_taxonomy as tx, search_volume_service as svs
    cl = await db.get(Client, c.client_id) if c.client_id else None
    subjects = list(dict.fromkeys(((cl.diseases if cl else None) or []) + ((cl.treatments if cl else None) or [])))
    regions = (cl.regions if cl else None) or []
    existing = {ke._norm(k.keyword): k for k in (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()}
    clean = [k.strip() for k in body.keywords if k and k.strip()]
    new_rows: List[CampaignKeyword] = []
    for kw in clean:
        if ke._norm(kw) in existing:
            continue
        category = tx.classify(kw, regions, subjects)
        score, why = tx.intent(kw, regions, subjects, category)
        row = CampaignKeyword(user_id=_uid(current_user), campaign_id=c.id, client_id=c.client_id, keyword=kw,
                              source="manual", selected=True, category=category,
                              intent_score=score, intent_reason=why)
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


async def _fill_intent(db: AsyncSession, c: Campaign, rows: List[CampaignKeyword]) -> None:
    """간절함 점수가 없는 행을 채운다. 글자만 보고 매기므로 읽을 때 채워도 값이 싸다."""
    missing = [k for k in rows if k.intent_score is None]
    if not missing:
        return
    from app.services import keyword_taxonomy as tx
    cl = await db.get(Client, c.client_id) if c.client_id else None
    regions = (cl.regions if cl else None) or []
    subjects = list(dict.fromkeys(((cl.diseases if cl else None) or []) + ((cl.treatments if cl else None) or [])))
    for k in missing:
        k.intent_score, k.intent_reason = tx.intent(k.keyword, regions, subjects, k.category)
    await db.commit()


@router.get("/campaigns/{campaign_id}/keywords", response_model=List[KeywordOut])
async def list_keywords(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    rows = (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()
    drafted = {r for (r,) in (await db.execute(select(Draft.keyword_id).where(Draft.campaign_id == c.id, Draft.keyword_id.isnot(None)))).all()}
    await _fill_intent(db, c, rows)
    # 쓸 키워드 먼저, 그다음 **간절한 순**. 검색량은 마지막 저울이다 —
    # 많이 검색되는 글이 아니라 환자가 될 사람이 보는 글부터 쓰라는 뜻이다.
    rows.sort(key=lambda k: (not k.selected, not k.passes_filter,
                             -int(k.intent_score or 0), -(k.monthly_mobile or 0), k.keyword))
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


@router.delete("/campaigns/{campaign_id}/keywords")
async def clear_keywords(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """이 캠페인의 키워드를 전부 비운다.

    지난 판정은 블로그 지수·경쟁 상황이 바뀌면 더 이상 맞지 않는다. 쌓아 두면 어느 것이
    이번에 본 것인지 알 수 없으므로, 새로 찾기 전에 싹 지울 수 있어야 한다
    (발굴 작업의 replace 와 같은 일을 사용자가 직접 하는 것)."""
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    removed = (await db.execute(delete(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).rowcount or 0
    await db.commit()
    return {"removed": removed}


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
    # 이미 예약이 걸린 원고인가. 걸려 있으면 다시 고를 수 없어야 한다.
    booked_at: Optional[str] = None           # 잡혀 있는 예약 시각(KST)
    booked_job_id: Optional[str] = None       # 그 예약(발행건) 번호 — 화면에서 바로 취소할 수 있게
    booked_status: Optional[str] = None       # queued=아직 네이버에 안 올림 / submitted=이미 등록됨


def _draft_out(d: Draft, with_body: bool = True, booked_at: Optional[str] = None,
               booked_job_id: Optional[str] = None, booked_status: Optional[str] = None) -> DraftOut:
    return DraftOut(
        booked_at=booked_at, booked_job_id=booked_job_id, booked_status=booked_status,
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
    """txt/md → (제목, 본문). 제목 = 첫 줄(없으면 파일명). 워드는 _parse_docx_upload 가 맡는다."""
    text = ""
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


def _data_url_bytes(raw: str) -> bytes:
    _, _, b64 = (raw or "").partition(",")
    try:
        return base64.b64decode(b64)
    except Exception:  # noqa: BLE001
        return b""


async def _store_doc_image(db: AsyncSession, user_id: str, block: Dict[str, Any], warnings: List[str]) -> Optional[str]:
    """문서 안 사진 한 장 → 사진 풀의 행. 바이트를 원고에 담지 않으려고 풀에 넣고 번호만 참조한다."""
    from app.api.media_pool import _normalize_upload, animated_gif_passthrough

    name = block.get("name") or "사진"
    raw = _data_url_bytes(block.get("image") or "")
    if not raw:
        warnings.append(f"{name}: 사진을 읽지 못해 건너뜁니다")
        return None
    try:
        # 움직이는 GIF 는 손대지 않는다. JPEG 로 줄이면 첫 장면만 남아 멈춘 그림이 된다.
        moving = await run_in_threadpool(animated_gif_passthrough, raw)
        content_type = "image/gif" if moving else "image/jpeg"
        data, w, h, ph, thumb = moving or await run_in_threadpool(_normalize_upload, raw)
    except Exception:  # noqa: BLE001
        warnings.append(f"{name}: 사진 형식을 알 수 없어 건너뜁니다")
        return None
    row = PoolImage(
        user_id=user_id, filename=name, content_type=content_type, data=data, thumbnail=thumb,
        original_phash=ph, width=w, height=h, size_bytes=len(data),
    )
    db.add(row)
    await db.flush()
    return row.id


async def _parse_docx_upload(db: AsyncSession, user_id: str, name: str, data: bytes) -> tuple[str, str, List[Dict[str, Any]], Dict[str, Any]]:
    """워드 → (제목, 평문, 서식 블록, 읽은 내역). 사진은 풀에 넣고 블록에는 번호만 남긴다."""
    try:
        parsed = await run_in_threadpool(docx_import.parse_docx, data, name=name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"{name}: {e}")

    blocks: List[Dict[str, Any]] = []
    for block in parsed.blocks:
        if block.get("type") != "image":
            blocks.append(block)
            continue
        pool_image_id = await _store_doc_image(db, user_id, block, parsed.warnings)
        if pool_image_id:
            blocks.append({"type": "image", "content": "", "pool_image_id": pool_image_id, "name": block.get("name")})
    summary = {
        "source": "docx",
        "links": parsed.links[:20],          # 원고에 걸려 있던 링크(본문에 그대로 살려 넣었다)
        "images": sum(1 for b in blocks if b["type"] == "image"),
        "tables": sum(1 for b in blocks if b["type"] == "table"),
        "headings": sum(1 for b in blocks if b["type"] == "heading"),
        "warnings": parsed.warnings[:10],
    }
    return parsed.title, parsed.text, blocks, summary


@router.post("/campaigns/{campaign_id}/drafts/upload", response_model=List[DraftOut])
async def upload_drafts(campaign_id: str, files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    client = await db.get(Client, c.client_id)
    kws = (await db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == c.id))).scalars().all()
    out: List[Draft] = []
    for f in files[:200]:
        data = await f.read()
        name = f.filename or "원고.txt"
        blocks: Optional[List[Dict[str, Any]]] = None
        imported: Optional[Dict[str, Any]] = None
        if name.lower().endswith(".docx"):
            # 워드는 글쓴이가 잡아 둔 서식이 곧 원고다. reflow 로 문단을 다시 나누면 블록과 어긋난다.
            title, body, blocks, imported = await _parse_docx_upload(db, _uid(current_user), name, data)
        else:
            title, body = _parse_upload(name, data)
            body = writer.reflow(body)
        # 키워드 자동 매칭: 제목/본문에 들어 있는 캠페인 키워드 중 가장 긴 것
        matched = None
        hay = (title + "\n" + body).replace(" ", "")
        for k in sorted(kws, key=lambda x: -len(x.keyword)):
            if k.keyword.replace(" ", "") in hay:
                matched = k
                break
        # 의료광고법 표현은 막지 않고 고친다 — 대안이 있으면 바꾸고, 없으면 그 문장을 덜어낸다.
        title, body, blocks, fixes = writer.sanitize_blocks(blocks, title, body)
        checks = writer.run_static_checks(title, body, client.forbidden_words if client else [])
        if fixes:
            checks["auto_fixed"] = fixes[:30]
        if imported:
            checks["import"] = imported
        d = Draft(
            user_id=_uid(current_user), client_id=c.client_id, campaign_id=c.id,
            keyword_id=matched.id if matched else None, keyword=matched.keyword if matched else None,
            source="upload", title=title[:200], body=body, blocks=blocks, char_count=writer.count_chars(body),
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


async def _heal_law_holds(db: AsyncSession, rows: List[Draft]) -> None:
    """의료광고법 표현 때문에 서 있던 옛 원고를 고쳐서 풀어 준다.

    규칙이 '막기'에서 '고치기'로 바뀌기 전에 올라온 원고들은 needs_review 인 채로 남아
    영영 예약되지 않는다. 읽을 때 한 번 고쳐 주면 사용자가 다시 올릴 일이 없다.
    병원이 등록한 금칙어에 걸린 원고는 건드리지 않는다 — 그것은 사람이 판단할 몫이다."""
    healed = False
    for d in rows:
        checks = dict(d.checks or {})
        if d.status != "needs_review" or checks.get("forbidden") or not checks.get("medical_law"):
            continue
        title, body, blocks, fixes = writer.sanitize_blocks(d.blocks, d.title, d.body or "")
        d.title, d.body, d.blocks = title[:200], body, blocks
        d.char_count = writer.count_chars(body)
        checks["medical_law"] = []
        checks["ok"] = True
        if fixes:
            checks["auto_fixed"] = (checks.get("auto_fixed") or []) + fixes[:30]
        d.checks = checks
        d.status = "ready"
        healed = True
    if healed:
        await db.commit()


@router.get("/campaigns/{campaign_id}/drafts", response_model=List[DraftOut])
async def list_drafts(campaign_id: str, with_body: bool = False, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    rows = (await db.execute(select(Draft).where(Draft.campaign_id == c.id).order_by(Draft.created_at.asc()))).scalars().all()
    await _heal_law_holds(db, rows)
    booked = {r: (jid, at, st) for r, jid, at, st in (await db.execute(
        select(PublishJob.draft_id, PublishJob.id, PublishJob.scheduled_at, PublishJob.status).where(
            PublishJob.campaign_id == c.id, PublishJob.status.in_(list(JOB_ACTIVE))))).all()}
    out = []
    for d in rows:
        jid, at, st = booked.get(d.id, (None, None, None))
        out.append(_draft_out(d, with_body=with_body,
                              booked_at=at.isoformat(timespec="minutes") if at else None,
                              booked_job_id=jid, booked_status=st))
    return out


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
        if d.blocks:
            # 본문을 손으로 고치면 워드 서식 블록은 더 이상 이 글이 아니다. 고친 글이 이긴다 —
            # 그대로 두면 발행은 블록을 먼저 보므로 수정이 조용히 사라진다.
            d.blocks = None
            checks.pop("import", None)
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
        for preserved in ('import','formatting'):
            if preserved in previous_checks:
                checks[preserved] = previous_checks[preserved]
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


@router.post("/drafts/{draft_id}/approve", response_model=DraftOut)
async def approve_draft(draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """'원고 검토 필요'를 사람이 보고 그대로 쓰겠다고 확인한다.

    검수는 글자 패턴 매칭이라 오탐이 많다('1,000원'·'무료 상담'·'보장'이 들어간 평범한 문장).
    올린 사람이 자기 원고를 보고 판단하는 것이 맞고, 확인하지 않으면 발행 단계에서 막혀
    아무것도 못 하게 된다. 무엇을 보고 승인했는지는 원고에 남긴다."""
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    if d.status not in ("needs_review", "ready"):
        raise HTTPException(status_code=400, detail="검토를 기다리는 원고만 확인할 수 있습니다")
    checks = dict(d.checks or {})
    checks["review"] = {
        "approved_at": datetime.utcnow().isoformat(timespec="seconds"),
        "by": "user",
        "flags": len(checks.get("medical_law") or []) + len(checks.get("forbidden") or []),
    }
    checks["ok"] = True
    d.checks = checks
    d.status = "ready"
    await db.commit()
    return _draft_out(d)


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _owned(db, Draft, draft_id, current_user, "원고")
    active = (await db.execute(select(func.count()).select_from(PublishJob).where(PublishJob.draft_id == d.id, PublishJob.status.in_(list(JOB_ACTIVE))))).scalar() or 0
    if active:
        raise HTTPException(status_code=400, detail=(
            "이 원고에는 예약이 걸려 있습니다. 줄 오른쪽의 [예약 취소]를 누른 뒤 지우세요."))
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
    # spread: 기간 안에 흩뿌린다(기존 마법사). interval: 고른 시각부터 고른 간격으로 하나씩(원스톱).
    mode: Literal["spread", "interval"] = "spread"
    start_at: Optional[datetime] = None      # interval 전용. 첫 글 시각(KST naive). 비우면 start_date 09:00
    every_minutes: Optional[int] = None      # interval 전용. 글 사이 간격(분). 비우면 120
    # at: start_at 부터 / after_last: 아는 마지막 예약 + 간격 부터(이미 예약된 글 다음에 이어 붙이기)
    start_mode: Literal["at", "after_last"] = "at"


class ScheduleItem(BaseModel):
    draft_id: str
    title: str
    blog_ref_id: str
    blog_label: str
    scheduled_at: str


class BlogReservations(BaseModel):
    """블로그 한 개의 '이미 잡혀 있는 자리' 현황. 화면이 이 숫자를 그대로 읽어 준다."""
    blog_ref_id: str
    label: str
    count: int = 0                       # 앞으로 남은 예약 건수(우리 것 + 네이버에서 읽어 온 것)
    last_at: Optional[str] = None        # 그중 가장 늦은 시각
    scanned_at: Optional[str] = None     # 네이버 목록을 마지막으로 읽어 온 때
    stale: bool = True                   # 읽은 적이 없거나 오래됨 → 완충을 넓혀 잡는다
    note: Optional[str] = None           # 못 읽었을 때의 사유


class SchedulePreview(BaseModel):
    total: int
    assigned: List[ScheduleItem]
    unassigned: int
    calendar: List[Dict[str, Any]]
    warnings: List[str] = []
    starts_after: Optional[str] = None           # '이미 예약된 글 다음부터'의 기준이 된 마지막 예약
    reservations: List[BlogReservations] = []


async def _schedule_inputs(db: AsyncSession, c: Campaign, body: ScheduleIn, user: User):
    blog_ids = body.blog_ids or c.blog_ids or []
    blogs = (await db.execute(select(Blog).where(Blog.id.in_(blog_ids), Blog.user_id == _uid(user)))).scalars().all() if blog_ids else []
    warnings: List[str] = []
    usable = []
    # 로그인·보안확인은 '올릴 때' 풀면 되는 문제다 — 예약 자체를 막지 않는다.
    LATER = {"login_required": "네이버 로그인이 필요합니다. 실행기가 띄운 크롬 창에서 로그인하면 그대로 올라갑니다.",
             "captcha": "네이버 보안 확인이 떴습니다. 실행기 창에서 풀어 주면 그대로 올라갑니다."}
    for b in blogs:
        name = b.label or b.blog_id
        if b.status in LATER:
            warnings.append(f"{name}: {LATER[b.status]}")
            usable.append(b)
            continue
        if b.status != "active":
            warnings.append(f"{name}: 상태가 '{b.status}'라 제외했습니다. {b.status_reason or ''}".strip())
            continue
        usable.append(b)
    if not usable:
        if blogs:
            trouble = ", ".join(f"{b.label or b.blog_id}({b.status})" for b in blogs)
            raise HTTPException(status_code=400, detail=(
                f"올릴 수 있는 블로그가 없습니다 — {trouble}. 병원 관리에서 이 블로그를 '정상'으로 바꾸거나 다른 블로그를 고르세요."))
        raise HTTPException(status_code=400, detail="올릴 블로그가 없습니다. 2번 칸에서 블로그를 골라 주세요.")
    q = select(Draft).where(Draft.campaign_id == c.id)
    statuses = ["ready"] + (["needs_review"] if body.include_needs_review else [])
    q = q.where(Draft.status.in_(statuses))
    if body.draft_ids:
        q = q.where(Draft.id.in_(body.draft_ids))
    drafts = (await db.execute(q.order_by(Draft.created_at.asc()))).scalars().all()
    # 변형의 원본만 제외한다. 올린 원고 전부를 빼면(예전 `source != "upload"`) 워드로 올린
    # 완성 원고를 영영 예약할 수 없다 — 변형을 안 뜬 원본과 구별되는 것은 자식의 유무뿐이다.
    # 이번에 고른 원고 밖의 변형도 봐야 하므로 캠페인 전체에서 부모를 모은다.
    parent_ids = {r for (r,) in (await db.execute(select(Draft.parent_draft_id).where(
        Draft.campaign_id == c.id, Draft.parent_draft_id.isnot(None)))).all()}
    drafts = [d for d in drafts if d.id not in parent_ids]
    # 이미 활성 발행건이 있는 원고는 제외
    busy = {r for (r,) in (await db.execute(select(PublishJob.draft_id).where(PublishJob.campaign_id == c.id, PublishJob.status.in_(list(JOB_ACTIVE))))).all()}
    skipped = [d for d in drafts if d.id in busy]
    if skipped:
        warnings.append(f"이미 예약된 원고 {len(skipped)}건은 제외했습니다.")
    drafts = [d for d in drafts if d.id not in busy]
    if not drafts:
        if skipped:
            raise HTTPException(status_code=400, detail=(
                f"고른 원고 {len(skipped)}건은 이미 예약이 걸려 있습니다. "
                "새 Word 원고를 올리거나, 아래 발행 현황에서 기존 예약을 취소한 뒤 다시 잡으세요."))
        if body.draft_ids:
            raise HTTPException(status_code=400, detail=(
                "고른 원고를 예약할 수 없습니다. 검토가 필요한 원고는 화면에서 확인을 눌러 풀어 주세요."))
        raise HTTPException(status_code=400, detail="예약할 원고가 없습니다. Word 원고를 먼저 올려 주세요.")
    plans = [se.blog_plan_from_model(b) for b in usable]
    if body.per_day:
        for p in plans:
            p.daily_limit = max(1, min(20, body.per_day))
    await se.load_taken_slots(db, _uid(user), plans)
    return usable, drafts, plans, warnings, _reservations_state(usable, plans, warnings)


# 네이버 예약 목록을 이만큼 못 읽었으면 '모르는 상태'로 본다.
# 모른다고 간격을 넓히지는 않는다 — 넓혀도 모르는 자리를 피하는 데는 도움이 안 되고,
# 사용자가 고른 간격("2시간마다")과 화면에 적힌 시각만 어긋난다. 대신 화면에 그대로 알린다.
RESERVATION_STALE_HOURS = 12


def _reservations_state(blogs: List[Blog], plans, warnings: List[str]) -> List["BlogReservations"]:
    """블로그별 '이미 잡혀 있는 자리' 현황.

    우리가 걸어 둔 예약은 자리 기록(ScheduleMark·PublishJob)에 그대로 남아 있으므로
    네이버 목록을 못 읽어도 우리끼리는 절대 겹치지 않는다. 목록이 필요한 경우는 하나뿐이다
    — 이 화면 밖에서(손으로·다른 도구로) 잡아 둔 예약."""
    now = se.kst_now()
    by_ref = {p.ref_id: p for p in plans}
    out: List[BlogReservations] = []
    for b in blogs:
        plan = by_ref.get(b.id)
        future = sorted(t for t in (plan.taken if plan else set())) if plan else []
        future = [t for t in future if t > now]
        scanned = b.reservations_scanned_at
        stale = not scanned or (datetime.utcnow() - scanned) > timedelta(hours=RESERVATION_STALE_HOURS)
        label = b.label or b.blog_id
        # '목록을 아직 못 읽었다'는 화면 위 상자가 이미 말한다(stale 값을 그대로 내려 준다).
        # 여기서 또 경고로 적으면 같은 말이 두 번 나온다.
        out.append(BlogReservations(
            blog_ref_id=b.id, label=label, count=len(future),
            last_at=future[-1].isoformat(timespec="minutes") if future else None,
            scanned_at=scanned.isoformat(timespec="minutes") if scanned else None,
            stale=stale, note=b.reservations_note,
        ))
    return out


def _preview(drafts: List[Draft], blogs: List[Blog], assigned, remaining, warnings, *, interval: bool = False,
             starts_after: Optional[str] = None, reservations: Optional[List[BlogReservations]] = None) -> SchedulePreview:
    label = {b.id: (b.label or b.blog_id) for b in blogs}
    items = []
    for d, (ref, at) in zip(drafts, assigned):
        items.append(ScheduleItem(draft_id=d.id, title=d.title, blog_ref_id=ref, blog_label=label.get(ref, ref), scheduled_at=at.isoformat(timespec="minutes")))
    if remaining:
        advice = "간격을 좁히거나 시작을 앞당기세요." if interval else "기간을 늘리거나 하루 건수를 올리세요."
        warnings = warnings + [f"자리가 모자라 {remaining}건을 배정하지 못했습니다. {advice}"]
    return SchedulePreview(total=len(drafts), assigned=items, unassigned=remaining,
                           calendar=se.calendar_view(assigned, label), warnings=warnings,
                           starts_after=starts_after, reservations=reservations or [])


def _allocate(body: ScheduleIn, c: Campaign, drafts: List[Draft], plans,
              blogs: Optional[List[Blog]] = None) -> Tuple[List[Tuple[str, datetime]], int, List[str], Optional[str]]:
    """예약 방식에 따라 자리를 잡는다. 반환 (배정, 미배정 건수, 추가 경고, 이어 붙인 기준 예약)."""
    blogs = blogs or []
    if body.mode == "interval":
        every = max(10, min(7 * 24 * 60, body.every_minutes or 120))
        # 이미 잡힌 자리와도 '고른 간격'만큼만 띄운다. 블로그 설정의 최소 간격으로 더 밀면
        # 화면에는 "마지막 예약 다음 2시간"이라 적고 실제로는 3시간 뒤에 올라간다.
        for p in plans:
            p.min_gap_minutes = every
        # '이미 예약된 글 다음부터' — 아는 마지막 예약에서 고른 간격만큼 떨어진 곳이 첫 글이다.
        last = se.latest_reserved(plans) if body.start_mode == "after_last" else None
        start_at = (last + timedelta(minutes=every)) if last else (body.start_at or datetime.combine(body.start_date, time(9, 0)))
        assigned, remaining = se.allocate_interval(len(drafts), plans, start_at, every, days=max(1, body.days))
        # 하루 몇 건이 되는지는 **간격이 정한다**. 블로그 설정의 하루 한도로 잔소리하지 않는다
        # — 손잡이가 하나뿐이어야 한다. 촘촘하면 많이, 넓히면 적게 올라가고 그 결과는
        # 바로 아래 미리보기에 실제 시각으로 다 적혀 있다(2026-09-23 사용자 결정).
        return assigned, remaining, [], (last.isoformat(timespec="minutes") if last else None)
    seed = body.seed if body.seed is not None else int(c.created_at.timestamp()) if c.created_at else 0
    assigned, remaining = se.allocate(len(drafts), plans, body.start_date, body.days, seed=seed)
    return assigned, remaining, [], None


@router.get("/campaigns/{campaign_id}/reservations", response_model=List[BlogReservations])
async def campaign_reservations(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """이 캠페인 블로그들에 이미 잡혀 있는 자리. 원고를 고르기 전에도 화면이 알려 줄 수 있어야 한다."""
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    blogs = (await db.execute(select(Blog).where(
        Blog.id.in_(c.blog_ids or []), Blog.user_id == _uid(current_user)))).scalars().all() if c.blog_ids else []
    if not blogs:
        return []
    plans = [se.blog_plan_from_model(b) for b in blogs]
    await se.load_taken_slots(db, _uid(current_user), plans)
    return _reservations_state(blogs, plans, [])


@router.post("/campaigns/{campaign_id}/reservations/rescan")
async def campaign_reservations_rescan(campaign_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """[예약 목록 새로 읽기]. 실행기가 다음 차례에 이 블로그들의 목록을 읽어 온다."""
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    blogs = (await db.execute(select(Blog).where(
        Blog.id.in_(c.blog_ids or []), Blog.user_id == _uid(current_user)))).scalars().all() if c.blog_ids else []
    for b in blogs:
        b.reservations_scan_requested_at = datetime.utcnow()
    await db.commit()
    return {"requested": len(blogs)}


@router.post("/campaigns/{campaign_id}/schedule/preview", response_model=SchedulePreview)
async def schedule_preview(campaign_id: str, body: ScheduleIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    blogs, drafts, plans, warnings, reservations = await _schedule_inputs(db, c, body, current_user)
    assigned, remaining, extra, starts_after = _allocate(body, c, drafts, plans, blogs)
    return _preview(drafts, blogs, assigned, remaining, warnings + extra, interval=body.mode == "interval",
                    starts_after=starts_after, reservations=reservations)


@router.post("/campaigns/{campaign_id}/schedule/commit", response_model=SchedulePreview)
async def schedule_commit(campaign_id: str, body: ScheduleIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    await db.execute(update(Campaign).where(Campaign.id == c.id).values(updated_at=datetime.utcnow()))
    blogs, drafts, plans, warnings, reservations = await _schedule_inputs(db, c, body, current_user)
    assigned, remaining, extra, starts_after = _allocate(body, c, drafts, plans, blogs)
    warnings = warnings + extra
    by_ref = {b.id: b for b in blogs}
    for d, (ref, at) in zip(drafts, assigned):
        b = by_ref[ref]
        d.checks = {**(d.checks or {}), 'formatting': PointFormatting.model_validate((c.settings or {}).get('formatting') or {}).model_dump()}
        db.add(PublishJob(
            user_id=_uid(current_user), campaign_id=c.id, draft_id=d.id, blog_ref_id=ref, naver_blog_id=b.blog_id,
            scheduled_at=at, status="queued", open_type=b.open_type or "public", category=b.default_category,
        ))
        # 예약 자리 기록(다른 경로의 간격 예약과 공유)
        db.add(ScheduleMark(user_id=_uid(current_user), blog_id=b.blog_id, scheduled_at=at, title=d.title[:200], source="campaign"))
    c.status = "scheduled"
    c.step = 6
    merged = dict(c.settings or {})
    merged["schedule"] = {"start_date": body.start_date.isoformat(), "days": body.days, "per_day": body.per_day,
                          "blog_ids": [b.id for b in blogs], "mode": body.mode,
                          "start_at": body.start_at.isoformat(timespec="minutes") if body.start_at else None,
                          "every_minutes": body.every_minutes, "start_mode": body.start_mode}
    c.settings = merged
    try:
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"예약 저장 실패(같은 시각이 이미 있을 수 있습니다): {e}")
    # 사진 사전 유니크화
    await job_worker.enqueue(db, "prepare_images", {"campaign_id": c.id}, _uid(current_user), dedupe_key=f"prep:{c.id}")
    await campaign_jobs._bump_stats(job_worker.JobContext(db=db, job=BackgroundJob()), c.id)
    return _preview(drafts, blogs, assigned, remaining, warnings, interval=body.mode == "interval",
                    starts_after=starts_after, reservations=reservations)


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
            # 네이버에서 읽어 온 자리는 남의 예약이다 — 우리 예약을 취소한다고 지우면 안 된다.
            mark = (await db.execute(select(ScheduleMark).where(
                ScheduleMark.user_id == _uid(current_user), ScheduleMark.blog_id == b.blog_id,
                ScheduleMark.scheduled_at == j.scheduled_at, ScheduleMark.source != "naver"))).scalars().first()
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
    await db.commit()                      # 취소는 여기서 확정한다
    # 잡아 둔 자리도 비운다. 안 그러면 취소한 시각이 영영 '찬 자리'로 남아 다음 예약이
    # 그 시간대를 피해 가고, 사용자는 왜 비는지 알 수 없다.
    # 자리 비우기가 실패해도 취소 자체는 유효하다 — 따로 커밋해 서로를 물고 늘어지지 않게 한다.
    try:
        b = await db.get(Blog, j.blog_ref_id)
        if b:
            mark = (await db.execute(select(ScheduleMark).where(
                ScheduleMark.user_id == _uid(current_user), ScheduleMark.blog_id == b.blog_id,
                ScheduleMark.scheduled_at == j.scheduled_at, ScheduleMark.source != "naver"))).scalars().first()
            if mark:
                await db.delete(mark)
                await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
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
    # 발굴로 이미 고른 키워드를 쓸 때(discover_keywords=False)도 대량 발행과 같은 검수·사진 기준을 적용한다.
    strict_quality: bool = False
    quality: PolicyConfig = Field(default_factory=PolicyConfig)


@router.post("/campaigns/{campaign_id}/automation", response_model=TaskOut)
async def start_automation(campaign_id: str, body: AutomationIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    uid = _uid(current_user)
    policy = None
    if body.discover_keywords or body.strict_quality:
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
    if body.discover_keywords or body.strict_quality:
        from app.services.autopilot import preflight
        issues = await preflight(db, campaign, body.quality)
        if issues:
            raise HTTPException(status_code=400, detail={"issues": issues})
        client = await db.get(Client, campaign.client_id)
        # 발굴로 고른 키워드는 그대로 쓴다. 발굴 없이 시작하면 파이프라인이 직접 찾는다(빈 목록).
        payload.update({**body.quality.model_dump(),
                        "keyword_ids": [] if body.discover_keywords else keyword_ids,
                        "strict_quality": True, "auto_schedule": True,
                        "collection_id": campaign.collection_id or client.default_collection_id})
        campaign.settings = {**(campaign.settings or {}), "landing": body.quality.model_dump()}
        if policy:
            policy.config = body.quality.model_dump()
    job = BackgroundJob(user_id=uid, type="automation_pipeline", status="pending",
                        payload=payload,
                        result={"requested": len(keyword_ids) or body.max_keywords} if (body.discover_keywords or body.strict_quality) else None,
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
    """발행 실행기로 보내는 블록 하나.

    `content` 는 항상 채운다 — 서식을 모르는 옛 실행기(rich_text_v1 능력 없음)에는
    서식 필드를 떼고 이것만 보낸다. 규격은 services/docx_import.py 참고.
    """
    type: str
    content: Optional[str] = None
    image: Optional[str] = None
    spans: Optional[List[Dict[str, Any]]] = None      # text/heading/quote
    level: Optional[int] = None                        # heading
    ordered: Optional[bool] = None                     # list
    items: Optional[List[List[Dict[str, Any]]]] = None  # list
    header: Optional[bool] = None                      # table
    rows: Optional[List[List[List[Dict[str, Any]]]]] = None  # table


class ClaimedJob(BaseModel):
    id: str
    lock_token: str
    title: str
    content: str
    # JobBlock 을 빈 필드 없이 편 것. 블록마다 null 8개를 실어 보내지 않으려고 dict 로 둔다.
    blocks: List[Dict[str, Any]]
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


async def _doc_blocks(db: AsyncSession, draft: Draft, include_images: bool) -> List[JobBlock]:
    """워드에서 올라온 원고 — 글쓴이가 잡아 둔 순서·서식 그대로. 사진은 풀에서 꺼내 실어 보낸다."""
    out: List[JobBlock] = []
    for block in draft.blocks or []:
        if block.get("type") == "image":
            if not include_images:
                continue
            image = await db.get(PoolImage, block.get("pool_image_id") or "")
            if not image or not image.data:
                raise ValueError("문서 안 사진을 찾지 못했습니다. 원고를 다시 올려 주세요")
            out.append(JobBlock(type="image", content="",
                                image=f"data:{image.content_type or 'image/jpeg'};base64,"
                                      + base64.b64encode(image.data).decode()))
            continue
        out.append(JobBlock(**{k: v for k, v in block.items() if k in JobBlock.model_fields}))
    return out


async def _assemble_blocks(db: AsyncSession, draft: Draft, variants: List[Dict[str, Any]], include_images: bool) -> List[JobBlock]:
    if draft.blocks:
        return await _doc_blocks(db, draft, include_images)
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


def _with_footer(blocks: List[JobBlock], b: Blog) -> List[JobBlock]:
    """이 아이디에 저장해 둔 링크·플레이스를 글 끝에 붙인다.

    주소를 한 줄로 두면 네이버가 알아서 링크 카드(플레이스면 지도 카드)로 만든다.
    원고 안에 이미 그 주소가 있으면 두 번 넣지 않는다."""
    body = "\n".join(x.content or "" for x in blocks)
    out = list(blocks)
    for label, url in ((b.footer_link_label, b.footer_link_url), (b.place_label, b.place_url)):
        if not url or url in body:
            continue
        if (label or "").strip():
            out.append(JobBlock(type="text", content=label.strip()))
        out.append(JobBlock(type="text", content=url))
    return out


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
        point_settings = (candidate_draft.checks or {}).get('formatting', {}) if candidate_draft else {}
        if point_settings.get('enabled') and 'point_styles_v1' not in body.capabilities:
            raise HTTPException(status_code=426, detail='중요 포인트 서식을 지원하는 최신 실행기로 업데이트하세요')
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
            blocks = await _assemble_blocks(db, draft, j.image_variants or [], body.include_images)
            if body.include_images and draft.image_plan and sum(b.type == "image" for b in blocks) != len(draft.image_plan):
                raise ValueError("필수 이미지가 누락되었습니다")
            if 'point_styles_v1' in body.capabilities:
                blocks = [JobBlock(**b) for b in apply_points(
                    [b.model_dump(exclude_none=True) for b in blocks], point_settings,
                    [draft.keyword or '', *(draft.emphasize or [])])]
            # 저장해 둔 링크·플레이스는 강조를 입힌 뒤에 붙인다 — 적어 둔 그대로 나가야 한다.
            blocks = _with_footer(blocks, blog)
            if "rich_text_v1" not in body.capabilities and 'point_styles_v1' not in body.capabilities:
                # 서식을 모르는 실행기 — 굵게·표·목록을 평문으로 눌러서 보낸다(사진은 그대로).
                blocks = [JobBlock(**b) for b in
                          docx_import.flatten_blocks([b.model_dump(exclude_none=True) for b in blocks])]
            payload = ClaimedJob(
                id=j.id, lock_token=token, title=draft.title,
                content="\n\n".join(b.content for b in blocks if b.type != "image" and b.content),
                blocks=[b.model_dump(exclude_none=True) for b in blocks],
                tags=(draft.tags or [])[:10], emphasize=draft.emphasize or [],
                schedule={"datetime": j.scheduled_at.isoformat(timespec="minutes") + "+09:00"},
                options={"openType": j.open_type or "public", "search": True, "category": j.category,
                         # 워드 원고는 글쓴이가 잡아 둔 줄바꿈이 곧 원고다. 실행기의 모바일 재정렬을 끈다.
                         "reformat": not draft.blocks,
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
    # 예약 목록을 다시 읽어야 하는가(웹에서 [새로 읽기]를 눌렀거나 읽은 지 오래됨)
    wants_scan: bool = True
    reservations_scanned_at: Optional[str] = None


@router.get("/agent/summary", response_model=List[AgentBlogSummary])
async def agent_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    blogs = (await db.execute(select(Blog).where(Blog.user_id == _uid(current_user)).order_by(Blog.created_at))).scalars().all()
    out = []
    for b in blogs:
        rows = (await db.execute(select(PublishJob.scheduled_at).where(PublishJob.blog_ref_id == b.id, PublishJob.status.in_(["queued", "assigned", "failed"])).order_by(PublishJob.scheduled_at.asc()))).all()
        scanned = b.reservations_scanned_at
        stale = not scanned or (datetime.utcnow() - scanned) > timedelta(hours=RESERVATION_STALE_HOURS)
        # 한 번 못 읽은 블로그는 계속 못 읽는다(주소를 모르는 것이지 일시적인 실패가 아니다).
        # 매 주기 헛되이 두드리면 그만큼 발행이 늦어진다 — 사용자가 [새로 읽기]를 누를 때만 다시 청한다.
        give_up = bool(b.reservations_note) and not b.reservations_scan_requested_at
        out.append(AgentBlogSummary(blog_ref_id=b.id, naver_blog_id=b.blog_id, label=b.label or b.blog_id, status=b.status or "active", status_reason=b.status_reason,
                                    pending=len(rows), next_at=rows[0][0].isoformat(timespec="minutes") if rows else None, login_id=b.login_id,
                                    wants_scan=bool(b.reservations_scan_requested_at or (stale and not give_up)),
                                    reservations_scanned_at=scanned.isoformat(timespec="minutes") if scanned else None))
    return out


# ───────────────── 네이버에 이미 걸린 예약(실행기가 읽어 온 목록) ─────────────────
# 예약 목록은 로그인한 브라우저 안에만 있다. 서버가 직접 볼 방법이 없어 실행기가 읽어다 준다.
# 받은 목록은 '덧붙이는 기록'이 아니라 '그 시점의 진실 전체'다 — 통째로 갈아 끼워야
# 네이버에서 지운 예약이 유령 자리로 남지 않는다.

class ReservationItem(BaseModel):
    at: datetime                          # 네이버 화면에 적힌 그대로의 시각(KST naive)
    title: Optional[str] = None


class ReservationsIn(BaseModel):
    ok: bool = True                       # False = 목록을 못 읽음. 장부는 손대지 않는다
    note: Optional[str] = None            # 못 읽은 사유(화면 변경·로그인 등)
    items: List[ReservationItem] = []


@router.post("/agent/blogs/{blog_ref_id}/reservations")
async def agent_reservations(blog_ref_id: str, body: ReservationsIn,
                             current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """이 블로그의 네이버 예약 목록 스냅샷. 미래의 'naver' 자리를 통째로 교체한다."""
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    b.reservations_scan_requested_at = None          # 요청은 소화했다(성공이든 실패든)
    if not body.ok:
        b.reservations_note = (body.note or "예약 목록을 읽지 못했습니다")[:300]
        await db.commit()
        return {"ok": False, "saved": 0}

    now = se.kst_now()
    slots = {se.floor_slot(i.at): (i.title or "")[:200] or None for i in body.items if i.at > now}
    uid = _uid(current_user)
    await db.execute(delete(ScheduleMark).where(
        ScheduleMark.user_id == uid, ScheduleMark.blog_id == b.blog_id,
        ScheduleMark.scheduled_at > now, ScheduleMark.source == "naver",
    ))
    # 우리가 걸어 둔 자리(source='campaign' 등)는 건드리지 않는다. 같은 시각이면 이미 같은 자리다.
    kept = {r for (r,) in (await db.execute(select(ScheduleMark.scheduled_at).where(
        ScheduleMark.user_id == uid, ScheduleMark.blog_id == b.blog_id,
        ScheduleMark.scheduled_at.in_(list(slots) or [now]),
    ))).all()}
    for at, title in slots.items():
        if at in kept:
            continue
        db.add(ScheduleMark(user_id=uid, blog_id=b.blog_id, scheduled_at=at, title=title, source="naver"))
    b.reservations_scanned_at = datetime.utcnow()
    b.reservations_note = None
    await db.commit()
    return {"ok": True, "saved": len(slots)}


class RescheduleIn(BaseModel):
    lock_token: str = Field(min_length=1, max_length=64)
    reason: Optional[str] = None
    taken_at: List[datetime] = []         # 실행기가 현장에서 본 예약 시각(즉시 장부에 반영)


@router.post("/agent/jobs/{job_id}/reschedule")
async def agent_reschedule(job_id: str, body: RescheduleIn,
                           current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """발행 직전 그 자리가 이미 차 있었다 → 올리지 말고 다음 빈 자리로 옮긴다.

    서버의 장부는 언제나 몇 분 과거다. 마지막 한 겹은 현장에서 본 것으로 막는다."""
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    uid = _uid(current_user)
    b = await db.get(Blog, j.blog_ref_id)
    if not b or b.user_id != uid:
        raise HTTPException(status_code=404, detail="블로그를 찾을 수 없습니다")
    # 1) 잠금을 먼저 푼다(queued 로 되돌아가고 시도 횟수는 늘지 않는다)
    try:
        await protocol.result(db, job_id, uid, body.lock_token,
                              {"ok": False, "release": True, "uncertain": False,
                               "message": (body.reason or "그 시각에 이미 예약된 글이 있어 옮깁니다")[:500],
                               "url": None, "need_login": False, "captcha": False, "receipt_id": None})
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # 2) 현장에서 본 자리를 장부에 남긴다(다음 배정도 이 자리를 피한다)
    now = se.kst_now()
    for raw in body.taken_at:
        at = se.floor_slot(raw)
        if at <= now:
            continue
        db.add(ScheduleMark(user_id=uid, blog_id=b.blog_id, scheduled_at=at, title=None, source="naver"))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()                      # 이미 아는 자리
    # 3) 다음 빈 자리로 옮긴다
    plan = se.blog_plan_from_model(b)
    await se.load_taken_slots(db, uid, [plan])
    # 원래 자리는 남겨 둔다 — 그 칸이 차 있어서 옮기는 것이므로 그 앞뒤로도 완충을 둬야 한다.
    gap = max(se.SLOT_MINUTES, plan.min_gap_minutes or 120)
    moved, _ = se.allocate_interval(1, [plan], j.scheduled_at + timedelta(minutes=se.SLOT_MINUTES), gap, days=60)
    if not moved:
        j.error = "옮길 빈 자리를 찾지 못했습니다. 예약 간격을 다시 잡아 주세요"
        await db.commit()
        raise HTTPException(status_code=409, detail=j.error)
    old, new_at = j.scheduled_at, moved[0][1]
    await db.execute(delete(ScheduleMark).where(
        ScheduleMark.user_id == uid, ScheduleMark.blog_id == b.blog_id,
        ScheduleMark.scheduled_at == old, ScheduleMark.source != "naver"))
    draft = await db.get(Draft, j.draft_id)
    db.add(ScheduleMark(user_id=uid, blog_id=b.blog_id, scheduled_at=new_at,
                        title=((draft.title if draft else "") or "")[:200] or None, source="campaign"))
    j.scheduled_at = new_at
    j.error = f"{old.strftime('%m/%d %H:%M')} 자리가 이미 차 있어 {new_at.strftime('%m/%d %H:%M')}으로 옮겼습니다"
    await db.commit()
    return {"ok": True, "scheduled_at": new_at.isoformat(timespec="minutes"), "was": old.isoformat(timespec="minutes")}


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
    # 켜져 있다고 신호는 보내는데 정작 발행을 한 번도 청하지 않는 상태.
    # 실행기 안에서 신호를 보내는 쪽과 글을 올리는 쪽이 따로 돌기 때문에 생긴다
    # (2026-09-23 실측: 토큰이 죽은 채 60초마다 헛돌고 초록불만 켜져 있었다).
    stalled: bool = False
    stalled_hint: Optional[str] = None


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


# 대기 중인 글이 이만큼 오래 그대로면 실행기가 '켜져 있기만 한' 것으로 본다.
STALL_MINUTES = 12


async def _stalled(db: AsyncSession, user_id: str) -> bool:
    """올릴 글이 밀려 있는데 실행기가 한참째 아무것도 청하지 않았는가."""
    now = datetime.utcnow()
    oldest = (await db.execute(select(func.min(PublishJob.created_at)).where(
        PublishJob.user_id == user_id, PublishJob.status == "queued"))).scalar()
    if not oldest or (now - oldest) < timedelta(minutes=STALL_MINUTES):
        return False
    last_try = (await db.execute(select(func.max(PublishAttempt.created_at)).where(
        PublishAttempt.user_id == user_id))).scalar()
    return not last_try or (now - last_try) > timedelta(minutes=STALL_MINUTES)


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
    running = any(d.running for d in live)
    try:
        stalled = bool(live and running) and await _stalled(db, user_id)
    except Exception:  # noqa: BLE001  신호등이 곁다리 질의 때문에 꺼지면 안 된다
        stalled = False
    return AgentStatusOut(
        online=bool(live), running=running,
        version=live[0].version if live else None, devices=devices[:5],
        stalled=stalled,
        stalled_hint=("실행기가 켜져 있다고는 하는데 올릴 글을 한참째 가져가지 않습니다. "
                      "실행기 창에서 [실행 중단]을 누른 뒤 [자동 발행 시작]을 다시 눌러 주세요.") if stalled else None)


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
    # 실행기가 만료 전에 미리 새로 받도록 남은 시간을 알려 준다. 모르면 만료된 뒤 401 을 보고서야 다시 받는다.
    expires_in: int = 0


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
    # 토큰 자체는 짧게 유지한다 — 홈페이지에서 연결을 끊으면 그만큼 빨리 먹통이 되어야 한다.
    # 대신 남은 시간을 알려 주어 실행기가 만료 전에 조용히 갈아끼운다.
    return DeviceTokenOut(access_token=create_access_token(subject=device.user_id),
                          email=await _user_email(db, device.user_id),
                          expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


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


@router.get("/agent/blogs/{blog_ref_id}/proxy")
async def agent_proxy(blog_ref_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """실행기가 브라우저를 띄우기 직전에 묻는다. 이 블로그 전용 고정 프록시(없으면 null)."""
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    return {"proxy": crypto.decrypt(b.proxy_enc) if b.proxy_enc else None}


@router.get("/agent/blogs/{blog_ref_id}/credential")
async def agent_credential(blog_ref_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """에이전트 자동 로그인용. 앱 화면에서는 쓰지 않는다."""
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    return {"login_id": b.login_id, "login_pw": crypto.decrypt(b.login_pw_enc), "naver_blog_id": b.blog_id}
