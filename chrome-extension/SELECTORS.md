# 네이버 SmartEditor ONE - 안정 셀렉터 맵 (2026-07 확보)

> 원칙: 해시 클래스(`__C5hlm` 등)는 **폴백**으로만. 우선순위는 `data-click-area` / `data-name` / `data-log` / `data-testid` (의미 기반, 버전 안정).

## 페이지 구조
- 글쓰기 URL: `https://blog.naver.com/GoBlogWrite.naver`
- 에디터는 **`#mainFrame` iframe** 내부 (`src=/PostWriteForm.naver?blogId=...`)
- content script는 `all_frames: true`로 iframe 내부에서도 실행됨 → iframe 안에서 직접 DOM 접근 가능

## 로그인 판별 (네이버 메인 / 글쓰기 공통)
- 글쓰기 페이지 초기 state: `window.__REACT_QUERY_STATE__` → GetCurrentUser → `result.loggedIn === true`, `result.naverId`
- 네이버 메인: `window['EAGER-DATA'].GV.login === true`
- 폴백: 로그아웃 버튼 존재 `.MyView-module__btn_logout___bsTOJ`

## 상단 버튼 바 (에디터 헤더) — `.header__Ceaap`
| 기능 | 안정 셀렉터 | 폴백 |
|---|---|---|
| **저장(임시저장)** | `[data-click-area="tpb.save"]` | `.save_btn__bzc5B` / text="저장" |
| 임시저장 목록 | `[data-click-area="tpb*s.count"]` | `.save_count_btn__ZTLNa` |
| 예약발행 목록 | `[data-click-area="tpb*t.schedule"]` | `.reserve_btn__Km5Xh` |
| **발행(레이어 열기)** | `[data-click-area="tpb.publish"]` | `.publish_btn__m9KHH` / text="발행" |
| 자동저장 메시지 | `.autosave_message__PgBf8` | — |

## 툴바 (본문 삽입) — `.se-toolbar.se-document-toolbar`
| 기능 | 안정 셀렉터 |
|---|---|
| **사진** | `button[data-name="image"][data-group="documentToolbar"]` (`[data-log="dot.img"]`) |
| MYBOX | `button[data-name="social-media-image"]` |
| 동영상 | `button[data-name="video"]` |
| 인용구 | `button[data-name="quotation"][data-value="default"]` |
| 구분선 | `button[data-name="horizontal-line"][data-value="default"]` |
| 링크 | `button[data-name="oglink"]` |

## 인라인 삽입 메뉴 (문단 왼쪽 + 버튼)
- 사진: `.se-insert-menu-button-image` (`[data-key="image"]`)
- 인용구: `.se-insert-menu-button-quotation`
- 구분선: `.se-insert-menu-button-horizontalLine`

## 제목 영역
- 컴포넌트: `.se-component.se-documentTitle`
- 입력 문단: `.se-documentTitle .se-title-text .se-text-paragraph` (contenteditable 대상)
- placeholder: `.se-documentTitle .se-placeholder` (text "제목")
- 빈 상태 표시: `.se-title-text.se-is-empty`

## 본문 영역
- 컴포넌트: `.se-component.se-text` → `.se-section-text`
- 입력 문단: `.se-component.se-text .se-text-paragraph`
- 텍스트 모듈: `.se-module-text.__se-unit`
- 폰트 노드: `span.__se-node` (`.se-ff-nanummaruburi.se-fs16`)
- placeholder: `.se-component.se-text .se-placeholder`

## 텍스트 입력 방식 (중요)
- SE ONE은 키입력을 숨은 버퍼(`#input_buffer...` iframe + hidden contenteditable)로 캡처
- **가장 안정적**: `chrome.debugger`(CDP) `Input.insertText` — 실제 타이핑처럼 캡처됨 (기존 background.js 방식 유지가 정답)
- 캐럿 위치: 문단 클릭(`Input.dispatchMouseEvent`) 후 insertText
- 캡차 iframe 존재 가능: `#ncaptcha-iframe-*` (`wtm.pstatic.net`) → 뜨면 사용자에게 넘김

## 발행 설정 레이어 — `.layer_publish__vA9PX`
| 기능 | 안정 셀렉터 |
|---|---|
| 카테고리 버튼 | `[data-click-area="tpb*i.category"]` |
| 공개-전체 | `#open_public` (`[data-testid="openType_2"]`) |
| 공개-비공개 | `#open_private` (`[data-testid="openType_0"]`) |
| 공개-이웃 | `#open_neighbor` / 서로이웃 `#open_both_neighbor` |
| 발행시간-현재 | `#radio_time1` (`[data-testid="nowTimeRadioBtn"]`) |
| 발행시간-예약 | `#radio_time2` (`[data-testid="preTimeRadioBtn"]`) |
| 태그 입력 | `#tag-input` |
| 검색허용 | `#publish-option-search` |
| 공지등록 | `#set-notice` |
| **최종 발행 버튼** | `[data-testid="seOnePublishBtn"]` (`[data-click-area="tpb*i.publish"]`) |

## 예약발행 시간 설정 (확보) — `#radio_time2`(예약) 클릭 후 나타남
- 컨테이너: `.time_setting__v6YRU`
- 날짜: `input.input_date__QmA0s` (readonly, 형식 "2026. 07. 13", 클릭 시 **jQuery UI datepicker** 오픈)
- 시: `select.hour_option__J_heO` (00~23)
- 분: `select.minute_option__Vb3xB` — **00/10/20/30/40/50 (10분 단위만!)**
- ⚠️ select는 React 제어 → native value setter + input/change 이벤트 dispatch 필요
- ⚠️ 예약 시간 계산 시 분은 10분 단위로 올림/반올림

### 날짜 캘린더 (jQuery UI datepicker, 2026-07 확보) — `input.input_date__QmA0s` 클릭 시
- 루트: `#ui-datepicker-div` (header + 날짜 table 을 감쌈)
- 헤더: `.ui-datepicker-header` / 연 `.ui-datepicker-year`("2026") / 월 `.ui-datepicker-month`("7월", 숫자만 파싱)
- 이전달: `.ui-datepicker-prev` (당월이 최소면 `.ui-state-disabled` + `pointer-events:none`)
- 다음달: `.ui-datepicker-next` (`title="다음달"`)
- 날짜 셀: `table td > button.ui-state-default` (구버전은 `a.ui-state-default`)
  - 비활성일: `td.ui-state-disabled` (지난 날짜 등) → **선택 제외 필수**
  - 오늘/선택: `button.ui-state-active`(+`ui-state-highlight`)
- 선택 방법: next/prev 로 목표 연·월 이동 → 목표 일 button 텍스트 매칭 클릭 (naver-poster `selectScheduleDate()` 구현)

## 캡차 (핸드오프) — `#ncaptcha-iframe-*` (wtm.pstatic.net, cross-origin)
- 감지: `iframe[id^="ncaptcha-iframe"]`, `iframe[src*="captcha"]`, `.captcha_wrap` 등 (iframe 요소 존재만 확인, 내부는 접근 불가)
- 대응: 발행 클릭 후 감지 시 자동화 멈추고 오버레이 안내 → 사용자가 직접 입력, 사라지면 재개 (naver-poster `waitForCaptchaResolved()`)

## ⏳ 아직 미확보
- 드래프트 복원 팝업(`작성 중이던 글`) 확인 버튼 셀렉터 — 현재 텍스트 매칭('취소'/'새로 작성')으로 best-effort
- **이미지 삽입 실측 미검증**: `dropImage` 합성 DragEvent drop 방식이 실제로 먹히는지 브라우저 확인 필요
- **이미지 컴포넌트 클래스 미확보**: 업로드된 사진이 어떤 컴포넌트로 붙는지 실측 안 됨.
  `naver-poster.js` `imageComponentCount()` 는 업로드 성공 판정에 이 값을 쓰는데,
  확실한 클래스를 모르므로 세 신호의 최댓값으로 방어한다:
  `.se-component.se-image` / `.se-component[class*="image" i]` / `.se-content img`.
  → 실측하면 정확한 셀렉터로 좁힐 것. **판정이 틀리면 정상 업로드가 실패로 찍혀 발행이 막힌다**
  (사진 없이 나가는 것보다는 낫지만, 배포 전 1~2건 실제 예약발행으로 반드시 확인).
- 로그인: 세션 재사용 설계라 자동 입력 안 함(수동 1회). 로그인 완료 후 복귀는 `content-login.js` v15가 `pendingJob` 감지해 처리

## 계정 정보 (확보)
- blogId: `platonmarketing`, naverId: `lhs0609c`, 닉네임: 플라톤마케터

---

# Gemini (gemini.google.com) - 셀렉터 맵 (2026-07 실측)

> 용도: 엑셀 키워드 배치 → 프롬프트 주입 → 글 수확. `gemini-writer.js` 가 사용.
> 원칙은 네이버와 동일 — `data-test-id` / `aria-label` 우선, Angular 해시 속성(`_ngcontent-ng-c2538485940`)은 **절대 쓰지 말 것**(빌드마다 바뀜).

## 앱 구조
- 루트: `chat-app-orchestrator#app-root` → `chat-app` → `chat-window`
- 대화 영역: `chat-window-content` → `infinite-scroller[data-test-id="chat-history-container"]`
- 대화 1턴: `.conversation-container[id]` (id = 응답 id, 예: `46a81ffe1ed2be77`)
- 로그인 판별: `sidenav-mavatar-footer .mavatar-image` 존재 여부 (없으면 로그아웃 상태)

## 입력 (Quill 에디터)
| 대상 | 셀렉터 |
|---|---|
| 입력창 | `rich-textarea .ql-editor[role="textbox"]` (`aria-label="Gemini 프롬프트 입력"`) |
| 빈 상태 판별 | 같은 요소에 `.ql-blank` 클래스 |
| 입력 영역 루트 | `input-area-v2 .text-input-field` |

**입력 방식 (중요)**: Quill 이라 SE ONE 과 동일하게 **CDP `Input.insertText`** 가 정답.
`textContent` 직접 대입은 Quill 내부 Delta 모델과 어긋나 전송이 안 된다.

**전송**: `rich-textarea[enterkeyhint="send"]` → **Enter 키(CDP `Input.dispatchKeyEvent`)로 전송**.
전송 버튼 셀렉터를 찾을 필요 없음 — 버튼은 입력이 비면 렌더링조차 안 되고, 위치도 자주 바뀐다.
Enter 방식이 UI 개편에 훨씬 강하다.

## 응답 완료 판정 (핵심)
휴리스틱(글자수 정체 감지) 불필요. DOM 에 명시적 신호가 있다:

| 신호 | 완료 시 값 | 신뢰도 |
|---|---|---|
| `.response-footer` | `class` 에 **`complete`** 추가 | 1순위 |
| `.markdown-main-panel` | `aria-busy="false"` | 2순위 |
| `message-actions` | 완료 후에만 존재 (복사/다시실행 버튼) | 3순위 |

→ 마지막 `model-response` 안에서 `.response-footer.complete` 를 폴링. 세 신호 중 2개 이상이면 완료로 간주.
생성 중에는 `thinking-overlay`, `structured-content-container.processing-state-visible` 가 활성.

## 응답 본문 수확
```
model-response:last-of-type message-content .markdown.markdown-main-panel
```
- `id="model-response-message-content<응답id>"` 형태, 내부는 `<p data-path-to-node="0">` 순서대로
- `innerText` 로 뽑으면 문단 구분 유지됨 → 기존 `splitTitleBody()` 에 그대로 투입
- 대안: `[data-test-id="copy-button"]` 클릭 시 마크다운째로 클립보드 복사. 다만 `clipboardRead` 권한이 추가로 필요하므로 **innerText 방식을 기본으로 쓴다**

## 사용자 질문 (검증용)
- `user-query .query-text` → 보낸 프롬프트가 실제로 들어갔는지 확인용

## 대화 초기화 / 모델
| 대상 | 셀렉터 | 비고 |
|---|---|---|
| **임시 채팅** | `[data-test-id="temp-chat-button"]` | **배치 실행 시 이걸 켤 것.** 사이드바에 기록이 안 쌓이고 이전 글이 다음 글에 영향 없음 |
| 새 채팅 | `[data-test-id="new-chat-button"] a[href="/app"]` | 페이지 재로드 발생 — 임시 채팅보다 느림 |
| 모델 선택 | `[data-test-id="bard-mode-menu-button"]` | 현재 `Flash`. 라벨은 `.picker-primary-text` |

## ⏳ 아직 미확보
- **정지 버튼** — 생성 중 마크업 미확보. 다만 `.response-footer.complete` 로 완료 판정이 되므로 현재 설계상 불필요.
  중간 취소 기능을 넣게 되면 그때 실측할 것
- **에러/한도 초과 상태** — `freemium-file-upload-quota-exceeded-disclaimer` 같은 요소는 보이지만 실제 트리거 시 마크업 미확인.
  무료 한도 초과 시 응답이 안 나오고 `complete` 도 안 붙어 **가드 타임아웃으로만 걸린다**. 배치 중 연속 실패하면 이걸 의심할 것
- 모델을 Flash 외(Pro 등)로 바꾸는 메뉴 항목 셀렉터 — 메뉴를 열어야 렌더링됨
