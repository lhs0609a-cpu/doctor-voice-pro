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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import User
from app.models.background_job import BackgroundJob
from app.models.campaign import (
    JOB_ACTIVE, Blog, BriefPreset, Campaign, CampaignKeyword, Client, Draft, PublishJob, SerpSnapshot,
)
from app.models.media_pool import ImageVariant, PoolCollection, PoolCollectionMember, PoolImage
from app.models.publish_queue import ScheduleMark
from app.services import campaign_crypto as crypto
from app.services import campaign_jobs
from app.services import campaign_writer as writer
from app.services import image_uniquifier as uniq
from app.services import job_worker
from app.services import schedule_engine as se

router = APIRouter()


def _uid(user: User) -> str:
    return str(user.id)


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


@router.post("/clients/{client_id}/blogs", response_model=BlogOut)
async def add_blog(client_id: str, body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _owned(db, Client, client_id, current_user, "병원")
    b = Blog(
        user_id=_uid(current_user), client_id=client_id, blog_id=body.blog_id.strip(), label=body.label,
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
    b.blog_id = body.blog_id.strip()
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
    jobs = (await db.execute(select(PublishJob).where(PublishJob.campaign_id == c.id, PublishJob.status.in_(["queued", "assigned", "failed", "uncertain"])))).scalars().all()
    n = 0
    for j in jobs:
        j.status = "cancelled"
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
    c = await _owned(db, Campaign, campaign_id, current_user, "캠페인")
    jobs = (await db.execute(select(PublishJob).where(PublishJob.campaign_id == c.id).order_by(PublishJob.scheduled_at.asc()))).scalars().all()
    return await _jobs_out(db, jobs)


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.status not in ("failed", "uncertain", "cancelled"):
        raise HTTPException(status_code=400, detail="실패·확인필요·취소 상태만 다시 시도할 수 있습니다")
    j.status, j.error, j.lock_token, j.lock_expires_at = "queued", None, None, None
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.status in ("published", "publishing"):
        raise HTTPException(status_code=400, detail="발행됐거나 발행 중인 건은 취소할 수 없습니다")
    j.status = "cancelled"
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


class MarkPublishedIn(BaseModel):
    result_url: Optional[str] = None


@router.post("/jobs/{job_id}/mark-published", response_model=JobOut)
async def mark_published(job_id: str, body: MarkPublishedIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """'확인 필요' 건을 사람이 네이버에서 확인한 뒤 발행됨으로 표시."""
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    j.status, j.result_url, j.published_at = "published", body.result_url, datetime.utcnow()
    await db.commit()
    return (await _jobs_out(db, [j]))[0]


# ======================================================================
# 발행 실행기(확장/에이전트) API
# ======================================================================
class ClaimIn(BaseModel):
    blog_ref_id: Optional[str] = None      # 특정 블로그 것만
    naver_blog_id: Optional[str] = None    # 확장이 현재 로그인된 블로그로 필터할 때
    limit: int = 10
    include_images: bool = True


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
    """발행 실행기가 대기 잡을 가져간다. queued/assigned(잠금 만료) → assigned + lock.
    사진이 아직 준비 안 된 건은 즉석에서 유니크화한다(느리지만 안전)."""
    now = datetime.utcnow()
    q = select(PublishJob).where(
        PublishJob.user_id == _uid(current_user),
        PublishJob.status.in_(["queued", "assigned", "failed"]),
    )
    if body.blog_ref_id:
        q = q.where(PublishJob.blog_ref_id == body.blog_ref_id)
    if body.naver_blog_id:
        q = q.where(PublishJob.naver_blog_id == body.naver_blog_id)
    rows = (await db.execute(q.order_by(PublishJob.scheduled_at.asc()).limit(body.limit * 3))).scalars().all()

    blogs = {b.id: b for b in (await db.execute(select(Blog).where(Blog.user_id == _uid(current_user)))).scalars().all()}
    claimed: List[ClaimedJob] = []
    kst_now = se.kst_now()
    for j in rows:
        if len(claimed) >= body.limit:
            break
        if j.status == "assigned" and j.lock_expires_at and j.lock_expires_at > now:
            continue  # 다른 실행기가 잡고 있음
        if j.status == "failed" and (j.next_retry_at is None or j.next_retry_at > now):
            continue
        b = blogs.get(j.blog_ref_id)
        if not b or b.status != "active":
            continue
        if j.scheduled_at <= kst_now + timedelta(minutes=15):
            # 예약 시각이 임박/경과 → 네이버가 '지금'으로 처리할 위험. 실패 처리하고 사람이 재배정하게 한다.
            j.status, j.error = "failed", "예약 시각이 지나 발행하지 못했습니다. 다시 시도하면 새 시각으로 배정하세요."
            j.next_retry_at = None
            continue
        draft = await db.get(Draft, j.draft_id)
        if not draft:
            j.status, j.error = "failed", "원고가 삭제되었습니다"
            continue
        # 변형 파일이 사라졌으면(재배포·볼륨 교체) 다시 만든다 — 사진 없이 나가는 사고 방지
        if j.images_ready and any(not Path(v.get("path", "")).exists() for v in (j.image_variants or [])):
            j.images_ready = False
        if body.include_images and not j.images_ready and (draft.image_plan or []):
            try:
                j.image_variants = await campaign_jobs.prepare_job_images(db, j, draft)
                j.images_ready = True
            except Exception as e:  # noqa: BLE001
                j.error = f"사진 준비 실패: {e}"[:500]
                j.status = "failed"
                j.next_retry_at = now + timedelta(minutes=10)
                continue
        token = secrets.token_hex(16)
        j.status, j.lock_token = "assigned", token
        j.lock_expires_at = now + timedelta(minutes=settings.PUBLISH_LOCK_MINUTES)
        blocks = _assemble_blocks(draft, j.image_variants or [], body.include_images)
        content = "\n\n".join(bk.content for bk in blocks if bk.type == "text" and bk.content)
        claimed.append(ClaimedJob(
            id=j.id, lock_token=token, title=draft.title, content=content, blocks=blocks,
            tags=(draft.tags or [])[:10], emphasize=draft.emphasize or ([draft.keyword] if draft.keyword else []),
            finalAction="schedule", schedule={"datetime": j.scheduled_at.isoformat(timespec="minutes")},
            options={"openType": j.open_type or "public", "search": True, "category": j.category or None},
            expectedBlogId=j.naver_blog_id, blog_ref_id=j.blog_ref_id, draft_id=j.draft_id,
        ))
    await db.commit()
    return claimed


class ResultIn(BaseModel):
    lock_token: Optional[str] = None
    ok: bool
    uncertain: bool = False
    message: Optional[str] = None
    url: Optional[str] = None
    need_login: bool = False
    captcha: bool = False
    release: bool = False       # 실행기가 시작도 못 했을 때(확장 미연결 등): 시도 횟수 없이 대기로 되돌림


@router.post("/agent/jobs/{job_id}/result")
async def agent_result(job_id: str, body: ResultIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = await _owned(db, PublishJob, job_id, current_user, "발행건")
    if j.lock_token and body.lock_token and j.lock_token != body.lock_token:
        raise HTTPException(status_code=409, detail="다른 실행기가 잡은 건입니다(잠금 불일치)")
    now = datetime.utcnow()
    j.lock_token, j.lock_expires_at = None, None
    b = await db.get(Blog, j.blog_ref_id)
    if body.release and not body.ok:
        j.status, j.next_retry_at = "queued", None
        j.error = body.message or None
        await db.commit()
        return {"success": True, "status": j.status}
    j.attempts = (j.attempts or 0) + 1
    if body.ok and not body.uncertain:
        j.status, j.result_url, j.published_at, j.error = "published", body.url, now, None
        if b:
            b.last_published_at = now
    elif body.uncertain:
        j.status, j.error = "uncertain", body.message or "시간 초과: 네이버 예약 목록에서 확인이 필요합니다"
    else:
        j.error = body.message or "발행 실패"
        if body.captcha or body.need_login:
            j.status, j.next_retry_at = "queued", None
            if b:
                b.status = "captcha" if body.captcha else "login_required"
                b.status_reason = body.message or ("네이버가 캡차를 요구했습니다. 크롬에서 한 번 풀어주면 이어서 합니다." if body.captcha else "로그인이 풀렸습니다. 크롬에서 다시 로그인하세요.")
                b.status_changed_at = now
        elif j.attempts < (j.max_attempts or 3):
            j.status, j.next_retry_at = "failed", now + timedelta(minutes=10 * j.attempts)
        else:
            j.status, j.next_retry_at = "failed", None
    await db.commit()
    await campaign_jobs._bump_stats(job_worker.JobContext(db=db, job=BackgroundJob()), j.campaign_id)
    return {"success": True, "status": j.status}


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


@router.get("/agent/blogs/{blog_ref_id}/credential")
async def agent_credential(blog_ref_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """에이전트 자동 로그인용. 앱 화면에서는 쓰지 않는다."""
    b = await _owned(db, Blog, blog_ref_id, current_user, "블로그")
    return {"login_id": b.login_id, "login_pw": crypto.decrypt(b.login_pw_enc), "naver_blog_id": b.blog_id}
