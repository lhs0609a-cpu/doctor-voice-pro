"""
블로그 지수 / 상위노출 가능성 API  (prefix /api/v1/blog-index)

빠른 것은 동기, 무거운 것(판정·천장·색인검증·경쟁도)은 워커 작업으로 만들고
/campaign/tasks/{id} 로 폴링한다(같은 BackgroundJob 테이블).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.campaign import TaskOut, _task_out
from app.api.deps import get_current_user, get_db
from app.blogindex import (
    DISCLAIMER_CEILING, DISCLAIMER_INDEX, DISCLAIMER_VERDICT, SCORING_VERSION,
    normalize_blog_id, normalize_keyword,
)
from app.models import User
from app.models.blog_index import BlogIndexSnapshot, CeilingCache, VerdictResult
from app.services import job_worker
from app.services.blog_index_jobs import summarize_verdict

router = APIRouter()


def _uid(user: User) -> str:
    return str(user.id)


# ───────────────────────── 블로그 지수 ─────────────────────────
class AnalyzeIn(BaseModel):
    blog_id: str
    keyword: Optional[str] = None
    fullparse: bool = True
    refresh: bool = False
    verify_index: bool = False
    background: bool = False        # True 면 워커 작업으로 만들고 TaskOut 반환


@router.post("/analyze")
async def analyze(body: AnalyzeIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    blog_id = normalize_blog_id(body.blog_id)
    if not blog_id:
        raise HTTPException(status_code=400, detail="블로그 ID 를 입력하세요")
    if body.background or body.verify_index:
        job = await job_worker.enqueue(db, "blog_analyze", body.model_dump() | {"blog_id": blog_id}, _uid(current_user))
        return {"task": _task_out(job).model_dump()}
    from app.blogindex import analyzer
    res = await analyzer.analyze_blog(db, blog_id, keyword=body.keyword, fullparse=body.fullparse, use_cache=not body.refresh)
    res.setdefault("disclaimer", DISCLAIMER_INDEX)
    # 병원 관리 블로그 계정에 기록
    if res.get("success"):
        from app.models.campaign import Blog
        idx = res.get("index") or {}
        for b in (await db.execute(select(Blog).where(Blog.user_id == _uid(current_user), Blog.blog_id == blog_id))).scalars().all():
            b.index_score, b.index_level, b.index_grade, b.index_at = idx.get("total_score"), idx.get("level"), idx.get("grade"), datetime.utcnow()
        await db.commit()
    return res


@router.get("/{blog_id}/index")
async def latest_index(blog_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.blogindex import analyzer
    bid = await analyzer.canonicalize(blog_id)   # 로그인 ID 로 조회해도 실제 블로그 주소의 최신 스냅샷을 준다
    snap = (await db.execute(
        select(BlogIndexSnapshot).where(BlogIndexSnapshot.blog_id == bid, BlogIndexSnapshot.scoring_version == SCORING_VERSION)
        .order_by(BlogIndexSnapshot.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="아직 분석한 적이 없습니다")
    return {**(snap.result or {}), "snapshot_at": snap.created_at, "disclaimer": DISCLAIMER_INDEX}


@router.get("/{blog_id}/history")
async def index_history(blog_id: str, limit: int = 60, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """시계열(같은 버전 + measurement_complete 만: 문서 2-4)."""
    from app.blogindex import analyzer
    bid = await analyzer.canonicalize(blog_id)
    rows = (await db.execute(
        select(BlogIndexSnapshot).where(BlogIndexSnapshot.blog_id == bid, BlogIndexSnapshot.scoring_version == SCORING_VERSION, BlogIndexSnapshot.measurement_complete == True)  # noqa: E712
        .order_by(BlogIndexSnapshot.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{"at": r.created_at, "score": r.total_score, "level": r.level, "grade": r.grade} for r in reversed(rows)]


# ───────────────────────── 상위노출 판정 v2 ─────────────────────────
class VerdictIn(BaseModel):
    blog_id: str
    keyword: str


class VerdictBatchIn(BaseModel):
    blog_id: str
    keywords: List[str]
    campaign_id: Optional[str] = None


@router.post("/verdict/facts")
async def verdict_facts(body: VerdictIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """STAGE 1: 반박 불가능한 사실(내 순위·1페이지 점유자·검색량). 3~8초."""
    from app.blogindex import analyzer, keyword_verdict
    return await keyword_verdict.stage1_facts(db, await analyzer.canonicalize(body.blog_id), body.keyword.strip())


@router.post("/verdict", response_model=TaskOut)
async def verdict(body: VerdictIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await job_worker.enqueue(db, "blog_verdict", {"blog_id": normalize_blog_id(body.blog_id), "keyword": body.keyword.strip()}, _uid(current_user))
    return _task_out(job)


@router.post("/verdict/batch", response_model=TaskOut)
async def verdict_batch(body: VerdictBatchIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    kws = [k.strip() for k in body.keywords if k and k.strip()]
    if not kws:
        raise HTTPException(status_code=400, detail="키워드가 없습니다")
    bid = normalize_blog_id(body.blog_id)
    job = await job_worker.enqueue(
        db, "blog_verdict_batch", {"blog_id": bid, "keywords": kws[:60], "campaign_id": body.campaign_id},
        _uid(current_user), dedupe_key=f"verdict:{_uid(current_user)}:{bid}:{body.campaign_id or 'adhoc'}", total=len(kws) + 1,
    )
    return _task_out(job)


class PrewarmIn(BaseModel):
    keywords: List[str]


@router.post("/prewarm", response_model=TaskOut)
async def prewarm(body: PrewarmIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """키워드들의 경쟁 블로그를 미리 채점(블로그 무관). 화면은 결과를 기다리지 않는다."""
    kws = [k.strip() for k in body.keywords if k and k.strip()][:40]
    if not kws:
        raise HTTPException(status_code=400, detail="키워드가 없습니다")
    key = "prewarm:" + ",".join(sorted(normalize_keyword(k) for k in kws))[:180]
    job = await job_worker.enqueue(db, "blog_prewarm", {"keywords": kws}, _uid(current_user), dedupe_key=key, max_attempts=1)
    return _task_out(job)


@router.get("/verdict/latest")
async def verdict_latest(blog_id: str, keywords: str = "", hours: int = 24, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """최근 판정 결과(화면 새로고침 복구용)."""
    from app.blogindex import analyzer
    bid = await analyzer.canonicalize(blog_id)
    wanted = {normalize_keyword(k) for k in keywords.split(",") if k.strip()}
    q = select(VerdictResult).where(VerdictResult.blog_id == bid, VerdictResult.created_at >= datetime.utcnow() - timedelta(hours=hours))
    if wanted:
        q = q.where(VerdictResult.keyword_norm.in_(list(wanted)))
    rows = (await db.execute(q.order_by(VerdictResult.created_at.desc()).limit(200))).scalars().all()
    out: Dict[str, Any] = {}
    for r in rows:
        if r.keyword_norm in out:
            continue
        out[r.keyword_norm] = {**summarize_verdict({**(r.result or {}), "keyword": r.keyword}), "at": r.created_at}
    return {"blog_id": bid, "items": list(out.values())}


# ───────────────────────── 보조 지표 ─────────────────────────
class BlogIn(BaseModel):
    blog_id: str
    refresh: bool = False


@router.get("/exposure-ceiling")
async def get_ceiling(blog_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(CeilingCache, normalize_blog_id(blog_id))
    if not row:
        raise HTTPException(status_code=404, detail="아직 측정하지 않았습니다. POST /exposure-ceiling 으로 측정 작업을 만드세요.")
    return {**(row.result or {}), "measured_at": row.measured_at, "disclaimer": DISCLAIMER_CEILING}


@router.post("/exposure-ceiling", response_model=TaskOut)
async def measure_ceiling(body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bid = normalize_blog_id(body.blog_id)
    job = await job_worker.enqueue(db, "blog_ceiling", {"blog_id": bid, "refresh": body.refresh}, _uid(current_user), dedupe_key=f"ceiling:{bid}")
    return _task_out(job)


@router.get("/serp-difficulty")
async def serp_difficulty(keyword: str, top_n: int = 10, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.blogindex import serp_difficulty as sd
    return await sd.serp_difficulty(db, keyword.strip(), top_n=top_n)


class JudgeIn(BaseModel):
    blog_id: str
    keyword: str
    include_serp: bool = True


@router.post("/judge-keyword")
async def judge_keyword_v1(body: JudgeIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """v1 판정(천장 대비 수요). 천장은 캐시가 있을 때만 쓴다(10-8)."""
    from app.blogindex import judge_v1, serp_difficulty as sd
    from app.services import search_volume_service as svs
    bid = normalize_blog_id(body.blog_id)
    row = await db.get(CeilingCache, bid)
    ceiling = (row.result if row else None) or {"ok": False}
    vol = 0
    try:
        m = await svs.get_keyword_metrics(db, [body.keyword])
        vol = m[0]["total_volume"] if m else 0
    except Exception:  # noqa: BLE001
        pass
    serp = await sd.serp_difficulty(db, body.keyword.strip()) if body.include_serp else None
    res = judge_v1.judge_keyword(ceiling, vol, serp)
    return {**res, "keyword": body.keyword, "blog_id": bid, "volume": vol, "ceiling": ceiling, "serp": serp}


@router.post("/verify-index", response_model=TaskOut)
async def verify_index(body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bid = normalize_blog_id(body.blog_id)
    job = await job_worker.enqueue(db, "blog_verify_index", {"blog_id": bid}, _uid(current_user), dedupe_key=f"verify:{bid}")
    return _task_out(job)


class CompetitionIn(BaseModel):
    keyword: str
    my_blog_id: Optional[str] = None


@router.post("/competition", response_model=TaskOut)
async def competition(body: CompetitionIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await job_worker.enqueue(db, "blog_competition", {"keyword": body.keyword.strip(), "my_blog_id": body.my_blog_id}, _uid(current_user))
    return _task_out(job)


@router.post("/post-exposure", response_model=TaskOut)
async def post_exposure(body: BlogIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bid = normalize_blog_id(body.blog_id)
    job = await job_worker.enqueue(db, "blog_post_exposure", {"blog_id": bid}, _uid(current_user), dedupe_key=f"postexp:{bid}")
    return _task_out(job)


@router.get("/config")
async def config_status(current_user: User = Depends(get_current_user)):
    from app.core.config import settings
    from app.services import search_volume_service as svs
    return {
        "search_ad": svs.is_configured(),
        "openapi": bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET),
        "scoring_version": SCORING_VERSION,
        "disclaimers": {"index": DISCLAIMER_INDEX, "ceiling": DISCLAIMER_CEILING, "verdict": DISCLAIMER_VERDICT},
    }
