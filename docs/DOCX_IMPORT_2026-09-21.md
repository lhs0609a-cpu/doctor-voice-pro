# 워드 업로드 — 서식을 살려서 발행까지

## 무엇이 문제였나

업로드는 `docx.Document(...).paragraphs` 로 문단 텍스트만 읽었다. `paragraphs` 는 표 안의
문단을 건너뛰기 때문에 **표가 통째로 사라졌고**, 굵게·색·소제목·인용·목록·문서 안 사진도
전부 평문이 됐다. 병원이 쓰던 원고가 네이버에 그대로 올라가지 않는 원인이다.

## 층

| 층 | 무엇 | 코드 |
| --- | --- | --- |
| 읽기 | .docx → 블록(서식·순서 보존) | `services/docx_import.py` |
| 저장 | 블록은 원고에, 사진 바이트는 사진 풀에 | `api/campaign.py` `_parse_docx_upload` |
| 보내기 | 실행기 능력에 맞춰 블록을 붙이거나 눌러서 | `api/campaign.py` `_doc_blocks` / `/agent/claim` |

### 읽기 — `services/docx_import.py`

문서 순서를 지키려고 `body` 의 자식(`w:p`, `w:tbl`)을 직접 순회한다. 블록 규격:

```
{"type": "text",    "spans": [span…], "content": "평문"}
{"type": "heading", "level": 1|2|3, "spans": […], "content": …}
{"type": "quote",   "spans": […], "content": …}
{"type": "list",    "ordered": bool, "items": [[span…], …], "content": …}
{"type": "table",   "header": bool, "rows": [[[span…], …], …], "content": …}
{"type": "image",   "image": "data:…", "name": "사진.png"}      ← 업로드가 풀로 옮긴다
span = {"t": "글자", "b": 굵게, "i": 기울임, "u": 밑줄, "color": "#RRGGBB", "size": 15.0}
```

- 서식이 없는 키는 아예 넣지 않는다(전송량·가독성).
- 모든 블록에 평문 `content` 를 같이 넣는다 — 서식을 모르는 실행기에는 이것만 보낸다.
- 제목 = 첫 소제목, 없으면 60자 이하인 첫 문단, 그것도 없으면 파일 이름.
- 한국어 워드 스타일 이름('제목 1', '인용')도 알아본다.
- 상한: 사진 30장·한 장 8MB·표 400칸. 넘으면 버리고 `warnings` 에 남긴다.

### 저장

- `campaign_drafts.blocks`(JSON) 신설. 없으면(생성·붙여넣기) 예전처럼 `body` 를 문단으로 자른다.
- 문서 안 사진은 **사진 풀 행**(`pool_images`)으로 넣고 블록에는 `pool_image_id` 만 남긴다.
  base64 를 원고 JSON 에 담으면 원고 1건이 수십 MB가 된다. 정규화는 풀 업로드와 같은
  `_normalize_upload`(비율 유지·최대폭 축소·JPEG).
- `draft.body` 는 표·목록까지 포함한 평문이다(글자수·금칙어·유사도 검사가 쓴다).
  워드 원고는 `writer.reflow` 를 걸지 않는다 — 글쓴이 줄바꿈이 곧 원고다.
- 읽은 내역은 `checks['import']` 에: `{source, images, tables, headings, warnings}`.
  업로드 토스트가 이것을 보여 준다("서식 그대로 읽었어요 — 표 1개 · 사진 3장").

### 보내기 — 실행기 능력 `rich_text_v1`

`/agent/claim` 이 `capabilities` 를 본다.

- `rich_text_v1` 있음 → 블록을 그대로. `JobBlock` 에 `spans·level·ordered·items·header·rows` 추가.
- 없음 → `docx_import.flatten_blocks` 로 평문 + 사진만. **지금 실행기가 여기 해당한다.**
  실행기의 `plan_blocks` 는 `text`/`image` 만 알아서, 누르지 않고 보내면 표·소제목이
  조용히 사라진다. 이 게이트가 그것을 막는다.
- 페이로드는 빈 필드를 뺀다(`exclude_none`). 블록마다 null 8개를 실어 보내지 않는다.
- 사진을 못 찾으면 발행을 중단한다(사진 빠진 채로 올리지 않는다).
- `options.reformat` 신설: 워드 원고면 `False`. 실행기가 모바일 재정렬(`mobile_format`)을
  건너뛴다. 옛 실행기는 이 키를 모르고 무시한다(= 기존 동작).

### 본문을 고치면

`PUT /drafts/{id}` 로 본문을 고치면 `blocks` 를 지운다. 남겨 두면 발행이 블록을 먼저 보고
고친 글이 조용히 사라진다. 고친 글이 이긴다.

## 실제 원고로 돌려 본 것 (2026-09-21)

`네이버발행_원고01_프리사이스로해달라던두분을.docx` (4.7MB, 9,566자, 사진 12장, 표 1개)로
로컬 백엔드 + 실행기까지 태웠다. 읽기·저장·예약은 통과, 네이버 등록은 로그인 대기에서 멈춰 있다.

그 과정에서 드러난 **세 가지 버그**(전부 이 기능 밖의 기존 코드):

1. **올린 원고는 예약이 안 됐다.** `_schedule_inputs` 가 `Draft.source != "upload"` 로 업로드를
   통째로 제외하고 있었다. 변형(variant)의 원본을 빼려던 필터인데, 워드로 올린 완성 원고까지
   막아 이 기능의 목적 자체가 불가능했다. 이제 **자식(변형)이 있는 원고만** 뺀다.
2. **첫 실행에서 크롬이 15초 안에 못 뜬다.** 컨텍스트 기본 타임아웃이 새 프로필 생성에는 모자라
   처음 쓰는 사람이 바로 오류를 본다. 글쓰기 페이지 이동에 자체 타임아웃을 준다.
3. **로그인 페이지에서 정체불명의 오류가 났다.** `wait_until="domcontentloaded"` 로 기다리다
   로그인 페이지 로딩에서 타임아웃 → "로그인 필요" 대신 `Page.goto: Timeout`. `commit` 으로
   바꿔, 무엇이 떴는지는 뒤따르는 판정 루프가 정한다.

## 검증

`backend/test_docx_import.py` 18개(파서) + `backend/test_docx_publish.py` 10개(업로드→클레임),
기존 발행·자동운영·키워드 검사까지 110개 통과. `publish-agent/test_dryrun_offline.py` 64개 통과.

**아직 안 한 것**

- 실행기가 `rich_text_v1` 을 구현하지 않았다. 즉 **지금은 표·소제목·인용이 평문으로 올라간다**
  (예전처럼 사라지지는 않는다). 스마트에디터에 굵게·색·표를 넣는 것은 Playwright 쪽 작업이고
  실제 네이버로 확인해야 한다.
- 문서 안 사진은 풀에 들어가지만 유니크화(메타 교체)를 거치지 않는다. 같은 사진을 여러 블로그에
  쓰면 중복으로 잡힐 수 있다.
- .doc(옛 형식)·HWP 는 여전히 못 읽는다.
