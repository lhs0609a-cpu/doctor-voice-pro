"""
블로그 지수 라이브 테스트 (네트워크 필요).
    cd backend && python test_blog_index_live.py [blog_id ...]

  1) 단위 검산: 절대 기준표 / 카테고리 감지
  2) 실제 공개 블로그 분석 → stats / index / breakdown 출력, 0~100 / 검산(2-10) assert
  3) score_blog_light 2회 → 두 번째는 6h 캐시 hit
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")

from app.db.database import AsyncSessionLocal, Base, engine  # noqa: E402
# User 매퍼가 'NaverBlog'(blog_outreach) 를 참조하는데 app.models/__init__ 이 그 모듈을 안 불러온다.
# main.py 는 startup 에서 따로 import 하므로, 스크립트에서는 첫 DB 사용 전에 직접 불러온다.
import app.models  # noqa: E402,F401
import app.models.blog_outreach  # noqa: E402,F401
from sqlalchemy.orm import configure_mappers  # noqa: E402
configure_mappers()
from app.blogindex import analyzer, collectors, scoring, weights  # noqa: E402

DEFAULT_BLOGS = ["ranto28", "naverschool"]


def unit_checks() -> None:
    assert scoring.get_blog_level_from_score(89.9) == (15, "최적4+"), scoring.get_blog_level_from_score(89.9)
    assert scoring.get_blog_level_from_score(83.6) == (9, "최적1")
    assert scoring.get_blog_level_from_score(76.2) == (6, "준최5")
    assert scoring.get_blog_level_from_score(7.6) == (2, "준최1")
    assert scoring.get_blog_level_from_score(5.0) == (1, "일반")
    assert scoring.get_level_from_percentile(50.0) == (6, "준최5")
    assert scoring.get_level_from_percentile(2.9) == (1, "일반")
    assert weights.detect_keyword_category("강남 임플란트 후기") == "의료"
    assert weights.detect_keyword_category("다이슨 청소기 후기") == "인테리어"
    assert weights.detect_keyword_category("내돈내산 솔직 사용기") == "리뷰"
    assert weights.detect_keyword_category("") == "default"
    w = weights.resolve_scoring_weights("강남 맛집")
    main = [w["c_rank"]["weight"], w["dia"]["weight"], w["content_factors"]["weight"]]
    assert abs(sum(main) - 1.0) < 0.01, main
    assert w["_category"] == "맛집" and w["_learned"] is False
    assert main == [0.238, 0.238, 0.524], main   # 13-2 예시: 맛집 (0.25,0.25,0.60) → (0.238,0.238,0.524)
    ps = scoring.calculate_post_score({"title_has_keyword": True, "title_keyword_position": 0,
                                       "keyword_density": 20, "content_length": 3000, "image_count": 10,
                                       "video_count": 1, "paragraph_count": 20, "heading_count": 3,
                                       "like_count": 30, "comment_count": 10, "post_age_days": 3})
    assert ps["total"] == round((95 + 95 + 90 + 95 + 85 + 95) / 6, 1), ps   # richness = 50 + 30(img cap) + 10(video x1)
    print("[OK] unit checks: _LEVEL_CUTS / percentile / detect_keyword_category / weights clamp / post score")


def check_breakdown(res: dict) -> None:
    idx = res["index"]
    score = idx["total_score"]
    assert score is not None and 0 <= score <= 100, score
    bd = idx["score_breakdown"]
    parts = [bd["c_rank"], bd["dia"]] + ([bd["content_factors"]] if bd["content_factors"] is not None else [])
    base = sum(parts)
    # 2-10: c_rank + dia + content_factors == base_score. total = (base + extra [*0.9]) * vitality
    penalty = 1.0 if ("scrape" in res["data_sources"] or not res["data_sources"]) else (0.9 if len(res["data_sources"]) == 1 else 1.0)
    expected = min(round((base + idx["extra_bonus"]) * penalty * idx["vitality"], 1), 100) if res["data_sources"] else 25 * idx["vitality"]
    diff = abs(expected - score)
    print(f"    검산: c_rank {bd['c_rank']} + dia {bd['dia']} + cf {bd['content_factors']} = base {base:.1f}; "
          f"(+extra {idx['extra_bonus']}) x penalty {penalty} x vitality {idx['vitality']} = {expected:.1f} vs total {score} (diff {diff:.2f})")
    assert diff <= 0.35, f"breakdown 검산 실패: expected {expected} got {score}"   # 반올림 3개소 허용 오차


async def run_blog(db, blog_id: str) -> dict:
    t0 = time.monotonic()
    res = await analyzer.analyze_blog(db, blog_id, use_cache=False, fullparse=True)
    dt = time.monotonic() - t0
    print(f"\n=== {blog_id} ({dt:.1f}s) success={res['success']} error={res.get('error_code')} {res.get('error_message') or ''}")
    print("  blog_name:", res["blog_name"], "| naver_level:", res["naver_level"], "| data_sources:", res["data_sources"])
    print("  stats:", json.dumps({k: v for k, v in res["stats"].items() if k != "visitor_series"}, ensure_ascii=False))
    print("  visitor_series:", res["stats"]["visitor_series"])
    print("  estimated_fields:", res["estimated_fields"], "| unmeasured:", res["unmeasured"], "| rss_empty:", res["rss_empty"])
    idx = res["index"]
    print("  index:", json.dumps({k: v for k, v in idx.items() if k != "score_breakdown"}, ensure_ascii=False))
    bd = idx.get("score_breakdown")
    if bd:
        print("  breakdown:", json.dumps({k: v for k, v in bd.items() if k not in ("raw_signals", "weights_used")}, ensure_ascii=False))
        print("  weights_used:", json.dumps(bd["weights_used"], ensure_ascii=False))
        print("  raw_signals:", json.dumps(bd["raw_signals"], ensure_ascii=False))
    if res["success"]:
        check_breakdown(res)
    return res


async def main(blog_ids) -> int:
    unit_checks()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    failures = 0
    async with AsyncSessionLocal() as db:
        # 수집기 단독 확인 (첫 블로그)
        first = blog_ids[0]
        s, v, r = await asyncio.gather(collectors.scrape_blog_stats(first),
                                       collectors.fetch_visitor_series(first),
                                       collectors.fetch_rss(first))
        print(f"[collectors] scrape={json.dumps(s, ensure_ascii=False)}")
        print(f"[collectors] visitors measured={v['measured']} today={v['today']} recent_avg={v['recent_avg']} n={len(v['series'])}")
        print(f"[collectors] rss ok={r['ok']} empty={r['rss_empty']} items={len(r['items'])} name={r['blog_name']} analysis={json.dumps(r['analysis'], ensure_ascii=False)}")

        for bid in blog_ids:
            try:
                res = await run_blog(db, bid)
                if not res["success"]:
                    failures += 1
            except AssertionError as e:
                failures += 1
                print("  [FAIL]", e)

        # score_blog_light 2회 — 두 번째는 캐시
        bid = blog_ids[0]
        t0 = time.monotonic()
        a = await analyzer.score_blog_light(db, bid, use_cache=True)
        t1 = time.monotonic()
        b = await analyzer.score_blog_light(db, bid, use_cache=True)
        t2 = time.monotonic()
        print(f"\n[score_blog_light] 1st ({t1 - t0:.2f}s): {a}")
        print(f"[score_blog_light] 2nd ({t2 - t1:.2f}s): {b}")
        if a is not None and b is not None:
            assert b["cached"] is True and b["score"] == a["score"], "2nd call should be cached"
            print("[OK] second score_blog_light call served from CompetitorScore cache")
        else:
            failures += 1
            print("[FAIL] score_blog_light returned None")

        # 1h 스냅샷 캐시 확인
        t0 = time.monotonic()
        c = await analyzer.analyze_blog(db, bid, use_cache=True)
        print(f"[snapshot cache] analyze_blog(use_cache=True) {time.monotonic() - t0:.2f}s cached={c.get('cached')} score={c['index']['total_score']}")

    await engine.dispose()
    print("\nDONE failures =", failures)
    return failures


if __name__ == "__main__":
    ids = sys.argv[1:] or DEFAULT_BLOGS
    sys.exit(1 if asyncio.run(main(ids)) else 0)
