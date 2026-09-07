# 캠페인(병원 단위 대량 발행) 가이드

2026-09 재설계로 추가된 흐름입니다. 설계 문서: https://claude.ai/code/artifact/8fb51d6a-4f7a-4750-984e-69b9bcd609d4

## 한 줄 요약

병원을 고르고 → 키워드를 확인하고 → 원고를 넣고 → 사진 배치를 확인하고 → "예약 걸기"를 누르면
여러 블로그에 수백 건이 나뉘어 예약됩니다. 글·사진·예약 상태는 전부 서버에 있어 어느 PC 에서 열어도 같습니다.

## 화면

| 화면 | 경로 | 하는 일 |
|---|---|---|
| 병원 관리 | `/dashboard/clients` | 병원 프로필(중점 질환·지역·검색량 하한·금칙어·고정 사실), 블로그 계정, 원고 브리프, 사진 세트, 구글시트 |
| 캠페인 | `/dashboard/campaign` | 캠페인 목록 → 6단계 마법사 |
| 사진 풀 | `/dashboard/media` | 사진 업로드·세트(앨범) + **AI 사진 인식**(업로드 후 1회) |

## 6단계

1. **병원·블로그**: 블로그 여러 개 선택, 브리프 프리셋, 사진 세트.
2. **키워드**: 지역×질환 조합 + 검색광고 연관키워드 + 검색량 필터(지역 모바일 20↑ / 전국 100↑) + 통합검색 분석(가능/경쟁/비추천, 권장 사진 수·글자수) + 구글시트 중복 대조.
3. **원고**: 키워드 자동 작성(브리프 흐름 준수 검사) / 원본 원고 변형 N개(고정 사실 보존·유사도 검사) / 파일 대량 업로드(txt·docx). 의료광고법·금칙어 자동 검사.
4. **사진**: 세트 사진을 AI 가 한 번 읽어 태그 저장 → 문단별 슬롯 계획 → 매칭 배치 → 카드에서 교체.
5. **예약**: 시작일·기간·블로그별 하루 한도·시간대 안에서 서버가 10분 단위로 랜덤 배분(기존 예약과 충돌 회피). 미리보기 후 "예약 걸기".
6. **현황**: 발행건 상태(대기/배정/발행중/발행됨/실패/확인 필요), 자동 재시도, 발행 URL. "이 블로그 발행 시작"으로 크롬 확장(v16.1.0+)에 넘겨 실행.

## 서버 구성

- 모델: `backend/app/models/campaign.py`(Client·Blog·BriefPreset·Campaign·CampaignKeyword·SerpSnapshot·Draft·PublishJob), `background_job.py`
- API: `backend/app/api/campaign.py` (prefix `/api/v1/campaign`)
- 워커: `backend/app/services/job_worker.py` + 핸들러 `campaign_jobs.py`
  - 기본은 API 프로세스 안에서 함께 실행(`RUN_WORKER_IN_APP=true`). 별도 프로세스: `cd backend && python -m app.worker`
- 서비스: `region_dictionary.py`(지역 사전), `keyword_expander.py`, `serp_analyzer.py`(모바일 통검), `campaign_writer.py`(Claude 원고/변형/슬롯/검수), `photo_tagger.py`·`photo_matcher.py`, `schedule_engine.py`, `google_sheets_service.py`, `claude_client.py`

## 환경변수 (backend/.env)

| 변수 | 용도 |
|---|---|
| `NAVER_AD_CUSTOMER_ID` / `NAVER_AD_API_KEY` / `NAVER_AD_SECRET_KEY` | 검색광고 API(검색량·연관키워드). 없으면 검색량 0, 직접 입력 키워드만 통과 |
| `ANTHROPIC_API_KEY` 또는 관리자 > API 키(claude) | 원고 생성/변형/사진 인식 |
| `CAMPAIGN_MODEL` | 기본 `claude-opus-5` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 시트 기입(선택). 읽기만이면 시트를 링크 공개로 |
| `MEDIA_DIR` | 유니크화 사진 파일 저장 폴더 |
| `DATABASE_URL` | 운영은 `postgresql+asyncpg://...` 권장(SQLite 는 단일 연결이라 대량에서 잠금) |

## 발행 실행기

- **지금(1단계)**: 크롬 확장 v16.1.0. 6단계 화면에서 "이 블로그 발행 시작" → 서버가 잡을 잠그고(20분) 확장에 넘김 → 결과(성공/실패/캡차/로그인 필요/확인 필요)를 서버에 보고. 캡차·로그인 풀림이면 그 블로그만 `captcha`/`login_required` 상태로 멈추고 나머지는 계속.
- **다음(3단계)**: `publish-agent/` 로컬 에이전트(Playwright, 블로그별 브라우저 프로필). `python agent.py --server ... --email ... --password ... --dry-run` 으로 드라이런 먼저.

## 안전 규칙

- 예약 날짜·시각 설정에 실패하면 발행 버튼을 누르지 않고 실패 처리합니다(즉시 발행 사고 방지).
- 예약 시각이 15분 이내로 임박한 건은 가져가지 않고 실패로 돌려 사람이 재배정하게 합니다.
- 시간초과 건은 "확인 필요"로 남기고, 사람이 네이버 예약 목록에서 확인한 뒤 "발행됨으로 표시"합니다(중복 방지).
- 사진 유니크화는 예약 확정 직후 워커가 미리 처리해 `MEDIA_DIR/variants/{job_id}/` 에 저장합니다.

## 로컬 실행

```
cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```
기본 계정 admin@doctorvoice.com / admin123!@# (main.py 가 시작 시 생성). 병원 관리에서 "예시 병원 5곳 넣기"로 바로 시작할 수 있습니다.
