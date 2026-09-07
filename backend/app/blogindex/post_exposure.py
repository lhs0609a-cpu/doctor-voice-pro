"""
글별 누락/순위 카드 (문서 1-6 보조, post_exposure_analyzer)

최근 글 N개를 제목 정확매칭(따옴표) 질의로 블로그탭·VIEW탭에서 찾아 순위를 표시한다.
  · 30위 밖 미노출 = 저품질 강한 신호 / 게시 후 24h(72h) 지나도 미색인 = 휴면/저품질 (5장 기준)
  · None 은 '미노출' 과 '측정불가' 가 섞이므로 measured 플래그로 구분해 표시한다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.blogindex import DISCLAIMER_INDEX, normalize_blog_id
from app.blogindex import serp as serp_mod
from app.blogindex.verifier import (LATENCY_NORMAL_HOURS, LATENCY_SLOW_HOURS, SEARCH_TOP_K, _quoted,
                                    age_hours, parse_pub_date)

logger = logging.getLogger(__name__)

SAMPLE_DEFAULT = 10
CONCURRENCY = 3


async def _card(sem: asyncio.Semaphore, blog_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title") or ""
    post_url = item.get("link") or ""
    quoted = _quoted(title)
    pub = parse_pub_date(item.get("pub_date"))
    hours = age_hours(pub)
    card = {
        "title": title, "post_url": post_url, "post_no": item.get("post_no"),
        "pub_date": item.get("pub_date"), "age_hours": None if hours is None else round(hours, 1),
        "query": quoted, "blog_tab_rank": None, "view_tab_rank": None,
        "blog_tab_measured": False, "view_tab_measured": False,
        "label": "노출안됨", "missing_after_24h": False, "missing_after_72h": False,
    }
    if not quoted:
        return card
    async with sem:
        async with serp_mod.fresh_session() as s:
            try:
                rows = await serp_mod._serp_rows_upto(s, quoted, SEARCH_TOP_K)
                if rows is not None:
                    card["blog_tab_measured"] = True
                    card["blog_tab_rank"] = serp_mod._find_rank(rows, blog_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("[post_exposure] 블로그탭 실패 (%s): %s", title[:20], e)
            try:
                vs = await serp_mod.view_tab_serp(s, quoted)
                if vs is not None:
                    card["view_tab_measured"] = True
                    target = serp_mod._post_no_of(post_url)
                    for r in vs["rows"][:SEARCH_TOP_K]:
                        if target and r.get("post_no") == target:
                            card["view_tab_rank"] = int(r["rank"])
                            break
            except Exception as e:  # noqa: BLE001
                logger.warning("[post_exposure] VIEW탭 실패 (%s): %s", title[:20], e)
    card["label"] = serp_mod.rank_label(card["blog_tab_rank"]) if card["blog_tab_measured"] else "측정불가"
    if card["blog_tab_measured"] and card["blog_tab_rank"] is None and hours is not None:
        card["missing_after_24h"] = hours >= LATENCY_NORMAL_HOURS
        card["missing_after_72h"] = hours >= LATENCY_SLOW_HOURS
    return card


async def post_exposure_cards(db, blog_id: str, sample: int = SAMPLE_DEFAULT) -> Dict[str, Any]:
    from app.blogindex import collectors  # 지연 import
    blog_id = normalize_blog_id(blog_id)
    try:
        rss = await collectors.fetch_rss(blog_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("[post_exposure] RSS 실패 %s: %s", blog_id, e)
        rss = None
    if not rss or not rss.get("ok") or not rss.get("items"):
        return {"ok": False, "blog_id": blog_id, "error": "no_posts_via_rss",
                "message": "RSS에서 글을 가져오지 못했습니다.", "cards": [], "disclaimer": DISCLAIMER_INDEX}

    items: List[Dict[str, Any]] = list(rss["items"])[:max(1, int(sample))]
    sem = asyncio.Semaphore(CONCURRENCY)
    cards = await asyncio.gather(*[_card(sem, blog_id, it) for it in items])

    measured = [c for c in cards if c["blog_tab_measured"]]
    summary = {
        "sample_size": len(cards),
        "measured": len(measured),
        "indexed_blog_tab": sum(1 for c in measured if c["blog_tab_rank"] is not None),
        "indexed_view_tab": sum(1 for c in cards if c["view_tab_rank"] is not None),
        "missing_after_24h": sum(1 for c in cards if c["missing_after_24h"]),
        "missing_after_72h": sum(1 for c in cards if c["missing_after_72h"]),
        "top3": sum(1 for c in measured if c["blog_tab_rank"] is not None and c["blog_tab_rank"] <= 3),
    }
    return {"ok": True, "blog_id": blog_id, "blog_name": rss.get("blog_name"), "cards": cards,
            "summary": summary, "measured_at": datetime.utcnow().isoformat(), "disclaimer": DISCLAIMER_INDEX}
