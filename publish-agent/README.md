# 닥터보이스 프로 발행 에이전트 (publish-agent)

서버(닥터보이스 백엔드)에 쌓인 **네이버 블로그 예약 발행 잡**을 가져와, 네이버 SmartEditor ONE 에
**예약발행**으로 등록하는 로컬 CLI 데몬입니다. 트레이 아이콘·GUI 없이 터미널에서 돕니다.

- 네이버 블로그(계정)마다 크롬 프로필을 따로 둡니다 → 로그인은 블로그당 한 번만.
- 크롬 확장(`chrome-extension/naver-poster.js` v15)의 검증된 셀렉터·순서를 Playwright 로 옮긴 것입니다.
- 사용자가 다른 일을 하는 동안 뒤에서 돕니다. 창은 처음 열 때만 뜨고, 이후에는 앞으로 끌어오지 않습니다.

## 1. 설치

- Python 3.12
- 패키지: `pip install -r requirements.txt` (또는 `pip install playwright httpx`)
- 브라우저: `playwright install chromium`
  - PC 에 크롬이 있으면 크롬(`channel=chrome`)을 우선 쓰고, 없으면 Playwright 번들 Chromium 을 씁니다.
  - 번들 Chromium 이 아직 설치되지 않았고 크롬도 없으면 위 명령을 한 번 실행하세요.

## 2. 실행

```bash
cd publish-agent
python agent.py --server http://127.0.0.1:8010 --email you@example.com --password '비밀번호'
```

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--server` | `http://127.0.0.1:8010` | 백엔드 주소 (`DV_SERVER` 환경변수로도 가능) |
| `--email` / `--password` | — | 닥터보이스 계정 (`DV_EMAIL` / `DV_PASSWORD`) |
| `--blog 라벨또는아이디` | 전체 | 이 블로그만 처리 |
| `--once` | 끔 | 한 바퀴만 돌고 종료 (기본은 `--interval` 초마다 반복) |
| `--dry-run` | 끔 | 최종 **발행 버튼만 누르지 않음** (아래 참고) |
| `--headless true` | false | 창 없이. 로그인/캡차를 사람이 봐야 하므로 평소엔 false 권장 |
| `--profiles-dir` | `./profiles` | 블로그별 크롬 프로필 저장 위치 (`profiles/<네이버ID>/`) |
| `--max-per-blog` | 5 | 한 바퀴에 블로그당 최대 발행 수 |
| `--min-gap` / `--max-gap` | 20 / 60 | 글 사이 무작위 대기(초) |
| `--interval` | 300 | 반복 주기(초) |
| `--captcha-wait` | 180 | 발행 단계 캡차를 사람이 풀 때까지 기다리는 시간(초) |
| `--window-pos x,y` | — | 브라우저 창 위치. 보조 모니터나 화면 밖(예: `2000,0`)으로 밀어 방해 최소화 |
| `--no-images` | 끔 | 사진 없이 발행(서버 `include_images=false`) |
| `-v` | | 상세 로그 |

한 바퀴의 흐름: 서버 로그인 → `agent/summary` → 대기 잡이 있는 블로그마다
크롬 프로필 열기 → 로그인 확인 → **로그인된 블로그 ID 대조** → `agent/claim` → 잡마다 글 작성·예약 등록 → 결과 보고.

### 첫 실행 (블로그당 1회)

1. 그 블로그의 크롬 창이 뜨고 글쓰기 페이지로 갑니다.
2. 세션이 없으면 네이버 로그인 페이지로 튕깁니다. 앱에 저장된 아이디/비밀번호가 있으면 **한 번** 자동 입력·제출합니다.
3. 네이버가 **캡차·새 기기 등록**을 요구하면 에이전트는 멈추고 서버의 블로그 상태를 `captcha`/`login_required` 로 바꿉니다.
   → 그 크롬 창에서 **직접** 로그인/캡차를 마쳐 주세요("로그인 상태 유지" 체크 권장). 세션은 프로필에 남습니다.
4. 다음 바퀴(또는 `--once` 로 다시 실행)에서 로그인이 확인되면 블로그 상태를 자동으로 `active` 로 되돌리고 이어서 합니다.

다른 계정으로 로그인돼 있으면(`platonmarketing` 을 기대했는데 다른 ID) 그 블로그는 건드리지 않고 `login_required` 로 표시합니다.

## 3. 예약 안전장치 (가장 중요)

네이버 발행 레이어의 기본값은 **"현재" 시각 발행**입니다. 예약 시간 설정이 조용히 실패한 채 발행 버튼을 누르면
글이 **즉시 공개**됩니다 — 100건 배치면 100건이 한꺼번에 나갑니다. 그래서:

1. **잡을 받자마자** 예약 시각을 검사합니다. 현재(KST)로부터 15분 이내면 화면을 건드리지도 않고 실패 보고합니다.
2. 발행 레이어에서 `예약` 라디오(`#radio_time2`) → 날짜(jQuery datepicker 로 연·월 이동 후 일 클릭)
   → 시/분 `select`(React 제어라 native setter + input/change) 순으로 설정하고, **각 단계마다 값을 다시 읽어 확인**합니다.
   - 분은 네이버가 10분 단위만 받으므로 **내림**합니다(14:37 → 14:30).
3. 어느 한 단계라도 실패하면 `ScheduleError` → **발행 버튼을 누르지 않고** 실패로 보고합니다. (`naver_editor.set_schedule`, `agent.run_job`)
4. 카테고리를 못 찾아도 발행하지 않습니다(엉뚱한 카테고리 공개 방지).
5. 발행 클릭 **이후**에 생긴 문제(캡차 미해결, 화면 변화 없음)는 `uncertain` 으로 보고해 사람이 네이버 예약 목록에서 확인하게 합니다.
   재큐잉하지 않습니다 — 이미 등록됐을 수 있어 중복 발행을 막기 위함입니다.

## 4. dry-run

```bash
python agent.py ... --once --dry-run
```

제목·본문·사진·카테고리·태그·예약 시각까지 **전부 실제로 입력**하고, 최종 발행 버튼만 누르지 않습니다.
서버에는 `ok=false, uncertain=false, message='dry-run'` 으로 보고하므로 **발행됨으로 표시되는 건 없습니다**.
단, 서버는 이를 실패 1회로 세어(`attempts+1`) 10분 뒤 재시도로 돌립니다. 네이버 에디터에는 작성 중인 글이 남으므로
확인 후 창에서 닫거나(임시저장 팝업은 '취소'), 다음 잡 시작 시 자동으로 새 글로 시작합니다.

## 5. 로그

- 콘솔 + `logs/agent-YYYY-MM-DD.log` (UTF-8). 모든 에디터 단계(프레임 탐지, 제목, 본문 동작 수, 이미지 경로, 카테고리, 예약 값 확인, 발행 후 판정)가 한 줄씩 남습니다.
- 브라우저 `alert/confirm` 은 자동으로 '확인'하고 내용을 로그·결과 메시지에 남깁니다.

## 6. 동작 세부 (포팅 메모)

| 단계 | 방법 (naver-poster.js 와 동일) |
|---|---|
| 에디터 프레임 | `.se-documentTitle` 이 최상위 문서에 있으면 그대로, 아니면 `#mainFrame` iframe 을 자동 선택 |
| 제목/본문 입력 | 문단 좌표 클릭 → Ctrl+A → `page.keyboard.insert_text` (DOM 대입 금지, SE ONE 이 무시함) |
| 줄바꿈 | 줄마다 Enter. 글 블록 사이 Enter 2회(빈 줄), 글↔사진 사이 1회 |
| 강조 | 문단(빈 줄 기준)당 키워드 1회만 Ctrl+B 감싸기, 긴 키워드 우선 |
| 사진 | 1순위: 툴바 `button[data-name="image"]` 클릭 → 파일 선택창 가로채서 `set_files` / 2순위: `DragEvent` + `DataTransfer(File)` 합성 드롭. 이미지 컴포넌트 수가 늘었는지로 확인, 3회 재시도, 실패 시 발행 안 함 |
| 공개/검색/카테고리 | `#open_public` 등 라디오, `#publish-option-search`, `[data-click-area="tpb*i.category"]` + `[role="menu"] input[data-testid^="categoryBtn_"]` |
| 태그 | `#tag-input` 에 하나씩 입력+Enter (없으면 생략, 발행은 계속) |
| 발행 | `[data-click-area="tpb.publish"]` → `[data-testid="seOnePublishBtn"]`. 확인 팝업 클릭 시 헤더 발행/최종 발행 버튼은 제외(이중 클릭 방지) |
| 캡차 | 모든 프레임에서 `iframe[id^="ncaptcha-iframe"]` 등 감지 |

## 7. 알려진 한계 / 미검증

이 포팅은 **실제 네이버 세션에서 아직 검증되지 않았습니다.** 오프라인 테스트(`test_dryrun_offline.py`)는 로직·서버 계약만 확인합니다.
배포 전 반드시 `--once --dry-run` 으로 1~2건 돌려 아래를 눈으로 확인하세요.

- 이미지: 파일 선택창 경로가 SE ONE 에서 실제로 캐럿 위치에 삽입되는지, 삽입 후 캐럿이 사진 뒤로 돌아오는지(`_refocus_body_end`).
  확장에서도 합성 드롭은 "실측 미검증"(SELECTORS.md) 상태였습니다.
- 발행 성공 판정: 예약 등록 후 네이버가 페이지를 이동하는지/레이어만 닫는지 실측이 없어 두 경우 모두 성공으로 봅니다. 20초 안에 아무 변화가 없으면 `uncertain`.
- 태그 입력(`#tag-input`)은 확장에 구현이 없던 부분이라 새로 넣었습니다(best-effort).
- 로그인 자동 입력은 네이버 봇 탐지로 캡차가 뜰 수 있습니다 → 그 창에서 한 번 직접 로그인하면 이후엔 세션 재사용.
- Windows 에서 새 창은 처음 열릴 때 한 번 포커스를 가져갑니다. `--window-pos` 로 화면 밖에 두면 덜 방해됩니다.
- 헤드리스에서는 네이버가 로그인·발행을 막을 가능성이 높습니다.

### 셀렉터가 바뀌었을 때

1. `chrome-extension/SELECTORS.md` 가 원본 지도입니다. 크롬 개발자도구로 새 `data-click-area` / `data-testid` / `data-name` 을 확보해 거기부터 갱신하세요.
2. `naver_editor.py` 상단 `S = {...}` 에 모든 셀렉터가 모여 있습니다. 카테고리/날짜 선택은 `JS_SELECT_CATEGORY` / `JS_SELECT_DATE` 안의 JS 문자열(확장 코드와 동일)을 고칩니다.
3. 해시 클래스(`input_date__QmA0s` 등)는 배포마다 바뀝니다. 가능하면 의미 기반 속성을 앞에, 해시 클래스는 폴백으로 뒤에 두세요.
4. 고친 뒤 `python test_dryrun_offline.py` → `python agent.py ... --once --dry-run` 순으로 확인합니다.

## 8. 테스트

```bash
python test_dryrun_offline.py
```

네이버·서버 없이 돕니다: 분 내림/예약 파싱, 블록→타이핑 계획, data URL 디코드, 모바일 포맷 멱등성,
가짜 서버(`http.server`)에 대한 요청 모양·401 재로그인, 그리고 대역 에디터로 `run_job` 의
"예약 설정 실패 시 발행 클릭 금지 / dry-run 은 발행 안 함 / 블로그 불일치 시 중단" 규칙을 검증합니다.

### 브라우저 포함 오프라인 테스트 (네이버 접속 없음)

```bash
python test_editor_fake_page.py
```

`fake_editor/` 의 가짜 SmartEditor 페이지(SELECTORS.md 셀렉터만 흉내, `#mainFrame` iframe 구조)를 로컬 http.server 로 띄우고
실제 Chromium 으로 `NaverEditor` 전 단계와 `agent.run_once` 엔드투엔드(가짜 서버 + 가짜 에디터: dry-run / 실발행 / 블로그 불일치)를 돌립니다.
Playwright Chromium 이 없으면 자동으로 건너뜁니다. **가짜 페이지가 통과해도 실제 네이버 DOM 과 같다는 보장은 아닙니다** — 셀렉터 계약만 검증합니다.
(`DV_WRITE_URL` 환경변수는 이 테스트가 글쓰기 URL 을 가짜 페이지로 바꾸는 훅입니다. 평소엔 설정하지 마세요.)

## 파일

- `agent.py` — CLI 데몬(루프, 블로그별 브라우저 풀, 로그인 처리, 잡 실행·보고)
- `naver_editor.py` — `NaverEditor(page)`: 에디터 자동화 포팅
- `plan.py` — 순수 로직(모바일 포맷, 타이핑 계획, 예약 시각, data URL)
- `server_client.py` — 백엔드 httpx 클라이언트
- `test_dryrun_offline.py` — 오프라인 테스트
- `profiles/` — 블로그별 크롬 프로필(자동 생성, 로그인 세션 포함 → 공유·커밋 금지)
- `logs/` — 일자별 로그
