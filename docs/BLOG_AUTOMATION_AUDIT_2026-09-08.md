# 블로그 자동화 코드 점검

점검일: 2026-09-08. 대상: 현재 저장소의 활성 소스. 운영 서버·실제 네이버 세션·배포 ZIP의 동작을 검증했다는 의미는 아니다. 구 배포본 `DoctorVoicePro_Ready/`는 수정 대상에서 제외했다.

## 결론

현재 제품에는 자동화에 필요한 기능이 상당 부분 있지만, 작업의 소유권·진행 상태·결과가 서버, 웹 페이지, 확장에 분산되어 있다. 정상 경로의 클릭 정확도를 높이는 것만으로 장시간 무인 운영을 달성하기 어렵다. 작업 큐를 통합하고, 실행 중단과 발행 결과 불확실성을 먼저 해결해야 한다.

새 구조와 전환 순서는 [재설계 명세](BLOG_AUTOMATION_V2_DESIGN.md)를 따른다. 아래 내용은 정적 코드 점검에서 확인한 구현과 그로부터 예상되는 장애를 구분하여 기록한다. 실제 장애 빈도는 측정하지 않았다.

## 구성별 확인 결과

| 영역 | 확인한 근거 | 문제와 영향 | 우선순위 |
|---|---|---|---|
| 발행 큐 중복 | `backend/app/api/__init__.py`에서 `/publish`, `/campaign`, `/schedules` 모두 등록 | 서로 다른 모델과 성공 정의를 사용하는 발행 경로가 공존 | P0 |
| 대량 큐 선점 | `api/publish_queue.py::fetch_jobs` | GET 조회 시 `registered`로 변경. DB 선점 경쟁 제어·만료 복구 없이 응답 전달 전에 등록 완료처럼 기록 | P0 |
| 캠페인 선점 | `api/campaign.py::agent_claim` | SELECT 후 ORM 값 변경. 조건부 UPDATE나 행 잠금 없이 두 실행기가 같은 행을 읽고 선점할 가능성 | P0 |
| 결과 소유권 | `api/campaign.py::agent_result` | 양쪽 토큰이 모두 있을 때만 비교. 토큰 생략으로 검사를 건너뛰며, 완료 상태에 대한 재보고 제한도 없음 | P0 |
| 잠금 수명 | `agent_claim`, `config.py::PUBLISH_LOCK_MINUTES`, `publish-agent/agent.py` | 기본 20분 잠금으로 여러 건을 한꺼번에 받지만 heartbeat가 없다. 대기 중 잠금이 만료되어 재선점될 수 있음 | P0 |
| 실행 단계 | `models/campaign.py::PublishJob`, `agent_result` | `publishing`이 정의되어 있지만 확인한 실행 경로에서 최종 클릭 전 서버에 이 상태를 기록하지 않음. 만료된 `assigned`를 안전하게 재시도할 근거 부족 | P0 |
| 페이지 의존 | `frontend/src/components/campaign/publish-runner.tsx` | 전체 payload와 잠금 토큰을 `jobsRef`에 보관. 페이지 종료·새로고침 시 본문 요청/결과 보고 경로가 사라짐 | P0 |
| 보고 유실 | 같은 파일 `onResult` | 서버 보고 실패를 알린 뒤에도 `jobsRef.delete(id)` 및 완료 집계. 결과 재전송 저장소 없음 | P0 |
| 결과 정보 손실 | 같은 파일 `onResult`, `content-website.js::relayJobResults` | 확장이 보낸 URL과 구조화된 로그인/캡차 플래그 대신 메시지 정규식에 의존하고 URL은 API로 넘기지 않음 | P1 |
| 확장 재시작 | `chrome-extension/background.js` | `currentJob`, `jobDoneResolver`, 배치 플래그 등이 메모리 상태. `pendingJob`만으로 전체 배치와 클릭 전후 상태를 복구할 수 없음 | P0 |
| 편집기 프레임 | `manifest.json::all_frames`, `background.js::EDITOR_READY` | 준비 신호 처리에서 작업의 tab/frame 소유권 검사가 없어 여러 프레임의 신호가 같은 작업 실행을 유발할 여지가 있음 | P0 |
| 확장 신뢰 경계 | `manifest.json`, `background.js::onMessageExternal` | 모든 `*.vercel.app`에서 연결 가능하고 핸들러에 정확한 origin 허용 목록 검사 없음. 발행·계정 저장 명령까지 노출 | P0 |
| 성공 판정 | `publish-agent/naver_editor.py::publish` | 레이어 닫힘·프레임 교체를 성공으로 판정. 네이버 예약 목록/게시물 식별자 대조가 없어 성공의 증거가 약함 | P0 |
| 등록과 공개 혼동 | `api/campaign.py::agent_result`, `publish_queue.py::report_result` | 예약 작업의 `ok`도 즉시 `published` 처리. 실제 공개 전에도 공개 완료로 보임 | P0 |
| 계정 확인 실패 | `publish-agent/agent.py::run_job` | 기존에는 예상/실제 ID 중 하나가 비어 있으면 비교를 통과. **이번 변경에서 입력 전 중단하도록 수정** | P0 |
| 클릭 후 결과 없음 | 같은 함수 | 기존에는 `publish()`가 None을 반환하면 일반 실패로 보고. **이번 변경에서 uncertain 처리** | P0 |
| 클릭 후 예외 | 같은 함수 | 로그인·계정·예약 종류의 예외가 클릭 후에도 일반 실패로 분류. **이번 변경에서 클릭 후 uncertain 유지** | P0 |
| 확인 필요 재시도 | `api/campaign.py::retry_job` | `uncertain`도 확인 증거 없이 queued로 변경 가능. 이미 예약된 글을 재등록할 수 있음 | P0 |
| 시험 실행 | `publish-agent/README.md`, `agent.py` | dry-run 결과가 일반 실패 API로 전달되어 재시도 횟수/정책에 섞임. 실제 작업과 시험 작업 분리 필요 | P1 |
| 로컬 원고 저장 | `frontend/src/lib/keyword-batch.ts`, `prepared-store.ts` | 생성 원고는 localStorage, 준비한 본문/사진은 IndexedDB 사용. DB 원고와 통합되지 않아 다른 기기에서 이어가기 어려움 | P1 |
| 생성 경로 분산 | `chrome-extension/gemini-writer.js`, `services/campaign_writer.py` | 브라우저 Gemini와 서버 생성 경로가 별도. 무인 생성의 실행·과금·재시도·검수 기준 통합 필요 | P1 |
| 사진 처리 | `api/campaign.py::agent_claim`, `services/campaign_jobs.py` | 선점 요청 안에서 이미지 생성/파일 접근/대형 base64 조립. 요청 지연과 잠금 처리 결합 | P1 |
| 예약 시간 | `publish_queue.py::_parse_local`, `models/publish_queue.py::ScheduleMark` | offset을 변환하지 않고 제거. 클라이언트 시간대가 KST가 아닐 때 의미가 바뀔 수 있음 | P1 |
| 블로그별 예약 | `publish_queue.py::list_schedule_marks` | marks는 blog_id로 거르지만 QueuedPost에는 블로그 필드가 없어 사용자 전체 큐 예약을 합산 | P1 |
| 카테고리 캐시 | `models/publish_queue.py::NaverCategoryCache` | user_id만 기본키. 동일 사용자 다중 블로그의 카테고리가 덮어써질 수 있음 | P1 |
| 구 예약 경로 | `services/schedule_service.py::execute_schedule`, `naver_blog_service.py` | 호출하는 `create_blog_post` 메서드가 해당 서비스에 없고 실제 정의는 `create_post`. 내부적으로 구 `/blog/writePost.json` 주소 사용 | P0 |
| 생성 워커 복구 | `services/job_worker.py::_reclaim_stale`, `JobContext.progress` | stale 판단은 locked_at 기준이나 progress는 updated_at만 갱신. 30분 이상 작업을 다른 워커가 회수할 가능성 | P1 |
| DB 변경 | `app/main.py::lifespan` | 앱 시작 중 create_all과 ALTER TABLE 실행. 다중 인스턴스 배포 시 변경 책임 분리 필요 | P1 |
| 배포 검증 | `.github/workflows/deploy.yml` | frontend/backend 배포는 있으나 발행 계약·실행기 회귀 테스트를 통과해야 배포하는 단계가 없음 | P1 |
| 개발/운영 설정 | `docker-compose.yml` | 개발용 비밀값, reload, DB/Redis 포트 공개가 포함된 개발 구성. 운영 구성과 명시적 분리 필요 | P1 |

P0는 자동발행 확대 전 해결, P1은 무인 운영 전 해결을 뜻한다. 잠금 경쟁과 프레임 중복 실행은 코드 구조로 도출한 위험이며 동시성 재현 테스트는 아직 수행하지 않았다.

## 보존할 구현

- `publish-agent`의 블로그별 프로필, 예약 값 재확인, 카테고리 실패 시 중단, 이미지 삽입 개수 확인.
- 캠페인의 병원/브리프/키워드/원고/사진 계획 모델과 기존 UI 구성요소.
- `schedule_engine`의 예약 슬롯 계산, `photo_matcher`의 사진 매칭: 순수 기능을 유지하고 상태 소유권만 통합.
- `job_worker`의 조건부 UPDATE 선점 아이디어: 캠페인 발행에도 같은 원칙을 적용하되 lease와 fencing을 보강.
- 확장 진단 로그와 네이버 셀렉터 지도. 실제 네이버 검증이 끝난 것으로 취급하지 않는다.

## 점검 범위의 한계

블로그 자동화에 연결된 확장, 실행기, 프론트, 큐/API, 생성·사진·예약 서비스, DB 초기화, 배포 흐름을 점검했다. 결제·카페·아웃리치 등 독립 기능의 전체 보안 감사, 운영 DB 상태 조사, 모든 소스의 줄 단위 검토는 포함하지 않았다. 저장소의 비밀정보 파일 내용은 점검 자료로 복사하지 않았다.

## 공식 문서 확인

- Chrome은 서비스워커의 예기치 않은 종료에 대비해 전역 변수 대신 상태를 저장하도록 안내한다. 현재 keepalive는 복구 설계의 대체재가 될 수 없다. [서비스워커 수명](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- 메시지 수신자는 발신자를 검증하고 허용할 동작을 제한해야 한다. [Chrome 메시지 전달](https://developer.chrome.com/docs/extensions/develop/concepts/messaging)
- 현재 네이버 공식 목록에는 블로그 검색과 카페 글쓰기가 명시되어 있다. 위 구 블로그 쓰기 경로의 지원 근거는 이 목록에서 확인하지 못했으므로 운영 경로로 전제하지 않는다. 종료 일자를 확인했다는 주장은 하지 않는다. [네이버 API 목록](https://developers.naver.com/products/intro/plan/plan.md)

## 이번 변경

전체 v2의 구현 완료가 아니라 재설계와 국소적인 실행기 오류 수정이다. `agent.run_job`의 계정 확인 실패 중단, 클릭 후 응답 없음/예외의 uncertain 분류, 성공 플래그보다 uncertain 우선 처리를 수정하고 기존 오프라인 테스트에 회귀 사례를 추가했다. 최종 변경 후 40개 테스트가 통과했다. 자세한 범위는 [재설계 명세의 검증 기록](BLOG_AUTOMATION_V2_DESIGN.md#검증-기록)에 기록한다.
