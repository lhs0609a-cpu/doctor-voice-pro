"""
네이버 검색광고 API 실연동 테스트 (인증/DB 없이 순수 API만 확인).

사용법 (backend 폴더에서):
    ./venv/Scripts/python.exe test_search_volume.py 임플란트 라식 강남치과

.env 에 아래가 설정돼 있어야 함:
    NAVER_AD_CUSTOMER_ID / NAVER_AD_API_KEY / NAVER_AD_SECRET_KEY
"""
import asyncio
import sys

import httpx

from app.core.config import settings
from app.services import search_volume_service as s


async def main():
    keywords = sys.argv[1:] or ["임플란트", "라식"]

    print("=" * 60)
    print("검색광고 API 자격증명 설정:", s.is_configured())
    print("  CUSTOMER_ID:", settings.NAVER_AD_CUSTOMER_ID or "(비어있음)")
    print("  API_KEY    :", (settings.NAVER_AD_API_KEY[:8] + "…") if settings.NAVER_AD_API_KEY else "(비어있음)")
    print("  SECRET_KEY :", "설정됨" if settings.NAVER_AD_SECRET_KEY else "(비어있음)")
    print("=" * 60)

    if not s.is_configured():
        print("\n[중단] .env 에 검색광고 키 3종을 먼저 설정하세요.")
        return

    # 1) 서비스 함수로 조회(실제 앱이 쓰는 경로)
    print(f"\n[1] fetch_keyword_volumes({keywords})")
    result = await s.fetch_keyword_volumes(keywords)
    if result:
        for norm, m in result.items():
            print(
                f"  · {m['keyword']:<12} "
                f"월 {m['total_volume']:>7,} "
                f"(PC {m['monthly_pc']:>6,} / 모바일 {m['monthly_mobile']:>6,}) "
                f"경쟁 {m['competition']}"
            )
    else:
        print("  결과 없음 — 아래 [2] 진단 응답을 확인하세요.")

    # 2) 원시 응답 진단(상태코드/본문 일부) — 401이면 서명/키 문제
    print("\n[2] 원시 응답 진단")
    path = "/keywordstool"
    url = f"{settings.NAVER_AD_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            params={"hintKeywords": ",".join(keywords[:5]), "showDetail": "1"},
            headers=s._headers("GET", path),
        )
        print("  HTTP", resp.status_code)
        body = resp.text
        print("  본문(앞 300자):", body[:300])
        if resp.status_code == 401:
            print("\n  → 401: API_KEY/SECRET_KEY/CUSTOMER_ID 또는 서명이 틀렸습니다.")
        elif resp.status_code == 200:
            print("\n  → 200: 연동 성공.")


if __name__ == "__main__":
    asyncio.run(main())
