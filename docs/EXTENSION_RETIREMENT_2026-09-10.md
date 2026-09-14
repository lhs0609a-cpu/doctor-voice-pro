# 크롬 확장 폐기 — PC 실행기로 일원화 (2026-09-10)

## 왜

확장은 웹스토어에 올리지 않아 자동 업데이트가 사실상 동작하지 않았고(CRX + updates.xml + 정책 레지스트리),
설치도 "압축 해제 → 개발자 모드 → 압축해제된 확장 로드"라 병원 사용자에게 무거웠다.
실제로 사용자가 PC 실행기 ZIP을 푼 폴더를 확장으로 로드하려다 `_asyncio.pyd` 예약 이름 오류를 만났다.

발행 로직은 이미 `publish-agent`(Playwright)가 확장의 `naver-poster.js`를 그대로 옮겨 갖고 있었으므로,
남은 것은 **웹이 확장에게 직접 넘기던 일**을 서버 큐로 돌리는 일뿐이었다.

## 무엇이 어디로 갔나

| 확장이 하던 일 | 지금 |
|---|---|
| `SUBMIT_JOB` (저장글·원클릭 발행) | `POST /publish/queue/job` → 실행기가 가져가 등록 |
| `SUBMIT_BATCH` (대량 발행) | `POST /publish/queue/bulk` (블로그 지정) → 실행기가 순서대로 |
| `SUBMIT_SERVER_JOB` (캠페인 1건 밀어넣기) | 불필요 — 실행기가 대기 작업을 알아서 처리 |
| `SYNC_CATEGORIES` | 실행기가 에디터에서 읽어 `POST /publish/categories` |
| `SYNC_BLOG` (지금 어느 블로그?) | 사용자가 등록된 블로그를 고른다(`campaign/agent/summary`) |
| `SUBMIT_GEN_BATCH` (제미나이 웹 조작 생성) | `POST /keyword-batch/generate` (서버 AI 호출) |
| `PING` 연결 표시등 | `POST /campaign/agent/heartbeat` + `GET /campaign/agent/status` (상단 바 신호등) |

## 서버 변경

- `queued_posts.blog_ref_id` — 어느 블로그로 발행할지. 실행기가 자기 블로그 몫만 가져간다.
  블로그가 하나뿐인 계정에서만 `claim_unassigned=true`로 대상 미지정(예전) 글까지 가져간다.
- `queued_posts.final_action` — `schedule | publish | draft`. 예약뿐 아니라 즉시 발행·임시저장도 큐로 간다.
- `GET /publish/queue/jobs?blog_ref_id=&claim_unassigned=` — 실행기 수령 창구. 건네준 글은 즉시
  `registered`로 표시해 두 번 나가지 않게 한다.
- `POST /publish/queue/job` — 브라우저가 만든 글 1건(사진 포함)을 큐에 담는다. 블록 60개,
  사진 1장 8MB, 전체 24MB 상한. 예약은 **지금부터 5분 뒤 이후**만 받는다(실행기가 에디터를 열 시간).
- `POST /keyword-batch/generate` — 키워드 1개 원고 생성(기본 제미나이). 지시문 20,000자 상한.
- 마이그레이션: `2026_09_10_queue_blog_ref.py` (컬럼별로 존재 여부를 확인하는 가산 마이그레이션).

## 실행기 변경

- `process_queue_jobs` — 캠페인 잡을 마친 뒤 발행 큐를 한 건씩 가져와 등록하고 결과를 보고한다.
  서버 잠금이 없는 경로라 **가져오면 곧바로 결과를 남긴다**. dry-run 은 결과를 왜곡하므로 아예 가져오지 않는다.
- `sync_categories` — 서버 카테고리 캐시가 비어 있을 때만 발행 레이어를 열어 목록을 읽고 되돌린다.
- `run_job` 이 `publish`(즉시)·`draft`(임시저장)를 지원한다. 즉시 발행은 '현재' 라디오를 명시적으로 켠다 —
  남아 있던 예약값으로 나가는 것을 막는다. 임시저장은 발행 레이어를 열지 않는다.
- 블로그 ID 대조는 모든 경로에서 그대로다. 로그인된 블로그가 다르면 제목도 쓰지 않고 멈춘다.

## 신호등·버전 탐지

- `agent_sessions` 테이블 — 기기(설치본)마다 한 줄. 실행기가 60초마다 갱신하고 150초 침묵이면 꺼짐.
- 웹은 `GET /campaign/agent/status` 로 켜짐·발행중·버전·기기 이름·현황 한 줄을 읽는다.
- 최신 버전은 `/downloads/launcher-version.json`(빌드가 함께 갱신) 과 대조해 '업데이트 필요'를 띄운다.
  같은 파일을 실행기도 읽어 스스로 업데이트하므로 버전 표기가 어긋날 일이 없다.

## 남은 것

- `chrome-extension/` 소스는 지우지 않고 남겨 두었다. 웹에서 부르는 곳이 없으므로 동작에는 영향이 없다.
- 큐 경로에는 캠페인 경로 같은 lease/journal 복구가 없다. 실행기가 글을 받은 뒤 죽으면 그 글은
  `registered` 상태로 남아 다시 나오지 않는다(확장 시절과 같은 성질). 복구가 필요하면
  캠페인 프로토콜처럼 잠금·재클레임을 도입해야 한다.
