// ============================================================
// 닥터보이스 프로 - Gemini 글 생성 Content Script v16
//  gemini.google.com 에서 프롬프트를 넣고 응답을 수확한다.
//
//  역할 분담은 naver-poster.js 와 동일하다:
//   - 이 스크립트: DOM 판정 + 좌표 제공 + 대기
//   - background.js: CDP 로 실제 입력(Input.insertText / Enter)
//  Gemini 입력창은 Quill 이라 textContent 직접 대입이 먹지 않는다. 네이버 SE ONE 과
//  같은 이유로 CDP 입력이 유일하게 안정적인 경로다.
// ============================================================
(() => {
  'use strict';
  const TAG = '[닥터보이스:gemini]';
  const VERSION = '16.0.2';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const q = (sel, root) => (root || document).querySelector(sel);
  const qa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------- 셀렉터 (SELECTORS.md 의 Gemini 섹션과 동기화할 것) ----------
  const SEL = {
    input: 'rich-textarea .ql-editor[role="textbox"]',
    conversation: '.conversation-container',
    modelResponse: 'model-response',
    markdown: '.markdown.markdown-main-panel',
    footer: '.response-footer',
    actions: 'message-actions',
    newChat: '[data-test-id="new-chat-button"] a',
    tempChat: '[data-test-id="temp-chat-button"]',
    modePicker: '[data-test-id="bard-mode-menu-button"]',
    avatar: 'sidenav-mavatar-footer .mavatar-image',
  };

  // ============================================================
  // 상태 판정
  // ============================================================
  function inputEl() { return q(SEL.input); }

  /** 앱이 뜨고 입력창이 살아있는가 */
  function isReady() {
    const el = inputEl();
    return !!(el && el.isConnected && el.getBoundingClientRect().width > 0);
  }

  /** 로그인 여부. 아바타가 없으면 세션이 끊긴 것 */
  function isLoggedIn() { return !!q(SEL.avatar); }

  function conversationCount() { return qa(SEL.conversation).length; }

  function lastResponse() {
    const all = qa(SEL.modelResponse);
    return all.length ? all[all.length - 1] : null;
  }

  /**
   * 응답 생성이 끝났는가.
   * Gemini 는 완료를 DOM 에 명시적으로 남긴다 — 글자수 정체 같은 휴리스틱이 필요 없다.
   * 다만 한 신호만 믿으면 UI 개편 때 통째로 깨지므로 세 신호 중 2개 이상으로 판정한다.
   * (네이버 imageComponentCount() 에서 단일 신호를 믿었다가 고생한 것과 같은 교훈)
   */
  function completionSignals(resp) {
    if (!resp) return { count: 0, detail: {} };
    const footer = q(SEL.footer, resp);
    const md = q(SEL.markdown, resp);
    const detail = {
      footerComplete: !!(footer && footer.classList.contains('complete')),
      notBusy: !!(md && md.getAttribute('aria-busy') === 'false'),
      hasActions: !!q(SEL.actions, resp),
    };
    const count = Object.values(detail).filter(Boolean).length;
    return { count, detail };
  }

  function isComplete(resp) { return completionSignals(resp).count >= 2; }

  function responseText(resp) {
    const md = q(SEL.markdown, resp);
    if (!md) return '';
    // innerText 는 문단 구분(\n)을 유지한다. textContent 는 다 붙어버려 못 쓴다.
    return (md.innerText || '').trim();
  }

  // ============================================================
  // 진행 오버레이
  // ============================================================
  let overlay = null;
  function ensureOverlay() {
    if (overlay && overlay.isConnected) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'dv-gem-overlay';
    overlay.innerHTML = `
      <div class="dv-gem-card">
        <div class="dv-gem-title">닥터보이스 글 생성 중</div>
        <div class="dv-gem-text">준비 중…</div>
        <div class="dv-gem-bar"><i></i></div>
        <div class="dv-gem-hint">이 탭을 닫거나 조작하지 마세요</div>
      </div>`;
    const style = document.createElement('style');
    style.id = 'dv-gem-style';
    style.textContent = `
      #dv-gem-overlay{position:fixed;left:0;right:0;top:0;z-index:2147483647;pointer-events:none;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic',sans-serif;
        display:flex;justify-content:center;padding-top:14px}
      #dv-gem-overlay .dv-gem-card{pointer-events:auto;background:#111827;color:#fff;border-radius:14px;
        padding:14px 18px;min-width:320px;box-shadow:0 12px 36px rgba(0,0,0,.35)}
      #dv-gem-overlay .dv-gem-title{font-size:12px;font-weight:700;letter-spacing:.04em;color:#a5b4fc;
        margin-bottom:6px}
      #dv-gem-overlay .dv-gem-text{font-size:14px;line-height:1.4;margin-bottom:10px}
      #dv-gem-overlay .dv-gem-bar{height:4px;background:#374151;border-radius:99px;overflow:hidden}
      #dv-gem-overlay .dv-gem-bar i{display:block;height:100%;width:0;background:#818cf8;
        border-radius:99px;transition:width .3s ease}
      #dv-gem-overlay .dv-gem-hint{margin-top:8px;font-size:11px;color:#9ca3af}`;
    document.documentElement.appendChild(style);
    document.documentElement.appendChild(overlay);
    return overlay;
  }
  function setProgress(text, pct) {
    const el = ensureOverlay();
    const t = q('.dv-gem-text', el);
    const bar = q('.dv-gem-bar i', el);
    if (t && text) t.textContent = text;
    if (bar && typeof pct === 'number') bar.style.width = Math.max(0, Math.min(100, pct)) + '%';
  }
  function hideOverlay() {
    if (overlay) { overlay.remove(); overlay = null; }
    const s = document.getElementById('dv-gem-style');
    if (s) s.remove();
  }

  // ============================================================
  // 동작
  // ============================================================
  async function waitFor(fn, timeout, label) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      try { if (fn()) return true; } catch (_) {}
      await sleep(200);
    }
    throw new Error(`${label} 대기 시간 초과(${Math.round(timeout / 1000)}초)`);
  }

  /** 입력창 좌표(뷰포트 기준). background 가 CDP 클릭에 쓴다. */
  function inputPosition() {
    const el = inputEl();
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
  }

  /**
   * 임시 채팅 켜기(best-effort).
   * 켜두면 100건을 돌려도 사이드바에 기록이 안 쌓인다. 다만 이것만으로 문맥이
   * 초기화되지는 않는다 — 글마다 newChat() 을 따로 불러야 한다.
   * 실패해도 생성 자체에는 지장이 없으므로 절대 throw 하지 않는다.
   */
  function enableTempChat() {
    try {
      const host = q(SEL.tempChat);
      if (!host) return false;
      const btn = host.querySelector('button') || host;
      const pressed = btn.getAttribute('aria-pressed');
      if (pressed === 'true') return true; // 이미 켜짐
      // aria-pressed 를 안 쓰는 빌드도 있다 → 설명 툴팁으로 판정(‘사용 설정’이면 꺼진 상태)
      const descId = btn.getAttribute('aria-describedby') || host.getAttribute('aria-describedby');
      const desc = descId ? document.getElementById(descId) : null;
      const off = !desc || /사용 설정|turn on/i.test(desc.textContent || '');
      if (!off) return true;
      btn.click();
      return true;
    } catch (_) { return false; }
  }

  /**
   * 새 채팅. 문맥 초기화의 핵심.
   * Angular SPA 라 페이지는 안 바뀌고 대화 컨테이너만 사라진다 → 그걸로 판정한다.
   */
  async function newChat() {
    const before = conversationCount();
    const link = q(SEL.newChat);
    if (!link) throw new Error('새 채팅 버튼을 찾지 못했습니다(Gemini UI 변경 가능성)');
    link.click();
    await waitFor(() => conversationCount() === 0, 15000, '새 채팅');
    await waitFor(isReady, 10000, '입력창 재생성');
    await sleep(300); // Quill 초기화 여유
    return { before, after: conversationCount() };
  }

  /**
   * 응답 완료까지 대기 후 본문 수확.
   * timeout 은 background 가 프롬프트 길이에 맞춰 정한다.
   */
  async function harvest(expectIndex, timeout) {
    // 새 응답 블록이 생길 때까지
    await waitFor(() => qa(SEL.modelResponse).length > expectIndex, 60000, '응답 시작');
    const started = Date.now();
    let lastLen = 0;
    while (Date.now() - started < timeout) {
      const resp = lastResponse();
      if (resp && isComplete(resp)) {
        const text = responseText(resp);
        if (text) return { ok: true, text, chars: text.length };
      }
      // 진행률 표시용(글자가 늘어나는 걸 보여줌)
      const cur = resp ? responseText(resp).length : 0;
      if (cur !== lastLen) {
        lastLen = cur;
        setProgress(`생성 중… ${cur.toLocaleString()}자`, Math.min(90, 20 + cur / 40));
      }
      await sleep(400);
    }
    // 시간 초과. 그때까지 나온 글이라도 넘겨서 background 가 길이로 판단하게 한다.
    const resp = lastResponse();
    const text = resp ? responseText(resp) : '';
    return { ok: false, text, chars: text.length, error: '응답 완료 신호를 받지 못했습니다' };
  }

  // ============================================================
  // 메시지 인터페이스 (background → 이 탭)
  // ============================================================
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || typeof msg.action !== 'string' || !msg.action.startsWith('GEM_')) return;
    (async () => {
      try {
        switch (msg.action) {
          case 'GEM_PING':
            sendResponse({
              ok: true, version: VERSION,
              ready: isReady(), loggedIn: isLoggedIn(),
              conversations: conversationCount(),
            });
            break;

          case 'GEM_WAIT_READY':
            await waitFor(isReady, msg.timeout || 30000, 'Gemini 앱 로딩');
            if (!isLoggedIn()) throw new Error('Gemini 에 로그인되어 있지 않습니다');
            if (msg.tempChat) enableTempChat();
            sendResponse({ ok: true });
            break;

          case 'GEM_NEW_CHAT': {
            const r = await newChat();
            sendResponse({ ok: true, ...r });
            break;
          }

          case 'GEM_INPUT_POS': {
            const el = inputEl();
            if (!el) throw new Error('입력창을 찾지 못했습니다');
            el.scrollIntoView({ block: 'center' });
            await sleep(120);
            sendResponse({ ok: true, pos: inputPosition(), count: qa(SEL.modelResponse).length });
            break;
          }

          case 'GEM_HARVEST': {
            const r = await harvest(msg.expectIndex || 0, msg.timeout || 180000);
            sendResponse(r);
            break;
          }

          // 폴링 수확용 — 기다리지 않고 '지금 상태'만 즉시 돌려준다.
          // background 가 짧은 간격으로 반복 호출한다(MV3 워커 유지 + 무한멈춤 방지).
          case 'GEM_STATUS': {
            const responses = qa(SEL.modelResponse);
            const started = responses.length > (msg.expectIndex || 0);
            const resp = responses.length ? responses[responses.length - 1] : null;
            const complete = !!(started && resp && isComplete(resp));
            const text = resp ? responseText(resp) : '';
            // text/chars 는 '지금까지 나온' 값(부분 포함). complete 로 완료 여부를 구분한다.
            sendResponse({ ok: true, started, complete, chars: text.length, text });
            break;
          }

          case 'GEM_PROGRESS':
            setProgress(msg.text, msg.pct);
            sendResponse({ ok: true });
            break;

          case 'GEM_HIDE_OVERLAY':
            hideOverlay();
            sendResponse({ ok: true });
            break;

          default:
            sendResponse({ ok: false, error: 'unknown action' });
        }
      } catch (e) {
        sendResponse({ ok: false, error: e.message });
      }
    })();
    return true; // 비동기 응답
  });

  console.log(TAG, `준비됨 v${VERSION}`);
})();
