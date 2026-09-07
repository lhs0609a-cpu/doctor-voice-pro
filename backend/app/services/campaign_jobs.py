"""
캠페인 워커 핸들러. job_worker.register 로 등록되며 run_forever 가 임포트한다.

유형
  keyword_expand   지역×질환 조합 + 연관어 + 검색량 → CampaignKeyword
  sheet_check      구글시트 중복 대조 → in_sheet
  serp_analyze     통합검색 분석(24h 캐시) → verdict/summary
  draft_generate   키워드 → 원고(브리프 기반) + 검수
  draft_variants   원본 원고 → 변형 N개 + 사실 보존 검수
  photo_tag        사진 세트 AI 태깅(미태깅분만)
  image_plan       원고 문단 슬롯 계획 + 사진 매칭
  prepare_images   발행건 사진 유니크화 사전 처리(파일로 저장)
  sheet_append     승인 키워드/발행 결과 시트 기입
"""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, func

from app.core.config import settings
from app.models.campaign import (
    Blog, BriefPreset, Campaign, CampaignKeyword, Client, Draft, PublishJob, SerpSnapshot,
)
from app.models.media_pool import ImageVariant, PoolCollectionMember, PoolImage
from app.services import campaign_writer as writer
from app.services import image_uniquifier as uniq
from app.services import keyword_expander
from app.services.job_worker import JobContext, register

logger = logging.getLogger(__name__)


def media_dir(*parts: str) -> Path:
    base = Path(settings.MEDIA_DIR)
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    p = base.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _client_dict(c: Client) -> Dict[str, Any]:
    return {
        "id": c.id, "name": c.name, "short_name": c.short_name, "specialty": c.specialty,
        "diseases": c.diseases or [], "treatments": c.treatments or [], "regions": c.regions or [],
        "forbidden_words": c.forbidden_words or [], "tone": c.tone, "facts": c.facts,
    }


def _brief_dict(b: Optional[BriefPreset]) -> Optional[Dict[str, Any]]:
    if not b:
        return None
    return {
        "id": b.id, "name": b.name, "description": b.description, "flow": b.flow or [],
        "rules": b.rules, "must_include": b.must_include or [], "avoid": b.avoid or [],
        "source_text": b.source_text, "target_chars": b.target_chars,
        "heading_count": b.heading_count, "keyword_count": b.keyword_count,
    }


async def _bump_stats(ctx: JobContext, campaign_id: str) -> None:
    """캠페인 stats 갱신(키워드/원고/발행건 수)."""
    camp = await ctx.db.get(Campaign, campaign_id)
    if not camp:
        return
    db = ctx.db
    kw = (await db.execute(select(func.count()).select_from(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id))).scalar() or 0
    kw_sel = (await db.execute(select(func.count()).select_from(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id, CampaignKeyword.selected == True))).scalar() or 0  # noqa: E712
    dr = (await db.execute(select(func.count()).select_from(Draft).where(Draft.campaign_id == campaign_id))).scalar() or 0
    dr_ready = (await db.execute(select(func.count()).select_from(Draft).where(Draft.campaign_id == campaign_id, Draft.status == "ready"))).scalar() or 0
    jobs = (await db.execute(select(PublishJob.status, func.count()).where(PublishJob.campaign_id == campaign_id).group_by(PublishJob.status))).all()
    by = {s: n for s, n in jobs}
    camp.stats = {
        "keywords": kw, "keywords_selected": kw_sel, "drafts": dr, "drafts_ready": dr_ready,
        "jobs": sum(by.values()), "published": by.get("published", 0), "failed": by.get("failed", 0),
        "queued": by.get("queued", 0) + by.get("assigned", 0), "uncertain": by.get("uncertain", 0),
    }
    camp.updated_at = datetime.utcnow()
    await db.commit()


# ─────────────────────────────── keyword_expand ───────────────────────────────
@register("keyword_expand")
async def keyword_expand(ctx: JobContext) -> dict:
    p = ctx.payload
    campaign_id = p["campaign_id"]
    camp = await ctx.db.get(Campaign, campaign_id)
    if not camp:
        raise ValueError("캠페인을 찾을 수 없습니다")
    client = await ctx.db.get(Client, camp.client_id)

    regions = p.get("regions") or (client.regions if client else []) or []
    diseases = p.get("diseases") or (client.diseases if client else []) or []
    seeds = p.get("seeds") or []
    level = int(p.get("level", client.region_expand_level if client else 1) or 0)

    rows = await keyword_expander.expand_keywords(
        ctx.db,
        seeds=seeds, regions=regions, diseases=diseases,
        suffixes=p.get("suffixes") or (client.suffixes if client and client.suffixes else None),
        region_level=level,
        min_volume_region=int(p.get("min_volume_region") or (client.min_volume_region if client else 20)),
        min_volume_national=int(p.get("min_volume_national") or (client.min_volume_national if client else 100)),
        include_related=bool(p.get("include_related", True)),
        max_candidates=int(p.get("max_candidates", 400)),
        progress=ctx.progress,
    )

    existing = {
        keyword_expander._norm(k.keyword): k
        for k in (await ctx.db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id))).scalars().all()
    }
    added = updated = 0
    now = datetime.utcnow()
    for r in rows:
        nk = keyword_expander._norm(r["keyword"])
        row = existing.get(nk)
        if row is None:
            row = CampaignKeyword(
                user_id=ctx.user_id, campaign_id=campaign_id, client_id=camp.client_id,
                keyword=r["keyword"], region=r.get("region"), disease=r.get("disease"),
                source=r.get("source", "combo"), scope=r.get("scope", "region"),
                selected=bool(r["passes_filter"]),
            )
            ctx.db.add(row)
            existing[nk] = row
            added += 1
        else:
            updated += 1
        row.monthly_mobile = r["monthly_mobile"]
        row.monthly_pc = r["monthly_pc"]
        row.total_volume = r["total_volume"]
        row.competition = r.get("competition", "mid")
        row.passes_filter = bool(r["passes_filter"])
        row.volume_fetched_at = now if r.get("has_volume") else row.volume_fetched_at
    await ctx.db.commit()

    # 시트가 연결돼 있으면 중복 대조까지 이어서(실패해도 확장 결과는 유지)
    sheet_result = None
    if client and client.sheet_url:
        try:
            sheet_result = await _sheet_check_impl(ctx, campaign_id, client)
        except Exception as e:  # noqa: BLE001
            logger.warning("[확장] 시트 대조 실패: %s", e)
            sheet_result = {"error": str(e)}

    await _bump_stats(ctx, campaign_id)
    return {"added": added, "updated": updated, "total": len(rows), "passing": sum(1 for r in rows if r["passes_filter"]), "sheet": sheet_result}


# ─────────────────────────────── sheet_check ───────────────────────────────
async def _sheet_check_impl(ctx: JobContext, campaign_id: str, client: Client) -> dict:
    from app.services import google_sheets_service as gs

    kws = (await ctx.db.execute(select(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id))).scalars().all()
    if not kws:
        return {"checked": 0}
    names = [k.keyword for k in kws]
    found_total = 0
    for tab in [client.sheet_blog_tab or "블로그", client.sheet_cafe_tab or "카페"]:
        try:
            found = await gs.find_keywords(client.sheet_url, tab, names)
        except gs.SheetsError as e:
            logger.warning("[시트] %s 탭 읽기 실패: %s", tab, e)
            continue
        for k in kws:
            hit = found.get(k.keyword)
            if hit:
                k.in_sheet = True
                k.sheet_note = f"{tab} 탭 {hit.get('row')}행"
                if k.selected:
                    k.selected = False
                found_total += 1
    await ctx.db.commit()
    return {"checked": len(names), "found": found_total}


@register("sheet_check")
async def sheet_check(ctx: JobContext) -> dict:
    campaign_id = ctx.payload["campaign_id"]
    camp = await ctx.db.get(Campaign, campaign_id)
    client = await ctx.db.get(Client, camp.client_id) if camp else None
    if not client or not client.sheet_url:
        raise ValueError("병원에 구글시트 주소가 없습니다")
    return await _sheet_check_impl(ctx, campaign_id, client)


# ─────────────────────────────── serp_analyze ───────────────────────────────
async def analyze_keyword_cached(db, keyword: str) -> SerpSnapshot:
    """24시간 안의 스냅샷이 있으면 재사용, 없으면 새로 분석해 저장."""
    from app.services import serp_analyzer as sa

    nk = sa.normalize_keyword(keyword)
    cutoff = datetime.utcnow() - timedelta(hours=getattr(sa, "SERP_CACHE_HOURS", 24))
    snap = (await db.execute(
        select(SerpSnapshot).where(SerpSnapshot.keyword_norm == nk, SerpSnapshot.fetched_at >= cutoff)
        .order_by(SerpSnapshot.fetched_at.desc()).limit(1)
    )).scalar_one_or_none()
    if snap and not snap.error:
        return snap
    result = await sa.analyze_keyword(keyword)
    snap = SerpSnapshot(
        keyword_norm=nk, keyword=keyword, fetched_at=datetime.utcnow(), device="mobile",
        posts=result.get("posts") or [], summary=result.get("summary") or {},
        verdict=result.get("verdict") or "unknown", verdict_reason=result.get("verdict_reason"),
        error=result.get("error"),
    )
    db.add(snap)
    await db.commit()
    return snap


@register("serp_analyze")
async def serp_analyze(ctx: JobContext) -> dict:
    p = ctx.payload
    campaign_id = p["campaign_id"]
    q = select(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id)
    if p.get("keyword_ids"):
        q = q.where(CampaignKeyword.id.in_(p["keyword_ids"]))
    else:
        q = q.where(CampaignKeyword.passes_filter == True)  # noqa: E712
    kws = (await ctx.db.execute(q.order_by(CampaignKeyword.monthly_mobile.desc()))).scalars().all()
    kws = kws[: int(p.get("limit", 60))]
    total = len(kws)
    done = 0
    counts = {"possible": 0, "contested": 0, "avoid": 0, "unknown": 0}
    for k in kws:
        if await ctx.cancelled():
            break
        try:
            snap = await analyze_keyword_cached(ctx.db, k.keyword)
            k.verdict = snap.verdict or "unknown"
            k.verdict_reason = snap.verdict_reason
            k.serp_summary = snap.summary
            if k.verdict == "avoid" and k.selected:
                k.selected = False
        except Exception as e:  # noqa: BLE001
            logger.warning("[통검] %s 실패: %s", k.keyword, e)
            k.verdict = "unknown"
            k.verdict_reason = f"분석 실패: {e}"[:300]
        counts[k.verdict if k.verdict in counts else "unknown"] += 1
        done += 1
        await ctx.progress(done, total, f"통검 분석 {done}/{total}: {k.keyword}")
    await ctx.db.commit()
    await _bump_stats(ctx, campaign_id)
    return {"analyzed": done, **counts}


# ─────────────────────────────── draft_generate ───────────────────────────────
@register("draft_generate")
async def draft_generate(ctx: JobContext) -> dict:
    p = ctx.payload
    campaign_id = p["campaign_id"]
    camp = await ctx.db.get(Campaign, campaign_id)
    client = await ctx.db.get(Client, camp.client_id)
    brief = await ctx.db.get(BriefPreset, p.get("brief_id") or camp.brief_id) if (p.get("brief_id") or camp.brief_id) else None

    q = select(CampaignKeyword).where(CampaignKeyword.campaign_id == campaign_id)
    if p.get("keyword_ids"):
        q = q.where(CampaignKeyword.id.in_(p["keyword_ids"]))
    else:
        q = q.where(CampaignKeyword.selected == True)  # noqa: E712
    kws = (await ctx.db.execute(q)).scalars().all()

    # 이미 원고가 있는 키워드는 건너뛴다(중복 생성 방지). force 면 새로 만든다.
    existing = set()
    if not p.get("force"):
        rows = (await ctx.db.execute(select(Draft.keyword_id).where(Draft.campaign_id == campaign_id, Draft.keyword_id.isnot(None)))).all()
        existing = {r for (r,) in rows}
    targets = [k for k in kws if k.id not in existing]

    # 화면에 바로 보이도록 '생성 중' 행을 먼저 만든다
    drafts: List[Draft] = []
    for k in targets:
        d = Draft(
            user_id=ctx.user_id, client_id=camp.client_id, campaign_id=campaign_id,
            keyword_id=k.id, keyword=k.keyword, source="generated", brief_id=brief.id if brief else None,
            title=k.keyword, body="", status="generating",
        )
        ctx.db.add(d)
        drafts.append(d)
    await ctx.db.commit()

    total = len(drafts)
    ok = failed = 0
    cdict = _client_dict(client)
    bdict = _brief_dict(brief)
    for i, d in enumerate(drafts):
        if await ctx.cancelled():
            break
        k = next((x for x in targets if x.id == d.keyword_id), None)
        serp = {"summary": k.serp_summary} if k and k.serp_summary else None
        await ctx.progress(i, total, f"원고 작성 {i + 1}/{total}: {d.keyword}")
        try:
            res = await writer.write_from_keyword(
                keyword=d.keyword, client=cdict, brief=bdict, serp=serp,
                target_chars=p.get("target_chars"), heading_count=p.get("heading_count"),
                keyword_count=p.get("keyword_count"), extra_instructions=p.get("instructions") or "",
            )
            d.title, d.body, d.char_count = res["title"], res["body"], res["char_count"]
            d.tags = res["tags"]
            d.emphasize = [d.keyword] if d.keyword else []
            checks = writer.run_static_checks(d.title, d.body, cdict.get("forbidden_words"))
            if bdict and bdict.get("flow"):
                try:
                    checks["flow"] = await writer.check_flow(d.body, bdict["flow"])
                except Exception as e:  # noqa: BLE001
                    checks["flow"] = {"ok": True, "notes": f"흐름 검사 생략: {e}"[:200]}
            flow_ok = checks.get("flow", {}).get("ok", True)
            d.checks = checks
            d.status = "ready" if (checks["ok"] and flow_ok) else "needs_review"
            d.image_count_target = int((serp or {}).get("summary", {}).get("recommended_image_count") or p.get("image_count") or 0) or 0
            ok += 1
        except Exception as e:  # noqa: BLE001
            logger.error("[원고] %s 실패: %s", d.keyword, e)
            d.status = "failed"
            d.error = str(e)[:1000]
            failed += 1
        await ctx.db.commit()
    await _bump_stats(ctx, campaign_id)
    return {"generated": ok, "failed": failed, "skipped_existing": len(kws) - len(targets)}


# ─────────────────────────────── draft_variants ───────────────────────────────
@register("draft_variants")
async def draft_variants(ctx: JobContext) -> dict:
    p = ctx.payload
    campaign_id = p.get("campaign_id")
    source = (p.get("source_text") or "").strip()
    if not source:
        raise ValueError("원본 원고가 비어 있습니다")
    count = max(1, min(20, int(p.get("count", 3))))
    keyword = p.get("keyword") or ""
    client = None
    if p.get("client_id"):
        client = await ctx.db.get(Client, p["client_id"])
    forbidden = (client.forbidden_words if client else []) or []

    # 원본을 parent 로 저장(발행 대상 아님: source=manual, campaign 연결은 유지)
    parent = Draft(
        user_id=ctx.user_id, client_id=p.get("client_id"), campaign_id=campaign_id,
        keyword=keyword, source="upload", title=(p.get("title") or source.splitlines()[0][:100]),
        body=source, char_count=writer.count_chars(source), status="ready",
        checks={"note": "원본(변형 소스)"},
    )
    ctx.db.add(parent)
    await ctx.db.commit()

    await ctx.progress(0, count + 1, "고정 사실 추출")
    facts = await writer.extract_facts(source)
    produced: List[Draft] = []
    for i in range(count):
        if await ctx.cancelled():
            break
        axis = writer.VARIANT_AXES[i % len(writer.VARIANT_AXES)]
        await ctx.progress(i + 1, count + 1, f"변형 {i + 1}/{count}: {axis['voice']}")
        d = Draft(
            user_id=ctx.user_id, client_id=p.get("client_id"), campaign_id=campaign_id,
            keyword=keyword, source="variant", parent_draft_id=parent.id, status="generating",
            title="", body="",
        )
        ctx.db.add(d)
        await ctx.db.commit()
        try:
            res = await writer.make_variant(source, axis, facts, forbidden, target_chars=p.get("target_chars"))
            d.title, d.body, d.char_count = res["title"] or parent.title, res["body"], res["char_count"]
            checks = writer.run_static_checks(d.title, d.body, forbidden)
            checks["axis"] = axis
            checks["similarity_to_source"] = round(writer.similarity(source, d.body), 3)
            checks["similarity_to_siblings"] = round(max([writer.similarity(s.body, d.body) for s in produced] or [0.0]), 3)
            try:
                checks["facts"] = await writer.check_facts(d.body, facts)
            except Exception as e:  # noqa: BLE001
                checks["facts"] = {"ok": True, "notes": f"사실 검사 생략: {e}"[:200]}
            too_similar = checks["similarity_to_source"] > 0.35 or checks["similarity_to_siblings"] > 0.35
            facts_ok = checks["facts"].get("ok", True)
            d.checks = checks
            d.tags = [keyword] if keyword else []
            d.status = "ready" if (checks["ok"] and facts_ok and not too_similar) else "needs_review"
            produced.append(d)
        except Exception as e:  # noqa: BLE001
            d.status = "failed"
            d.error = str(e)[:1000]
        await ctx.db.commit()
    if campaign_id:
        await _bump_stats(ctx, campaign_id)
    return {"parent_id": parent.id, "produced": len(produced), "facts": len(facts)}


# ─────────────────────────────── photo_tag ───────────────────────────────
@register("photo_tag")
async def photo_tag(ctx: JobContext) -> dict:
    from app.services import photo_tagger
    p = ctx.payload
    return await photo_tagger.tag_untagged(
        ctx.db, ctx.user_id, collection_id=p.get("collection_id"), limit=int(p.get("limit", 300)), progress=ctx.progress,
    )


# ─────────────────────────────── image_plan ───────────────────────────────
async def _collection_photos(db, user_id: str, collection_id: Optional[str]) -> List[Any]:
    """세트(또는 전체 풀)의 사진 메타만 읽는다. data(BLOB) 는 읽지 않는다."""
    cols = (
        PoolImage.id, PoolImage.scene, PoolImage.tags, PoolImage.caption, PoolImage.has_text,
        PoolImage.suitable_for, PoolImage.use_count, PoolImage.last_used_at,
    )
    q = select(*cols).where(PoolImage.user_id == user_id, PoolImage.active == True)  # noqa: E712
    if collection_id:
        q = q.join(PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id).where(
            PoolCollectionMember.collection_id == collection_id
        )
    q = q.order_by(PoolImage.use_count.asc(), PoolImage.created_at.asc())
    return (await db.execute(q)).all()


@register("image_plan")
async def image_plan(ctx: JobContext) -> dict:
    from app.services import photo_matcher as pm
    from app.services import photo_tagger

    p = ctx.payload
    campaign_id = p["campaign_id"]
    camp = await ctx.db.get(Campaign, campaign_id)
    collection_id = p.get("collection_id") or camp.collection_id
    if collection_id and not camp.collection_id:
        camp.collection_id = collection_id
        await ctx.db.commit()

    # 0) 미태깅 사진 먼저 태깅(비용은 사진당 1회)
    try:
        tag_res = await photo_tagger.tag_untagged(ctx.db, ctx.user_id, collection_id=collection_id, limit=300, progress=ctx.progress)
    except Exception as e:  # noqa: BLE001
        logger.warning("[사진계획] 태깅 단계 오류(계속 진행): %s", e)
        tag_res = {"error": str(e)}

    photos_rows = await _collection_photos(ctx.db, ctx.user_id, collection_id)
    photos = [
        pm.Photo(
            id=r.id, scene=r.scene, tags=list(r.tags or []), caption=r.caption, has_text=r.has_text,
            suitable_for=list(r.suitable_for or []), use_count=r.use_count or 0, last_used_at=r.last_used_at,
        )
        for r in photos_rows
    ]
    if not photos:
        raise ValueError("사진 세트에 사진이 없습니다. 먼저 사진 풀에 업로드하고 세트에 담아주세요.")

    q = select(Draft).where(Draft.campaign_id == campaign_id, Draft.status.in_(["ready", "needs_review"]), Draft.source != "upload")
    if p.get("draft_ids"):
        q = q.where(Draft.id.in_(p["draft_ids"]))
    drafts = (await ctx.db.execute(q.order_by(Draft.created_at.asc()))).scalars().all()
    # 변형 원본(parent)은 발행 대상이 아니므로 제외
    parent_ids = {d.parent_draft_id for d in drafts if d.parent_draft_id}
    drafts = [d for d in drafts if d.id not in parent_ids]

    default_count = int(p.get("image_count") or 0)
    recently: set = set()
    total = len(drafts)
    planned = 0
    for i, d in enumerate(drafts):
        if await ctx.cancelled():
            break
        n_img = default_count or d.image_count_target or 5
        n_img = max(1, min(20, n_img))
        await ctx.progress(i, total, f"사진 배치 {i + 1}/{total}: {d.title[:20]}")
        try:
            slots_raw = await writer.plan_image_slots(d.body, n_img, d.keyword or "")
        except Exception as e:  # noqa: BLE001
            logger.warning("[사진계획] 슬롯 계획 실패, 균등 배치: %s", e)
            slots_raw = []
        if not slots_raw:
            para_n = max(1, len([x for x in d.body.split("\n\n") if x.strip()]))
            slots = pm.fallback_slots(para_n, n_img)
            for sl in slots:  # matcher 의 fallback 은 1-based("N번째 문단 뒤") → 우리 계획은 0-based
                sl.after_paragraph = max(0, sl.after_paragraph - 1)
        else:
            slots = [pm.Slot(index=s["slot"], after_paragraph=s["after_paragraph"], need=s.get("need", ""), keywords=s.get("keywords", []), stage=s.get("stage", "기타")) for s in slots_raw]
        assigned = pm.assign(slots, photos, recently_used_ids=recently, allow_repeat=len(photos) < len(slots))
        need_by_slot = {s.index: s for s in slots}
        plan = []
        for a in assigned:
            s = need_by_slot.get(a["slot"])
            plan.append({
                "slot": a["slot"], "after_paragraph": a["after_paragraph"], "pool_image_id": a["pool_image_id"],
                "score": a.get("score"), "reason": a.get("reason"),
                "need": s.need if s else "", "keywords": s.keywords if s else [], "stage": s.stage if s else "기타",
            })
            recently.add(a["pool_image_id"])
        # 최근 사용 집합은 너무 커지지 않게(세트 크기의 절반)
        if len(recently) > max(4, len(photos) // 2):
            recently = set(list(recently)[-(len(photos) // 2):])
        d.image_plan = plan
        d.image_count_target = n_img
        planned += 1
        await ctx.db.commit()
    return {"planned": planned, "photos": len(photos), "tagging": tag_res}


# ─────────────────────────────── prepare_images ───────────────────────────────
async def prepare_job_images(db, job: PublishJob, draft: Draft) -> List[Dict[str, Any]]:
    """발행건 하나의 사진을 유니크화해 파일로 저장. [{slot, pool_image_id, path, phash}]"""
    out: List[Dict[str, Any]] = []
    plan = sorted(draft.image_plan or [], key=lambda s: (s.get("after_paragraph", 0), s.get("slot", 0)))
    if not plan:
        return out
    ids = list({s["pool_image_id"] for s in plan if s.get("pool_image_id")})
    imgs = {p.id: p for p in (await db.execute(select(PoolImage).where(PoolImage.id.in_(ids)))).scalars().all()} if ids else {}
    folder = media_dir("variants", job.id)
    for s in plan:
        pimg = imgs.get(s.get("pool_image_id"))
        if not pimg:
            continue
        srows = (await db.execute(
            select(ImageVariant.phash, ImageVariant.trim).where(ImageVariant.pool_image_id == pimg.id)
            .order_by(ImageVariant.created_at.desc()).limit(uniq.SIBLING_WINDOW)
        )).all()
        siblings = [h for (h, _t) in srows if h]
        result = await run_in_threadpool(uniq.uniquify, pimg.data, sibling_hashes=siblings, trim_start=(srows[0][1] if srows else None))
        path = folder / f"{int(s['slot']):02d}.jpg"
        path.write_bytes(result.image_bytes)
        db.add(ImageVariant(
            pool_image_id=pimg.id, user_id=job.user_id, phash=result.phash, dhash=result.dhash,
            frame_style=result.frame_style, ssim=result.ssim, min_distance=result.min_distance,
            passed=result.passed, attempts=result.attempts, trim=result.trim, post_id=job.id,
        ))
        pimg.use_count = (pimg.use_count or 0) + 1
        pimg.last_used_at = datetime.utcnow()
        out.append({"slot": s["slot"], "after_paragraph": s.get("after_paragraph", 0), "pool_image_id": pimg.id, "path": str(path), "phash": result.phash, "passed": result.passed})
    return out


@register("prepare_images")
async def prepare_images(ctx: JobContext) -> dict:
    p = ctx.payload
    q = select(PublishJob).where(PublishJob.images_ready == False, PublishJob.status.in_(["queued", "assigned"]))  # noqa: E712
    if p.get("campaign_id"):
        q = q.where(PublishJob.campaign_id == p["campaign_id"])
    if p.get("job_ids"):
        q = q.where(PublishJob.id.in_(p["job_ids"]))
    jobs = (await ctx.db.execute(q.order_by(PublishJob.scheduled_at.asc()))).scalars().all()
    total = len(jobs)
    done = 0
    for j in jobs:
        if await ctx.cancelled():
            break
        draft = await ctx.db.get(Draft, j.draft_id)
        if not draft:
            continue
        await ctx.progress(done, total, f"사진 준비 {done + 1}/{total}: {draft.title[:20]}")
        try:
            j.image_variants = await prepare_job_images(ctx.db, j, draft)
            j.images_ready = True
        except Exception as e:  # noqa: BLE001
            logger.error("[사진준비] %s 실패: %s", j.id, e)
            j.error = f"사진 준비 실패: {e}"[:500]
        done += 1
        await ctx.db.commit()
    return {"prepared": done}


# ─────────────────────────────── sheet_append ───────────────────────────────
@register("sheet_append")
async def sheet_append(ctx: JobContext) -> dict:
    from app.services import google_sheets_service as gs
    p = ctx.payload
    client = await ctx.db.get(Client, p["client_id"])
    if not client or not client.sheet_url:
        raise ValueError("병원에 구글시트 주소가 없습니다")
    if not gs.is_write_configured():
        raise ValueError("시트 쓰기에는 서비스 계정 키(GOOGLE_SERVICE_ACCOUNT_JSON)가 필요합니다")
    rows = p.get("rows") or []
    n = await gs.append_rows(client.sheet_url, p.get("tab") or client.sheet_blog_tab or "블로그", rows)
    return {"appended": n}


def image_as_data_url(path: str) -> Optional[str]:
    try:
        b = Path(path).read_bytes()
    except Exception:  # noqa: BLE001
        return None
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()
