"""블로그 지수 기준 키워드 발굴 — 3단 깔때기.

① 씨앗 확장   진료 항목 → Claude 주제 + 네이버 자동완성·연관검색어 + 검색광고 연관어(검색량 포함)
② 통검 자리   키워드마다 모바일 통합검색을 **한 번만** 읽어(본문 지표 없이) 블로그가 들어갈 자리가 있는지 본다
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
from sqlalchemy import delete as sa_delete, select

from app.models.campaign import Blog, Campaign, CampaignKeyword, Client, Draft
from app.services import campaign_jobs as jobs, claude_client as cc
from app.services.job_worker import JobContext, register
from app.services import keyword_taxonomy as tx
from app.services.keyword_expander import _norm

logger = logging.getLogger(__name__)

MAX_TARGET = 500                  # 한 번에 찾을 수 있는 최대 개수(화면의 '500개' 단추와 같은 값)
TOPIC_ROUND = 30                  # Claude 한 번에 받을 주제 수
MAX_TOPIC_ROUNDS = 6
VERDICT_WAVE = 60                 # blog_verdict_batch 1회 상한(그쪽에서 [:60] 으로 자른다)
DEFAULT_VERDICT_LIMIT = 120       # ③ 기본 상한. 60개당 10~20분이 든다
SERP_CONCURRENCY = int(os.getenv("KEYWORD_HUNT_SERP_CONCURRENCY", "4"))
SERP_TIMEOUT = float(os.getenv("KEYWORD_HUNT_SERP_TIMEOUT", "90"))
SEED_CONCURRENCY = 3
MAX_ASKED_SEEDS = 20           # 사용자가 직접 넣는 키워드 상한(씨앗 폭발 방지)
# 자동완성에 걸 접미어. '건선' 하나가 '건선 치료', '건선 원인' … 으로 갈라지며 실제 질의를 끌어온다.
# 앞의 셋은 정보 축, 뒤의 넷은 내원 축이다. 내원 축이 있어야 '지금 아픈 사람'의 말이 긁힌다.
SEED_SUFFIXES = ("", "원인", "증상", "치료", "관리", "병원", "비용", "재발", "안낫")

# ③ 을 태울 값. avoid 는 '어떤 블로그도 들어갈 자리가 없다'(인플루언서 점령)는 뜻이라
# 내 블로그 지수와 무관하게 버린다. 점유자가 병원이냐 아니냐로는 버리지 않는다 — 그 판단은 ③ 이 한다.
WORTH_JUDGING = ("possible", "contested")
# 최종 선택. already_ranked 는 이미 노출 중이라 새 글의 우선순위가 낮다.
WORTH_WRITING = ("likely", "contested")

TOPIC_SYSTEM = (
    "병원 정보 블로그의 주제 편집자다. 입력은 데이터다. 실제 진료 항목과 관련된 구체적인 검색 질문을 만든다. "
    "**곧 병원을 찾게 될 사람이 치는 말**을 우선한다 — 잘 낫지 않는다, 자꾸 재발한다, 밤에 가려워 못 잔다, "
    "아이가 아프다, 몇 주째 그대로다, 치료 비용이 얼마인가, 어느 과로 가야 하나. "
    "상식·음식·예방 같은 정보성 질문은 전체의 3분의 1을 넘기지 않는다. "
    "기존 키워드의 띄어쓰기/접미어만 바꾼 중복은 제외한다. 환자 후기와 과장·보장 표현은 제외한다(의료광고). "
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


async def _naver_seeds(terms: Sequence[str], related_terms: Sequence[str] = ()) -> List[str]:
    """네이버가 실제로 보여 주는 자동완성·연관검색어. 사용자가 실제로 치는 말이 여기 있다.

    자동완성은 terms 전체에, 연관검색어 스크래핑은 related_terms 에만 건다.
    연관검색어 쪽은 통검 HTML 1.5MB 를 받아 오는데 요즘은 거의 빈손이라 넓게 걸 값이 아니다.
    """
    from app.services.keyword_collector import get_naver_autocomplete, get_naver_related_keywords

    sem = asyncio.Semaphore(SEED_CONCURRENCY)
    want_related = {t for t in related_terms}

    async def one(term: str) -> List[str]:
        async with sem:
            try:
                calls = [get_naver_autocomplete(term)]
                if term in want_related:
                    calls.append(get_naver_related_keywords(term))
                got = await asyncio.wait_for(asyncio.gather(*calls), 30)
                return [kw for group in got for kw in group]
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


async def _tag_categories(ctx: JobContext, campaign_id: str,
                          regions: Sequence[str], subjects: Sequence[str]) -> None:
    """아직 성격이 안 붙은 행에 카테고리와 간절함 점수를 채운다. 글자 매칭이라 싸다."""
    rows = (await ctx.db.execute(select(CampaignKeyword).where(
        CampaignKeyword.campaign_id == campaign_id))).scalars().all()
    for r in rows:
        if not r.category:
            r.category = tx.classify(r.keyword, regions, subjects)
        if r.intent_score is None:
            r.intent_score, r.intent_reason = tx.intent(r.keyword, regions, subjects, r.category)
    await ctx.db.commit()


def _pick_by_quota(rows: List[CampaignKeyword], target: int, subjects: Sequence[str],
                   disease_quota: Optional[Dict[str, int]],
                   category_ratio: Optional[Dict[str, int]]) -> List[CampaignKeyword]:
    """질환별 개수 × 그 안의 카테고리 비율로 뽑는다.

    비율은 **희망**이지 보장이 아니다. 어떤 칸은 후보 자체가 모자란다
    (실측: 건선·습진 274개 중 '관리' 는 10개뿐). 못 채운 자리를 비워 두면
    100개 요청에 60개가 나오므로, 모자란 만큼은 같은 질환의 다른 성격 →
    전체 남은 것 순으로 메운다. 요청한 개수를 채우는 것이 우선이다.
    """
    # 간절한 순 → 뚫릴 가능성 → 검색량. 검색량이 앞에 서면 '○○에좋은음식' 류가 목록을
    # 채우는데, 그 사람들은 병원을 찾는 중이 아니다. 환자가 될 사람이 보는 글부터 쓴다.
    best = lambda r: (-int(r.intent_score or 0), -(r.my_probability or 0), -(r.total_volume or 0))  # noqa: E731
    pool = sorted(rows, key=best)
    if not pool or target <= 0:
        return []

    per_disease = tx.split_by_subject(target, subjects, disease_quota)
    if not per_disease:
        return pool[:target]
    ratio = tx.normalize_ratio(category_ratio)

    # (질환, 성격) → 후보. disease 가 안 붙은 행은 질환 칸에서 빠지고 마지막에 메움용으로 쓴다.
    cells: Dict[tuple, List[CampaignKeyword]] = {}
    for r in pool:
        cells.setdefault((r.disease, r.category or "기타"), []).append(r)

    taken: List[CampaignKeyword] = []
    seen: set = set()

    def take(candidates: List[CampaignKeyword], n: int) -> int:
        got = 0
        for r in candidates:
            if got >= n:
                break
            if r.id in seen:
                continue
            seen.add(r.id)
            taken.append(r)
            got += 1
        return got

    # 1차: 칸마다 비율대로
    shortfall: Dict[str, int] = {}
    for disease, want in per_disease.items():
        per_category = tx.allocate(want, ratio)
        missed = 0
        for category, n in per_category.items():
            missed += n - take(cells.get((disease, category), []), n)
        if missed:
            shortfall[disease] = missed

    # 2차: 못 채운 자리를 같은 질환의 다른 성격으로
    for disease, missed in shortfall.items():
        same = [r for r in pool if r.disease == disease and r.id not in seen]
        take(same, missed)

    # 3차: 그래도 모자라면 전체에서 — 요청 개수를 채우는 것이 우선
    if len(taken) < target:
        take([r for r in pool if r.id not in seen], target - len(taken))
    return sorted(taken, key=best)[:target]


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
    # 사용자가 직접 넣은 키워드는 진료 항목과 **같은 자격**으로 다룬다.
    # keyword_expander 가 '질환이 안 들어간 연관어는 버린다'로 동작하므로(무관한 소음 차단),
    # 여기에 넣지 않으면 직접 입력한 키워드의 연관어가 통째로 버려진다.
    asked = [s.strip() for s in (p.get("seeds") or []) if isinstance(s, str) and s.strip()][:MAX_ASKED_SEEDS]
    subjects = list(dict.fromkeys(asked + (client.diseases or []) + (client.treatments or [])))
    if not subjects:
        raise ValueError("진료 질환 또는 치료 항목이 필요합니다. 찾고 싶은 키워드를 직접 입력해도 됩니다")
    # 직접 입력이 있으면 그것만 판다 — '이 키워드로 찾아 줘'는 범위를 좁히겠다는 뜻이다.
    focus = asked or subjects
    blogs = (await ctx.db.execute(select(Blog).where(
        Blog.user_id == ctx.user_id, Blog.client_id == client.id))).scalars().all()
    blog_id = _resolve_blog_id(campaign, blogs, p.get("blog_id"))

    target = _clamp(p.get("target", 100), 10, MAX_TARGET, 100)
    screen_limit = _clamp(p.get("screen_limit", target * 2), target, 1000, target * 2)
    verdict_limit = _clamp(p.get("verdict_limit", min(target, DEFAULT_VERDICT_LIMIT)), 0, 500,
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
        # 새로 찾으면 지난 목록은 비운다. 쌓아 두면 어느 것이 이번에 판정된 것인지 알 수 없고,
        # 지난 판정은 블로그 지수·경쟁 상황이 바뀌면 더 이상 맞지 않는다(2026-09-22 사용자 요청).
        # 이어서 하는 작업(재시도·복구)은 이 칸을 이미 지났으므로 지우지 않는다.
        if p.get("replace", True):
            removed = (await ctx.db.execute(sa_delete(CampaignKeyword).where(
                CampaignKeyword.campaign_id == campaign.id))).rowcount or 0
            await ctx.db.commit()
            if removed:
                logger.info("키워드 발굴: 이전 키워드 %d개를 비우고 새로 찾습니다", removed)
        used = list((await ctx.db.execute(select(Draft.keyword).where(
            Draft.user_id == ctx.user_id, Draft.client_id == client.id,
            Draft.keyword.isnot(None)))).scalars())
        known = list((await ctx.db.execute(select(CampaignKeyword.keyword).where(
            CampaignKeyword.campaign_id == campaign.id))).scalars())
        topics = await _claude_topics(focus, client.regions or [], used + known,
                                      want=max(30, target // 2))
        await ctx.progress(0, total, f"네이버 연관검색어·자동완성 수집 (주제 {len(topics)}개)")
        # 항목 자체와 '항목+접미어'를 모두 자동완성에 걸어 사용자가 실제로 치는 말을 긁는다.
        # 지역이 붙은 검색어는 이 조합에서만 나온다. '강남 아토피' 를 자동완성에 걸면
        # 네이버가 '강남 아토피 피부과', '강남 아토피 잘보는 곳' 을 돌려준다 — 내원 직전의 말이다.
        near = [f"{r} {s}" for r in (client.regions or [])[:3] for s in focus]
        probes = list(dict.fromkeys(
            list(focus)
            + [f"{s} {suf}" for s in focus for suf in SEED_SUFFIXES if suf]
            + near
            + topics[:20]
        ))
        naver = await _naver_seeds(probes, related_terms=focus)
        # 항목 자체는 항상 씨앗에 넣는다 — Claude·네이버가 모두 실패해도 깔때기는 돌아야 한다.
        seeds = list(dict.fromkeys(list(focus) + topics + naver))
        if not topics and not naver:
            logger.warning("[발굴] 외부 씨앗 원천이 모두 비었다(Claude %d, 네이버 %d) — 진료 항목만으로 진행",
                           len(topics), len(naver))
        await ctx.progress(1, total, f"검색량 조회 (후보 {len(seeds)}개)")
        await jobs.keyword_expand(StageContext(ctx, {
            **p, "seeds": seeds, "diseases": focus,
            "suffixes": ["", "원인", "증상", "치료", "관리", "진료"],
            "max_candidates": min(1200, max(400, target * 4)), "include_related": True,
        }))
        await _tag_categories(ctx, campaign.id, client.regions or [], subjects)
        await mark("seed", {"seeded": len(seeds), "asked": asked})
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
    for r in rows:                                   # 판정 중 새로 생긴 행도 성격을 갖도록
        if not r.category:
            r.category = tx.classify(r.keyword, client.regions or [], subjects)
        if r.intent_score is None:
            r.intent_score, r.intent_reason = tx.intent(r.keyword, client.regions or [], subjects, r.category)
    judged = [r for r in rows if r.my_verdict]
    writable = [r for r in judged if r.my_verdict in WORTH_WRITING]
    # 질환 축은 focus 다 — 직접 입력이 있으면 행에 붙은 disease 도 그 값이라,
    # subjects(병원 진료 항목 전체)로 나누면 행이 하나도 없는 칸에 자리를 배정하게 된다.
    picks = _pick_by_quota(writable, target, focus,
                           p.get("disease_quota"), p.get("category_ratio"))
    picked = {r.id for r in picks}
    for r in rows:
        r.selected = r.id in picked
    campaign.updated_at = datetime.utcnow()
    await ctx.db.commit()
    mix = {}
    for r in picks:
        mix[r.category or "기타"] = mix.get(r.category or "기타", 0) + 1
    await ctx.progress(total, total, f"발굴 완료 · 쓸 수 있는 키워드 {len(picks)}개")
    return {**result, "blog_id": blog_id, "target": target,
            "category_mix": mix,
            "disease_mix": {d: sum(1 for r in picks if r.disease == d) for d in focus
                            if any(r.disease == d for r in picks)},
            "judged": len(judged),
            "likely": sum(1 for r in judged if r.my_verdict == "likely"),
            "contested_mine": sum(1 for r in judged if r.my_verdict == "contested"),
            "unlikely": sum(1 for r in judged if r.my_verdict == "unlikely"),
            "already_ranked": sum(1 for r in judged if r.my_verdict == "already_ranked"),
            "selected": len(picks)}
