"""
상위노출 가능성 판정(B) 포팅 검증 스크립트 — 단위 테스트 + 라이브 SERP.

  python test_blog_verdict_live.py            # 단위 + 라이브
  python test_blog_verdict_live.py --unit     # 단위만

라이브 부분은 네트워크/차단 상태에 따라 결과가 달라진다. 차단이면 LAST_HTTP_DEBUG
(status / size / links / parse_mode)를 그대로 출력해 무엇이 왔는지 보고한다.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import app.main  # noqa: F401  — 모델 등록

from app.db.database import AsyncSessionLocal, Base, engine
from app.blogindex import serp, keyword_verdict, seo_difficulty, judge_v1, exposure_ceiling
from app.blogindex import competition_analyzer as ca
from app.blogindex import verifier, serp_difficulty

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [ok]   {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def _comp(rank, score, idle=3):
    return {"rank": rank, "blog_id": f"b{rank}", "score": score, "recent_activity_days": idle}


def unit_tests():
    print("== unit: compute_verdict ==")
    strong = [_comp(i + 1, 60 + i) for i in range(10)]
    v = keyword_verdict.compute_verdict(my={"score": 85.0}, competitors=strong, volume=1000, my_rank=None,
                                        topical=5, ceiling=None, serp_reliable=True)
    check("strong me → likely", v["verdict"] == "likely", v)
    check("probability capped 0.90", v["probability"] <= 0.90, v["probability"])
    check("cut_line = min", v["cut_line"] == 60.0, v["cut_line"])
    check("entry_bar = mean of lowest 2", v["entry_bar"] == 60.5, v["entry_bar"])
    check("confidence high (>=7 scored + topical)", v["confidence"] == "high", v["confidence"])
    check("reason has gap sentence", any("점 위입니다" in r for r in v["reasons"]), v["reasons"])

    weak_comps = [_comp(i + 1, 70 + i) for i in range(10)]
    v2 = keyword_verdict.compute_verdict(my={"score": 40.0}, competitors=weak_comps, volume=1000, my_rank=None,
                                         topical=0, ceiling=None)
    check("weak me → unlikely", v2["verdict"] == "unlikely", v2)
    check("probability floor 0.02", v2["probability"] >= 0.02, v2["probability"])
    check("topical==0 sentence", any("주제 적합도가 약합니다" in r for r in v2["reasons"]), v2["reasons"])

    few = [_comp(1, 70), _comp(2, 71), _comp(11, 50), _comp(12, 55)]
    v3 = keyword_verdict.compute_verdict(my={"score": 80.0}, competitors=few, volume=100, my_rank=None,
                                         topical=None, ceiling=None)
    check("<3 scored → unknown", v3["verdict"] == "unknown" and v3["probability"] is None, v3)
    v4 = keyword_verdict.compute_verdict(my=None, competitors=strong, volume=100, my_rank=None, topical=None, ceiling=None)
    check("my None → unknown (never 0)", v4["verdict"] == "unknown" and v4["probability"] is None, v4)

    # vacancy + indexed30 + ceiling_head + fallback parsing
    dormant = [_comp(i + 1, 65, idle=200 if i < 4 else 3) for i in range(10)]
    v5 = keyword_verdict.compute_verdict(my={"score": 66.0}, competitors=dormant, volume=500, my_rank=15,
                                         topical=3, ceiling={"ceiling_p50": 5000}, serp_reliable=False)
    check("vacancy_count 4", v5["vacancy_count"] == 4, v5["vacancy_count"])
    check("indexed30 feature", v5["features"]["indexed30"] == 1.0, v5["features"])
    check("ceiling_head = log10(5001/501)=1.0", abs(v5["features"]["ceiling_head"] - 0.999) < 0.01, v5["features"])
    check("fallback parsing → confidence low + warning", v5["confidence"] == "low"
          and any("폴백" in r for r in v5["reasons"]), v5)
    check("model version", v5["model_version"] == "v1-heuristic", v5["model_version"])

    print("== unit: compute_difficulty ==")
    s, l, b = seo_difficulty.compute_difficulty(top10_min_score=60, top10_avg_score=70, median_vitality=1.0, search_volume=1000)
    check("score 69.0 / hard", s == 69.0 and l == "hard", (s, l, b))
    s2, l2, b2 = seo_difficulty.compute_difficulty(top10_min_score=None, top10_avg_score=None, median_vitality=1.0, search_volume=1000)
    check("missing scores → None/unknown", s2 is None and l2 == "unknown" and b2.get("reason") == "top10_score_missing", (s2, l2, b2))
    s3, l3, b3 = seo_difficulty.compute_difficulty(top10_min_score=30, top10_avg_score=40, median_vitality=None, search_volume=None)
    check("no vitality/no volume → 2 parts", set(b3) == {"entry_bar", "field"} and s3 == 34.0, (s3, l3, b3))
    check("label boundaries", [seo_difficulty.label_for(x) for x in (72, 58, 44, 30, 29.9, None)]
          == ["very_hard", "hard", "moderate", "easy", "very_easy", "unknown"])
    check("demand pressure 10→20, 1000→60, 100000→100",
          seo_difficulty._demand_pressure(10) == 20.0 and abs(seo_difficulty._demand_pressure(1000) - 60) < 1e-9
          and seo_difficulty._demand_pressure(100000) == 100.0 and seo_difficulty._demand_pressure(0) is None)

    print("== unit: judge_keyword (v1) ==")
    ceil = {"ok": True, "ceiling_volume": 5000, "ceiling_p50": 1000, "confidence": "high"}
    j1 = judge_v1.judge_keyword(ceil, 500)
    check("≤p50 → likely 0.75", j1["verdict"] == "likely" and j1["probability"] == 0.75, j1)
    j2 = judge_v1.judge_keyword(ceil, 3000)
    check("p50<v≤ceil → contested 0.45", j2["verdict"] == "contested" and j2["probability"] == 0.45, j2)
    j3 = judge_v1.judge_keyword(ceil, 20000)
    check("v>ceil → unlikely, prob=max(0.03, 0.2*5000/20000)=0.05", j3["verdict"] == "unlikely" and j3["probability"] == 0.05, j3)
    j4 = judge_v1.judge_keyword(ceil, 20000, serp={"ok": True, "difficulty_label": "very_easy"})
    check("very_easy → up one step (contested), +0.12", j4["verdict"] == "contested" and j4["serp_adjustment"] == "up"
          and j4["probability"] == 0.17, j4)
    j5 = judge_v1.judge_keyword({**ceil, "confidence": "low"}, 500)
    check("low confidence shrink: 0.35+0.35*(0.75-0.35)=0.49", j5["probability"] == 0.49, j5)
    j6 = judge_v1.judge_keyword({"ok": False}, 500)
    check("no ceiling → unknown None", j6["verdict"] == "unknown" and j6["probability"] is None, j6)
    j7 = judge_v1.judge_keyword({"ok": False}, 500, serp={"ok": True, "difficulty_label": "easy"})
    check("no ceiling + easy serp → contested 0.30", j7["verdict"] == "contested" and j7["probability"] == 0.30, j7)
    j8 = judge_v1.judge_keyword(ceil, 500, serp={"ok": True, "difficulty_label": "very_hard"})
    check("very_hard → down one step, likely→contested", j8["verdict"] == "contested" and j8["probability"] == 0.63, j8)
    check("v1 cap 0.95", judge_v1.judge_keyword(ceil, 10, serp={"ok": True, "difficulty_label": "easy"})["probability"] <= 0.95)

    print("== unit: ceiling_from_observations ==")
    rows = [{"keyword": "a", "volume": 3000, "rank": 1}, {"keyword": "b", "volume": 800, "rank": 5},
            {"keyword": "c", "volume": 400, "rank": 10}, {"keyword": "d", "volume": 9000, "rank": 20},
            {"keyword": "e", "volume": 50000, "rank": None}, {"keyword": "f", "volume": 20, "rank": None}]
    c = exposure_ceiling.ceiling_from_observations(rows)
    check("ceiling_volume 3000", c["ceiling_volume"] == 3000, c)
    check("ceiling_p50 800", c["ceiling_p50"] == 800, c)
    check("top30_ceiling 9000", c["top30_ceiling"] == 9000, c)
    check("win_rate 0.5", c["win_rate"] == 0.5, c)
    check("confidence medium (6 tested, 3 page1)", c["confidence"] == "medium", c)
    check("ranked_keywords sorted by volume desc", [r["keyword"] for r in c["ranked_keywords"]] == ["d", "a", "b", "c"])
    c0 = exposure_ceiling.ceiling_from_observations([])
    check("empty → None ceilings, win_rate 0.0", c0["ceiling_volume"] is None and c0["win_rate"] == 0.0)
    check("_confidence 12/4 high, 11/4 medium, 5/2 low", exposure_ceiling._confidence(12, 4) == "high"
          and exposure_ceiling._confidence(11, 4) == "medium" and exposure_ceiling._confidence(5, 2) == "low")
    check("_char_bigrams", exposure_ceiling._char_bigrams("경희온담한의원") == {"경희", "희온", "온담", "담한", "한의", "의원"})
    # 7-3 확장 필터: 흔한 슁글(한의/의원)만 겹치는 연관어는 제외, 변별 슁글(아토/토피)이 겹치면 포함
    core = ["강남아토피", "한의원"]
    wanted = {"강남아토피": {"keyword": "강남아토피", "total_volume": 500}, "한의원": {"keyword": "한의원", "total_volume": 9000}}
    related = {"역삼아토피": {"keyword": "역삼아토피", "total_volume": 120},
               "부산한의원": {"keyword": "부산한의원", "total_volume": 8000},
               "자율신경실조증": {"keyword": "자율신경실조증", "total_volume": 3000}}
    cands = exposure_ceiling._expand_candidates(core, wanted, related)
    check("expand: bigram overlap filter", [c["keyword"] for c in cands] == ["한의원", "강남아토피", "역삼아토피"], cands)
    # 7-4 exploit/explore: indexed 8 + explore 2 = 10, 볼륨순 유지
    pre = [{"keyword": f"k{i}", "volume": 1000 - i, "openapi_rank": (5 if i % 3 else None)} for i in range(15)]
    plan = exposure_ceiling._plan_confirms(pre)
    idx_kw = [p["keyword"] for p in pre if p["openapi_rank"] is not None][:8]
    non_kw = [p["keyword"] for p in pre if p["openapi_rank"] is None][:2]
    check("plan_confirms exploit 8 + explore 2", [p["keyword"] for p in plan] == idx_kw + non_kw and len(plan) == 10, plan)
    plan2 = exposure_ceiling._plan_confirms(pre[:4])
    check("plan_confirms fills from remaining when short", len(plan2) == 4 and len({p["keyword"] for p in plan2}) == 4)

    print("== unit: calculate_entry_probability (12-3) ==")
    bs = ca.BlogStats(min_score=60, high_scorer_count=0, elite_scorer_count=0)
    cr = ca.ContentRelevance(title_keyword_ratio=0.3)
    check("my None, comp 20 → 75", ca.calculate_entry_probability(None, 20, bs, cr) == 75)
    check("my None, comp 75 → 15", ca.calculate_entry_probability(None, 75, bs, cr) == 15)
    check("my 80 vs min 60, comp 40 → 60+20 = 80", ca.calculate_entry_probability(80, 40, bs, cr) == 80)
    bs2 = ca.BlogStats(min_score=70, high_scorer_count=6, elite_scorer_count=3)
    cr2 = ca.ContentRelevance(title_keyword_ratio=0.8)
    check("my 50 vs min 70, comp 60, elite 3, ratio .8 → clamp 5", ca.calculate_entry_probability(50, 60, bs2, cr2) == 5)
    check("labels", [ca.difficulty_label(x)[1] for x in (70, 55, 40, 25, 24)] == ["VERY_HARD", "HARD", "MODERATE", "EASY", "VERY_EASY"])
    posts = [{"title_has_keyword": True, "keyword_density": 2.0, "post_age_days": 3, "like_count": 60, "comment_count": 5},
             {"title_has_keyword": False, "keyword_density": 0.0, "post_age_days": 100, "like_count": 1, "comment_count": 0}]
    crx = ca.content_relevance_axis(posts)
    check("content_relevance axis", abs(crx.score - (0.5 * 100 * 0.4 + 100 * 0.3 + 50 * 0.3)) < 1e-9, crx)
    check("blog_score axis", abs(ca.blog_score_axis([90, 80, 60]).score - (76.666667 * 0.4 + 66.666667 * 0.35 + 33.333333 * 0.25)) < 1e-3)

    print("== unit: SERP HTML parsers ==")
    html = """
    <ul class="lst_total"><li class="info_item"><a href="https://blog.naver.com/carousel1/111">캐러셀</a></li></ul>
    <div class="q8qyx0TaRoC1n7jj fds-ugc-single-intention-item-list-tab abc">
      <a href="https://blog.naver.com/first_blog/1001"><img/></a>
      <a href="https://blog.naver.com/first_blog/1001">첫 번째 글 제목 새 창 열림</a>
      <a href="https://blog.naver.com/second-blog/2002?from=x">두 번째 새창 열림</a>
      <a href="https://blog.naver.com/first_blog/1003">같은 블로그 다른 글</a>
      <a href="https://blog.naver.com/Third/3003">셋째</a>
    </div>"""
    rows, mode, found = serp.parse_blog_tab_html(html)
    check("container found → list", mode == "list" and found)
    check("carousel excluded, dedupe by blog_id, rank order",
          [r["blog_id"] for r in rows] == ["first_blog", "second-blog", "Third"], rows)
    check("'새 창 열림' stripped + title from 2nd anchor", rows[0]["title"] == "첫 번째 글 제목" and rows[1]["title"] == "두 번째", rows)
    check("post_url normalized", rows[1]["post_url"] == "https://blog.naver.com/second-blog/2002")
    rows2, mode2, found2 = serp.parse_blog_tab_html('<div><a href="https://blog.naver.com/x/1">x</a></div>')
    check("no container → regex fallback", mode2 == "regex" and not found2 and rows2[0]["blog_id"] == "x")
    check("no-result page marker vs reduced page",
          serp.is_no_result_page('<div id="notfound" class="api_noresult_wrap"><p>…에 대한 검색결과가 없습니다.</p></div>')
          and not serp.is_no_result_page("<html><body><div class='reduced'></div></body></html>"))
    view_html = ('<a href="https://blog.naver.com/adblog/1?ad=1">ad</a><a href="https://blog.naver.com/p1/100?x=1">a</a>'
                 '<a href="https://blog.naver.com/p1/100">dup</a><a href="https://blog.naver.com/PostView.naver?blogId=p2&logNo=200">b</a>')
    vrows = serp.parse_view_tab_html(view_html)
    check("view tab: ad excluded, dedupe, logNo", [(r["blog_id"], r["post_no"]) for r in vrows] == [("p1", "100"), ("p2", "200")], vrows)
    check("rank_label", [serp.rank_label(x) for x in (None, 1, 3, 4, 7, 8, 10)]
          == ["노출안됨", "상위권", "상위권", "중위권", "중위권", "하위권", "하위권"])

    print("== unit: verifier helpers ==")
    check("_clean_title", verifier._clean_title("강남 아토피!! 한의원 (후기) #1") == "강남 아토피 한의원 후기 1")
    check("_quoted", verifier._quoted("a,b") == '"a b"' and verifier._quoted("!!!") == "")
    check("_extract_keywords stopwords (한글 2+, 영문 3+)", verifier._extract_keywords("오늘 강남아토피 후기 ab abc 리뷰") == ["강남아토피", "abc"])
    lv = [verifier._to_detailed_level(s) for s in (34.9, 35, 64.9, 65, 84.9, 85, 100)]
    check("_to_detailed_level interpolation", lv == [(1, "일반"), (2, "준최1"), (8, "준최7"), (9, "최적1"), (11, "최적3"), (12, "최적1+"), (15, "최적4+")], lv)
    check("latency: indexed <12h → 100 very_fast", verifier._latency_score(5, True) == (100.0, "very_fast"))
    check("latency: missing ≥24h → 0", verifier._latency_score(30, False) == (0.0, "missing_after_24h"))
    check("latency: too recent → 40", verifier._latency_score(10, False) == (40.0, "too_recent_to_judge"))
    check("vitality_from_gap", [serp_difficulty._vitality_from_gap(x) for x in (None, 7, 30, 60, 90, 180, 365, 366)]
          == [0.6, 1.0, 0.95, 0.82, 0.65, 0.42, 0.25, 0.15])

    print("== unit: count_keyword_related_posts (10-4) ==")
    posts = [{"title": "강남 아토피 치료 후기", "description": "", "category": ""},
             {"title": "아토피 관리법", "description": "강남에서", "category": ""},
             {"title": "다른 글", "description": "", "category": "아토피"},
             {"title": "무관", "description": "무관", "category": ""}]
    n = keyword_verdict.count_keyword_related_posts("강남 아토피", posts)
    check("full 1 (both parts) + full 1 + partial(category) 1 → 2 + 0 = 2", n == 2, n)
    one = {"title": "아토피 이야기", "description": "", "category": ""}
    check("generic parts removed: 1 significant part hit = partial → 2 posts = 1",
          keyword_verdict.count_keyword_related_posts("아토피 추천", [one]) == 0
          and keyword_verdict.count_keyword_related_posts("아토피 추천", [one, one]) == 1)
    check("load_model default", keyword_verdict.load_model()["weights"]["score_margin"] == 1.15)

    print(f"\nunit result: {PASS} passed, {FAIL} failed")


async def live():
    print("\n== live ==")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        t0 = time.time()
        res = await serp.blog_tab_serp(db, "강남아토피", limit=20, use_cache=True)
        print(f"blog_tab_serp('강남아토피') {time.time() - t0:.1f}s → LAST_HTTP_DEBUG={json.dumps(serp.LAST_HTTP_DEBUG, ensure_ascii=False)}")
        if res is None:
            print("  → None (측정불가). playwright available:", serp._POOL.available)
        else:
            print(f"  parse_mode={res['parse_mode']} source={res['source']} cached={res['cached']} rows={len(res['rows'])} endpoint={res.get('endpoint')} html_size={res.get('html_size')}")
            for r in res["rows"][:5]:
                print(f"   {r['rank']:>2}. {r['blog_id']:<20} {r['post_no']:<14} {r['title'][:40]}")

        t0 = time.time()
        facts = await keyword_verdict.stage1_facts(db, "ahcherb", "강남아토피")
        fx = facts.get("facts") or {}
        print(f"\nstage1_facts(ahcherb, 강남아토피) {time.time() - t0:.1f}s ok={facts['ok']} msg={facts.get('message')}")
        print(f"  my_rank={fx.get('my_rank')} already_page1={fx.get('already_page1')} volume={fx.get('volume')} measured={fx.get('volume_measured')} "
              f"serp_source={fx.get('serp_source')} parse_mode={fx.get('serp_parse_mode')} cached={fx.get('serp_cached')} size={fx.get('serp_size')}")
        for p in fx.get("page1") or []:
            print(f"   {p['rank']:>2}. {p['blog_id']:<20} {p['post_title'][:40]}")

        t0 = time.time()
        prog = []
        v = await keyword_verdict.stage2_verdict(db, "ahcherb", "강남아토피", facts=facts,
                                                 progress=lambda d, t: prog.append((d, t)))
        print(f"\nstage2_verdict {time.time() - t0:.1f}s (elapsed field {v.get('elapsed')}) progress_events={len(prog)}")
        print(f"  verdict={v.get('verdict')} probability={v.get('probability')} confidence={v.get('confidence')} "
              f"cut_line={v.get('cut_line')} entry_bar={v.get('entry_bar')} median={v.get('median_score')} my_score={v.get('my_score')}")
        print(f"  scored_competitors={v.get('scored_competitors')} topical_posts={v.get('topical_posts')} ceiling={v.get('ceiling')}")
        print(f"  difficulty={json.dumps(v.get('difficulty'), ensure_ascii=False)}")
        for r in v.get("reasons") or []:
            print(f"  - {r}")
        for c in v.get("competitors") or []:
            print(f"   {c['rank']:>2}. {c['blog_id']:<20} score={c.get('score')} grade={c.get('grade')} idle={c.get('recent_activity_days')} measured={c.get('measured')}")

        # 1페이지에 없는 블로그로 경쟁자 채점 경로(컷라인)까지 태운다
        other = "naverschool"
        t0 = time.time()
        prog = []
        v = await keyword_verdict.stage2_verdict(db, other, "강남아토피", progress=lambda d, t: prog.append((d, t)))
        print(f"\nstage2_verdict({other}) {time.time() - t0:.1f}s (elapsed field {v.get('elapsed')}) progress_events={len(prog)}")
        print(f"  ok={v.get('ok')} my_rank={(v.get('facts') or {}).get('my_rank')} verdict={v.get('verdict')} probability={v.get('probability')} "
              f"confidence={v.get('confidence')} cut_line={v.get('cut_line')} entry_bar={v.get('entry_bar')} median={v.get('median_score')} my_score={v.get('my_score')}")
        print(f"  my={v.get('my')} scored_competitors={v.get('scored_competitors')} topical_posts={v.get('topical_posts')} "
              f"vacancy_count={v.get('vacancy_count')} features={v.get('features')}")
        print(f"  difficulty={json.dumps(v.get('difficulty'), ensure_ascii=False)}")
        for r in v.get("reasons") or []:
            print(f"  - {r}")
        for c in v.get("competitors") or []:
            print(f"   {c['rank']:>2}. {c['blog_id']:<20} score={c.get('score')} grade={c.get('grade')} idle={c.get('recent_activity_days')} measured={c.get('measured')}")

        t0 = time.time()
        sd = await serp_difficulty.serp_difficulty(db, "강남아토피")
        print(f"\nserp_difficulty {time.time() - t0:.1f}s ok={sd.get('ok')} score={sd.get('difficulty_score')} label={sd.get('difficulty_label')} "
              f"alive={sd.get('alive_ratio')} dormant={sd.get('dormant_ratio')} measured={sd.get('measured_count')} conf={sd.get('confidence')}")

        from app.blogindex import post_exposure
        t0 = time.time()
        pe = await post_exposure.post_exposure_cards(db, "ahcherb", sample=3)
        print(f"\npost_exposure_cards(ahcherb, 3) {time.time() - t0:.1f}s ok={pe.get('ok')} summary={pe.get('summary')}")
        for c in pe.get("cards") or []:
            print(f"   blog_tab={c['blog_tab_rank']} view={c['view_tab_rank']} label={c['label']} measured={c['blog_tab_measured']} "
                  f"age_h={c['age_hours']} missing24={c['missing_after_24h']} | {c['title'][:35]}")

        t0 = time.time()
        ce = await exposure_ceiling.measure_ceiling(db, "ahcherb")
        print(f"\nmeasure_ceiling(ahcherb) {time.time() - t0:.1f}s ok={ce.get('ok')} error={ce.get('error')} "
              f"ceiling_volume={ce.get('ceiling_volume')} p50={ce.get('ceiling_p50')} conf={ce.get('confidence')} msg={ce.get('message')}")
    # 타임아웃으로 shield 된 백그라운드 채점이 끝나길 기다린 뒤 엔진을 닫는다
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        print(f"\nwaiting {len(pending)} background task(s)…")
        await asyncio.gather(*pending, return_exceptions=True)
    await engine.dispose()
    with __import__("contextlib").suppress(Exception):
        await serp._POOL.discard()


if __name__ == "__main__":
    unit_tests()
    if "--unit" not in sys.argv:
        asyncio.run(live())
    sys.exit(1 if FAIL else 0)
