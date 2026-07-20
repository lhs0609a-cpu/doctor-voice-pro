// ============================================================
// 닥터보이스 프로 - 네이버 블로그 자동 포스팅 엔진 v15
// SmartEditor ONE (blog.naver.com) 인페이지 컨트롤러
// 실제 확보한 안정 셀렉터(data-click-area / data-name / data-testid) 기반
// ============================================================
(() => {
  'use strict';
  const TAG = '[닥터보이스]';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 이 프레임이 실제 에디터가 있는 프레임인지 판별
  const isEditorFrame = () =>
    !!document.querySelector('.se-component.se-documentTitle, .se-documentTitle');

  // ---------- 유틸: 요소 대기 ----------
  async function waitFor(selector, { timeout = 20000, root = document } = {}) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const el = root.querySelector(selector);
      if (el) return el;
      await sleep(150);
    }
    return null;
  }

  // ---------- 유틸: iframe 오프셋을 더한 뷰포트 절대 좌표 ----------
  function absoluteRect(el) {
    const r = el.getBoundingClientRect();
    let offX = 0;
    let offY = 0;
    try {
      // content script는 mainFrame(iframe) 내부에서 실행됨.
      // 같은 오리진(blog.naver.com)이라 frameElement 접근 가능.
      if (window.frameElement) {
        const fr = window.frameElement.getBoundingClientRect();
        offX = fr.left;
        offY = fr.top;
      }
    } catch (e) { /* cross-origin fallback: 오프셋 0 */ }
    return {
      x: Math.round(offX + r.left + r.width / 2),
      y: Math.round(offY + r.top + Math.min(r.height / 2, 24)),
      left: offX + r.left,
      top: offY + r.top,
      width: r.width,
      height: r.height,
    };
  }

  // ---------- 진행 오버레이 ----------
  let overlayEl = null;
  function showOverlay(text, pct) {
    if (!isTopDoc()) return; // 오버레이는 최상위 문서에만
    if (!overlayEl) {
      overlayEl = document.createElement('div');
      overlayEl.id = 'dv-poster-overlay';
      overlayEl.innerHTML = `
        <div class="dv-ov-card">
          <div class="dv-ov-spinner"></div>
          <div class="dv-ov-text">준비 중...</div>
          <div class="dv-ov-bar"><i></i></div>
          <div class="dv-ov-ver">닥터보이스 프로 v15.0.1</div>
        </div>`;
      const s = document.createElement('style');
      s.textContent = `
        #dv-poster-overlay{position:fixed;inset:0;z-index:2147483646;display:flex;
          align-items:center;justify-content:center;background:rgba(15,23,42,.55);
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
        #dv-poster-overlay .dv-ov-card{background:#fff;border-radius:16px;padding:28px 34px;
          min-width:300px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.3)}
        #dv-poster-overlay .dv-ov-spinner{width:40px;height:40px;margin:0 auto 16px;
          border:4px solid #d1fae5;border-top-color:#10b981;border-radius:50%;
          animation:dvspin .8s linear infinite}
        @keyframes dvspin{to{transform:rotate(360deg)}}
        #dv-poster-overlay .dv-ov-text{font-size:15px;font-weight:600;color:#111827;margin-bottom:14px}
        #dv-poster-overlay .dv-ov-bar{height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden}
        #dv-poster-overlay .dv-ov-bar i{display:block;height:100%;width:0;
          background:linear-gradient(90deg,#10b981,#059669);transition:width .3s}
        #dv-poster-overlay .dv-ov-ver{margin-top:12px;font-size:11px;color:#9ca3af}`;
      document.documentElement.appendChild(s);
      document.documentElement.appendChild(overlayEl);
    }
    overlayEl.querySelector('.dv-ov-text').textContent = text;
    if (typeof pct === 'number') overlayEl.querySelector('.dv-ov-bar i').style.width = pct + '%';
  }
  function hideOverlay() {
    if (overlayEl) { overlayEl.remove(); overlayEl = null; }
  }
  const isTopDoc = () => {
    try { return window.top === window.self; } catch (e) { return false; }
  };

  // ---------- 드래프트 복원 팝업 자동 취소 ----------
  async function dismissDraftPopup() {
    // "작성 중이던 글이 있습니다" 류 팝업 → '취소'(새 글로 시작) 클릭
    await sleep(300);
    const candidates = [...document.querySelectorAll('button, a, .se-popup-button, [class*="popup"] button')];
    for (const btn of candidates) {
      const t = (btn.textContent || '').trim();
      if (t === '취소' || t === '아니오' || t === '새로 작성' || t === '새글쓰기') {
        try { btn.click(); console.log(TAG, '드래프트 팝업 취소'); await sleep(300); return true; } catch (e) {}
      }
    }
    return false;
  }

  // ---------- 이미지: base64 → File ----------
  function base64ToFile(dataUrl, name) {
    const [head, body] = dataUrl.split(',');
    const mime = (head.match(/data:(.*?);/) || [])[1] || 'image/jpeg';
    const bin = atob(body);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new File([arr], name, { type: mime });
  }

  // ---------- 이미지 드롭 삽입 ----------
  // 현재 캐럿(커서) 위치의 화면 좌표. 인터리브 삽입 시 문단 사이에 떨어뜨리기 위함.
  function caretPoint() {
    try {
      const sel = window.getSelection();
      if (sel && sel.rangeCount) {
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        if (rect && (rect.top || rect.left) && rect.top > 0) {
          return { x: rect.left + 2, y: rect.top + rect.height / 2 };
        }
      }
    } catch (e) { /* noop */ }
    return null;
  }

  async function dropImage(file, atCaret) {
    const target =
      document.querySelector('.se-content .se-components-wrap') ||
      document.querySelector('.se-content') ||
      document.querySelector('.se-dnd-wrap') ||
      document.querySelector('.se-component.se-text');
    if (!target) throw new Error('드롭 대상 없음');

    const dt = new DataTransfer();
    dt.items.add(file);
    // atCaret 이면 커서 위치, 아니면 에디터 하단(기존 동작)
    let x, y;
    const cp = atCaret ? caretPoint() : null;
    if (cp) { x = cp.x; y = cp.y; }
    else { const r = target.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top + r.height - 8; }
    const opts = { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, clientX: x, clientY: y };
    target.dispatchEvent(new DragEvent('dragenter', opts));
    target.dispatchEvent(new DragEvent('dragover', opts));
    target.dispatchEvent(new DragEvent('drop', opts));
  }

  // 에디터에 실제로 올라간 이미지 수. 드롭 성공 여부를 이걸로 확인한다.
  //
  // 주의: SELECTORS.md 기준 이미지 컴포넌트의 정확한 클래스는 아직 실측되지 않았다
  // (문서에 확보된 건 se-documentTitle / se-text 뿐). 그래서 클래스 하나에 걸지 않고
  // 여러 신호의 최댓값을 쓴다 — 하나가 빗나가도 나머지가 잡아준다.
  // 특히 마지막 img 세기는 클래스명이 바뀌어도 유효하다(업로드되면 결국 img 가 생긴다).
  function imageComponentCount() {
    const counts = [
      document.querySelectorAll('.se-component.se-image').length,
      document.querySelectorAll('.se-component[class*="image" i]').length,
      document.querySelectorAll('.se-content img, .se-components-wrap img').length,
    ];
    return Math.max.apply(null, counts);
  }

  // 드롭 후 '이미지 컴포넌트가 실제로 늘었는지'까지 확인한다.
  // 예전엔 DragEvent 3개를 쏘고 sleep(1800) 만 기다렸다 — 네이버가 업로드를 거부하거나
  // 1.8초 안에 못 끝내면 0장이 들어갔는데도 성공으로 셌다.
  async function dropImageVerified(file, atCaret, timeoutMs) {
    const before = imageComponentCount();
    await dropImage(file, atCaret);
    const deadline = Date.now() + (timeoutMs || 25000);
    while (Date.now() < deadline) {
      await sleep(300);
      if (imageComponentCount() > before) return true;
    }
    return false;
  }

  async function insertImages(images, atCaret) {
    if (!images || !images.length) return { inserted: 0, expected: 0, failed: [] };
    let ok = 0;
    const failed = [];
    for (let i = 0; i < images.length; i++) {
      let placed = false;
      let lastErr = '';
      // 업로드는 네트워크·서버 사정으로 곧잘 실패한다 → 3회까지 재시도.
      for (let attempt = 1; attempt <= 3 && !placed; attempt++) {
        try {
          const file = base64ToFile(images[i], `image_${Date.now()}_${i}_${attempt}.jpg`);
          placed = await dropImageVerified(file, atCaret);
          if (!placed) lastErr = '업로드 확인 실패(시간 초과)';
        } catch (e) {
          lastErr = e.message;
        }
        if (!placed && attempt < 3) {
          console.warn(TAG, `이미지 ${i} 삽입 재시도 ${attempt}/3`, lastErr);
          showOverlay(`🖼️ 이미지 재시도 중... (${i + 1}/${images.length})`, 60);
          await sleep(2000 * attempt); // 점증 대기
        }
      }
      if (placed) {
        ok++;
        showOverlay(`🖼️ 이미지 삽입 중... (${ok}/${images.length})`, 60 + (i / images.length) * 20);
        await sleep(600); // 다음 드롭 전 안정화(업로드 완료는 위에서 이미 확인)
      } else {
        console.error(TAG, '이미지 삽입 최종 실패', i, lastErr);
        failed.push({ index: i, error: lastErr });
      }
    }
    // 호출부(background)가 이 값을 보고 발행을 중단한다. 사진 빠진 글이 나가면 안 된다.
    return { inserted: ok, expected: images.length, failed };
  }

  // ---------- React 제어 select 값 설정 ----------
  function setNativeValue(el, value) {
    const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype
      : el instanceof HTMLInputElement ? HTMLInputElement.prototype
      : HTMLElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ---------- 블로그 식별 ----------
  // 예약 기준 시각은 블로그마다 따로 관리해야 한다. 계정을 바꿔도 같은 기준을 쓰면
  // 남의 블로그 예약 위에 겹쳐 잡히고, 반대로 이 블로그 예약이 저 블로그 기준을 오염시킨다.
  function readBlogId() {
    const fromUrl = (u) => {
      const m = /[?&]blogId=([^&]+)/.exec(u || '');
      return m ? decodeURIComponent(m[1]) : '';
    };
    // 1) 현재 URL (PostWriteForm.naver?blogId=...)
    let id = fromUrl(location.href);
    if (id) return id;
    // 2) 에디터 iframe 의 src
    for (const f of document.querySelectorAll('iframe')) {
      id = fromUrl(f.getAttribute('src'));
      if (id) return id;
    }
    // 3) blog.naver.com/<blogId> 형태. 뒤에 /?끝 이 와야 하므로 'GoBlogWrite.naver' 같은
    //    페이지 이름은 걸리지 않는다.
    const m = /blog\.naver\.com\/([A-Za-z0-9_-]+)(?:[/?#]|$)/.exec(location.href);
    return m ? m[1] : '';
  }

  // ---------- 공개설정 라디오 ----------
  function setOpenType(type) {
    const map = { public: '#open_public', neighbor: '#open_neighbor', both: '#open_both_neighbor', private: '#open_private' };
    const el = document.querySelector(map[type] || map.public);
    if (el && !el.checked) { el.click(); }
  }

  // ---------- 카테고리 ----------
  // 주의: 네이버 클래스명(selectbox_button__jb1Dt 등)은 배포마다 바뀌는 해시라 절대 쓰지 말 것.
  //       data-click-area / data-testid 만 사용한다.
  const CATEGORY_BTN = '[data-click-area="tpb*i.category"], button[aria-label="카테고리 목록 버튼"]';
  const CATEGORY_ITEM = '[role="menu"] input[data-testid^="categoryBtn_"]';

  function normText(s) {
    // JS 의 \s 는 NBSP(U+00A0)를 포함한다. 카테고리명에 NBSP 가 섞여 있어도(예: 'PLT 지급대행 서비스')
    // 이 한 줄로 일반 공백과 동일하게 정규화된다.
    return (s || '').replace(/\s+/g, ' ').trim();
  }

  // 버튼 안의 현재 카테고리명. 목록 항목과 data-testid 가 겹치므로 반드시 버튼 하위로 스코프를 좁힌다.
  function currentCategoryName() {
    const el = document.querySelector(CATEGORY_BTN)?.querySelector('[data-testid^="categoryItemText_"]');
    return normText(el && el.textContent);
  }

  // 열린 레이어에서 [{id, name, label}] 수집. [role="menu"] 로 스코프를 좁혀 버튼 자신을 제외한다.
  function readCategoryItems() {
    return [...document.querySelectorAll(CATEGORY_ITEM)].map((inp) => {
      const id = (inp.dataset.testid || '').replace('categoryBtn_', '');
      const li = inp.closest('li') || inp.parentElement;
      const nameEl = li && li.querySelector('[data-testid^="categoryItemText_"]');
      return { id, name: normText(nameEl && nameEl.textContent), label: li && li.querySelector('label'), input: inp };
    }).filter((c) => c.id && c.name);
  }

  async function openCategoryLayer(btn) {
    if (btn.getAttribute('aria-expanded') === 'true') return true;
    btn.click();
    const ok = await waitFor(CATEGORY_ITEM, { timeout: 5000 });
    await sleep(150);
    return !!ok;
  }

  async function closeCategoryLayer(btn) {
    if (btn.getAttribute('aria-expanded') === 'true') { btn.click(); await sleep(150); }
  }

  /** 목록만 읽고 원래 상태로 되돌린다. → [{id, name}] */
  async function readCategories() {
    const btn = document.querySelector(CATEGORY_BTN);
    if (!btn) return [];
    const wasOpen = btn.getAttribute('aria-expanded') === 'true';
    if (!(await openCategoryLayer(btn))) return [];
    const list = readCategoryItems().map(({ id, name }) => ({ id, name }));
    if (!wasOpen) await closeCategoryLayer(btn);
    return list;
  }

  /**
   * 카테고리 선택. category 는 번호("24") 또는 이름("대표작성 칼럼(노하우,생각)").
   * 번호를 우선 매칭한다 — 이름은 사용자가 언제든 바꿀 수 있지만 번호는 유지되기 때문.
   * @returns {{ok:boolean, categories:{id,name}[], current:string, error?:string}}
   */
  async function selectCategory(category) {
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

    // input 은 role="none" tabindex="-1" 이라 클릭 핸들러가 없다. label[role="button"] 을 클릭해야 반영된다.
    (hit.label || hit.input).click();
    await sleep(400);

    // 버튼 텍스트가 실제로 바뀌었는지 확인 — 조용히 기본 카테고리로 발행되는 것을 막는다.
    const after = currentCategoryName();
    if (after !== hit.name) {
      return { ok: false, categories, current: after, error: `카테고리 반영 실패 (현재 '${after || '?'}')` };
    }
    return { ok: true, categories, current: after };
  }

  /**
   * 앱의 '카테고리 동기화'용. 발행 레이어가 닫혀 있으면 열어서 목록만 읽고 원래대로 되돌린다.
   * 첫 발행 전에도 앱 드롭다운을 채울 수 있게 하는 용도라 글을 발행하지는 않는다.
   */
  async function syncCategories() {
    const alreadyOpen = !!document.querySelector(CATEGORY_BTN);
    if (!alreadyOpen) {
      const openBtn =
        document.querySelector('[data-click-area="tpb.publish"]') ||
        [...document.querySelectorAll('button')].find((b) => (b.textContent || '').trim() === '발행');
      if (!openBtn) return { ok: false, categories: [], error: '발행 버튼을 찾지 못했습니다(에디터가 열려 있어야 합니다)' };
      openBtn.click();
      if (!(await waitFor(CATEGORY_BTN, { timeout: 8000 }))) {
        return { ok: false, categories: [], error: '발행 레이어를 열지 못했습니다' };
      }
      await sleep(300);
    }

    const categories = await readCategories();

    // 우리가 연 경우에만 닫는다. 사용자가 이미 열어둔 레이어는 건드리지 않는다.
    if (!alreadyOpen) {
      const closeBtn = document.querySelector('[data-click-area="tpb.publish"]');
      if (closeBtn) closeBtn.click();
      else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      await sleep(200);
    }
    return { ok: categories.length > 0, categories, error: categories.length ? undefined : '카테고리를 읽지 못했습니다' };
  }

  // ---------- 캡차 감지 / 사용자 핸드오프 ----------
  function captchaPresent() {
    return !!document.querySelector(
      'iframe[id^="ncaptcha-iframe"], iframe[src*="ncaptcha"], iframe[src*="captcha"], ' +
      '#ncaptcha, .captcha_wrap, [class*="captcha"] input[type="text"]'
    );
  }
  async function waitForCaptchaResolved(timeout = 180000) {
    if (!captchaPresent()) return true;
    console.log(TAG, '캡차 감지 → 사용자 입력 대기');
    const start = Date.now();
    while (Date.now() - start < timeout) {
      showOverlay('🔐 보안문자(캡차)가 나타났습니다. 직접 입력해 주세요...', 96);
      await sleep(800);
      if (!captchaPresent()) { await sleep(600); return true; }
    }
    showOverlay('⚠️ 캡차 대기 시간 초과 — 직접 발행을 마쳐주세요.', 100);
    return false;
  }

  // ---------- 예약발행 날짜: jQuery UI datepicker 선택 (당일 아닌 예약 지원) ----------
  async function selectScheduleDate(dt) {
    const targetY = dt.getFullYear();
    const targetM = dt.getMonth() + 1;
    const targetD = dt.getDate();

    const dateInput = document.querySelector(
      'input.input_date__QmA0s, .date__Lkn7S input, input[readonly][class*="input_date"]'
    );
    if (!dateInput) { console.warn(TAG, '날짜 input 없음'); return false; }
    dateInput.click();

    // datepicker 표시 대기 후 루트 확보 (#ui-datepicker-div 가 header+table 을 감쌈)
    await waitFor('.ui-datepicker-header', { timeout: 4000 });
    const header = document.querySelector('.ui-datepicker-header');
    const root = document.querySelector('#ui-datepicker-div') || (header && header.parentElement);
    if (!root) { console.warn(TAG, 'datepicker 미표시'); return false; }

    const readShown = () => ({
      y: parseInt(root.querySelector('.ui-datepicker-year')?.textContent || '0', 10),
      m: parseInt((root.querySelector('.ui-datepicker-month')?.textContent || '0').replace(/[^0-9]/g, ''), 10),
    });

    // 목표 연·월까지 이동 (미래는 next, 과거 방향은 prev — 단 과거달은 disabled)
    for (let i = 0; i < 36; i++) {
      const { y, m } = readShown();
      if (!y || !m || (y === targetY && m === targetM)) break;
      const goNext = (y < targetY) || (y === targetY && m < targetM);
      const nav = root.querySelector(goNext ? '.ui-datepicker-next' : '.ui-datepicker-prev');
      if (!nav || nav.classList.contains('ui-state-disabled')) { console.warn(TAG, '월 이동 불가(범위 밖)'); break; }
      nav.click();
      await sleep(220);
    }

    // 목표 일 클릭 (비활성일 td.ui-state-disabled 제외)
    const dayEls = [...root.querySelectorAll(
      'td:not(.ui-state-disabled) a.ui-state-default, td:not(.ui-state-disabled) button.ui-state-default'
    )];
    const cell = dayEls.find((el) => (el.textContent || '').trim() === String(targetD));
    if (!cell) { console.warn(TAG, '해당 일자 선택 불가(비활성/미표시)', targetD); return false; }
    cell.click();
    await sleep(220);
    return true;
  }

  // ---------- 최종 동작: 임시저장 / 즉시발행 / 예약발행 ----------
  async function finalize(job) {
    const action = job.finalAction || 'draft';

    if (action === 'draft') {
      // 임시저장
      showOverlay('💾 임시저장 중...', 90);
      const saveBtn =
        document.querySelector('[data-click-area="tpb.save"]') ||
        document.querySelector('.save_btn__bzc5B') ||
        [...document.querySelectorAll('button')].find((b) => (b.textContent || '').trim() === '저장');
      if (!saveBtn) throw new Error('임시저장 버튼 없음');
      saveBtn.click();
      await sleep(1500);
      // 저장 확인 팝업이 뜨면 확인 클릭
      await clickConfirmIfAny();
      return { done: true, action: 'draft' };
    }

    // 발행 계열: 발행 버튼 클릭 → 레이어 열기
    showOverlay('📤 발행 설정 여는 중...', 88);
    const publishOpenBtn =
      document.querySelector('[data-click-area="tpb.publish"]') ||
      document.querySelector('.publish_btn__m9KHH') ||
      [...document.querySelectorAll('button')].find((b) => (b.textContent || '').trim() === '발행');
    if (!publishOpenBtn) throw new Error('발행 버튼 없음');
    publishOpenBtn.click();

    // 레이어 대기
    const finalBtn = await waitFor('[data-testid="seOnePublishBtn"], [data-click-area="tpb*i.publish"]', { timeout: 8000 });
    if (!finalBtn) throw new Error('발행 레이어 열림 실패');
    await sleep(400);

    // 공개설정 반영
    if (job.options?.openType) setOpenType(job.options.openType);
    // 검색허용 반영(옵션)
    if (job.options && job.options.search === false) {
      const s = document.querySelector('#publish-option-search');
      if (s && s.checked) s.click();
    }

    // 카테고리 반영. 미지정이면 손대지 않고 네이버 기본 카테고리로 둔다.
    let categories = [];
    if (job.options?.category) {
      showOverlay('🗂️ 카테고리 설정 중...', 90);
      const r = await selectCategory(job.options.category);
      categories = r.categories;
      // 엉뚱한 카테고리로 공개 발행되면 수동으로 되돌려야 하므로, 못 찾으면 발행하지 않는다.
      if (!r.ok) {
        const avail = r.categories.map((c) => `${c.name}(${c.id})`).join(', ');
        throw new Error(`${r.error}. 사용 가능한 카테고리: ${avail || '목록을 읽지 못했습니다'}`);
      }
    }

    if (action === 'schedule' && job.schedule?.datetime) {
      showOverlay('⏰ 예약 시간 설정 중...', 92);
      // 예약 라디오 켜기
      const pre = document.querySelector('#radio_time2, [data-testid="preTimeRadioBtn"]');
      if (pre && !pre.checked) pre.click();
      await sleep(400);

      const dt = new Date(job.schedule.datetime);

      // 날짜: jQuery UI datepicker 로 정확히 선택 (당일이 아니어도 지원)
      // 실패하면 여기서 멈춘다 — 예전엔 경고만 찍고 계속 진행해 네이버 기본값(오늘/지금)으로
      // 즉시 발행돼버렸다. 100건 배치라면 예약해둔 글이 전부 한꺼번에 나간다.
      const dateOk = await selectScheduleDate(dt);
      if (!dateOk) throw new Error('예약 날짜를 지정하지 못했습니다(네이버 화면 변경 가능). 즉시 발행을 막기 위해 중단합니다');

      // 시/분 (분은 10분 단위만 허용 → 내림)
      const hh = String(dt.getHours()).padStart(2, '0');
      const mm = String(Math.floor(dt.getMinutes() / 10) * 10).padStart(2, '0');
      const hourSel = document.querySelector('select.hour_option__J_heO, .hour__ckNMb select');
      const minSel = document.querySelector('select.minute_option__Vb3xB, .minute__KXXvZ select');
      if (!hourSel || !minSel) throw new Error('예약 시각 입력란을 찾지 못했습니다(네이버 화면 변경 가능). 즉시 발행을 막기 위해 중단합니다');
      setNativeValue(hourSel, hh);
      setNativeValue(minSel, mm);
      await sleep(300);
    }

    // 최종 발행 클릭
    showOverlay(action === 'schedule' ? '⏰ 예약발행 확정...' : '📤 발행 중...', 96);
    finalBtn.click();
    await sleep(2000);

    // 캡차가 나타나면 사용자에게 넘기고 해결될 때까지 대기
    const captchaOk = await waitForCaptchaResolved();
    if (!captchaOk) return { done: false, action, error: '캡차 시간 초과' };

    await clickConfirmIfAny();
    return { done: true, action, categories };
  }

  async function clickConfirmIfAny() {
    await sleep(400);
    const btn = [...document.querySelectorAll('button, a')].find((b) => {
      const t = (b.textContent || '').trim();
      return t === '확인' || t === '발행' || t === '예';
    });
    if (btn) { try { btn.click(); await sleep(500); } catch (e) {} }
  }

  // ============================================================
  // 메시지 라우터 (background ↔ 이 프레임)
  // ============================================================
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || !msg.action) return;

    // 에디터 프레임만 처리하는 명령들
    const editorOnly = ['GET_POSITIONS', 'DISMISS_POPUP', 'INSERT_IMAGES', 'FINALIZE', 'PROGRESS', 'READ_CATEGORIES'];
    if (editorOnly.includes(msg.action) && !isEditorFrame()) return; // 다른 프레임은 무시

    // blogId 는 프레임마다 알 수 있고 없고가 갈린다(에디터 iframe 의 src 에 들어 있다).
    // 모르는 프레임이 빈 값으로 먼저 답해버리면 그 답이 채택되므로, 찾은 프레임만 답한다.
    if (msg.action === 'READ_BLOG_ID' && !readBlogId()) return;

    (async () => {
      try {
        switch (msg.action) {
          case 'PING':
            sendResponse({ ok: true, version: '15.0.1', editor: isEditorFrame() });
            break;
          case 'PROGRESS':
            showOverlay(msg.text, msg.pct);
            sendResponse({ ok: true });
            break;
          case 'DISMISS_POPUP':
            await dismissDraftPopup();
            sendResponse({ ok: true });
            break;
          case 'GET_POSITIONS': {
            const titlePara = document.querySelector('.se-documentTitle .se-text-paragraph');
            const bodyPara = document.querySelector('.se-component.se-text .se-text-paragraph');
            sendResponse({
              ok: !!(titlePara && bodyPara),
              title: titlePara ? absoluteRect(titlePara) : null,
              body: bodyPara ? absoluteRect(bodyPara) : null,
            });
            break;
          }
          case 'INSERT_IMAGES': {
            const res = await insertImages(msg.images, msg.atCaret);
            sendResponse({ ok: true, ...res });
            break;
          }
          case 'FINALIZE': {
            const res = await finalize(msg.job);
            hideOverlay();
            // ok 를 res 로 덮어쓰지 않도록 뒤에 둔다 — 예전엔 { ok:true, ...res } 라
            // 캡차 시간 초과(done:false) 같은 실패가 성공으로 보고됐다.
            sendResponse({ ...res, ok: res.done !== false });
            break;
          }
          case 'READ_CATEGORIES': {
            const res = await syncCategories();
            sendResponse(res);
            break;
          }
          case 'READ_BLOG_ID': {
            sendResponse({ ok: true, blogId: readBlogId() });
            break;
          }
          case 'HIDE_OVERLAY':
            hideOverlay();
            sendResponse({ ok: true });
            break;
          default:
            break;
        }
      } catch (e) {
        console.error(TAG, msg.action, '실패', e);
        sendResponse({ ok: false, error: e.message });
      }
    })();
    return true; // async
  });

  // ============================================================
  // 진입: 에디터 준비되면 background에 알림
  // ============================================================
  async function boot() {
    if (!/GoBlogWrite|PostWriteForm|editor/i.test(location.href) && !isEditorFrame()) {
      // 글쓰기 관련 페이지가 아니면 대기만
    }
    // 편집 대상 프레임에서만 부팅
    const title = await waitFor('.se-documentTitle .se-text-paragraph', { timeout: 25000 });
    if (!title) { console.log(TAG, '에디터 미발견(이 프레임 아님)'); return; }

    console.log(TAG, '에디터 준비됨, background에 EDITOR_READY 전송');
    showOverlay('✍️ 자동 작성을 시작합니다...', 5);
    try {
      const resp = await chrome.runtime.sendMessage({ action: 'EDITOR_READY' });
      if (!resp || !resp.hasJob) hideOverlay();
    } catch (e) {
      console.log(TAG, 'EDITOR_READY 전송 실패', e.message);
      hideOverlay();
    }
  }

  if (document.readyState === 'complete') boot();
  else window.addEventListener('load', boot);
})();
