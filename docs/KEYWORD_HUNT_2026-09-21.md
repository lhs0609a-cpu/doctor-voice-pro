# 키워드 발굴 — 통합검색 자리 + 우리 블로그로 뚫리는지

## 왜 세 층으로 나눴나

세 가지가 서로 다른 질문이고, 비용도 한 자릿수씩 차이가 난다.

| 층 | 질문 | 코드 | 값 |
| --- | --- | --- | --- |
| ① 키워드 | 통합검색에 병원 블로그가 들어갈 자리가 있나 | `serp_analyzer.analyze_keyword` | `possible / contested / avoid / unknown` |
| ② 블로그 | 우리 블로그 점수로 그 자리를 뚫나 | `blog_index_jobs.blog_verdict_batch` | `likely / contested / unlikely / already_ranked` + 확률 |
| ③ 글 | 우리가 쓸 글이 상위글 기준을 넘나 | `rank_feasibility._build_target` | 글자수·이미지·소제목 목표 프로필 |

①은 키워드당 SERP 1회, ②는 키워드당 1페이지 점유 블로그 ~10개 채점이다. 300개를 전부 ②에
넣으면 고유 경쟁 블로그가 1,000개를 넘어 몇 시간이 걸린다. 그래서 ①에서 `avoid`를 먼저 버리는
것이 전체 비용을 결정한다.

## 깔때기 — `services/keyword_hunt.py`, 잡 타입 `keyword_hunt`

```
① 씨앗   진료 항목 → Claude 주제(30개씩 여러 라운드) + 네이버 연관검색어·자동완성
         → keyword_expand(검색광고 연관어 + 검색량, max_candidates = target×4, 최대 1200)
② 통검   passes_filter && verdict='unknown' 행을 검색량 순 screen_limit(기본 target×2, 최대 600)개
         analyze_keyword(fetch_post_metrics=False) — 본문 8개 크롤을 건너뛰어 SERP 1회로 끝낸다
         동시성 KEYWORD_HUNT_SERP_CONCURRENCY(기본 4), 키워드당 90초 상한
③ 판정   verdict in (possible, contested) 인 행을 possible 우선·검색량 순으로 verdict_limit
         (기본 min(target,120), 최대 300)개만, blog_verdict_batch 60개 웨이브로
마무리   my_verdict in (likely, contested) 를 확률·검색량 순 target 개까지 selected=True
```

- 단계 결과는 `job.result['completed']`에 남아 재실행이 끝난 단계를 건너뛴다. 중간에 끊겨도
  같은 잡을 다시 돌리면 이어서 한다.
- 판정 결과는 `campaign_keywords` 행에 쌓인다(`verdict`=통검, `my_verdict`/`my_probability`=내 블로그).
  화면은 잡 진행률과 키워드 목록을 함께 폴링해 표를 실시간으로 채운다.
- 금칙어가 들어간 후보는 ②에 태우지 않는다.
- ②의 요약에는 `depth: 'light'`를 적어 둔다. 본문 지표 없이 섹션·블로그 유형만 본 판정이며,
  나중의 정밀 `serp_analyze`가 덮어쓴다.

## 붙인 자리

- `POST /api/campaign/campaigns/{id}/keywords/hunt` — `target`(10~300), `blog_id`, `screen_limit`, `verdict_limit`.
  `dedupe_key=hunt:{campaign_id}`라 중복 시작은 기존 작업을 돌려준다.
- 원스톱 화면이 4칸에서 5칸이 됐다: 실행기 → 블로그 → **키워드 찾기** → 사진 → 글 쓰기.
- `blog_verdict_batch`에 `stream_partial` 옵션을 넣었다. 다른 잡이 한 단계로 부를 때 그 잡의
  `result`를 부분 결과로 덮지 않게 한다.
- 대량 발행이 발굴한 키워드를 쓴다: 고른 키워드가 있으면 `discover_keywords=False`,
  `strict_quality=True`로 시작한다. `start_automation`이 이 경우에도 검수 기준·사진 세트·
  `bulk_publication` 표식을 붙이도록 고쳤다 — 표식이 없으면 반복 운영 일시정지가 이 예약까지 막는다.
- 한 번에 쓰는 글은 여전히 50개 상한(`AutomationIn.max_keywords`)이다. 300개를 찾아 두고
  50개씩 나눠 쓴다.

## 검증

`backend/test_keyword_hunt.py` 10개 + 기존 파이프라인·자동운영·발행 검사 48개, 총 58개 통과.
외부 호출(Claude 주제, 네이버 연관검색어, 통합검색, 경쟁자 채점)은 전부 대역이다. 프런트는
TypeScript와 프로덕션 빌드 통과.

**아직 안 한 것**

- 실제 네이버로 300개를 돌린 실측이 없다. 소요 시간(30~60분 추정)과 차단 빈도는 미확인이다.
- ③ 목표 프로필(`_build_target`)을 원고 생성 프롬프트에 넘기는 연결은 아직 없다.
- 발행 후 실제 노출 회수(`post_exposure.post_exposure_cards`)로 ②의 확률을 보정하는 루프가 없다.
  이게 없으면 '가능성 78%'는 검증된 적 없는 추정값이다.
- `frontend/tests/automation_ux_smoke.py`는 09-15 화면 재작성 이전 것이라 이미 낡았다.
  이번에는 `/keywords` 대역만 추가했고 전체 동선 복구는 하지 않았다.
