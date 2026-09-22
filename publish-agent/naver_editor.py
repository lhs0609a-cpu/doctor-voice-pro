"""네이버 SmartEditor ONE 자동화 (chrome-extension/naver-poster.js v15 + background.js 의 Playwright 포트).

원칙
- 셀렉터는 chrome-extension/SELECTORS.md 에 실측된 것만 쓴다(data-click-area / data-name / data-testid 우선,
  해시 클래스는 폴백). 새로 지어내지 않는다.
- 텍스트는 반드시 키보드 insertText(page.keyboard.insert_text)로 넣는다. DOM 대입은 SE ONE 이 무시한다.
- 예약 날짜/시각 설정이 조금이라도 실패하면 ScheduleError 를 던져 '발행' 클릭 전에 멈춘다.
  (안 멈추면 네이버 기본값 '지금'으로 즉시 발행되는 최악의 사고가 난다.)
- 에디터는 #mainFrame iframe 안에 있을 수도, 최상위 문서에 있을 수도 있어 매번 프레임을 탐지한다.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from playwright.async_api import Frame, Page, TimeoutError as PWTimeout

from plan import Op, camera_filename, decode_data_url, ext_for_mime, merge_text_ops, plan_blocks, has_formatting

log = logging.getLogger("editor")

WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"

# 예약 글 목록 — 로그인한 브라우저 안에서만 보이는 화면이다. 서버는 이 목록을 볼 길이 없어
# 실행기가 읽어다 준다. 주소는 네이버가 언제든 바꾸므로 후보를 차례로 열어 보고, 예약 행이
# 읽히는 첫 화면을 쓴다. 현장에서 주소가 바뀌면 DV_RESERVE_URL 로 덮어쓸 수 있다(재배포 없이).
# {blog} 자리에 블로그 ID 가 들어간다.
RESERVE_URLS = (
    "https://admin.blog.naver.com/{blog}/post/reserve",
    "https://blog.naver.com/PostWriteList.naver?blogId={blog}&reserveYn=Y",
)


# 예약 행에 적힌 시각. "2026. 9. 23. 14:30", "9월 23일 오후 2:30", "2026-09-23 14:30" 모두 받는다.
RESERVE_AT_RE = re.compile(
    r"(?:(?P<y>20\d{2})\s*[.\-/년]\s*)?(?P<m>\d{1,2})\s*[.\-/월]\s*(?P<d>\d{1,2})\s*일?"
    r"[^\d]{0,10}?(?P<ampm>오전|오후)?\s*(?P<h>\d{1,2})\s*[:시]\s*(?P<min>\d{2})"
)


def parse_reservation_rows(rows, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """예약 목록 행 텍스트에서 (예약 시각, 제목)을 뽑는다.

    네이버는 올해 글의 연도를 생략한다. 연도가 없으면 앞으로 다가올 날짜로 읽는다
    — 예약 목록에 과거만 남는 일은 없으므로, 12월에 본 '1월 3일'은 내년이다."""
    now = now or datetime.now()
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        text = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        m = RESERVE_AT_RE.search(text)
        if not m:
            continue
        hour, minute = int(m.group("h")), int(m.group("min"))
        if m.group("ampm") == "오후" and hour < 12:
            hour += 12
        elif m.group("ampm") == "오전" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            continue
        year = int(m.group("y")) if m.group("y") else now.year
        try:
            at = datetime(year, int(m.group("m")), int(m.group("d")), hour, minute)
        except ValueError:
            continue
        if not m.group("y") and (now - at).days > 30:
            at = at.replace(year=year + 1)        # 연말에 본 내년 예약
        title = re.sub(r"\s+", " ", str(row.get("title") or "")).strip()
        if not title:
            title = RESERVE_AT_RE.sub("", text).strip(" ·|-")[:200]
        key = at.replace(second=0, microsecond=0)
        if key in seen:
            continue
        seen.add(key)
        out.append({"at": key, "title": title or None})
    return sorted(out, key=lambda r: r["at"])


# ---------------------------------------------------------------- 예외
class EditorError(RuntimeError):
    """자동화 중 복구 불가한 오류(잡은 실패로 보고)."""


class ScheduleError(EditorError):
    """예약 날짜/시각 설정 실패 — 반드시 발행 클릭 전에 발생해야 한다."""


class LoginRequired(EditorError):
    """로그인 페이지로 튕김 / 세션 없음."""


class CaptchaDetected(EditorError):
    """캡차·기기등록 등 보안 확인 화면. 사람이 풀어야 한다."""


class BlogMismatch(EditorError):
    """로그인된 블로그가 기대한 블로그와 다름."""


# ---------------------------------------------------------------- 셀렉터 (SELECTORS.md)
S = {
    "title_para": ".se-documentTitle .se-text-paragraph",
    "body_para": ".se-component.se-text .se-text-paragraph",
    "editor_marker": ".se-component.se-documentTitle, .se-documentTitle",
    "toolbar_image": 'button[data-name="image"][data-group="documentToolbar"], button[data-name="image"], .se-insert-menu-button-image',
    "publish_open": '[data-click-area="tpb.publish"]',
    "publish_open_fallback": ".publish_btn__m9KHH",
    "publish_final": '[data-testid="seOnePublishBtn"], [data-click-area="tpb*i.publish"]',
    "open_type": {"public": "#open_public", "neighbor": "#open_neighbor", "both": "#open_both_neighbor", "private": "#open_private"},
    "search_allow": "#publish-option-search",
    "tag_input": "#tag-input",
    "save_draft": '[data-click-area="tpb.save"], .save_btn__bzc5B',
    "time_now": '#radio_time1, [data-testid="nowTimeRadioBtn"]',
    "time_reserve": '#radio_time2, [data-testid="preTimeRadioBtn"]',
    # 네이버는 클래스 뒤의 해시 꼬리(__J_heO 등)를 배포 때마다 바꾼다(2026-09-11 실측: hour_option__J_heO → __Vk2eR).
    # 이름 앞부분으로 찾아야 꼬리가 바뀌어도 예약 시각을 넣을 수 있다. 예전 이름도 그대로 인정한다.
    "date_input": 'input.input_date__QmA0s, .date__Lkn7S input, input[class*="input_date__"], input[readonly][class*="input_date"]',
    "hour_select": 'select.hour_option__J_heO, .hour__ckNMb select, select[class*="hour_option__"], [class*="hour__"] select',
    "minute_select": 'select.minute_option__Vb3xB, .minute__KXXvZ select, select[class*="minute_option__"], [class*="minute__"] select',
    "captcha": (
        'iframe[id^="ncaptcha-iframe"], iframe[src*="ncaptcha"], iframe[src*="captcha"], '
        '#ncaptcha, .captcha_wrap, [class*="captcha"] input[type="text"], #captcha, img#captchaimg'
    ),
    "login_challenge": 'iframe[id^="ncaptcha-iframe"], iframe[src*="captcha"], .captcha_wrap, #captcha, .device_reg, #deviceRegForm',
    "login_id": "#id",
    "login_pw": "#pw",
    "login_keep": "#keep",
    "login_submit": '#log\\.login, button[type="submit"], .btn_login',
}


# ---------------------------------------------------------------- 페이지 안 JS (naver-poster.js 그대로)
JS_DISMISS_DRAFT = r"""
async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await sleep(300);
  const candidates = [...document.querySelectorAll('button, a, .se-popup-button, [class*="popup"] button')];
  for (const btn of candidates) {
    const t = (btn.textContent || '').trim();
    if (t === '취소' || t === '아니오' || t === '새로 작성' || t === '새글쓰기') {
      try { btn.click(); await sleep(300); return t; } catch (e) {}
    }
  }
  return null;
}
"""

JS_IMAGE_COUNT = r"""
() => Math.max(
  document.querySelectorAll('.se-component.se-image').length,
  document.querySelectorAll('.se-component[class*="image" i]').length,
  document.querySelectorAll('.se-content img, .se-components-wrap img').length
)
"""

# 사진이 아직 네이버로 올라가는 중인지. 컴포넌트가 생긴 것만 보고 넘어가면 '전송중…' 상태로
# 발행돼 사진이 빠진 글이 나간다(2026-09-21 실측: 움짤이 0/1 인 채 발행 레이어로 넘어감).
JS_UPLOAD_STATE = r"""
() => {
  const comps = [...document.querySelectorAll('.se-component.se-image')];
  const pending = comps.filter(c => {
    const el = c.querySelector('img, video');
    const src = el ? (el.getAttribute('src') || el.currentSrc || '') : '';
    return !src || src.startsWith('blob:');
  }).length;
  const text = document.body ? (document.body.innerText || '') : '';
  return {total: comps.length, pending, busy: /전송중|업로드 준비|업로드 중/.test(text)};
}
"""

JS_UPLOAD_BUSY_TEXT = r"""
() => !!document.body && /전송중|업로드 준비|업로드 중/.test(document.body.innerText || '')
"""

# 폴백: 합성 DragEvent 드롭 (naver-poster dropImage). File 은 base64 로 만든다.
JS_DROP_IMAGE = r"""
async ({ b64, mime, name, atCaret }) => {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  const file = new File([arr], name, { type: mime });

  const target =
    document.querySelector('.se-content .se-components-wrap') ||
    document.querySelector('.se-content') ||
    document.querySelector('.se-dnd-wrap') ||
    document.querySelector('.se-component.se-text');
  if (!target) throw new Error('드롭 대상 없음');

  const dt = new DataTransfer();
  dt.items.add(file);
  let x, y, cp = null;
  if (atCaret) {
    try {
      const sel = window.getSelection();
      if (sel && sel.rangeCount) {
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        if (rect && (rect.top || rect.left) && rect.top > 0) cp = { x: rect.left + 2, y: rect.top + rect.height / 2 };
      }
    } catch (e) {}
  }
  if (cp) { x = cp.x; y = cp.y; }
  else { const r = target.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top + r.height - 8; }
  const opts = { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, clientX: x, clientY: y };
  target.dispatchEvent(new DragEvent('dragenter', opts));
  target.dispatchEvent(new DragEvent('dragover', opts));
  target.dispatchEvent(new DragEvent('drop', opts));
  return true;
}
"""

JS_CLICK_IF_UNCHECKED = r"""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  if (!el.checked) el.click();
  return !!el.checked;
}
"""

JS_UNCHECK_IF_CHECKED = r"""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  if (el.checked) el.click();
  return !!el.checked;
}
"""

# React 제어 select: native setter + input/change
JS_SET_NATIVE = r"""
({ sel, value }) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype
    : el instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) setter.call(el, value); else el.value = value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return el.value;
}
"""

JS_READ_VALUE = r"""
(sel) => { const el = document.querySelector(sel); return el ? el.value : null; }
"""

JS_SELECT_CATEGORY = r"""
async (category) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const waitFor = async (selector, timeout) => {
    const start = Date.now();
    while (Date.now() - start < timeout) { const el = document.querySelector(selector); if (el) return el; await sleep(150); }
    return null;
  };
  const CATEGORY_BTN = '[data-click-area="tpb*i.category"], button[aria-label="카테고리 목록 버튼"]';
  const CATEGORY_ITEM = '[role="menu"] input[data-testid^="categoryBtn_"]';
  const normText = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const currentCategoryName = () =>
    normText(document.querySelector(CATEGORY_BTN)?.querySelector('[data-testid^="categoryItemText_"]')?.textContent);
  const readCategoryItems = () => [...document.querySelectorAll(CATEGORY_ITEM)].map((inp) => {
    const id = (inp.dataset.testid || '').replace('categoryBtn_', '');
    const li = inp.closest('li') || inp.parentElement;
    const nameEl = li && li.querySelector('[data-testid^="categoryItemText_"]');
    return { id, name: normText(nameEl && nameEl.textContent), label: li && li.querySelector('label'), input: inp };
  }).filter((c) => c.id && c.name);
  const openCategoryLayer = async (btn) => {
    if (btn.getAttribute('aria-expanded') === 'true') return true;
    btn.click();
    const ok = await waitFor(CATEGORY_ITEM, 5000);
    await sleep(150);
    return !!ok;
  };
  const closeCategoryLayer = async (btn) => {
    if (btn.getAttribute('aria-expanded') === 'true') { btn.click(); await sleep(150); }
  };

  const want = normText(String(category));
  const btn = document.querySelector(CATEGORY_BTN);
  if (!btn) return { ok: false, categories: [], current: '', error: '카테고리 버튼을 찾지 못했습니다' };
  if (!(await openCategoryLayer(btn))) {
    return { ok: false, categories: [], current: currentCategoryName(), error: '카테고리 목록을 열지 못했습니다' };
  }
  const items = readCategoryItems();
  const categories = items.map(({ id, name }) => ({ id, name }));
  const hit = items.find((c) => c.id === want) || items.find((c) => c.name === want);
  if (!hit) {
    await closeCategoryLayer(btn);
    return { ok: false, categories, current: currentCategoryName(), error: `카테고리 '${want}' 를 찾지 못했습니다` };
  }
  (hit.label || hit.input).click();
  await sleep(400);
  const after = currentCategoryName();
  if (after !== hit.name) return { ok: false, categories, current: after, error: `카테고리 반영 실패 (현재 '${after || '?'}')` };
  return { ok: true, categories, current: after };
}
"""

JS_READ_RESERVATIONS = r"""
() => {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const AT = /(?:20\d{2}\s*[.\-\/년]\s*)?\d{1,2}\s*[.\-\/월]\s*\d{1,2}\s*일?[^\d]{0,10}?(?:오전|오후)?\s*\d{1,2}\s*[:시]\s*\d{2}/;
  const body = norm(document.body ? document.body.innerText : '');
  if (!body) return { ok: false, rows: [], empty: false, error: '화면이 비어 있습니다' };
  const nodes = [...document.querySelectorAll('li, tr, article, [class*="item"], [class*="post"], [class*="list"] > div')];
  const rows = [];
  const seen = new Set();
  for (const el of nodes) {
    if (el.querySelector('li, tr, article')) continue;          // 바깥 컨테이너는 건너뛴다
    const text = norm(el.innerText);
    if (!text || text.length > 300 || !AT.test(text)) continue;
    if (seen.has(text)) continue;
    seen.add(text);
    const t = el.querySelector('a, strong, [class*="title"]');
    rows.push({ text, title: norm(t && t.innerText) });
  }
  // '예약된 글이 없습니다' 는 실패가 아니라 0건이다. 이 둘을 섞으면 자리를 영영 못 푼다.
  const empty = /예약[^.]{0,16}(없습니다|없음|0건)/.test(body);
  return { ok: rows.length > 0 || empty, rows, empty,
           error: (rows.length || empty) ? null : '예약 목록에서 읽을 행을 찾지 못했습니다' };
}
"""


JS_READ_CATEGORIES = r"""
async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const waitFor = async (selector, timeout) => {
    const start = Date.now();
    while (Date.now() - start < timeout) { const el = document.querySelector(selector); if (el) return el; await sleep(150); }
    return null;
  };
  const CATEGORY_BTN = '[data-click-area="tpb*i.category"], button[aria-label="카테고리 목록 버튼"]';
  const CATEGORY_ITEM = '[role="menu"] input[data-testid^="categoryBtn_"]';
  const normText = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const btn = document.querySelector(CATEGORY_BTN);
  if (!btn) return { ok: false, categories: [], error: '카테고리 버튼을 찾지 못했습니다' };
  const wasOpen = btn.getAttribute('aria-expanded') === 'true';
  if (!wasOpen) {
    btn.click();
    if (!(await waitFor(CATEGORY_ITEM, 5000))) return { ok: false, categories: [], error: '카테고리 목록을 열지 못했습니다' };
    await sleep(150);
  }
  const categories = [...document.querySelectorAll(CATEGORY_ITEM)].map((inp) => {
    const id = (inp.dataset.testid || '').replace('categoryBtn_', '');
    const li = inp.closest('li') || inp.parentElement;
    const nameEl = li && li.querySelector('[data-testid^="categoryItemText_"]');
    return { id, name: normText(nameEl && nameEl.textContent) };
  }).filter((c) => c.id && c.name);
  // 우리가 연 경우에만 닫는다 — 사용자가 열어둔 목록은 건드리지 않는다.
  if (!wasOpen && btn.getAttribute('aria-expanded') === 'true') { btn.click(); await sleep(150); }
  return { ok: categories.length > 0, categories, error: categories.length ? undefined : '카테고리를 읽지 못했습니다' };
}
"""

# jQuery UI datepicker 로 연·월 이동 후 일 클릭 (naver-poster selectScheduleDate)
JS_SELECT_DATE = r"""
async ({ y: targetY, m: targetM, d: targetD }) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const waitFor = async (selector, timeout) => {
    const start = Date.now();
    while (Date.now() - start < timeout) { const el = document.querySelector(selector); if (el) return el; await sleep(150); }
    return null;
  };
  const dateInput = document.querySelector('input.input_date__QmA0s, .date__Lkn7S input, input[readonly][class*="input_date"]');
  if (!dateInput) return { ok: false, reason: '날짜 input 없음' };
  dateInput.click();

  await waitFor('.ui-datepicker-header', 4000);
  const header = document.querySelector('.ui-datepicker-header');
  const root = document.querySelector('#ui-datepicker-div') || (header && header.parentElement);
  if (!root) return { ok: false, reason: 'datepicker 미표시' };

  const readShown = () => ({
    y: parseInt(root.querySelector('.ui-datepicker-year')?.textContent || '0', 10),
    m: parseInt((root.querySelector('.ui-datepicker-month')?.textContent || '0').replace(/[^0-9]/g, ''), 10),
  });

  for (let i = 0; i < 36; i++) {
    const { y, m } = readShown();
    if (!y || !m || (y === targetY && m === targetM)) break;
    const goNext = (y < targetY) || (y === targetY && m < targetM);
    const nav = root.querySelector(goNext ? '.ui-datepicker-next' : '.ui-datepicker-prev');
    if (!nav || nav.classList.contains('ui-state-disabled')) return { ok: false, reason: '월 이동 불가(범위 밖)', shown: readShown() };
    nav.click();
    await sleep(220);
  }
  const shown = readShown();
  if (shown.y !== targetY || shown.m !== targetM) return { ok: false, reason: '목표 연·월로 이동 실패', shown };

  const dayEls = [...root.querySelectorAll(
    'td:not(.ui-state-disabled) a.ui-state-default, td:not(.ui-state-disabled) button.ui-state-default'
  )];
  const cell = dayEls.find((el) => (el.textContent || '').trim() === String(targetD));
  if (!cell) return { ok: false, reason: `해당 일자(${targetD}) 선택 불가(비활성/미표시)`, shown };
  cell.click();
  await sleep(220);
  return { ok: true, shown, value: dateInput.value };
}
"""

# 확인 팝업(발행 후). 헤더 '발행'(tpb.publish)과 최종 발행 버튼은 제외 — 재클릭으로 이중 발행/레이어 재오픈 방지.
JS_CLICK_CONFIRM = r"""
() => {
  const skip = (b) => b.closest('[data-click-area="tpb.publish"], [data-testid="seOnePublishBtn"], [data-click-area="tpb*i.publish"]');
  const btn = [...document.querySelectorAll('button, a')].find((b) => {
    if (skip(b)) return false;
    const t = (b.textContent || '').trim();
    return t === '확인' || t === '발행' || t === '예';
  });
  if (btn) { try { btn.click(); return (btn.textContent || '').trim(); } catch (e) {} }
  return null;
}
"""

# 발행 뒤 글 주소 찾기 — 크롬 확장 naver-poster 의 findPostUrl 이식.
# 현재 주소·모든 프레임 주소·완료 안내창(레이어/팝업/토스트)의 링크를 본다. 못 찾으면 null.
JS_FIND_POST_URL = r"""
() => {
  const RE = /blog\.naver\.com\/[A-Za-z0-9_.-]+\/\d{6,}(?:[?#/]|$)|PostView\.naver\?[^#]*logNo=\d+/;
  const cands = [];
  try { cands.push(location.href); } catch (e) {}
  try { cands.push(window.top.location.href); } catch (e) {}
  for (const fr of document.querySelectorAll('iframe')) {
    try { cands.push(fr.contentWindow.location.href); } catch (e) {}
    cands.push(fr.getAttribute('src') || '');
  }
  for (const u of cands) if (u && RE.test(u)) return u;
  for (const a of document.querySelectorAll('[class*="layer"] a[href], [class*="popup"] a[href], [role="dialog"] a[href], [class*="toast"] a[href]')) {
    if (RE.test(a.href)) return a.href;
  }
  return null;
}
"""


def normalize_post_url(raw: Optional[str]) -> Optional[str]:
    """blog.naver.com/{id}/{번호} 또는 PostView.naver?blogId=..&logNo=.. → https://blog.naver.com/{id}/{번호}"""
    if not raw:
        return None
    from urllib.parse import parse_qs, urlparse

    m = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)/(\d{6,})(?:[?#/]|$)", raw)
    if m and m.group(1) != "PostView.naver":
        return f"https://blog.naver.com/{m.group(1)}/{m.group(2)}"
    q = parse_qs(urlparse(raw).query)
    blog, log_no = (q.get("blogId") or [""])[0], (q.get("logNo") or [""])[0]
    if re.fullmatch(r"[A-Za-z0-9_-]+", blog) and re.fullmatch(r"\d+", log_no):
        return f"https://blog.naver.com/{blog}/{log_no}"
    return None


JS_READ_TEXT = r"""
(sel) => { const el = document.querySelector(sel); return el ? (el.textContent || '') : null; }
"""


def left_editor(before: str, now: str) -> bool:
    """최종 발행 뒤 글쓰기 화면을 벗어났는가(성공 신호).

    네이버 글쓰기 화면의 바깥 주소는 이미 blog.naver.com/{id}?Redirect=Write 라서, 예전처럼
    'blog.naver.com 이고 PostWriteForm/GoBlogWrite 가 아니면 이동'으로 보면 발행 버튼을 누르자마자 항상 참이
    됐다(2026-09-11 실제 네이버 실측) — 발행이 거부돼도 성공으로 보고할 수 있었다."""
    if not now or now == before or "blog.naver.com" not in now:
        return False
    return not any(k in now for k in ("PostWriteForm", "GoBlogWrite", "Redirect=Write", "redirect=Write"))


async def _visible_match(scope: Any, selector: str) -> bool:
    """선택자에 걸리는 요소 중 화면에 실제로 보이는 것이 있는가.

    네이버 글쓰기 화면에는 보이지 않는 캡차 프레임(ncaptcha-iframe-*, 0x0)이 항상 들어 있다.
    '있기만 하면 캡차'로 보면 로그인돼 있어도 매번 캡차로 오판해 발행하지 못한다(2026-09-11 실측)."""
    loc = scope.locator(selector)
    for i in range(min(await loc.count(), 10)):
        try:
            if await loc.nth(i).is_visible():
                return True
        except Exception:  # noqa: BLE001 — 프레임 이동 중
            continue
    return False


@dataclass
class PublishOutcome:
    ok: bool
    uncertain: bool = False
    url: Optional[str] = None
    message: str = ""
    dialogs: List[str] = field(default_factory=list)


# ================================================================ 에디터
class NaverEditor:
    def __init__(self, page: Page, *, captcha_wait_sec: int = 180, write_url: str = WRITE_URL):
        self.page = page
        self.captcha_wait_sec = captcha_wait_sec
        self.write_url = write_url  # 테스트용 가짜 에디터 페이지로 바꿀 수 있다
        self._frame: Optional[Frame] = None
        self.dialogs: List[str] = []
        page.on("dialog", self._on_dialog)

    async def _on_dialog(self, dialog) -> None:
        msg = dialog.message
        self.dialogs.append(msg)
        log.info("브라우저 다이얼로그(%s): %s → 확인", dialog.type, msg[:120])
        try:
            await dialog.accept()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 프레임
    async def _scan_editor_frame(self, marker: str = S["editor_marker"]) -> Optional[Frame]:
        for f in self.page.frames:
            try:
                if f.is_detached():
                    continue
                if await f.locator(marker).count() > 0:
                    return f
            except Exception:  # noqa: BLE001
                continue
        return None

    async def frame(self, timeout_ms: int = 25000) -> Frame:
        """에디터가 있는 프레임(최상위 문서 또는 #mainFrame)."""
        if self._frame is not None and not self._frame.is_detached():
            return self._frame
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            f = await self._scan_editor_frame()
            if f is not None:
                self._frame = f
                where = "최상위 문서" if f == self.page.main_frame else f"iframe({f.name or 'mainFrame'})"
                log.info("에디터 프레임: %s", where)
                return f
            await asyncio.sleep(0.3)
        raise EditorError("에디터 프레임(.se-documentTitle)을 찾지 못했습니다")

    # ------------------------------------------------------------ 페이지 열기 / 로그인
    async def open_write_page(self, timeout_ms: int = 30000) -> None:
        """글쓰기 페이지로 이동해 제목/본문 문단이 나타날 때까지 기다린다.
        로그인 페이지로 튕기면 LoginRequired, 보안 화면이면 CaptchaDetected."""
        self._frame = None
        log.info("글쓰기 페이지 이동: %s", self.write_url)
        # 이동이 '시작'된 것까지만 기다리고, 무엇이 떴는지는 아래 루프가 판단한다.
        # domcontentloaded 로 기다리면 세션 없는 첫 실행에서 로그인 페이지 로딩에 걸려
        # 타임아웃이 나고, '로그인 필요' 대신 알 수 없는 오류로 끝난다(2026-09-21 실측).
        # 컨텍스트 기본 타임아웃(15초)도 새 크롬 프로필 첫 이동에는 모자라 넉넉히 준다.
        await self.page.goto(self.write_url, wait_until="commit", timeout=timeout_ms)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            url = self.page.url or ""
            if "nid.naver.com" in url:
                raise LoginRequired("로그인 페이지로 이동됨(세션 없음)")
            if await self.detect_captcha():
                raise CaptchaDetected("글쓰기 페이지에서 캡차/보안 확인이 나타났습니다")
            f = await self._scan_editor_frame(S["title_para"])
            if f is not None:
                try:
                    if await f.locator(S["body_para"]).count() > 0:
                        self._frame = f
                        log.info("에디터 준비됨 (%s)", url[:80])
                        return
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(0.5)
        raise EditorError(f"에디터가 준비되지 않았습니다({timeout_ms // 1000}초) — {self.page.url[:80]}")

    async def on_login_page(self) -> bool:
        return "nid.naver.com" in (self.page.url or "")

    async def login_challenge_present(self) -> bool:
        try:
            return await _visible_match(self.page, S["login_challenge"])
        except Exception:  # noqa: BLE001
            return False

    async def try_login(self, login_id: str, login_pw: str, timeout_ms: int = 25000) -> None:
        """nid.naver.com 로그인 폼에 저장된 계정을 한 번 입력·제출한다(content-login.js 포트).
        캡차/기기등록이 보이면 CaptchaDetected, 그래도 로그인 페이지에 남으면 LoginRequired."""
        if not await self.on_login_page():
            return
        if await self.login_challenge_present():
            raise CaptchaDetected("로그인 화면에 캡차/기기 인증이 있습니다. 브라우저에서 직접 한 번 완료해 주세요.")
        page = self.page
        id_el, pw_el = page.locator(S["login_id"]), page.locator(S["login_pw"])
        try:
            await id_el.wait_for(timeout=8000)
        except PWTimeout:
            raise LoginRequired("로그인 폼(#id)을 찾지 못했습니다 — 네이버 로그인 화면이 바뀌었을 수 있습니다")
        log.info("자동 로그인 시도: %s", login_id)
        await id_el.click()
        await page.keyboard.press("Control+a")
        await page.keyboard.insert_text(login_id)
        await pw_el.click()
        await page.keyboard.press("Control+a")
        await page.keyboard.insert_text(login_pw)
        try:
            await page.evaluate(JS_CLICK_IF_UNCHECKED, S["login_keep"])
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.4)
        if await self.login_challenge_present():
            raise CaptchaDetected("로그인 제출 직전에 캡차가 나타났습니다. 브라우저에서 직접 완료해 주세요.")
        submit = page.locator(S["login_submit"]).first
        if await submit.count():
            await submit.click()
        else:
            await page.keyboard.press("Enter")

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            url = page.url or ""
            if "nid.naver.com" not in url:
                log.info("로그인 성공 → %s", url[:80])
                return
            if await self.login_challenge_present():
                raise CaptchaDetected("로그인 후 캡차/새 기기 등록 화면이 나타났습니다. 브라우저에서 직접 완료해 주세요.")
            if "deviceConfirm" in url or "device" in url.lower():
                # 새 기기 등록 안내: '등록안함' 을 눌러 넘어간다(best-effort)
                try:
                    clicked = await page.evaluate(
                        "() => { const b=[...document.querySelectorAll('button,a')].find(x=>/등록\\s*안\\s*함/.test(x.textContent||'')); if(b){b.click();return true;} return false; }"
                    )
                    if clicked:
                        log.info("새 기기 등록 안내 → '등록안함' 클릭")
                        continue
                except Exception:  # noqa: BLE001
                    pass
        raise LoginRequired("자동 로그인 후에도 로그인 페이지에 머물러 있습니다(아이디/비밀번호 확인 필요)")

    # ------------------------------------------------------------ 팝업 / 식별
    async def dismiss_draft_popup(self) -> bool:
        f = await self.frame()
        try:
            t = await f.evaluate(JS_DISMISS_DRAFT)
        except Exception as e:  # noqa: BLE001
            log.warning("드래프트 팝업 처리 중 오류(무시): %s", e)
            return False
        if t:
            log.info("드래프트 복원 팝업 '%s' 클릭", t)
            return True
        log.info("드래프트 팝업 없음")
        return False

    async def read_blog_id(self) -> str:
        """현재 로그인된 블로그 ID(naver-poster readBlogId 포트). 못 읽으면 ''."""

        def from_url(u: str) -> str:
            m = re.search(r"[?&]blogId=([^&]+)", u or "")
            return m.group(1) if m else ""

        urls = [self.page.url]
        try:
            urls += await self.page.evaluate("() => [...document.querySelectorAll('iframe')].map(f => f.getAttribute('src') || '')")
        except Exception:  # noqa: BLE001
            pass
        urls += [f.url for f in self.page.frames]
        for u in urls:
            bid = from_url(u)
            if bid:
                log.info("블로그 ID: %s", bid)
                return bid
        for u in urls:
            m = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)(?:[/?#]|$)", u or "")
            if m and m.group(1) not in ("GoBlogWrite.naver", "PostWriteForm.naver"):
                log.info("블로그 ID(경로): %s", m.group(1))
                return m.group(1)
        log.warning("블로그 ID 를 읽지 못했습니다")
        return ""

    # ------------------------------------------------------------ 입력 헬퍼
    async def _click_paragraph(self, selector: str, *, last: bool = False) -> None:
        """문단을 좌표 클릭해 캐럿을 둔다(background.js clickAt: 가운데 x, 위에서 최대 24px)."""
        f = await self.frame()
        loc = f.locator(selector)
        n = await loc.count()
        if n == 0:
            raise EditorError(f"문단을 찾지 못했습니다: {selector}")
        el = loc.nth(n - 1) if last else loc.first
        await el.scroll_into_view_if_needed()
        box = await el.bounding_box()
        if not box:
            raise EditorError(f"문단 좌표를 얻지 못했습니다: {selector}")
        x = box["x"] + box["width"] / 2
        y = box["y"] + min(box["height"] / 2, 24)
        await self.page.mouse.click(x, y)
        await asyncio.sleep(0.25)

    async def _ctrl_a(self) -> None:
        await self.page.keyboard.press("Control+a")
        await asyncio.sleep(0.08)

    async def _enter(self) -> None:
        await self.page.keyboard.press("Enter")
        await asyncio.sleep(0.03)

    async def _insert(self, text: str) -> None:
        if text:
            await self.page.keyboard.insert_text(text)

    async def _bold(self, text: str) -> None:
        await self.page.keyboard.press("Control+b")
        await asyncio.sleep(0.03)
        await self._insert(text)
        await self.page.keyboard.press("Control+b")
        await asyncio.sleep(0.03)

    # ------------------------------------------------------------ 제목 / 본문
    async def set_title(self, title: str) -> None:
        """제목을 넣고 다시 읽어 확인한다. 늦게 뜬 '작성 중인 글' 팝업이 입력을 가로채면 닫고 한 번 더 넣는다.
        그래도 안 들어가면 EditorError — 제목 없는 글이 발행되면 안 된다
        (2026-09-11 실제 네이버: 입력칸이 '제목' 그대로인 채 경고만 남기고 발행까지 진행됐다)."""
        want = title.strip()
        for attempt in (1, 2):
            log.info("제목 입력: %s", title[:60])
            await self._click_paragraph(S["title_para"])
            await self._ctrl_a()
            await self._insert(title)
            await asyncio.sleep(0.4)
            f = await self.frame()
            got = (await f.evaluate(JS_READ_TEXT, S["title_para"]) or "").strip()
            if not want or want[:10] in got:
                return
            log.warning("제목 확인 실패(입력 '%s' / 현재 '%s')%s", title[:30], got[:30],
                        " → 팝업을 닫고 다시 입력" if attempt == 1 else "")
            if attempt == 1:
                await self.dismiss_draft_popup()
        raise EditorError("제목이 입력되지 않았습니다. 제목 없는 글이 올라가지 않도록 발행하지 않고 중단합니다")

    async def insert_body_blocks(self, blocks: Sequence[Dict[str, Any]], emphasize: Sequence[str], *, reformat: bool = True) -> int:
        """블록(글/이미지) 순서대로 본문에 넣는다. 반환: 삽입된 이미지 수.
        이미지 한 장이라도 실패하면 EditorError (사진 빠진 글이 나가면 안 된다)."""
        if has_formatting(blocks):
            from rich_editor import insert_rich_blocks
            return await insert_rich_blocks(self, blocks)
        ops = merge_text_ops(plan_blocks(blocks, emphasize, reformat=reformat))
        n_img = sum(1 for o in ops if o.kind == "image")
        n_txt = sum(len(o.payload) for o in ops if o.kind in ("text", "bold"))
        log.info("본문 입력 계획: 동작 %d개 (글자 %d, 이미지 %d, 강조 %d)", len(ops), n_txt, n_img, sum(1 for o in ops if o.kind == "bold"))

        await self._click_paragraph(S["body_para"])
        await self._ctrl_a()
        inserted = 0
        for i, op in enumerate(ops):
            if op.kind == "text":
                await self._insert(op.payload)
            elif op.kind == "bold":
                await self._bold(op.payload)
            elif op.kind == "enter":
                await self._enter()
            elif op.kind == "image":
                log.info("이미지 삽입 (%d/%d)", inserted + 1, n_img)
                await self._insert_image_verified(op.payload, index=inserted)
                inserted += 1
                await asyncio.sleep(0.6)
                await self._refocus_body_end()
        if inserted < n_img:
            raise EditorError(f"이미지 {n_img}장 중 {inserted}장만 삽입됨")
        log.info("본문 입력 완료 (이미지 %d장)", inserted)
        return inserted

    async def _refocus_body_end(self) -> None:
        """이미지 삽입 후 캐럿을 본문 끝으로 되돌린다(다음 문단이 이미지 뒤에 오도록)."""
        try:
            await self._click_paragraph(S["body_para"], last=True)
            await self.page.keyboard.press("Control+End")
            await asyncio.sleep(0.15)
        except Exception as e:  # noqa: BLE001
            log.warning("본문 끝 포커스 복귀 실패(계속 진행): %s", e)

    async def verify_links(self, urls):
        """Require actual clickable anchors, not merely the visible URL text."""
        f = await self.frame()
        for _ in range(10):
            ok = await f.evaluate('''(urls) => {
                const normalize = value => { try { return new URL(value).href; } catch { return ''; } };
                const links = [...document.querySelectorAll('.se-component a[href]')].map(a => normalize(a.href));
                return urls.every(url => links.includes(normalize(url)));
            }''', urls)
            if ok:
                return
            await asyncio.sleep(.5)
        raise EditorError('랜딩 URL이 클릭 가능한 링크로 확인되지 않았습니다. 발행을 보류합니다')

    async def image_count(self) -> int:
        f = await self.frame()
        try:
            return int(await f.evaluate(JS_IMAGE_COUNT))
        except Exception:  # noqa: BLE001
            return 0

    async def _wait_image_increase(self, before: int, timeout_sec: float = 25.0) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            await asyncio.sleep(0.3)
            if await self.image_count() > before:
                return True
        return False

    async def _insert_image_once(self, data_url: str, name: str) -> bool:
        """1) 툴바 '사진' 버튼 → 파일 선택창 가로채기(setInputFiles 계열) 2) 실패 시 합성 드롭."""
        mime, data = decode_data_url(data_url)
        f = await self.frame()
        before = await self.image_count()

        btn = f.locator(S["toolbar_image"]).first
        if await btn.count():
            try:
                async with self.page.expect_file_chooser(timeout=5000) as fc:
                    await btn.click()
                chooser = await fc.value
                await chooser.set_files({"name": name, "mimeType": mime, "buffer": data})
                log.info("이미지: 파일 선택창 경유 업로드 (%s, %d bytes)", name, len(data))
                if await self._wait_image_increase(before):
                    return True
                log.warning("이미지: 파일 선택창 업로드 후 컴포넌트 증가 없음 → 드롭 폴백")
            except PWTimeout:
                log.info("이미지: 파일 선택창이 열리지 않음 → 드롭 폴백")
            except Exception as e:  # noqa: BLE001
                log.warning("이미지: 파일 선택창 경로 실패(%s) → 드롭 폴백", e)
        else:
            log.info("이미지: 툴바 사진 버튼 없음 → 드롭 폴백")

        before = await self.image_count()
        import base64

        await f.evaluate(JS_DROP_IMAGE, {"b64": base64.b64encode(data).decode(), "mime": mime, "name": name, "atCaret": True})
        log.info("이미지: 합성 DragEvent 드롭 전송")
        return await self._wait_image_increase(before)

    async def wait_upload_settled(self, timeout_sec: float = 90.0) -> bool:
        """사진 바이트가 다 올라갈 때까지 기다린다. 못 기다리면 경고만 남기고 진행(발행은 사람이 판단)."""
        deadline = time.monotonic() + timeout_sec
        state = None
        while time.monotonic() < deadline:
            try:
                frame = await self.frame()
                state = await frame.evaluate(JS_UPLOAD_STATE)
                busy = bool(state.get("pending")) or bool(state.get("busy"))
                if not busy:
                    busy = bool(await self.page.evaluate(JS_UPLOAD_BUSY_TEXT))
                if not busy:
                    return True
            except Exception as e:  # noqa: BLE001 — 읽지 못하면 예전처럼 그냥 진행한다
                log.debug("업로드 상태 확인 실패(계속 진행): %s", e)
                return True
            await asyncio.sleep(0.5)
        log.warning("사진 업로드가 %d초 안에 끝나지 않았습니다(%s) — 그대로 진행합니다", int(timeout_sec), state)
        return False

    async def _insert_image_verified(self, data_url: str, *, index: int) -> None:
        mime, raw = decode_data_url(data_url)
        # 매번 같은 틀(image_타임스탬프)의 이름은 그 자체가 흔적이 된다 → 사진 EXIF 기종·촬영시각에 맞춘 카메라식 이름.
        # 재시도해도 같은 사진은 같은 이름이다(실제 파일을 다시 고른 것처럼).
        name = camera_filename(raw, ext_for_mime(mime))
        last_err = ""
        for attempt in range(1, 4):
            try:
                if await self._insert_image_once(data_url, name):
                    await self.wait_upload_settled()
                    return
                last_err = "업로드 확인 실패(시간 초과)"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            if attempt < 3:
                log.warning("이미지 %d 삽입 재시도 %d/3: %s", index, attempt, last_err)
                await asyncio.sleep(2.0 * attempt)
        raise EditorError(f"이미지 {index + 1} 삽입 최종 실패 — {last_err}")

    # ------------------------------------------------------------ 발행 레이어
    async def open_publish_layer(self, timeout_ms: int = 8000) -> None:
        # 사진이 아직 전송 중이면 발행 레이어로 넘어가지 않는다.
        await self.wait_upload_settled()
        f = await self.frame()
        btn = f.locator(S["publish_open"]).first
        if not await btn.count():
            btn = f.locator(S["publish_open_fallback"]).first
        if not await btn.count():
            btn = f.get_by_role("button", name="발행", exact=True).first
        if not await btn.count():
            raise EditorError("발행 버튼 없음")
        final = f.locator(S["publish_final"]).first
        if await final.count() and await final.is_visible():
            log.info("발행 레이어 이미 열림")
            return
        await btn.click()
        try:
            await final.wait_for(state="visible", timeout=timeout_ms)
        except PWTimeout:
            raise EditorError("발행 레이어 열림 실패")
        await asyncio.sleep(0.4)
        log.info("발행 레이어 열림")

    async def set_open_type(self, open_type: str) -> None:
        f = await self.frame()
        sel = S["open_type"].get(open_type or "public", S["open_type"]["public"])
        r = await f.evaluate(JS_CLICK_IF_UNCHECKED, sel)
        if r is None:
            log.warning("공개설정 라디오 없음: %s (네이버 기본값 유지)", sel)
        else:
            log.info("공개설정 %s → checked=%s", open_type, r)

    async def set_search_allow(self, allow: bool) -> None:
        f = await self.frame()
        r = await f.evaluate(JS_CLICK_IF_UNCHECKED if allow else JS_UNCHECK_IF_CHECKED, S["search_allow"])
        log.info("검색허용 %s → %s", allow, r)

    async def set_category(self, category: Optional[str]) -> None:
        """번호("24") 또는 이름. 못 찾거나 반영 안 되면 EditorError — 엉뚱한 카테고리 공개 발행 방지."""
        if not category:
            log.info("카테고리 미지정 → 네이버 기본 카테고리")
            return
        f = await self.frame()
        r = await f.evaluate(JS_SELECT_CATEGORY, str(category))
        if not r or not r.get("ok"):
            avail = ", ".join(f"{c['name']}({c['id']})" for c in (r or {}).get("categories", []))
            raise EditorError(f"{(r or {}).get('error', '카테고리 설정 실패')}. 사용 가능한 카테고리: {avail or '목록을 읽지 못했습니다'}")
        log.info("카테고리: %s", r.get("current"))

    async def read_categories(self) -> List[Dict[str, str]]:
        """발행 레이어에서 카테고리 목록만 읽어 온다(선택은 하지 않는다).

        확장의 SYNC_CATEGORIES 를 대신한다 — 앱 드롭다운은 이 목록으로 채워진다.
        레이어는 호출자가 열어 둔다."""
        f = await self.frame()
        r = await f.evaluate(JS_READ_CATEGORIES)
        if not r or not r.get("ok"):
            log.warning("카테고리 목록 읽기 실패: %s", (r or {}).get("error", "?"))
            return []
        items = [{"id": str(c["id"]), "name": str(c["name"])} for c in r.get("categories", [])]
        log.info("카테고리 %d개 확인", len(items))
        return items

    async def read_reservations(self, naver_blog_id: str, urls: Optional[Sequence[str]] = None,
                                timeout_ms: int = 20000) -> Optional[List[Dict[str, Any]]]:
        """네이버에 걸려 있는 예약 글 목록을 읽는다.

        반환은 셋 중 하나다. 목록(비어 있을 수 있다) / None(못 읽었다).
        **빈 목록과 못 읽음을 절대 같은 값으로 돌려주지 않는다** — 못 읽은 것을 0건으로 치면
        서버가 '자리가 다 비었다'고 믿고 남의 예약 위에 겹쳐 잡는다.

        목록 화면은 발행과 무관하므로 실패해도 예외를 올리지 않는다(로그인 문제만 올린다)."""
        for raw in (urls or RESERVE_URLS):
            url = raw.format(blog=naver_blog_id) if "{blog}" in raw else raw
            try:
                await self.page.goto(url, wait_until="commit", timeout=timeout_ms)
                await self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                await asyncio.sleep(0.6)
            except PWTimeout:
                log.info("예약 목록 열기 시간 초과: %s", url)
                continue
            except Exception as e:  # noqa: BLE001
                log.info("예약 목록을 열지 못했습니다(%s): %s", url, e)
                continue
            if "nid.naver.com" in (self.page.url or ""):
                raise LoginRequired("예약 목록을 보려면 로그인이 필요합니다")
            try:
                r = await self.page.evaluate(JS_READ_RESERVATIONS)
            except Exception as e:  # noqa: BLE001
                log.info("예약 목록을 읽지 못했습니다(%s): %s", url, e)
                continue
            if not r or not r.get("ok"):
                log.info("예약 목록 아님(%s): %s", url, (r or {}).get("error", "?"))
                continue
            items = parse_reservation_rows(r.get("rows") or [])
            log.info("예약 %d건 확인 (%s)", len(items), url)
            return items
        log.warning("예약 목록 화면을 찾지 못했습니다. 주소가 바뀌었다면 DV_RESERVE_URL 로 알려 주세요")
        return None

    async def set_publish_now(self) -> None:
        """즉시 발행: '현재' 라디오를 확실히 켠다. 예약이 남아 있으면 엉뚱한 시각에 나간다."""
        f = await self.frame()
        r = await f.evaluate(JS_CLICK_IF_UNCHECKED, S["time_now"])
        if r is not True:
            raise EditorError("즉시 발행 라디오를 켜지 못했습니다")
        log.info("즉시 발행 라디오 ON")

    async def save_draft(self, *, dry_run: bool = False) -> Optional[PublishOutcome]:
        """임시저장 버튼 클릭. 발행 레이어를 열지 않는다."""
        await self.wait_upload_settled()
        f = await self.frame()
        btn = f.locator(S["save_draft"]).first
        if not await btn.count():
            btn = f.get_by_role("button", name="저장", exact=True).first
        if not await btn.count():
            raise EditorError("임시저장 버튼을 찾지 못했습니다")
        if dry_run:
            log.info("[dry-run] 임시저장 버튼은 클릭하지 않습니다")
            return None
        self.dialogs.clear()
        await btn.click()
        await asyncio.sleep(2.0)
        log.info("임시저장 클릭")
        return PublishOutcome(ok=True, message="임시저장", dialogs=list(self.dialogs))

    async def set_tags(self, tags: Sequence[str]) -> int:
        """#tag-input 에 태그를 하나씩 입력+Enter. 입력란이 없으면 경고만(발행은 계속)."""
        clean = [re.sub(r"^#", "", t).strip() for t in (tags or []) if isinstance(t, str)]
        clean = [t for t in clean if t][:10]
        if not clean:
            return 0
        f = await self.frame()
        inp = f.locator(S["tag_input"]).first
        if not await inp.count():
            log.warning("태그 입력란(#tag-input) 없음 → 태그 생략")
            return 0
        await inp.click()
        for t in clean:
            await self._insert(t)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(0.15)
        log.info("태그 %d개 입력: %s", len(clean), ", ".join(clean))
        return len(clean)

    async def set_schedule(self, dt: datetime) -> None:
        """예약발행 라디오 → 날짜(datepicker) → 시/분(select). 어느 단계든 실패하면 ScheduleError.
        호출자는 ScheduleError 시 절대 publish() 를 부르면 안 된다."""
        f = await self.frame()
        hh = f"{dt.hour:02d}"
        mm = f"{(dt.minute // 10) * 10:02d}"

        r = await f.evaluate(JS_CLICK_IF_UNCHECKED, S["time_reserve"])
        await asyncio.sleep(0.4)
        if r is not True:
            raise ScheduleError("예약발행 라디오(#radio_time2)를 켜지 못했습니다(네이버 화면 변경 가능). 즉시 발행을 막기 위해 중단합니다")
        log.info("예약발행 라디오 ON")

        d = await f.evaluate(JS_SELECT_DATE, {"y": dt.year, "m": dt.month, "d": dt.day})
        if not d or not d.get("ok"):
            raise ScheduleError(f"예약 날짜를 지정하지 못했습니다({(d or {}).get('reason', '?')}). 즉시 발행을 막기 위해 중단합니다")
        shown = await f.evaluate(JS_READ_VALUE, S["date_input"])
        want = f"{dt.year}. {dt.month:02d}. {dt.day:02d}"
        if shown is not None and re.sub(r"\s+", "", str(shown)) != re.sub(r"\s+", "", want):
            raise ScheduleError(f"예약 날짜 확인 실패(입력란 '{shown}', 목표 '{want}'). 즉시 발행을 막기 위해 중단합니다")
        log.info("예약 날짜: %s", shown or want)

        for sel, val, label in ((S["hour_select"], hh, "시"), (S["minute_select"], mm, "분")):
            got = await f.evaluate(JS_SET_NATIVE, {"sel": sel, "value": val})
            if got is None:
                raise ScheduleError(f"예약 {label} 입력란을 찾지 못했습니다(네이버 화면 변경 가능). 즉시 발행을 막기 위해 중단합니다")
            await asyncio.sleep(0.15)
            back = await f.evaluate(JS_READ_VALUE, sel)
            if str(back).zfill(2) != val:
                raise ScheduleError(f"예약 {label} 반영 실패(설정 {val}, 현재 {back}). 즉시 발행을 막기 위해 중단합니다")
        await asyncio.sleep(0.3)

        still = await f.evaluate("(sel) => { const el = document.querySelector(sel); return el ? !!el.checked : null; }", S["time_reserve"])
        if still is not True:
            raise ScheduleError("예약발행 라디오가 다시 꺼졌습니다. 즉시 발행을 막기 위해 중단합니다")
        log.info("예약 시각: %s %s:%s (분은 10분 단위 내림)", want, hh, mm)

    # ------------------------------------------------------------ 발행
    async def publish(self, *, dry_run: bool = False, settle_sec: float = 20.0) -> Optional[PublishOutcome]:
        """최종 발행 버튼 클릭. dry_run 이면 클릭하지 않고 None.
        반환 PublishOutcome.ok 는 '발행 레이어가 닫히거나 페이지가 이동함' 기준. 애매하면 uncertain."""
        f = await self.frame()
        final = f.locator(S["publish_final"]).first
        if not await final.count():
            raise EditorError("최종 발행 버튼이 없습니다(레이어가 닫혔나요?)")
        if dry_run:
            log.info("[dry-run] 최종 발행 버튼은 클릭하지 않습니다")
            return None

        self.dialogs.clear()
        before_url = self.page.url or ""
        log.info("최종 발행 클릭")
        await final.click()
        await asyncio.sleep(2.0)

        if await self.detect_captcha():
            log.warning("캡차 감지 → 사용자 입력 대기(최대 %ds)", self.captcha_wait_sec)
            if not await self.wait_for_captcha_resolved(self.captcha_wait_sec):
                raise CaptchaDetected("발행 단계에서 캡차가 나타났고 시간 안에 풀리지 않았습니다")

        try:
            t = await f.evaluate(JS_CLICK_CONFIRM)
            if t:
                log.info("확인 팝업 '%s' 클릭", t)
        except Exception:  # noqa: BLE001
            pass

        deadline = time.monotonic() + settle_sec
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            url = self.page.url or ""
            if left_editor(before_url, url):
                log.info("발행 후 페이지 이동: %s", url[:100])
                post_url = normalize_post_url(url) or await self.harvest_post_url()
                return PublishOutcome(ok=True, url=post_url, message="예약 등록 후 페이지 이동", dialogs=list(self.dialogs))
            try:
                fin = f.locator(S["publish_final"]).first
                if f.is_detached() or await fin.count() == 0 or not await fin.is_visible():
                    log.info("발행 레이어 닫힘 → 예약 등록으로 판단")
                    return PublishOutcome(ok=True, url=await self.harvest_post_url(), message="발행 레이어 닫힘", dialogs=list(self.dialogs))
            except Exception:  # noqa: BLE001
                return PublishOutcome(ok=True, url=await self.harvest_post_url(), message="에디터 프레임 교체됨", dialogs=list(self.dialogs))
        msg = "발행 클릭 후 화면 변화가 확인되지 않았습니다. 네이버 예약 목록에서 확인이 필요합니다"
        if self.dialogs:
            msg += " / 다이얼로그: " + " | ".join(d[:80] for d in self.dialogs)
        log.warning(msg)
        return PublishOutcome(ok=False, uncertain=True, message=msg, dialogs=list(self.dialogs))

    async def harvest_post_url(self, timeout_sec: float = 6.0) -> Optional[str]:
        """발행 직후 글 주소(글 번호)를 찾는다. 번호가 있으면 서버가 그 주소로 공개를 확인하고,
        없어도 발행은 성공으로 보고된다(서버가 예약 시각 뒤 RSS 로 확인). 여기서는 실패하지 않는다."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            for fr in [self.page.main_frame, *self.page.frames]:
                try:
                    if fr.is_detached():
                        continue
                    found = normalize_post_url(await fr.evaluate(JS_FIND_POST_URL))
                except Exception:  # noqa: BLE001 — 프레임 이동 중
                    continue
                if found:
                    log.info("발행된 글 주소: %s", found)
                    return found
            await asyncio.sleep(0.4)
        log.info("발행된 글 주소를 찾지 못했습니다 — 서버가 예약 시각 뒤 공개 여부를 확인합니다")
        return None

    # ------------------------------------------------------------ 캡차
    async def detect_captcha(self) -> bool:
        """최상위 문서 + 모든 프레임에서 '보이는' 캡차 iframe/요소가 있는가(숨은 ncaptcha 프레임은 제외)."""
        for fr in self.page.frames:
            try:
                if fr.is_detached():
                    continue
                if await _visible_match(fr, S["captcha"]):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def wait_for_captcha_resolved(self, timeout_sec: int) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            await asyncio.sleep(0.8)
            if not await self.detect_captcha():
                await asyncio.sleep(0.6)
                log.info("캡차 해결됨")
                return True
        return False
