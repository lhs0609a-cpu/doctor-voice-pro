"""
통검(모바일 통합검색) 분석 모듈 수동 테스트 스크립트 (pytest 아님)

실행: backend 디렉토리에서 `python test_serp_analyzer.py [키워드] [--dump]`
  --dump : 통검 원본 HTML 을 scratch 디렉토리(환경변수 SERP_DUMP_DIR, 기본 ./)에 저장
"""

import asyncio
import json
import os
import sys
import urllib.parse

import httpx

from app.services.serp_analyzer import (
    SERP_URL_TEMPLATES,
    _build_headers,
    analyze_keyword,
    classify_blog_type,
    normalize_keyword,
    parse_mobile_serp_html,
)


def check(label: str, actual, expected) -> bool:
    ok = actual == expected
    print(f"  [{'OK' if ok else 'FAIL'}] {label}: got={actual!r} expected={expected!r}")
    return ok


def unit_checks() -> bool:
    print("== classify_blog_type ==")
    all_ok = True
    cases = [
        ("gangnamskinclinic", "강남 아토피 치료 잘하는 곳", None, "hospital"),
        ("happymom0101", "강남아토피 한의원 다녀왔어요", None, "hospital"),  # 제목의 한의원 우선
        ("happymom0101", "강남아토피 체험단 후기 (제공받아 작성)", None, "experience"),
        ("happymom0101", "우리 아기 아토피 육아 일기", None, "daily"),
        ("dailylife_j", "강남아토피 후기", None, "daily"),
        ("reviewer_kim", "강남아토피 크림 3종 비교", None, "influencer"),
        ("abcd1234", "강남아토피", None, "unknown"),
        ("abcd1234", "", {"blog_name": "서울 피부과", "title": "무제"}, "hospital"),
        ("abcd1234", "", {"blog_name": "맘스 다이어리"}, "daily"),
    ]
    for blog_id, title, metrics, expected in cases:
        all_ok &= check(f"{blog_id} / {title[:20]}", classify_blog_type(blog_id, title, metrics), expected)

    print("== normalize_keyword ==")
    all_ok &= check("공백/소문자", normalize_keyword(" 강남 아토피 abc "), "강남아토피ABC")

    print("== parse_mobile_serp_html (offline) ==")
    html = """
    <html><body>
    <section class="sc_new sp_nreview"><div class="api_subject_bx">
      <div class="title_area"><h2 class="api_title">인기글</h2></div>
      <ul>
        <li><a class="thumb" href="https://blog.naver.com/hosp1/223000000001"><img src="x"></a>
            <a class="title_link" href="https://blog.naver.com/hosp1/223000000001">강남아토피 피부과 후기</a></li>
        <li><a class="title_link" href="https://m.blog.naver.com/momlife/223000000002">아기 아토피 육아 일상</a></li>
        <li><a class="title_link" href="https://blog.naver.com/PostView.naver?logNo=223000000003&blogId=third">세번째 글</a></li>
        <li><a class="title_link" href="https://blog.naver.com/hosp1/223000000001">중복 링크</a></li>
        <li><a href="https://blog.naver.com/hosp1">블로그 홈 (제외)</a></li>
      </ul>
    </div></section>
    <section class="sc_new sp_ncafe"><h2 class="api_title">카페</h2>
      <a class="title_link" href="https://cafe.naver.com/momcafe/12345">카페 글</a>
      <a class="title_link" href="https://cafe.naver.com/ca-fe/web/cafes/momcafe/articles/12346">카페 글2</a>
    </section>
    <a href="https://search.naver.com/other">기타</a>

    <!-- 2026 fender/sds 마크업: 개별 카드 (헤더 없음, data-block-id 로 섹션 유추) -->
    <div class="spw_fsolid _fsolid_body" data-slog-container="urB_boR" data-collection="urB_boR">
      <div class="fsolid_list">
        <div id="fdr-1" data-fender-root="true" data-block-id="review/prs_template_v2_review_blog_rra_mo.ts">
          <div class="fds-default-mode api_subject_bx">
            <div class="sds-comps-profile" data-sds-comp="Profile">
              <a href="https://m.blog.naver.com/ahcherb"><img src="p"></a>
              <a href="https://m.blog.naver.com/ahcherb"><span>♡친절한 허브한의원♡</span></a>
              <span>3주 전</span>
            </div>
            <a href="https://m.blog.naver.com/ahcherb/224360723929"><img src="t"></a>
            <a href="https://m.blog.naver.com/ahcherb/224360723929"><span class="sds-comps-text">강남아토피 한의원 햇빛 알레르기</span></a>
          </div>
        </div>
      </div>
    </div>
    <!-- fender 마크업: 헤더가 있는 섹션 (이미지 → 제외 대상) -->
    <div class="fds-default-mode api_subject_bx">
      <div class="sds-comps-header"><div class="sds-comps-header-title"><span class="sds-comps-text-type-headline3">이미지</span></div></div>
      <a href="https://blog.naver.com/imgblog/224000000009">이미지 결과</a>
    </div>
    <!-- fender 마크업: 브랜드 콘텐츠 (광고 → is_ad) -->
    <div class="fds-default-mode api_subject_bx">
      <div class="sds-comps-header"><div class="sds-comps-header-title"><span>건강·의학 관련 브랜드 콘텐츠</span></div></div>
      <a href="https://blog.naver.com/adclinic/224000000010">브랜드 콘텐츠 글</a>
    </div>
    </body></html>
    """
    parsed = parse_mobile_serp_html(html)
    all_ok &= check("결과 수 (중복/홈/이미지 제외)", len(parsed), 7)
    all_ok &= check("1번 blog_id", parsed[0]["blog_id"], "hosp1")
    all_ok &= check("1번 제목 (썸네일 앵커 → 텍스트 앵커 보강)", parsed[0]["title"], "강남아토피 피부과 후기")
    all_ok &= check("1번 섹션", parsed[0]["section"], "인기글")
    all_ok &= check("3번 PostView 파싱", (parsed[2]["blog_id"], parsed[2]["post_no"]), ("third", "223000000003"))
    all_ok &= check("4번 kind", parsed[3]["kind"], "cafe")
    all_ok &= check("4번 섹션", parsed[3]["section"], "카페")
    all_ok &= check("5번 카페 신형 URL", parsed[4]["post_no"], "12346")
    all_ok &= check("6번 fender 카드 섹션 (block-id 유추)", parsed[5]["section"], "블로그")
    all_ok &= check("6번 fender 카드 블로그명", parsed[5]["blog_name"], "♡친절한 허브한의원♡")
    all_ok &= check("6번 fender 카드 제목", parsed[5]["title"], "강남아토피 한의원 햇빛 알레르기")
    all_ok &= check("7번 브랜드 콘텐츠 is_ad", (parsed[6]["blog_id"], parsed[6]["is_ad"]), ("adclinic", True))
    all_ok &= check("이미지 섹션 제외", any(p["blog_id"] == "imgblog" for p in parsed), False)
    all_ok &= check("position 연속", [p["position"] for p in parsed], [1, 2, 3, 4, 5, 6, 7])
    return all_ok


async def dump_raw_html(keyword: str) -> None:
    out_dir = os.environ.get("SERP_DUMP_DIR", ".")
    encoded = urllib.parse.quote(keyword)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for i, tpl in enumerate(SERP_URL_TEMPLATES):
            url = tpl.format(q=encoded)
            try:
                r = await client.get(url, headers=_build_headers())
            except Exception as exc:
                print(f"  dump {i}: 요청 실패 {exc}")
                continue
            path = os.path.join(out_dir, f"serp_dump_{i}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"  dump {i}: status={r.status_code} len={len(r.text)} final_url={r.url} -> {path}")
            await asyncio.sleep(1.0)


async def live_run(keyword: str) -> None:
    print(f"== analyze_keyword({keyword!r}) ==")
    result = await analyze_keyword(keyword, max_posts=8, fetch_post_metrics=True)
    print("error       :", result["error"])
    print("fetched_at  :", result["fetched_at"])
    print("verdict     :", result["verdict"])
    print("reason      :", result["verdict_reason"])
    print("summary     :", json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"posts ({len(result['posts'])}) - first 3:")
    for p in result["posts"][:3]:
        print(json.dumps(p, ensure_ascii=False, indent=2))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    keyword = args[0] if args else "강남아토피"

    ok = unit_checks()
    print("unit checks:", "ALL OK" if ok else "SOME FAILED")

    if "--dump" in flags:
        asyncio.run(dump_raw_html(keyword))
    asyncio.run(live_run(keyword))


if __name__ == "__main__":
    main()
