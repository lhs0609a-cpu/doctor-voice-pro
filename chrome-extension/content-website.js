// ============================================================
// 닥터보이스 프로 - 웹사이트 브릿지 Content Script v15
//  1) 확장 ID를 페이지에 노출 (프론트 one-click-publish 가 읽음)
//  2) 새 버전 감지 시 웹사이트에 업데이트 팝업 표시
// ============================================================
(() => {
  'use strict';
  const TAG = '[닥터보이스:web]';
  const EXTENSION_ID = chrome.runtime.id;

  // ---------- 1) 확장 ID 노출 + 준비 신호 ----------
  function exposeExtensionId() {
    try {
      localStorage.setItem('doctorvoice-extension-id', EXTENSION_ID);
    } catch (e) { /* private mode 등 */ }

    let indicator = document.getElementById('doctorvoice-extension-connected');
    if (!indicator && document.body) {
      indicator = document.createElement('div');
      indicator.id = 'doctorvoice-extension-connected';
      indicator.style.display = 'none';
      indicator.dataset.extensionId = EXTENSION_ID;
      document.body.appendChild(indicator);
    }
    console.log(TAG, '확장 연결됨, ID:', EXTENSION_ID);

    // 웹 신호등이 즉시 재확인하도록 준비 이벤트 발사 (버전 포함)
    try {
      chrome.runtime.sendMessage({ action: 'GET_VERSION' }, (res) => {
        const version = (res && res.version) || null;
        if (version) {
          try { localStorage.setItem('doctorvoice-extension-version', version); } catch (e) {}
          if (indicator) indicator.dataset.version = version;
        }
        window.dispatchEvent(new CustomEvent('doctorvoice-extension-ready', {
          detail: { extensionId: EXTENSION_ID, version },
        }));
      });
    } catch (e) {
      window.dispatchEvent(new CustomEvent('doctorvoice-extension-ready', {
        detail: { extensionId: EXTENSION_ID, version: null },
      }));
    }
  }

  // ---------- 2) 업데이트 팝업 ----------
  const DISMISS_KEY = 'doctorvoice-update-dismissed'; // 값 = 무시한 latest 버전

  function alreadyDismissed(latest) {
    try { return localStorage.getItem(DISMISS_KEY) === latest; } catch (e) { return false; }
  }
  function dismiss(latest) {
    try { localStorage.setItem(DISMISS_KEY, latest); } catch (e) {}
  }

  function showUpdatePopup(info) {
    if (document.getElementById('dv-update-popup')) return;
    if (!document.body) return;

    const wrap = document.createElement('div');
    wrap.id = 'dv-update-popup';
    wrap.innerHTML = `
      <div class="dv-up-card">
        <button class="dv-up-close" aria-label="닫기">&times;</button>
        <div class="dv-up-head">
          <span class="dv-up-badge">NEW</span>
          <strong>확장 프로그램 업데이트</strong>
        </div>
        <div class="dv-up-ver">v${info.current} &rarr; <b>v${info.latest}</b></div>
        <div class="dv-up-notes">${(info.notes || '새로운 버전이 준비되었습니다.').replace(/</g, '&lt;')}</div>
        <div class="dv-up-actions">
          <a class="dv-up-download" href="${info.downloadUrl || '#'}" target="_blank" rel="noopener">
            새 버전 다운로드
          </a>
          <button class="dv-up-later">나중에</button>
        </div>
        <div class="dv-up-hint">다운로드 후 chrome://extensions 에서 압축 해제한 폴더를 갱신해 주세요</div>
      </div>`;

    const style = document.createElement('style');
    style.textContent = `
      #dv-update-popup{position:fixed;right:20px;bottom:20px;z-index:2147483647;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic',sans-serif;}
      #dv-update-popup .dv-up-card{position:relative;width:320px;background:#fff;border-radius:16px;
        padding:20px 22px;box-shadow:0 16px 48px rgba(0,0,0,.24);border:1px solid #e5e7eb;
        animation:dvUpIn .3s ease}
      @keyframes dvUpIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
      #dv-update-popup .dv-up-close{position:absolute;top:10px;right:12px;border:0;background:none;
        font-size:20px;line-height:1;color:#9ca3af;cursor:pointer}
      #dv-update-popup .dv-up-head{display:flex;align-items:center;gap:8px;font-size:15px;color:#111827}
      #dv-update-popup .dv-up-badge{background:#ef4444;color:#fff;font-size:10px;font-weight:700;
        padding:2px 7px;border-radius:999px;letter-spacing:.03em}
      #dv-update-popup .dv-up-ver{margin:10px 0 6px;font-size:13px;color:#6b7280}
      #dv-update-popup .dv-up-ver b{color:#059669}
      #dv-update-popup .dv-up-notes{font-size:13px;color:#374151;line-height:1.5;margin-bottom:14px}
      #dv-update-popup .dv-up-actions{display:flex;gap:8px}
      #dv-update-popup .dv-up-download{flex:1;text-align:center;background:#10b981;color:#fff;
        text-decoration:none;font-size:13px;font-weight:600;padding:9px 0;border-radius:9px}
      #dv-update-popup .dv-up-download:hover{background:#059669}
      #dv-update-popup .dv-up-later{background:#f3f4f6;color:#4b5563;border:0;font-size:13px;
        padding:9px 14px;border-radius:9px;cursor:pointer}
      #dv-update-popup .dv-up-later:hover{background:#e5e7eb}
      #dv-update-popup .dv-up-hint{margin-top:10px;font-size:11px;color:#9ca3af;line-height:1.4}`;

    document.documentElement.appendChild(style);
    document.body.appendChild(wrap);

    const close = () => { wrap.remove(); style.remove(); };
    wrap.querySelector('.dv-up-close').addEventListener('click', () => { dismiss(info.latest); close(); });
    wrap.querySelector('.dv-up-later').addEventListener('click', () => { dismiss(info.latest); close(); });
    wrap.querySelector('.dv-up-download').addEventListener('click', () => { dismiss(info.latest); });
  }

  // background 에 최신 버전 확인 요청 → 새 버전이면 팝업
  function checkUpdateAndNotify() {
    try {
      chrome.runtime.sendMessage({ action: 'CHECK_UPDATE' }, (info) => {
        if (chrome.runtime.lastError || !info) return;
        if (info.updateAvailable && !alreadyDismissed(info.latest)) {
          showUpdatePopup({
            current: info.current,
            latest: info.latest,
            notes: info.notes,
            downloadUrl: info.downloadUrl,
          });
        }
      });
    } catch (e) { /* 서비스워커 미기동 등 */ }
  }

  // ---------- 3) 배치 결과 릴레이 (background → 페이지) ----------
  function relayJobResults() {
    try {
      chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.action === 'JOB_RESULT') {
          window.dispatchEvent(new CustomEvent('doctorvoice-job-result', {
            detail: { id: msg.id, ok: msg.ok, message: msg.message, uncertain: !!msg.uncertain },
          }));
        }
      });
    } catch (e) { /* noop */ }
  }

  // ---------- 3-2) 글 생성 결과 릴레이 (background → 페이지) ----------
  // 키워드 1건이 끝날 때마다 온다. id === '__done__' 이면 배치 전체 종료 신호.
  function relayGenResults() {
    try {
      chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.action === 'GEN_RESULT') {
          window.dispatchEvent(new CustomEvent('doctorvoice-gen-result', {
            detail: {
              id: msg.id, ok: !!msg.ok, keyword: msg.keyword || '',
              text: msg.text || '', chars: msg.chars || 0,
              error: msg.error || '', done: !!msg.done, fatal: !!msg.fatal,
            },
          }));
        }
      });
    } catch (e) { /* noop */ }
  }

  // ---------- 4) job payload 릴레이 (background → 페이지 → background) ----------
  // 배치는 메타데이터만 먼저 받고, 사진이 담긴 실제 payload 는 그 글을 처리하기
  // 직전에 한 건씩 받아온다. 100건 × 사진 10장을 한 메시지에 담으면 크롬의
  // 64MiB 메시지 한계를 넘어 전송 자체가 실패하기 때문이다.
  // 페이지가 IndexedDB 에서 사진을 꺼내 blocks 를 만드는 시간까지 감안해 넉넉히 잡는다.
  const PAYLOAD_TIMEOUT = 30000;

  function relayJobRequests() {
    try {
      chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
        if (!msg || msg.action !== 'REQUEST_JOB') return;
        // 응답이 어느 요청의 것인지 구분한다(배치가 연달아 돌 때 섞이지 않도록).
        const token = 'dvjob-' + Math.random().toString(36).slice(2) + '-' + Date.now();
        let settled = false;
        const finish = (job) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          window.removeEventListener('doctorvoice-job-payload', onPayload);
          sendResponse({ job: job || null });
        };
        const onPayload = (e) => {
          const d = (e && e.detail) || {};
          if (d.token !== token) return;
          finish(d.job);
        };
        // 페이지가 응답하지 않으면(다른 화면으로 이동 등) 배치 전체가 멈추지 않도록 끊는다.
        const timer = setTimeout(() => finish(null), PAYLOAD_TIMEOUT);
        window.addEventListener('doctorvoice-job-payload', onPayload);
        window.dispatchEvent(new CustomEvent('doctorvoice-job-request', {
          detail: { id: msg.id, token },
        }));
        return true; // 비동기 응답
      });
    } catch (e) { /* noop */ }
  }

  // ---------- 초기화 ----------
  function init() {
    exposeExtensionId();
    checkUpdateAndNotify();
    relayJobResults();
    relayGenResults();
    relayJobRequests();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
