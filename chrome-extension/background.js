// ============================================================
// 닥터보이스 프로 - 백그라운드 서비스워커 v15
// CDP(chrome.debugger) 기반 실제 입력 + 오케스트레이션 + 자동 업데이트
// ============================================================
const VERSION = '15.1.0';
const UPDATE_URL = 'https://doctor-voice-pro-ghwi.vercel.app/extension/version.json';
const WRITE_URL = 'https://blog.naver.com/GoBlogWrite.naver';

let currentJob = null;
let debuggerTabId = null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log('[닥터보이스:bg]', ...a);

// ============================================================
// 외부 메시지 (닥터보이스 웹사이트에서)
// ============================================================
chrome.runtime.onMessageExternal.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.action) {
        case 'PING': {
          // 캐시된 업데이트 정보를 함께 반환 (웹사이트 신호등이 1회 왕복으로 버전/업데이트 파악)
          const cached = (await chrome.storage.local.get('updateInfo')).updateInfo || {};
          sendResponse({
            success: true,
            version: VERSION,
            updateAvailable: !!cached.updateAvailable,
            latest: cached.latest || VERSION,
            downloadUrl: cached.downloadUrl || '',
            notes: cached.notes || '',
          });
          // 오래된 캐시면 백그라운드로 갱신 (응답은 지연시키지 않음)
          if (!cached.checkedAt || Date.now() - cached.checkedAt > 30 * 60 * 1000) {
            checkForUpdate().catch(() => {});
          }
          break;
        }
        case 'CHECK_UPDATE': {
          const info = await checkForUpdate();
          sendResponse({ success: true, current: VERSION, ...info });
          break;
        }
        case 'SUBMIT_JOB':
        case 'ONE_CLICK_PUBLISH': // 구버전 호환
          await startJob(normalizeJob(msg.job || msg.postData));
          sendResponse({ success: true });
          break;
        default:
          sendResponse({ success: false, error: 'unknown action' });
      }
    } catch (e) {
      log('외부 메시지 오류', e);
      sendResponse({ success: false, error: e.message });
    }
  })();
  return true;
});

// ============================================================
// 내부 메시지 (content script에서)
// ============================================================
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.action === 'EDITOR_READY') {
        if (!currentJob) {
          const stored = await chrome.storage.local.get('pendingJob');
          currentJob = stored.pendingJob || null;
        }
        if (currentJob && sender.tab) {
          sendResponse({ hasJob: true });
          runAutomation(sender.tab.id, currentJob).catch((e) => log('자동화 실패', e));
        } else {
          sendResponse({ hasJob: false });
        }
        return;
      }
      if (msg.action === 'GET_VERSION') {
        sendResponse({ version: VERSION });
        return;
      }
      if (msg.action === 'CHECK_UPDATE') {
        const info = await checkForUpdate();
        sendResponse({ current: VERSION, ...info });
        return;
      }
      sendResponse({ ok: false });
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }
  })();
  return true;
});

// ============================================================
// Job 정규화
// ============================================================
function normalizeJob(raw) {
  if (!raw) return null;
  return {
    id: raw.id || String(Date.now()),
    title: raw.title || raw.suggested_titles?.[0] || '',
    content: raw.content || raw.generated_content || '',
    images: raw.images || [], // base64 data URL 배열 (EXIF는 프론트에서 제거됨)
    tags: raw.tags || raw.keywords || raw.seo_keywords || [],
    options: {
      openType: raw.options?.openType || 'public',
      search: raw.options?.search !== false,
    },
    finalAction: raw.finalAction || 'draft', // 'draft' | 'publishNow' | 'schedule'
    schedule: raw.schedule || null, // { datetime: ISOString }
  };
}

async function startJob(job) {
  currentJob = job;
  await chrome.storage.local.set({ pendingJob: job });
  log('Job 시작:', job.title, '| 최종동작:', job.finalAction);

  // 기존 글쓰기 탭 재사용 or 새 탭
  const tabs = await chrome.tabs.query({});
  const existing = tabs.find((t) => t.url && t.url.includes('blog.naver.com') &&
    (t.url.includes('Write') || t.url.includes('editor') || t.url.includes('PostWriteForm')));
  if (existing) {
    await chrome.tabs.update(existing.id, { active: true });
    await chrome.tabs.reload(existing.id);
  } else {
    await chrome.tabs.create({ url: WRITE_URL, active: true });
  }
}

// ============================================================
// 자동화 시퀀스 (CDP)
// ============================================================
async function runAutomation(tabId, job) {
  log('=== 자동화 시작 ===', tabId);
  try {
    await progress(tabId, '팝업 정리 중...', 8);
    await sendToTab(tabId, { action: 'DISMISS_POPUP' });

    // 위치 확보 (재시도)
    let pos = null;
    for (let i = 0; i < 20; i++) {
      const r = await sendToTab(tabId, { action: 'GET_POSITIONS' });
      if (r && r.ok && r.title && r.body) { pos = r; break; }
      await sleep(400);
    }
    if (!pos) throw new Error('제목/본문 위치 확보 실패');

    await attachDebugger(tabId);
    await sleep(400);

    // 제목 입력
    await progress(tabId, '제목 입력 중...', 25);
    await clickAt(tabId, pos.title.x, pos.title.y);
    await sleep(250);
    await ctrlA(tabId);
    await sleep(80);
    await insertText(tabId, job.title);
    await sleep(400);

    // 본문 입력 (문단별)
    await progress(tabId, '본문 입력 중...', 45);
    await clickAt(tabId, pos.body.x, pos.body.y);
    await sleep(250);
    await ctrlA(tabId);
    await sleep(80);
    await typeBody(tabId, job.content);
    await sleep(400);

    // CDP 해제 (이미지 드롭/버튼 클릭은 일반 DOM으로)
    await detachDebugger(tabId);
    await sleep(300);

    // 이미지 삽입
    if (job.images && job.images.length) {
      await progress(tabId, `이미지 삽입 중... (${job.images.length}개)`, 60);
      await sendToTab(tabId, { action: 'INSERT_IMAGES', images: job.images });
    }

    // 최종 동작 (임시저장 / 발행 / 예약)
    await progress(tabId, '마무리 중...', 88);
    const fin = await sendToTab(tabId, { action: 'FINALIZE', job });
    log('최종 동작 결과:', fin);

    // 완료
    await chrome.storage.local.remove('pendingJob');
    currentJob = null;
    await chrome.storage.local.set({
      lastResult: { ok: !!(fin && fin.ok), action: job.finalAction, title: job.title, at: Date.now() },
    });
    log('=== 자동화 완료 ===');
  } catch (e) {
    log('자동화 오류:', e);
    try { await detachDebugger(tabId); } catch (_) {}
    await sendToTab(tabId, { action: 'PROGRESS', text: '⚠️ 오류: ' + e.message, pct: 100 });
    await chrome.storage.local.set({ lastResult: { ok: false, error: e.message, at: Date.now() } });
  }
}

// 본문: 줄바꿈을 문단으로 처리
async function typeBody(tabId, content) {
  const lines = (content || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].length) await insertText(tabId, lines[i]);
    if (i < lines.length - 1) { await pressEnter(tabId); await sleep(30); }
  }
}

// ============================================================
// CDP 헬퍼
// ============================================================
function cdp(tabId, method, params) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand({ tabId }, method, params || {}, (res) => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(res);
    });
  });
}

async function attachDebugger(tabId) {
  if (debuggerTabId) { try { await detachDebugger(debuggerTabId); } catch (_) {} }
  await new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, '1.3', () => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else { debuggerTabId = tabId; resolve(); }
    });
  });
}
async function detachDebugger(tabId) {
  await new Promise((resolve) => {
    chrome.debugger.detach({ tabId }, () => { debuggerTabId = null; resolve(); });
  });
}
async function clickAt(tabId, x, y) {
  await cdp(tabId, 'Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await sleep(40);
  await cdp(tabId, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}
async function insertText(tabId, text) {
  if (!text) return;
  await cdp(tabId, 'Input.insertText', { text });
}
async function pressEnter(tabId) {
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
}
async function ctrlA(tabId) {
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, modifiers: 2 });
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 });
  await sleep(40);
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 });
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, modifiers: 0 });
}

// tab 메시지 (editor 프레임 응답 사용)
function sendToTab(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (res) => {
      if (chrome.runtime.lastError) resolve(null); else resolve(res);
    });
  });
}
async function progress(tabId, text, pct) {
  await sendToTab(tabId, { action: 'PROGRESS', text, pct });
}

// ============================================================
// 자동 업데이트 (팝업)
//  - 개발자모드(압축해제) 설치는 무음 자동설치가 불가(크롬 정책).
//  - 대신 주기적으로 version.json 확인 → 새 버전이면 웹사이트에 팝업 표시 신호.
// ============================================================
async function checkForUpdate() {
  try {
    const res = await fetch(UPDATE_URL + '?t=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) return { updateAvailable: false };
    const data = await res.json();
    const latest = data.version;
    const updateAvailable = compareVersion(latest, VERSION) > 0;
    await chrome.storage.local.set({
      updateInfo: { current: VERSION, latest, updateAvailable, downloadUrl: data.downloadUrl, notes: data.notes || '', checkedAt: Date.now() },
    });
    if (updateAvailable) {
      chrome.action.setBadgeText({ text: 'NEW' });
      chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
    } else {
      chrome.action.setBadgeText({ text: '' });
    }
    return { updateAvailable, latest, downloadUrl: data.downloadUrl, notes: data.notes || '' };
  } catch (e) {
    log('업데이트 확인 실패', e.message);
    return { updateAvailable: false, error: e.message };
  }
}
function compareVersion(a, b) {
  const pa = String(a || '0').split('.').map(Number);
  const pb = String(b || '0').split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) > (pb[i] || 0)) return 1;
    if ((pa[i] || 0) < (pb[i] || 0)) return -1;
  }
  return 0;
}

// ============================================================
// 라이프사이클
// ============================================================
chrome.runtime.onInstalled.addListener(() => { checkForUpdate(); });
chrome.runtime.onStartup.addListener(() => { checkForUpdate(); });
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.create('updateCheck', { periodInMinutes: 180 }); // 3시간마다
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'updateCheck') checkForUpdate();
});
chrome.debugger.onDetach.addListener(() => { debuggerTabId = null; });

log('백그라운드 v15 시작');
