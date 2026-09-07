"""
블로그 지수 / 상위노출 판정 — 워커 핸들러.

무거운 경로(경쟁자 10명 채점, 노출 천장 스크래핑 10회, 색인 검증)는 API 이벤트루프가 아니라
워커에서 돌리고 진행률(done/total)을 BackgroundJob 에 흘린다(문서 14-4).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select

from app.blogindex import DISCLAIMER_VERDICT, normalize_blog_id, normalize_keyword
from app.models.background_job import BackgroundJob
from app.models.campaign import Blog, CampaignKeyword
from app.blogindex.dbwrite import isolated_write
from app.services.job_worker import JobContext, register

logger = logging.getLogger(__name__)


def _percent(p):
    return None if p is None else int(round(float(p) * 100))


VERDICT_LABEL = {
    "already_ranked": "이미 노출 중",
    "likely": "가능성 높음",
    "contested": "경합",
    "unlikely": "가능성 낮음",
    "unknown": "측정 불가",
}


def summarize_verdict(v: Dict[str, Any]) -> Dict[str, Any]:
    """화면용 요약(퍼센트·라벨·핵심 근거)."""
    prob = v.get("probability")
    return {
        "keyword": v.get("keyword"),
        "verdict": v.get("verdict") or "unknown",
        "label": VERDICT_LABEL.get(v.get("verdict") or "unknown", "측정 불가"),
        "probability": prob,
        "percent": _percent(prob),
        "confidence": v.get("confidence"),
        "my_score": v.get("my_score") or (v.get("my") or {}).get("score"),
        "my_grade": (v.get("my") or {}).get("grade"),
        "cut_line": v.get("cut_line"),
        "median_score": v.get("median_score"),
        "my_rank": (v.get("facts") or {}).get("my_rank"),
        "volume": (v.get("facts") or {}).get("volume"),
        "reasons": v.get("reasons") or [],
        "scored_competitors": v.get("scored_competitors"),
        "vacancy_count": v.get("vacancy_count"),
        "ok": bool(v.get("ok", True)),
    }


@register("blog_analyze")
async def blog_analyze(ctx: JobContext) -> dict:
    from app.blogindex import analyzer
    p = ctx.payload
    blog_id = normalize_blog_id(p["blog_id"])
    await ctx.progress(0, 1, f"{blog_id} 지수 분석")
    res = await analyzer.analyze_blog(
        ctx.db, blog_id, keyword=p.get("keyword"), fullparse=bool(p.get("fullparse", True)),
        use_cache=not bool(p.get("refresh")), verify_index=bool(p.get("verify_index")), progress=ctx.progress,
    )
    await _store_blog_index(ctx, blog_id, res)
    return res


async def _store_blog_index(ctx: JobContext, blog_id: str, res: Dict[str, Any]) -> None:
    """병원 관리의 블로그 계정에 최근 지수를 적어 둔다(같은 사용자 것만)."""
    if not ctx.user_id or not res.get("success"):
        return
    idx = res.get("index") or {}
    rows = (await ctx.db.execute(select(Blog).where(Blog.user_id == ctx.user_id, Blog.blog_id == blog_id))).scalars().all()
    for b in rows:
        b.index_score, b.index_level, b.index_grade, b.index_at = idx.get("total_score"), idx.get("level"), idx.get("grade"), datetime.utcnow()
    if rows:
        await ctx.db.commit()


@register("blog_verdict")
async def blog_verdict(ctx: JobContext) -> dict:
    from app.blogindex import analyzer, keyword_verdict
    p = ctx.payload
    blog_id = await analyzer.canonicalize(normalize_blog_id(p["blog_id"]))
    keyword = (p.get("keyword") or "").strip()
    await ctx.progress(0, 2, f"{keyword}: 실제 검색 결과 조회")
    facts = await keyword_verdict.stage1_facts(ctx.db, blog_id, keyword)
    await ctx.progress(1, 2, f"{keyword}: 경쟁자 채점")
    res = await keyword_verdict.stage2_verdict(ctx.db, blog_id, keyword, facts=facts, progress=ctx.progress, user_id=ctx.user_id)
    res["summary"] = summarize_verdict(res)
    res.setdefault("disclaimer", DISCLAIMER_VERDICT)
    return res


@register("blog_verdict_batch")
async def blog_verdict_batch(ctx: JobContext) -> dict:
    """여러 키워드를 같은 블로그로 판정. campaign_id 가 있으면 캠페인 키워드 행에 기록."""
    from app.blogindex import analyzer, keyword_verdict
    p = ctx.payload
    requested_id = normalize_blog_id(p["blog_id"])
    blog_id = await analyzer.canonicalize(requested_id)
    keywords: List[str] = [k.strip() for k in (p.get("keywords") or []) if k and k.strip()][:60]
    campaign_id = p.get("campaign_id")
    total = len(keywords) + 1
    await ctx.progress(0, total, f"{blog_id} 내 블로그 지수 채점")
    # 내 블로그는 한 번만(항상 새로) 채점해 모든 키워드에 재사용
    from app.blogindex import serp as serp_mod

    # ── 1) 검색 결과(stage1)는 키워드 전부 동시에. 내 블로그 채점도 같이 돌린다 ──
    s1_sem = asyncio.Semaphore(int(os.getenv("BLOGINDEX_STAGE1_CONCURRENCY", "4")))

    async def _s1(kw: str):
        async with s1_sem:
            async with serp_mod.fresh_session() as s:
                try:
                    return kw, await asyncio.wait_for(keyword_verdict.stage1_facts(s, blog_id, kw), 120)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[판정] stage1 실패 %s: %s", kw, e)
                    return kw, None

    async def _my():
        try:
            async with serp_mod.fresh_session() as s_my:   # 워커 세션과 분리(동시 사용 방지)
                return await analyzer.score_blog_light(s_my, blog_id, use_cache=False, fullparse_n=15)
        except Exception as e:  # noqa: BLE001
            logger.warning("[판정] 내 블로그 채점 실패 %s: %s", blog_id, e)
            return None

    await ctx.progress(0, total, f"{blog_id} 지수 채점 + 검색 결과 {len(keywords)}개 조회")
    s1_results, my = await asyncio.gather(asyncio.gather(*[_s1(k) for k in keywords]), _my())
    facts_map = {kw: f for kw, f in s1_results}

    # ── 2) 경쟁자 합집합을 한 번에 채점(같은 주제 키워드는 점유자가 겹친다 — 문서 10-3) ──
    need: List[str] = []
    seen_ids = set()
    for kw in keywords:
        f = facts_map.get(kw) or {}
        fx = f.get("facts") or {}
        if not f.get("ok") or fx.get("already_page1"):
            continue
        for pg in fx.get("page1") or []:
            bid = pg.get("blog_id")
            if bid and bid != blog_id and bid not in seen_ids:
                seen_ids.add(bid)
                need.append(bid)
    pre_sem = asyncio.Semaphore(analyzer.SCORE_CONCURRENCY)
    pre_done = 0
    job_id_pre = ctx.job.id

    async def _pre(bid: str):
        nonlocal pre_done
        async with pre_sem:
            try:
                async with serp_mod.fresh_session() as s:
                    await asyncio.wait_for(analyzer.score_blog_light(s, bid, use_cache=True), keyword_verdict.PER_BLOG_TIMEOUT)
            except Exception as e:  # noqa: BLE001
                logger.info("[판정] 사전 채점 실패 %s: %s", bid, e)
        pre_done += 1
        if pre_done % 3 == 0 or pre_done == len(need):
            msg = f"경쟁 블로그 채점 {pre_done}/{len(need)}"

            async def _do(sess, _m=msg):
                j = await sess.get(BackgroundJob, job_id_pre)
                if j is not None:
                    j.message = _m
                    j.updated_at = datetime.utcnow()
            await isolated_write(_do, what="pre-score progress", retries=1)

    if need:
        await ctx.progress(0, total, f"경쟁 블로그 채점 0/{len(need)}")
        await asyncio.gather(*[_pre(b) for b in need])
    items: List[Dict[str, Any]] = []
    kw_rows = {}
    if campaign_id:
        rows = (await ctx.db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id))).scalars().all()
        kw_rows = {normalize_keyword(r.keyword): r for r in rows}
    for i, kw in enumerate(keywords):
        if await ctx.cancelled():
            break
        await ctx.progress(i + 1, total, f"판정 {i + 1}/{len(keywords)}: {kw} — 검색 결과 조회")
        loop = asyncio.get_running_loop()
        job_id = ctx.job.id

        def _sub(done: int, tot: int, _i=i, _kw=kw):
            # ctx.db 는 stage2 가 쓰고 있으므로 진행률은 자기 세션으로 쓴다(한 세션 동시 사용 금지)
            msg = f"판정 {_i + 1}/{len(keywords)}: {_kw} — 경쟁자 채점 {done}/{tot}"

            async def _do(s):
                j = await s.get(BackgroundJob, job_id)
                if j is not None:
                    j.message = msg[:300]
                    j.updated_at = datetime.utcnow()

            loop.create_task(isolated_write(_do, what="verdict progress", retries=1))

        try:
            hard_cap = keyword_verdict.STAGE2_BUDGET + 120
            facts = facts_map.get(kw) or await asyncio.wait_for(keyword_verdict.stage1_facts(ctx.db, blog_id, kw), 120)
            res = await asyncio.wait_for(
                keyword_verdict.stage2_verdict(ctx.db, blog_id, kw, facts=facts, my=my, user_id=ctx.user_id, progress=_sub),
                hard_cap,
            )
        except asyncio.TimeoutError:
            logger.warning("[판정] %s 하드 상한 초과 — 측정 불가 처리", kw)
            res = {"ok": False, "keyword": kw, "verdict": "unknown", "probability": None, "confidence": "low",
                   "reasons": ["판정 시간이 너무 오래 걸려 중단했습니다. 잠시 후 다시 시도하세요."], "facts": {}}
        except Exception as e:  # noqa: BLE001
            logger.warning("[판정] %s 실패: %s", kw, e)
            res = {"ok": False, "keyword": kw, "verdict": "unknown", "probability": None, "confidence": "low",
                   "reasons": [f"판정 실패: {e}"[:200]], "facts": {}}
        res["keyword"] = kw
        summ = summarize_verdict(res)
        items.append({**summ, "detail": res})
        # 부분 결과 스트리밍: 화면은 완료를 기다리지 않고 키워드마다 바로 표에 그린다
        partial = {"blog_id": blog_id, "requested_blog_id": requested_id, "partial": True,
                   "my": ({"score": my.get("score"), "level": my.get("level"), "grade": my.get("grade"), "blog_name": my.get("blog_name")} if my else None),
                   "items": [{k: v for k, v in x.items() if k != "detail"} for x in items]}
        _jid = ctx.job.id

        async def _do_partial(sess, _p=partial, _j=_jid):
            j = await sess.get(BackgroundJob, _j)
            if j is not None and j.status == "running":
                j.result = _p
        await isolated_write(_do_partial, what="partial result", retries=1)
        row = kw_rows.get(normalize_keyword(kw))
        if row is not None:
            row.my_blog_id = blog_id
            row.my_verdict = summ["verdict"]
            row.my_probability = summ["probability"]
            row.my_verdict_result = {k: v for k, v in summ.items() if k != "detail"}
            row.my_verdict_at = datetime.utcnow()
            await ctx.db.commit()
    my_summary = None
    if my:
        my_summary = {"score": my.get("score"), "level": my.get("level"), "grade": my.get("grade"), "blog_name": my.get("blog_name")}
    return {"blog_id": blog_id, "requested_blog_id": requested_id, "my": my_summary, "items": items, "disclaimer": DISCLAIMER_VERDICT}


@register("blog_ceiling")
async def blog_ceiling(ctx: JobContext) -> dict:
    from app.blogindex import exposure_ceiling
    p = ctx.payload
    return await exposure_ceiling.measure_ceiling(ctx.db, normalize_blog_id(p["blog_id"]), refresh=bool(p.get("refresh")), progress=ctx.progress)


@register("blog_verify_index")
async def blog_verify_index(ctx: JobContext) -> dict:
    from app.blogindex import verifier
    p = ctx.payload
    return await verifier.verify_index(ctx.db, normalize_blog_id(p["blog_id"]), sample_size=int(p.get("sample_size", 12)))


@register("blog_competition")
async def blog_competition(ctx: JobContext) -> dict:
    from app.blogindex import competition_analyzer
    p = ctx.payload
    return await competition_analyzer.analyze_competition(ctx.db, (p.get("keyword") or "").strip(), my_blog_id=normalize_blog_id(p["my_blog_id"]) if p.get("my_blog_id") else None)


@register("blog_post_exposure")
async def blog_post_exposure(ctx: JobContext) -> dict:
    from app.blogindex import post_exposure
    p = ctx.payload
    return await post_exposure.post_exposure_cards(ctx.db, normalize_blog_id(p["blog_id"]), sample=int(p.get("sample", 10)))


@register("blog_prewarm")
async def blog_prewarm(ctx: JobContext) -> dict:
    """키워드들의 1페이지 경쟁자를 미리 채점해 캐시에 넣는다(블로그 무관).
    원스톱 1단계에서 '다음'을 누르는 순간, 캠페인에서 키워드를 고르는 순간 뒤에서 돌려
    2단계 판정이 캐시 히트로 몇 초 안에 끝나게 한다."""
    from app.blogindex import analyzer, keyword_verdict, serp as serp_mod
    p = ctx.payload
    keywords: List[str] = [k.strip() for k in (p.get("keywords") or []) if k and k.strip()][:40]
    if not keywords:
        return {"prewarmed": 0}
    s1_sem = asyncio.Semaphore(int(os.getenv("BLOGINDEX_STAGE1_CONCURRENCY", "4")))

    async def _serp(kw: str):
        async with s1_sem:
            async with serp_mod.fresh_session() as s:
                try:
                    r = await asyncio.wait_for(serp_mod.blog_tab_serp(s, kw, limit=20, use_cache=True), 60)
                    return [x["blog_id"] for x in (r or {}).get("rows") or [] if x.get("rank", 99) <= keyword_verdict.PAGE1_CUTOFF]
                except Exception as e:  # noqa: BLE001
                    logger.info("[prewarm] SERP 실패 %s: %s", kw, e)
                    return []

    await ctx.progress(0, len(keywords) + 1, f"검색 결과 {len(keywords)}개 조회")
    lists = await asyncio.gather(*[_serp(k) for k in keywords])
    need: List[str] = []
    seen = set()
    for ids in lists:
        for b in ids:
            if b not in seen:
                seen.add(b)
                need.append(b)
    sem = asyncio.Semaphore(analyzer.SCORE_CONCURRENCY)
    done = 0

    async def _one(bid: str):
        nonlocal done
        async with sem:
            try:
                async with serp_mod.fresh_session() as s:
                    await asyncio.wait_for(analyzer.score_blog_light(s, bid, use_cache=True), keyword_verdict.PER_BLOG_TIMEOUT)
            except Exception as e:  # noqa: BLE001
                logger.info("[prewarm] 채점 실패 %s: %s", bid, e)
        done += 1
        if done % 5 == 0 or done == len(need):
            await ctx.progress(min(done, len(keywords)), len(keywords) + 1, f"경쟁 블로그 사전 채점 {done}/{len(need)}")

    await asyncio.gather(*[_one(b) for b in need])
    return {"keywords": len(keywords), "prewarmed": len(need)}
