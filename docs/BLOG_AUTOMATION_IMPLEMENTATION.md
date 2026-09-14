# 블로그 자동화 구현·전환 기록

2026-09-08. 저장소 변경 기준이며 운영 배포 완료 기록은 아니다.

## 구현된 경로

캠페인에서 병원·블로그·사진 세트와 키워드를 설정한 다음 **선택한 키워드로 자동 준비**를 실행한다. 서버 작업이 원고 생성, 검수, 사진 배치, 선택적 예약 대기열 등록과 사진 준비를 이어서 수행한다. 검토 모드에서는 예약을 생성하지 않는다. 검수 실패 원고는 자동 예약에서 제외된다. 재실행은 기존 원고·예약과 단계 기록을 이용한다.

로컬 실행기는 대기열에서 한 번에 한 건씩 선점한다. DB 조건부 UPDATE와 블로그별 유일 잠금으로 동시 선점을 제어한다. 작업 토큰이 없거나 다른 작업 토큰이면 결과와 checkpoint를 거절한다. 최종 클릭은 유효한 lease를 가진 실행기가 서버에 클릭 의도를 기록한 후 수행한다. 동일 결과 재전송은 시도 횟수를 다시 증가시키지 않는다.

확장 17은 캠페인 화면에서 작업별 권한만 받아 서버에 직접 본문을 요청하고 결과를 보고한다. 웹 로그인 토큰을 확장으로 넘기지 않는다. 원래 페이지가 닫혀도 서버 결과 전달 경로는 유지된다. service worker 재시작 후 storage outbox를 전송하고 최종 클릭 이후의 미확인 작업은 자동 재실행하지 않는다. 웹 origin과 실행 API origin을 제한하고, 편집 작업의 tab/frame 소유권을 확인한다.

로컬 실행기는 SQLite journal과 프로필 폴더 잠금을 사용한다. 30초 heartbeat, 120초 lease, 서버 최종 클릭 권한 확인, 결과 먼저 저장 후 전송, 재시작 시 결과 우선 복구를 연결했다. dry-run은 서버에서 별도 시험 완료 상태로 기록하며 자동 실발행 재시도에 섞이지 않는다.

예약 시각의 offset은 한국 시간으로 변환한다. 확장은 날짜·시각·예약 라디오 값을 확인하고 임박한 시각이면 발행을 중단한다. 예약 등록은 공개 완료와 구분한다. 정확한 게시물 식별자를 얻은 작업은 `submitted`, 확인할 수 없는 결과는 `uncertain`, 예약 시각 이후 공개 페이지 식별 정보를 확인한 작업은 `published`다.

화면에는 원고 자동 준비, 서버 작업 재조회, 준비 중단, 예약 등록/공개 확인 구분, 결과 대조와 명시적 미등록 확인이 추가됐다. 결과 대조가 필요한 글은 일반 재시도로 돌릴 수 없다.

## 파일 경계

| 영역 | 주요 파일 |
|---|---|
| 실행 계약 | `backend/app/services/publish_protocol.py`, `backend/app/api/campaign.py` |
| 영구 실행 기록 | `backend/app/models/campaign.py::PublishAttempt`, `AutomationRun` |
| 원고→예약 자동 준비 | `backend/app/services/automation_pipeline.py` |
| 공개 확인 | `backend/app/services/publication_verifier.py` |
| 실행기 복구 | `publish-agent/journal.py`, `agent.py`, `server_client.py` |
| 확장 직접 연결 | `chrome-extension/server-runner.js`, `background.js` |
| 운영 화면 | `automation-panel.tsx`, `publish-runner.tsx`, `step6-status.tsx` |
| 패키징/검사 | `chrome-extension/build_release.py`, `.github/workflows/automation-tests.yml` |

## 설치·전환

1. 기존 API/실행기에서 진행 중인 글과 예약 목록을 대조한다. 동일 블로그에서 구/신 발행 경로를 함께 실행하지 않는다.
2. 백엔드에 변경 소스를 설치한다. 새 테이블은 `campaign_publish_attempts`, `campaign_automation_runs`다. 기존 앱의 모델 초기화에서도 생성되며 Alembic 버전 관리 DB에는 두 additive migration이 제공된다. 이미 테이블이 있는 비버전 DB에 초기 Alembic migration 전체를 무작정 재실행하지 않는다.
3. 서버 워커를 시작한다: `backend`에서 `python -m app.worker`. 별도 워커를 쓸 때 API 환경은 `RUN_WORKER_IN_APP=false`로 둔다. 새 자동 준비 핸들러가 이 워커에서 실행된다.
4. 새 프론트와 실행기를 함께 사용한다. protocol 1 claim에는 HTTP 426을 반환하므로 예전 캠페인 실행기는 먼저 업데이트해야 한다.
5. 확장은 `frontend/public/extension/doctorvoice-extension-v17.0.0.zip`을 풀고 개발자 모드에서 로드한다. ZIP은 `python chrome-extension/build_release.py`로 재생성한다. 서명 CRX와 기존 `updates.xml` 자동 배포는 이번 작업에서 갱신하지 않았다.
6. 실행기는 기존 README 설치 절차로 준비하고 `--once --dry-run`으로 시작한다. 시험 완료한 글을 실제 등록하려면 캠페인 현황에서 다시 대기로 넣는다.
7. 실제 네이버 등록과 공개 확인은 지정 계정에서 실측해야 한다. 이 작업에서는 실제 계정 로그인이나 공개 발행을 실행하지 않았다.

## 검증

- 서버 작업 소유권/API/자동 준비/공개 식별 검사: 20개 통과 (선점/취소 경쟁 포함).
- 실행기 오프라인 및 journal 복구: 43개 통과.
- 실제 Chromium을 사용한 가짜 에디터 E2E: 9개 통과.
- 확장 worker 복구·동시 시작·API origin 검사: 5개 통과.
- 프론트 TypeScript 검사, Next.js 프로덕션 빌드(50개 페이지 생성), `git diff --check` 통과. 위 자동화 테스트는 합계 77개다. 빌드에 기존 결제 설정 화면의 client rendering 전환 경고 1건이 있었다.
- 실제 네이버 DOM과 예약 목록은 가짜 에디터 검사로 검증되지 않는다. 공개 확인기는 증거를 찾지 못하면 공개 완료로 추정하지 않는다.

## 남은 전체 재설계 범위

이 변경으로 캠페인의 자동 준비와 발행 계약을 연결했지만 [전체 설계](BLOG_AUTOMATION_V2_DESIGN.md)의 모든 항목을 완료한 것은 아니다. 기존 `/publish` 대량 큐·로컬 saved-posts·구 `/schedules` 데이터의 통합 이관, 완전한 원고 revision 모델, 이미지 객체 저장소 전환, OS 자격증명 저장소/장치 등록, 서명 CRX 배포, PostgreSQL 동시성 실측, 실제 네이버 예약 목록 자동 대조는 남아 있다.

자동 공개 확인은 식별 가능한 URL과 OG 메타데이터가 있는 경우에만 동작한다. 예약 응답에 식별자가 없는 경우에는 결과 대조 필요 상태가 유지된다. 실제 네이버 화면을 확인하지 않은 채 임의의 성공 셀렉터를 추가하지 않았다. 운영 배포·실계정 검증·장시간 무인 운영 통과를 완료로 표시하지 않는다.
# 2026-09-09 추가 구현

반복 자동 운영, 키워드 발굴, 근거·품질 검수 및 자동 수정, 랜딩 URL·UTM,
Windows 실행기와 확장 17.1 변경은 [최신 구현·운영 문서](BLOG_AUTOPILOT_AND_LANDING_2026-09-09.md)를 참고한다.
아래 내용은 2026-09-08 구현 시점의 기록이다.
