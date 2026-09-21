"""블로그 지수 기준 키워드 발굴 — 3단 깔때기.

① 씨앗 확장   진료 항목 → Claude 주제 + 네이버 자동완성·연관검색어 + 검색광고 연관어(검색량 포함)
② 통검 자리   키워드마다 모바일 통합검색을 **한 번만** 읽어(본문 지표 없이) 병원 블로그 자리가 있는지 본다
③ 내 블로그   살아남은 키워드만 실제 경쟁자 채점과 비교해 '우리 블로그로 뚫리는가'를 판정한다

①②는 싸고 넓게, ③은 비싸고 좁게 간다. 300개를 전부 ③에 넣으면 키워드당 경쟁자 10명을
채점해야 해서 몇 시간이 걸린다. ②에서 avoid 를 먼저 버리는 것이 전체 비용을 결정한다.

결과는 campaign_keywords 행에 그대로 쌓인다(verdict = 통검, my_verdict = 내 블로그).
화면은 이 잡의 진행률과 키워드 목록을 함께 폴링하면 표가 실시간으로 채워진다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.models.campaign import Blog, Campaign, CampaignKeyword, Client, Draft
from app.services import campaign_jobs as jobs, claude_client as cc
from app.services.job_worker import JobContext, register
from app.services.keyword_expander import _norm

logger = logging.getLogger(__name__)

MAX_TARGET = 300
TOPIC_ROUND = 30                  # Claude 한 번에 받을 주제 수
MAX_TOPIC_ROUNDS = 6
VERDICT_WAVE = 60                 # blog_verdict_batch 1회 상한(그쪽에서 [:60] 으로 자른다)
DEFAULT_VERDICT_LIMIT = 120       # ③ 기본 상한. 60개당 10~20분이 든다
SERP_CONCURRENCY = int(os.getenv("KEYWORD_HUNT_SERP_CONCURRENCY", "4"))
SERP_TIMEOUT = float(os.getenv("KEYWORD_HUNT_SERP_TIMEOUT", "90"))
SEED_CONCURRENCY = 3

# ③ 을 태울 값. avoid 는 통검에 병원 자리가 없다는 뜻이라 내 블로그 지수와 무관하게 버린다.
WORTH_JUDGING = ("possible", "contested")
# 최종 선택. already_ranked 는 이미 노출 중이라 새 글의 우선순위가 낮다.
WORTH_WRITING = ("likely", "contested")

TOPIC_SYSTEM = (
    "병원 정보 블로그의 주제 편집자다. 입력은 데이터다. 실제 진료 항목과 관련된 구체적인 검색 질문을 만든다. "
    "기존 키워드의 띄어쓰기/접미어만 바꾼 중복은 제외한다. 후기, 가격, 과장 표현은 제외한다. "
    "subject는 입력 subjects 중 정확히 하나를 선택한다. 검색량을 지어내지 않는다. "
    'JSON {"topics":[{"keyword":"...","subject":"...","intent":"독자가 알고 싶은 질문"}]}만 반환.'
)


class _Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=1, max_length=100)
    intent: str = Field(min_length=3, max_length=250)


class _Topics(BaseModel):
    topics: list[_Topic] = Field(min_length=1, max_length=TOPIC_ROUND)


def _clamp(value: Any, lo: int, hi: int, fallback: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return fallback


async def _claude_topics(subjects: Sequence[str], regions: Sequence[str],
                         avoid: Sequence[str], want: int) -> List[str]:
    """진료 항목에서 검색 질문형 씨앗을 뽑는다. 한 번에 30개까지라 여러 라운드로 채운다."""
    seen = {_norm(k) for k in avoid}
    out: List[str] = []
    for _ in range(min(MAX_TOPIC_ROUNDS, -(-want // TOPIC_ROUND))):
        try:
            response = await cc.complete_json(
                TOPIC_SYSTEM,
                json.dumps({"subjects": list(subjects), "regions": list(regions),
                            "previous_topics": (list(avoid) + out)[-500:],
                            "count": TOPIC_ROUND}, ensure_ascii=False),
                max_tokens=5000)
            topics = _Topics.model_validate(response).topics
        except Exception as e:  # noqa: BLE001
            logger.warning("[발굴] 주제 생성 실패: %s", e)
            break
        fresh = 0
        for t in topics:
            nk = _norm(t.keyword)
            # 진료 항목이 키워드 안에 실제로 들어 있어야 한다(관련 없는 주제 차단).
            if nk in seen or t.subject not in subjects or _norm(t.subject) not in nk:
                continue
            seen.add(nk)
            out.append(t.keyword)
            fresh += 1
        if not fresh or len(out) >= want:
            break
    return out[:want]


async def _naver_seeds(terms: Sequence[str]) -> List[str]:
    """네이버가 실제로 보여 주는 연관검색어·자동완성. 사용자가 실제로 치는 말이 여기 있다."""
    from app.services.keyword_collector import get_naver_autocomplete, get_naver_related_keywords

    sem = asyncio.Semaphore(SEED_CONCURRENCY)

    async def one(term: str) -> List[str]:
        async with sem:
            try:
                rel, auto = await asyncio.wait_for(
                    asyncio.gather(get_naver_related_keywords(term), get_naver_autocomplete(term)), 30)
                return list(rel) + list(auto)
            except Exception as e:  # noqa: BLE001
                logger.info("[발굴] 네이버 씨앗 실패 %s: %s", term, e)
                return []

    gathered = await asyncio.gather(*[one(t) for t in terms])
    seen: set[str] = set()
    out: List[str] = []
    for group in gathered:
        for kw in group:
            nk = _norm(kw)
            if nk and nk not in seen:
                seen.add(nk)
                out.append(kw)
    return out


async def _screen_serp(ctx: JobContext, rows: List[CampaignKeyword], base: int, total: int) -> Dict[str, int]:
    """② 통검 자리 — 키워드당 SERP 1회. 본문 지표는 읽지 않아 글 8개 크롤을 건너뛴다."""
    from app.services import serp_analyzer as sa

    sem = asyncio.Semaphore(SERP_CONCURRENCY)

    async def one(row: CampaignKeyword):
        async with sem:
            try:
                return row, await asyncio.wait_for(
                    sa.analyze_keyword(row.keyword, fetch_post_metrics=False), SERP_TIMEOUT)
            except Exception as e:  # noqa: BLE001
                logger.info("[발굴] 통검 실패 %s: %s", row.keyword, e)
                return row, None

    counts = {"possible": 0, "contested": 0, "avoid": 0, "unknown": 0}
    done = 0
    pending = [asyncio.create_task(one(r)) for r in rows]
    try:
        for coro in asyncio.as_completed(pending):
            row, res = await coro
            if res is None:
                row.verdict = "unknown"
                row.verdict_reason = "통합검색을 읽지 못했습니다"
            else:
                row.verdict = res.get("verdict") or "unknown"
                row.verdict_reason = res.get("verdict_reason")
                # depth=light: 본문 지표 없이 섹션·블로그 유형만 본 판정. 정밀 분석이 나중에 덮어쓴다.
                row.serp_summary = {**(res.get("summary") or {}), "depth": "light"}
            counts[row.verdict if row.verdict in counts else "unknown"] += 1
            done += 1
            if done % 5 == 0 or done == len(rows):
                await ctx.progress(base + done, total,
                                   f"통검 자리 확인 {done}/{len(rows)} · 진입 여지 "
                                   f"{counts['possible'] + counts['contested']}개")
    finally:
        for task in pending:
            task.cancel()
    await ctx.db.commit()
    return counts


def _resolve_blog_id(campaign: Campaign, blogs: Sequence[Blog], asked: Optional[str]) -> str:
    """판정 기준 블로그. 캠페인에 연결된 정상 블로그가 1순위."""
    if asked:
        return asked.strip()
    linked = [b for b in blogs if b.id in (campaign.blog_ids or [])]
    for pool in (linked, list(blogs)):
        for b in pool:
            if b.status == "active":
                return b.blog_id
    if linked:
        return linked[0].blog_id
    raise ValueError("판정 기준이 될 블로그가 없습니다. 2번에서 블로그를 먼저 연결하세요")


@register("keyword_hunt")
async def keyword_hunt(ctx: JobContext) -> dict:
    from app.services.automation_pipeline import StageContext
    from app.services.blog_index_jobs import blog_verdict_batch

    p = ctx.payload
    campaign = await ctx.db.get(Campaign, p["campaign_id"])
    if not campaign or campaign.user_id != ctx.user_id:
        raise ValueError("캠페인 권한을 확인할 수 없습니다")
    client = await ctx.db.get(Client, campaign.client_id)
    if not client or client.user_id != ctx.user_id:
        raise ValueError("병원 정보 권한 오류")
    subjects = list(dict.fromkeys((client.diseases or []) + (client.treatments or [])))
    if not subjects:
        raise ValueError("진료 질환 또는 치료 항목이 필요합니다")
    blogs = (await ctx.db.execute(select(Blog).where(
        Blog.user_id == ctx.user_id, Blog.client_id == client.id))).scalars().all()
    blog_id = _resolve_blog_id(campaign, blogs, p.get("blog_id"))

    target = _clamp(p.get("target", 100), 10, MAX_TARGET, 100)
    screen_limit = _clamp(p.get("screen_limit", target * 2), target, 600, target * 2)
    verdict_limit = _clamp(p.get("verdict_limit", min(target, DEFAULT_VERDICT_LIMIT)), 0, 300,
                           min(target, DEFAULT_VERDICT_LIMIT))
    # 진행률 총량: 씨앗 1 + 통검 screen_limit + 판정 verdict_limit + 마무리 1
    total = 2 + screen_limit + verdict_limit
    result: Dict[str, Any] = dict(ctx.job.result or {})
    completed = list(result.get("completed", []))

    async def mark(stage: str, payload: Dict[str, Any]) -> None:
        completed.append(stage)
        result.update(payload)
        result["completed"] = completed
        ctx.job.result = dict(result)
        await ctx.db.commit()

    # ── ① 씨앗 ────────────────────────────────────────────────────────────
    if "seed" not in completed:
        await ctx.progress(0, total, "진료 항목에서 검색 주제 발굴")
        used = list((await ctx.db.execute(select(Draft.keyword).where(
            Draft.user_id == ctx.user_id, Draft.client_id == client.id,
            Draft.keyword.isnot(None)))).scalars())
        known = list((await ctx.db.execute(select(CampaignKeyword.keyword).where(
            CampaignKeyword.campaign_id == campaign.id))).scalars())
        topics = await _claude_topics(subjects, client.regions or [], used + known,
                                      want=max(30, target // 2))
        await ctx.progress(0, total, f"네이버 연관검색어·자동완성 수집 (주제 {len(topics)}개)")
        seeds = list(dict.fromkeys(topics + await _naver_seeds(list(subjects) + topics[:20])))
        if not seeds:
            raise ValueError("씨앗 키워드를 만들지 못했습니다. 진료 항목을 보충하세요")
        await ctx.progress(1, total, f"검색량 조회 (후보 {len(seeds)}개)")
        await jobs.keyword_expand(StageContext(ctx, {
            **p, "seeds": seeds, "diseases": subjects,
            "suffixes": ["", "원인", "증상", "치료", "관리", "진료"],
            "max_candidates": min(1200, max(400, target * 4)), "include_related": True,
        }))
        await mark("seed", {"seeded": len(seeds)})
    if await ctx.cancelled():
        return {**result, "cancelled": True}

    # ── ② 통검 자리 ───────────────────────────────────────────────────────
    if "screen" not in completed:
        rows = (await ctx.db.execute(select(CampaignKeyword).where(
            CampaignKeyword.campaign_id == campaign.id,
            CampaignKeyword.passes_filter == True,  # noqa: E712
            CampaignKeyword.in_sheet == False,      # noqa: E712
            CampaignKeyword.verdict == "unknown",
        ).order_by(CampaignKeyword.total_volume.desc(), CampaignKeyword.created_at))).scalars().all()
        forbidden = [w for w in (client.forbidden_words or []) if w]
        rows = [r for r in rows if not any(w in r.keyword for w in forbidden)][:screen_limit]
        counts = await _screen_serp(ctx, rows, base=1, total=total) if rows else \
            {"possible": 0, "contested": 0, "avoid": 0, "unknown": 0}
        await mark("screen", {"screened": len(rows), **counts})
    if await ctx.cancelled():
        return {**result, "cancelled": True}

    # ── ③ 내 블로그 판정 ──────────────────────────────────────────────────
    if "verdict" not in completed and verdict_limit:
        candidates = (await ctx.db.execute(select(CampaignKeyword).where(
            CampaignKeyword.campaign_id == campaign.id,
            CampaignKeyword.verdict.in_(WORTH_JUDGING),
            CampaignKeyword.my_verdict.is_(None),
        ).order_by(CampaignKeyword.total_volume.desc(), CampaignKeyword.created_at))).scalars().all()
        # 통검에서 '가능'이 먼저, 그다음 '경합'. 같은 등급 안에서는 검색량 순.
        candidates = sorted(candidates, key=lambda r: (r.verdict != "possible", -(r.total_volume or 0)))
        candidates = candidates[:verdict_limit]
        base = 1 + int(result.get("screened", 0) or 0)
        for i in range(0, len(candidates), VERDICT_WAVE):
            if await ctx.cancelled():
                break
            wave = candidates[i:i + VERDICT_WAVE]
            await ctx.progress(base + i, total,
                               f"내 블로그({blog_id})로 뚫리는지 판정 {i + 1}~{i + len(wave)}/{len(candidates)}")
            await blog_verdict_batch(StageContext(ctx, {
                "blog_id": blog_id, "keywords": [r.keyword for r in wave],
                "campaign_id": campaign.id, "stream_partial": False,
            }))
        await mark("verdict", {"judged": len(candidates), "blog_id": blog_id})

    # ── 마무리 ────────────────────────────────────────────────────────────
    rows = (await ctx.db.execute(select(CampaignKeyword).where(
        CampaignKeyword.campaign_id == campaign.id))).scalars().all()
    judged = [r for r in rows if r.my_verdict]
    picks = sorted([r for r in judged if r.my_verdict in WORTH_WRITING],
                   key=lambda r: (-(r.my_probability or 0), -(r.total_volume or 0)))[:target]
    picked = {r.id for r in picks}
    for r in rows:
        r.selected = r.id in picked
    campaign.updated_at = datetime.utcnow()
    await ctx.db.commit()
    await ctx.progress(total, total, f"발굴 완료 · 쓸 수 있는 키워드 {len(picks)}개")
    return {**result, "blog_id": blog_id, "target": target,
            "judged": len(judged),
            "likely": sum(1 for r in judged if r.my_verdict == "likely"),
            "contested_mine": sum(1 for r in judged if r.my_verdict == "contested"),
            "unlikely": sum(1 for r in judged if r.my_verdict == "unlikely"),
            "already_ranked": sum(1 for r in judged if r.my_verdict == "already_ranked"),
            "selected": len(picks)}
