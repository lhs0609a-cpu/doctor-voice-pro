// ============================================================
// 닥터보이스 프로 - 백그라운드 서비스워커 v15
// CDP(chrome.debugger) 기반 실제 입력 + 오케스트레이션 + 자동 업데이트
// ============================================================
const VERSION = '15.4.0';
const UPDATE_URL = 'https://doctor-voice-pro-ghwi.vercel.app/extension/version.json';
const WRITE_URL = 'https://blog.naver.com/GoBlogWrite.naver';

let currentJob = null;
let debuggerTabId = null;
let jobDoneResolver = null;   // 현재 job 자동화 완료 시 resolve
let batchRunning = false;

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
        case 'SUBMIT_BATCH': {
          // 대량 예약: 여러 job 을 순차적으로 네이버 예약발행 등록
          const jobs = (msg.jobs || []).map(normalizeJob).filter(Boolean);
          sendResponse({ success: true, accepted: jobs.length });
          startBatch(jobs, sender); // 백그라운드로 진행(응답 대기 안 함)
          break;
        }
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
  // blocks(글-이미지 인터리브)가 있으면 content/images 를 파생
  let content = raw.content || raw.generated_content || '';
  let images = raw.images || [];
  let blocks = raw.blocks || null;
  if (blocks && blocks.length) {
    content = blocks.filter((b) => b.type === 'text' && b.content).map((b) => b.content).join('\n\n');
    images = blocks.filter((b) => b.type === 'image' && b.image).map((b) => b.image);
  }
  return {
    id: raw.id || String(Date.now()),
    title: raw.title || raw.suggested_titles?.[0] || '',
    content,
    images, // base64 data URL 배열 (EXIF는 프론트에서 제거됨)
    blocks, // [{type:'text',content} | {type:'image',image}] — 인터리브 삽입용(향후)
    emphasize: Array.isArray(raw.emphasize) ? raw.emphasize : [], // 자동 굵게할 키워드
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
// 대량 배치: 여러 job 을 순차적으로 예약발행 등록
// ============================================================
async function startBatch(jobs, sender) {
  if (batchRunning) { log('배치가 이미 진행 중'); return; }
  batchRunning = true;
  log(`=== 배치 시작: ${jobs.length}건 ===`);
  const webTabId = sender && sender.tab ? sender.tab.id : null;

  for (let i = 0; i < jobs.length; i++) {
    const job = jobs[i];
    log(`배치 ${i + 1}/${jobs.length}: ${job.title}`);
    let result;
    try {
      result = await runOne(job);
    } catch (e) {
      result = { ok: false, error: e.message };
    }
    // 결과를 웹사이트로 전달 → 백엔드에 보고
    reportJobResult(webTabId, job.id, !!(result && result.ok), (result && (result.error || result.action)) || '');
    await sleep(1500); // 연속 등록 사이 여유(봇 감지 완화)
  }

  batchRunning = false;
  log('=== 배치 완료 ===');
}

// 단일 job 자동화를 실행하고 완료될 때 resolve
function runOne(job) {
  return new Promise((resolve) => {
    // 안전장치: 3분 내 완료 신호 없으면 실패 처리하고 다음으로
    const guard = setTimeout(() => {
      if (jobDoneResolver) { const r = jobDoneResolver; jobDoneResolver = null; r({ ok: false, error: 'timeout' }); }
    }, 180000);
    jobDoneResolver = (res) => { clearTimeout(guard); resolve(res); };
    startJob(job).catch((e) => {
      if (jobDoneResolver) { const r = jobDoneResolver; jobDoneResolver = null; r({ ok: false, error: e.message }); }
    });
  });
}

function finishJob(result) {
  if (jobDoneResolver) {
    const r = jobDoneResolver;
    jobDoneResolver = null;
    r(result);
  }
}

// 결과를 닥터보이스 웹 탭으로 전달(content-website 가 CustomEvent 로 페이지에 알림)
function reportJobResult(webTabId, id, ok, message) {
  const payload = { action: 'JOB_RESULT', id, ok, message };
  try {
    if (webTabId) {
      chrome.tabs.sendMessage(webTabId, payload, () => void chrome.runtime.lastError);
    } else {
      // sender 탭을 모르면 닥터보이스 탭을 찾아 전달
      chrome.tabs.query({}, (tabs) => {
        const t = tabs.find((x) => x.url && (x.url.includes('doctor-voice') || x.url.includes('vercel.app') || x.url.includes('localhost')));
        if (t) chrome.tabs.sendMessage(t.id, payload, () => void chrome.runtime.lastError);
      });
    }
  } catch (_) {}
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

    // 인터리브(글-이미지-글-이미지) 블록이 있으면 순서대로, 없으면 기존 방식
    const hasImageBlocks = Array.isArray(job.blocks) && job.blocks.some((b) => b.type === 'image' && b.image);
    if (hasImageBlocks) {
      await typeBlocksInterleaved(tabId, job);
      await sleep(300);
      try { await detachDebugger(tabId); } catch (_) {}
      await sleep(200);
    } else {
      await typeBody(tabId, job.content, job.emphasize);
      await sleep(400);
      await detachDebugger(tabId);
      await sleep(300);
      if (job.images && job.images.length) {
        await progress(tabId, `이미지 삽입 중... (${job.images.length}개)`, 60);
        await sendToTab(tabId, { action: 'INSERT_IMAGES', images: job.images });
      }
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
    finishJob({ ok: !!(fin && fin.ok), action: job.finalAction });
  } catch (e) {
    log('자동화 오류:', e);
    try { await detachDebugger(tabId); } catch (_) {}
    await sendToTab(tabId, { action: 'PROGRESS', text: '⚠️ 오류: ' + e.message, pct: 100 });
    await chrome.storage.local.set({ lastResult: { ok: false, error: e.message, at: Date.now() } });
    finishJob({ ok: false, error: e.message });
  }
}

// 본문: 줄바꿈을 문단으로 처리. emphasize(키워드) 는 Ctrl+B 로 자동 굵게.
function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

async function typeBody(tabId, content, emphasize) {
  const words = (Array.isArray(emphasize) ? emphasize : [])
    .filter((w) => typeof w === 'string' && w.trim().length >= 2)
    .map((w) => w.trim());
  // 긴 단어부터 매칭(부분매칭 방지)
  const uniq = [...new Set(words)].sort((a, b) => b.length - a.length);
  const re = uniq.length ? new RegExp('(' + uniq.map(escapeRe).join('|') + ')') : null;
  const wordSet = new Set(uniq);

  const lines = (content || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.length) {
      if (re) {
        for (const part of line.split(re)) {
          if (!part) continue;
          if (wordSet.has(part)) {
            await ctrlB(tabId); await insertText(tabId, part); await ctrlB(tabId);
          } else {
            await insertText(tabId, part);
          }
        }
      } else {
        await insertText(tabId, line);
      }
    }
    if (i < lines.length - 1) { await pressEnter(tabId); await sleep(30); }
  }
}

// 블록 순서대로 입력: 글 → 이미지 → 글 → 이미지 (문단 사이 삽입)
// 텍스트는 CDP 타이핑, 이미지는 CDP 분리 후 커서 위치에 드롭 → 재부착.
async function typeBlocksInterleaved(tabId, job) {
  const blocks = job.blocks || [];
  let first = true;
  let cleared = false;
  for (const b of blocks) {
    if (b.type === 'text' && b.content) {
      if (!first) { await pressEnter(tabId); await sleep(40); }
      await typeBody(tabId, b.content, job.emphasize);
      first = false; cleared = true;
    } else if (b.type === 'image' && b.image) {
      if (!cleared) { await insertText(tabId, ''); cleared = true; } // ctrlA 선택분 제거
      if (!first) { await pressEnter(tabId); await sleep(40); }
      await progress(tabId, '이미지 삽입 중...', 60);
      // 이미지 드롭은 일반 DOM → CDP 분리
      try { await detachDebugger(tabId); } catch (_) {}
      await sleep(150);
      await sendToTab(tabId, { action: 'INSERT_IMAGES', images: [b.image], atCaret: true });
      await sleep(1900);
      // 다음 문단 타이핑을 위해 CDP 재부착 + 본문 포커스 복귀
      await attachDebugger(tabId);
      await sleep(200);
      first = false;
    }
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
// Ctrl+B 토글 (굵게 켜기/끄기)
async function ctrlB(tabId) {
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'Control', code: 'ControlLeft', windowsVirtualKeyCode: 17, modifiers: 2 });
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'b', code: 'KeyB', windowsVirtualKeyCode: 66, modifiers: 2 });
  await sleep(30);
  await cdp(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'b', code: 'KeyB', windowsVirtualKeyCode: 66, modifiers: 2 });
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
