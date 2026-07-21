// ============================================================
// 닥터보이스 프로 - 백그라운드 서비스워커 v15
// CDP(chrome.debugger) 기반 실제 입력 + 오케스트레이션 + 자동 업데이트
// ============================================================
const VERSION = '16.0.3';
const UPDATE_URL = 'https://doctor-voice-pro-ghwi.vercel.app/extension/version.json';
const WRITE_URL = 'https://blog.naver.com/GoBlogWrite.naver';

let currentJob = null;
let debuggerTabId = null;
let jobDoneResolver = null;   // 현재 job 자동화 완료 시 resolve
let batchRunning = false;
let genRunning = false;       // Gemini 글 생성 배치 진행 중
let genCancel = false;        // 사용자가 중단을 눌렀는가
let geminiTabId = null;       // 생성에 쓰는 Gemini 탭

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log('[닥터보이스:bg]', ...a);

// ── MV3 서비스워커 keepalive ────────────────────────────────
// 긴 배치(글 생성·대량 발행)는 수십 분~수 시간 걸린다. MV3 워커는 30초 유휴면
// 강제 종료되는데, 그러면 배치가 통째로 멈춘다(Gemini 탭이 빈 채 방치되고 결과도
// 에러도 오지 않아 화면이 영영 '생성 중'). alarms 최소 주기(30초)는 유휴 한계와
// 정확히 겹쳐 경계에서 진다 → 25초마다 무해한 확장 API 를 호출해 타이머를 리셋한다.
// 배치가 겹칠 수 있어 참조 수로 켜고 끈다.
let keepAliveTimer = null;
let keepAliveRefs = 0;
function startKeepAlive() {
  keepAliveRefs++;
  if (keepAliveTimer) return;
  keepAliveTimer = setInterval(() => {
    chrome.runtime.getPlatformInfo(() => void chrome.runtime.lastError);
  }, 25000);
  log('keepalive 시작');
}
function stopKeepAlive() {
  keepAliveRefs = Math.max(0, keepAliveRefs - 1);
  if (keepAliveRefs === 0 && keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
    log('keepalive 종료');
  }
}

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
          // 대량 예약: 여러 job 을 순차적으로 네이버 예약발행 등록.
          // 사진이 빠진 메타데이터만 올 수 있다(64MiB 한계 회피) — 정규화는 실제 payload 를
          // 손에 쥔 뒤 startBatch 안에서 한다.
          const jobs = (msg.jobs || []).filter(Boolean);
          // 이미 돌고 있으면 조용히 무시하지 않고 알려준다 — 예전엔 페이지가 성공 토스트를
          // 띄운 채 아무 일도 안 일어나 "발행이 안 된다"로 보였다.
          if (batchRunning) {
            sendResponse({ success: false, error: '이미 발행이 진행 중입니다. 끝난 뒤 다시 시도하세요.' });
            break;
          }
          // 시작 전에 계정부터 확인한다 — 다른 블로그에 100건이 통째로 올라가는 걸 막는다.
          if (msg.expectedBlogId) {
            const who = await syncBlogId();
            if (who.success && who.blogId !== msg.expectedBlogId) {
              sendResponse({
                success: false,
                error: `로그인된 블로그가 다릅니다(예상 '${msg.expectedBlogId}', 현재 '${who.blogId}'). 발행을 중단했습니다.`,
              });
              break;
            }
          }
          sendResponse({ success: true, accepted: jobs.length });
          startBatch(jobs, sender); // 백그라운드로 진행(응답 대기 안 함)
          break;
        }
        case 'SUBMIT_GEN_BATCH': {
          // 키워드 대량 생성: Gemini 탭을 열어 프롬프트를 넣고 글을 수확한다.
          const items = (msg.items || []).filter((x) => x && x.prompt);
          if (genRunning) {
            sendResponse({ success: false, error: '이미 글 생성이 진행 중입니다. 끝난 뒤 다시 시도하세요.' });
            break;
          }
          if (!items.length) {
            sendResponse({ success: false, error: '생성할 키워드가 없습니다.' });
            break;
          }
          sendResponse({ success: true, accepted: items.length });
          startGenBatch(items, sender, msg.options || {});
          break;
        }
        case 'CANCEL_GEN_BATCH': {
          genCancel = true;
          sendResponse({ success: true, running: genRunning });
          break;
        }
        case 'SYNC_BLOG': {
          // 앱이 "지금 어느 블로그인지" 물어본다 → 예약 기준/준비함을 블로그별로 나눈다.
          const r = await syncBlogId();
          sendResponse(r);
          break;
        }
        case 'SYNC_CATEGORIES': {
          // 확장이 스스로 네이버 글쓰기를 열어 카테고리를 읽고 원래대로 정리한다.
          const r = await syncCategories();
          sendResponse(r);
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
      // 카테고리 번호("24") 또는 이름. 미지정이면 네이버 기본 카테고리로 발행된다.
      category: raw.options?.category || null,
    },
    finalAction: raw.finalAction || 'draft', // 'draft' | 'publishNow' | 'schedule'
    schedule: raw.schedule || null, // { datetime: ISOString }
    // 앱이 예약을 계산할 때 기준으로 삼은 블로그. 발행 직전 실제 로그인 계정과 대조한다.
    expectedBlogId: raw.expectedBlogId || null,
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
// 카테고리 동기화: 확장이 스스로 네이버에 다녀온다
// (사용자가 글쓰기 화면을 미리 열어둘 필요 없이, 앱에서 바로 목록을 받게 하기 위함)
// ============================================================
const NAVER_WRITE_MATCH = (u) =>
  !!u && u.includes('blog.naver.com') &&
  (u.includes('Write') || u.includes('editor') || u.includes('PostWriteForm'));

/** 에디터 프레임이 준비될 때까지 대기.
 *  PING 은 editorOnly 가 아니라 모든 프레임이 답한다 — 최상위 프레임이 먼저 답하면
 *  editor:false 를 받아 헛돈다. editorOnly 이면서 부작용 없는 GET_POSITIONS 로 확인한다.
 */
async function waitForEditorReady(tabId, timeout = 25000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    // 로그인 페이지로 튕겼는지 먼저 확인 — 여기서 계속 기다려봐야 의미 없다.
    let tab;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch (e) {
      return { ok: false, error: '탭이 닫혔습니다' };
    }
    if (tab.url && tab.url.includes('nid.naver.com')) return { ok: false, needLogin: true };

    const r = await sendToTab(tabId, { action: 'GET_POSITIONS' });
    if (r && r.ok) return { ok: true };   // 에디터 프레임만 응답 = 본문까지 로드됨
    await sleep(500);
  }
  return { ok: false, error: '에디터가 준비되지 않았습니다' };
}

/** 현재 로그인된 네이버 블로그 ID. 못 읽으면 ''. */
async function readBlogId(tabId) {
  const r = await sendToTab(tabId, { action: 'READ_BLOG_ID' });
  return (r && r.blogId) || '';
}

/**
 * 지금 로그인된 블로그가 앱이 기대한 블로그와 같은지 확인한다.
 * 발행 도중 다른 계정으로 로그인하면 예전엔 그대로 진행돼 엉뚱한 블로그에 글이 올라갔다.
 * @returns {{ok:boolean, blogId:string, error?:string}}
 */
async function assertBlog(tabId, expected) {
  const blogId = await readBlogId(tabId);
  if (!expected || !blogId) return { ok: true, blogId }; // 확인할 수 없으면 막지 않는다
  if (blogId !== expected) {
    return {
      ok: false, blogId,
      error: `로그인된 블로그가 다릅니다(예상 '${expected}', 현재 '${blogId}'). 엉뚱한 블로그에 발행되지 않도록 중단했습니다.`,
    };
  }
  return { ok: true, blogId };
}

/**
 * 네이버 글쓰기 탭을 (없으면) 열어 현재 블로그 ID 를 읽는다.
 * 앱이 예약 기준·준비함을 블로그별로 나누기 위해 쓴다.
 */
async function syncBlogId() {
  const tabs = await chrome.tabs.query({});
  const existing = tabs.find((t) => NAVER_WRITE_MATCH(t.url));
  let tabId;
  const opened = !existing;
  let keepTab = false;
  if (existing) tabId = existing.id;
  else tabId = (await chrome.tabs.create({ url: WRITE_URL, active: false })).id;

  try {
    const ready = await waitForEditorReady(tabId);
    if (!ready.ok) {
      if (ready.needLogin) {
        keepTab = true;
        await chrome.tabs.update(tabId, { active: true });
        return { success: false, needLogin: true, error: '네이버 로그인이 필요합니다. 열린 탭에서 로그인해주세요.' };
      }
      return { success: false, error: ready.error };
    }
    const blogId = await readBlogId(tabId);
    if (!blogId) return { success: false, error: '블로그 ID를 읽지 못했습니다' };
    log('블로그 확인:', blogId);
    return { success: true, blogId };
  } finally {
    if (opened && !keepTab) { try { await chrome.tabs.remove(tabId); } catch (e) {} }
  }
}

/**
 * 네이버 글쓰기 탭을 (없으면) 열어 카테고리 목록을 읽고, 우리가 연 탭이면 닫는다.
 * @returns {{success:boolean, categories?:Array, error?:string, needLogin?:boolean}}
 */
async function syncCategories() {
  const tabs = await chrome.tabs.query({});
  const existing = tabs.find((t) => NAVER_WRITE_MATCH(t.url));

  let tabId;
  const opened = !existing;
  let keepTab = false;   // 로그인 등 사용자 조작이 필요하면 탭을 남긴다
  if (existing) {
    tabId = existing.id;
  } else {
    // 사용자 작업을 방해하지 않도록 비활성 탭으로 연다.
    const tab = await chrome.tabs.create({ url: WRITE_URL, active: false });
    tabId = tab.id;
  }

  try {
    const ready = await waitForEditorReady(tabId);
    if (!ready.ok) {
      if (ready.needLogin) {
        // 로그인 필요 → 탭을 사용자에게 보여주고 직접 로그인하게 한다(세션 재사용 설계).
        // 이 탭을 닫으면 로그인할 방법이 사라지므로 반드시 남겨야 한다.
        keepTab = true;
        await chrome.tabs.update(tabId, { active: true });
        return { success: false, needLogin: true, error: '네이버 로그인이 필요합니다. 열린 탭에서 로그인한 뒤 다시 시도해주세요.' };
      }
      return { success: false, error: ready.error };
    }

    // 새 글쓰기를 열면 '작성 중인 글이 있습니다' 팝업이 떠 레이어 조작을 막는다(발행 흐름과 동일).
    await sendToTab(tabId, { action: 'DISMISS_POPUP' });
    await sleep(300);

    const res = await sendToTab(tabId, { action: 'READ_CATEGORIES' });
    if (!res || !res.ok || !res.categories?.length) {
      return { success: false, error: (res && res.error) || '카테고리를 읽지 못했습니다' };
    }
    log(`카테고리 ${res.categories.length}개 수집`);
    return { success: true, categories: res.categories };
  } finally {
    // 우리가 연 탭만 닫는다. 사용자가 쓰던 탭이나 로그인해야 할 탭은 건드리지 않는다.
    if (opened && !keepTab) { try { await chrome.tabs.remove(tabId); } catch (e) {} }
  }
}

// ============================================================
// 대량 배치: 여러 job 을 순차적으로 예약발행 등록
// ============================================================
/** 메타데이터에 본문/사진이 이미 들어있는가(구버전 페이지는 통째로 보낸다). */
function hasPayload(m) {
  return !!(m && ((m.blocks && m.blocks.length) || (m.images && m.images.length) || m.content));
}

/**
 * 사진이 담긴 실제 job 을 페이지에서 한 건만 받아온다.
 * 배치 전체(58건 × 사진 10장 ≈ 수백 MB)를 한 메시지에 담으면 크롬의 64MiB 한계에
 * 걸려 전송 자체가 실패하므로, 처리 직전에 그 글만 끌어온다(≈5MB).
 */
async function requestJobPayload(webTabId, id) {
  if (!webTabId) return null;
  // 페이지가 IndexedDB 에서 사진을 꺼내오므로 한 번쯤 늦을 수 있다 → 한 번 더 시도한다.
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const res = await sendToTab(webTabId, { action: 'REQUEST_JOB', id });
      if (res && res.job) return res.job;
    } catch (e) {
      log(`payload 요청 실패(${attempt}/2)`, e && e.message);
    }
    if (attempt === 1) await sleep(1000);
  }
  return null;
}

async function startBatch(metas, sender) {
  if (batchRunning) { log('배치가 이미 진행 중'); return; }
  batchRunning = true;
  startKeepAlive(); // 배치 내내 워커가 죽지 않도록
  const webTabId = sender && sender.tab ? sender.tab.id : null;
  let missStreak = 0; // payload 를 연속으로 못 받은 횟수(= 닥터보이스 탭이 사라졌다는 신호)

  try {
    log(`=== 배치 시작: ${metas.length}건 ===`);
    for (let i = 0; i < metas.length; i++) {
      const meta = metas[i];
      log(`배치 ${i + 1}/${metas.length}: ${meta.title}`);
      let result;
      try {
        // 구버전 페이지는 payload 를 통째로 보낸다 — 그대로 쓰고, 아니면 지금 받아온다.
        const raw = hasPayload(meta) ? meta : await requestJobPayload(webTabId, meta.id);
        const job = normalizeJob(raw);
        if (!job) throw new Error('글 데이터를 받지 못했습니다(닥터보이스 탭이 닫혔을 수 있습니다)');
        missStreak = 0;
        result = await runOne(job);
      } catch (e) {
        result = { ok: false, error: e.message };
        missStreak++;
      }
      // 결과를 웹사이트로 전달 → 준비함에서 성공한 건만 제거 + 백엔드에 보고
      reportJobResult(
        webTabId, meta.id, !!(result && result.ok),
        (result && (result.error || result.action)) || '',
        !!(result && result.uncertain)
      );

      // 탭이 닫혔다면 남은 수십 건을 헛돌릴 필요가 없다 — 남은 건 실패로 알리고 끝낸다.
      // (준비함에 그대로 남으므로 탭을 다시 열어 이어서 발행할 수 있다)
      if (missStreak >= 3 && i + 1 < metas.length) {
        log(`payload 를 ${missStreak}건 연속 못 받아 배치를 중단합니다`);
        for (let k = i + 1; k < metas.length; k++) {
          reportJobResult(webTabId, metas[k].id, false, '닥터보이스 탭이 닫혀 중단됨');
        }
        break;
      }
      await sleep(1500); // 연속 등록 사이 여유(봇 감지 완화)
    }
  } catch (e) {
    log('배치 오류', e);
  } finally {
    // 중간에 무슨 일이 있어도 반드시 푼다 — 안 그러면 다음 발행이 영영 막힌다.
    batchRunning = false;
    stopKeepAlive();
    log('=== 배치 완료 ===');
  }
}

// 이 건이 끝나기까지 최대 얼마나 기다릴지. 사진이 많을수록 오래 걸린다.
// 고정 180초였을 때 문제:
//  - 사진 30장이면 삽입만 120초가 넘어 정상 작업이 timeout 으로 찍혔다
//  - finalize 안의 캡차 대기가 정확히 180초라, 캡차가 뜨면 반드시 가드가 먼저 터졌다
// 가드가 터져도 runAutomation 은 계속 돌아 실제로는 발행이 끝나므로, 프론트가 실패로 알고
// 재시도하면 같은 글이 두 번 예약된다 → 가드는 '진짜 멈춤'에서만 터지도록 넉넉히 잡는다.
function jobGuardMs(job) {
  const imgs = (job.blocks || []).filter((b) => b.type === 'image' && b.image).length
    || (job.images || []).length;
  const base = 180000;          // 페이지 로드 + 타이핑 + finalize
  const captcha = 200000;       // 캡차 대기(180초)보다 반드시 길게
  return base + captcha + imgs * 30000; // 이미지 1장당 30초(재시도 3회 여유 포함)
}

// 단일 job 자동화를 실행하고 완료될 때 resolve
function runOne(job) {
  return new Promise((resolve) => {
    // 안전장치: 이 시간 내 완료 신호가 없으면 멈춘 것으로 보고 다음으로 넘어간다.
    // 이 경로로 끝난 건은 '발행됐을 수도 있음'이라 프론트가 자동 재시도하면 안 된다.
    const guard = setTimeout(() => {
      if (jobDoneResolver) {
        const r = jobDoneResolver; jobDoneResolver = null;
        r({ ok: false, error: 'timeout', uncertain: true });
      }
    }, jobGuardMs(job));
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
// uncertain = 가드 시간 초과로 끝난 건. 실제로는 발행됐을 수 있으므로 프론트가
// 그냥 재시도하면 중복 예약이 된다 → 별도로 표시해 사용자가 네이버에서 확인하게 한다.
function reportJobResult(webTabId, id, ok, message, uncertain) {
  const payload = { action: 'JOB_RESULT', id, ok, message, uncertain: !!uncertain };
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
// Gemini 글 생성 배치
//  키워드 1건 = 새 채팅 1개. 같은 대화에서 계속 쓰면 앞 글의 문체·구조를 따라가
//  글이 갈수록 비슷해지고 짧아지기 때문에, 매번 문맥을 비우고 프롬프트 전문을 다시 넣는다.
//  (건당 5초쯤 손해지만 100건 품질이 균일해지는 편이 훨씬 남는다)
// ============================================================
const GEMINI_URL = 'https://gemini.google.com/app';

const GEN_DEFAULTS = {
  newChatEvery: 1,     // N건마다 새 채팅 (1 = 매번)
  reloadEvery: 20,     // N건마다 탭 통째로 재로드 (SPA 메모리 누수/좀비 상태 방지)
  minChars: 800,       // 이보다 짧으면 실패로 보고 재시도
  retries: 1,          // 품질 미달 시 재시도 횟수
  tempChat: true,      // 임시 채팅(사이드바에 기록 안 남김)
  gapMs: 1500,         // 건 사이 여유
};

/** 생성용 Gemini 탭을 확보한다. 이미 있으면 재사용, 없으면 새로 연다. */
async function ensureGeminiTab() {
  if (geminiTabId) {
    try {
      const t = await chrome.tabs.get(geminiTabId);
      if (t && t.url && t.url.includes('gemini.google.com')) return geminiTabId;
    } catch (_) { /* 닫힘 */ }
    geminiTabId = null;
  }
  // 사용자가 이미 열어둔 Gemini 탭이 있으면 그걸 쓴다
  const found = await chrome.tabs.query({ url: 'https://gemini.google.com/*' });
  if (found && found.length) {
    geminiTabId = found[0].id;
    return geminiTabId;
  }
  const tab = await chrome.tabs.create({ url: GEMINI_URL, active: false });
  geminiTabId = tab.id;
  await waitForGeminiReady(geminiTabId, 45000, true);
  return geminiTabId;
}

/** content script 가 응답할 때까지(=앱이 뜰 때까지) 기다린다. */
async function waitForGeminiReady(tabId, timeout, tempChat) {
  const started = Date.now();
  let sawAny = false;   // content script 가 한 번이라도 응답했는가
  let reloaded = false; // 스크립트 주입용 새로고침을 이미 했는가
  while (Date.now() - started < timeout) {
    const r = await sendToTab(tabId, { action: 'GEM_PING' });
    if (r) sawAny = true;
    if (r && r.ok && r.ready) {
      if (!r.loggedIn) throw new Error('Gemini 에 로그인되어 있지 않습니다. 그 탭에서 구글 로그인 후 다시 시도하세요.');
      if (tempChat) await sendToTab(tabId, { action: 'GEM_WAIT_READY', tempChat: true, timeout: 5000 });
      return true;
    }
    // 응답이 전혀 없다 = content script 미주입. 확장 설치/갱신 전부터 열려 있던
    // 탭을 재사용할 때 흔하다(다른 컴퓨터에서 '준비 안 됨'의 주된 원인).
    // 탭을 한 번 새로고침하면 스크립트가 주입되므로 자동으로 되살린다.
    if (!sawAny && !reloaded && Date.now() - started > 4000) {
      reloaded = true;
      log('Gemini 탭에 스크립트가 없어 새로고침으로 주입 시도');
      try { await chrome.tabs.reload(tabId); } catch (_) {}
      await sleep(3000);
    }
    await sleep(700);
  }
  throw new Error('Gemini 페이지가 준비되지 않았습니다. 그 탭에서 Gemini 에 로그인돼 있는지 확인하고, 탭을 새로고침한 뒤 다시 시도하세요.');
}

async function reloadGeminiTab(tabId, tempChat) {
  await chrome.tabs.reload(tabId);
  await sleep(2000);
  await waitForGeminiReady(tabId, 45000, tempChat);
}

/**
 * 프롬프트 1건을 보내고 글을 수확한다.
 * 입력은 CDP(Input.insertText) — Quill 은 DOM 직접 대입을 무시한다.
 * 전송은 Enter — 입력창에 enterkeyhint="send" 가 걸려 있어 버튼을 찾을 필요가 없고,
 * 버튼 위치가 바뀌어도 안 깨진다.
 */
async function genOne(tabId, prompt, timeoutMs) {
  const pos = await sendToTab(tabId, { action: 'GEM_INPUT_POS' });
  if (!pos || !pos.ok || !pos.pos) throw new Error((pos && pos.error) || '입력창을 찾지 못했습니다');

  await attachDebugger(tabId);
  try {
    await clickAt(tabId, pos.pos.x, pos.pos.y);
    await sleep(200);
    await insertText(tabId, prompt);
    await sleep(400); // Quill 이 Delta 를 반영할 여유
    await pressEnter(tabId);
  } finally {
    // 수확은 DOM 감시라 디버거가 필요 없다. 상단 '디버깅 중' 배너를 오래 띄우지 않는다.
    try { await detachDebugger(tabId); } catch (_) {}
  }

  // 폴링 수확 — 긴 단일 await(최대 5분) 대신 1.5초마다 짧게 상태를 확인한다.
  //  · MV3 워커는 긴 유휴 await 도중 종료될 수 있는데, 잦은 메시지 왕복이 워커를
  //    확실히 살려둔다(setInterval keepalive 만으로는 얼어붙을 수 있다).
  //  · 프롬프트 전송이 실패하면(입력창에 안 들어감) 응답이 시작되지 않으므로,
  //    60초 내 '시작'이 없으면 무한 대기 대신 실패로 끊어 화면에 사유를 보여준다.
  const expectIndex = pos.count || 0;
  const started = Date.now();
  let sawStart = false;
  let lastChars = -1;
  while (Date.now() - started < timeoutMs) {
    await sleep(1500);
    const st = await sendToTab(tabId, { action: 'GEM_STATUS', expectIndex });
    if (!st || !st.ok) continue; // 일시적 무응답은 다음 폴에서 재시도
    if (st.started) sawStart = true;
    if (!sawStart && Date.now() - started > 60000) {
      return { ok: false, text: '', chars: 0, error: '응답이 시작되지 않았습니다(프롬프트 전송 실패 가능성)' };
    }
    const cur = st.chars || 0;
    if (cur !== lastChars) {
      lastChars = cur;
      await sendToTab(tabId, {
        action: 'GEM_PROGRESS',
        text: `생성 중… ${cur.toLocaleString()}자`,
        pct: Math.min(90, 20 + cur / 40),
      });
    }
    if (st.complete && st.text) return { ok: true, text: st.text, chars: st.chars };
  }
  // 타임아웃 — 그때까지 나온 글이라도 넘겨 background 가 길이로 판단하게 한다.
  const fin = await sendToTab(tabId, { action: 'GEM_STATUS', expectIndex });
  const text = fin && fin.ok ? (fin.text || '') : '';
  return { ok: false, text, chars: text.length, error: '응답 완료 신호를 받지 못했습니다' };
}

async function startGenBatch(items, sender, options) {
  if (genRunning) { log('생성 배치가 이미 진행 중'); return; }
  genRunning = true;
  genCancel = false;
  startKeepAlive(); // 배치 내내 워커가 죽지 않도록
  const webTabId = sender && sender.tab ? sender.tab.id : null;
  const opt = { ...GEN_DEFAULTS, ...(options || {}) };
  let sinceReload = 0;

  try {
    log(`=== 글 생성 시작: ${items.length}건 ===`, opt);
    const tabId = await ensureGeminiTab();
    await waitForGeminiReady(tabId, 45000, opt.tempChat);

    for (let i = 0; i < items.length; i++) {
      if (genCancel) {
        log('사용자 중단');
        for (let k = i; k < items.length; k++) {
          reportGenResult(webTabId, items[k].id, false, { error: '사용자가 중단했습니다' });
        }
        break;
      }
      const item = items[i];
      const label = item.keyword || item.id;
      log(`생성 ${i + 1}/${items.length}: ${label}`);

      let result = null;
      let lastError = '';
      for (let attempt = 0; attempt <= opt.retries; attempt++) {
        try {
          // 재로드가 우선 — 재로드하면 새 채팅도 자동으로 된 셈이다.
          if (sinceReload >= opt.reloadEvery) {
            await sendToTab(tabId, { action: 'GEM_PROGRESS', text: 'Gemini 새로고침 중…', pct: 5 });
            await reloadGeminiTab(tabId, opt.tempChat);
            sinceReload = 0;
          } else if (i > 0 || attempt > 0) {
            // 매 건 새 채팅으로 문맥을 비운다(품질 균일화의 핵심).
            if ((i % opt.newChatEvery === 0) || attempt > 0) {
              const nc = await sendToTab(tabId, { action: 'GEM_NEW_CHAT' });
              if (!nc || !nc.ok) throw new Error((nc && nc.error) || '새 채팅 실패');
            }
          }

          await sendToTab(tabId, {
            action: 'GEM_PROGRESS',
            text: `${i + 1}/${items.length} · ${label}${attempt ? ` (재시도 ${attempt})` : ''}`,
            pct: Math.round(((i + 1) / items.length) * 100),
          });

          const r = await genOne(tabId, item.prompt, genTimeoutMs(item.prompt));
          sinceReload++;

          // 완료 신호를 못 받았어도 글이 충분히 길면 성공으로 인정한다.
          // 반대로 신호는 왔는데 짧으면(= 거절/축약 응답) 실패다.
          if ((r.chars || 0) >= opt.minChars) { result = r; break; }
          lastError = r.ok
            ? `글이 너무 짧습니다(${r.chars || 0}자 < ${opt.minChars}자)`
            : (r.error || '생성 실패');
        } catch (e) {
          lastError = e.message;
          // 탭이 죽었을 수 있다 → 다음 시도 전에 되살린다.
          try { await waitForGeminiReady(tabId, 20000, opt.tempChat); } catch (_) {}
        }
      }

      if (result) {
        reportGenResult(webTabId, item.id, true, {
          keyword: item.keyword || '',
          text: result.text,
          chars: result.chars,
        });
      } else {
        reportGenResult(webTabId, item.id, false, { keyword: item.keyword || '', error: lastError });
      }
      await sleep(opt.gapMs);
    }
  } catch (e) {
    log('생성 배치 오류', e);
    // 시작 자체가 실패하면(로그인 안 됨 등) 전건을 실패로 알려 화면이 멈춰 보이지 않게 한다.
    for (const it of items) reportGenResult(webTabId, it.id, false, { error: e.message, fatal: true });
  } finally {
    genRunning = false;
    genCancel = false;
    if (geminiTabId) { try { await sendToTab(geminiTabId, { action: 'GEM_HIDE_OVERLAY' }); } catch (_) {} }
    reportGenResult(webTabId, '__done__', true, { done: true });
    stopKeepAlive();
    log('=== 글 생성 완료 ===');
  }
}

// 프롬프트가 길수록 답도 길어진다 → 대기 상한도 같이 늘린다.
function genTimeoutMs(prompt) {
  const base = 180000;
  return base + Math.min(120000, Math.floor((prompt || '').length / 10) * 1000);
}

function reportGenResult(webTabId, id, ok, extra) {
  const payload = { action: 'GEN_RESULT', id, ok, ...(extra || {}) };
  try {
    if (webTabId) {
      chrome.tabs.sendMessage(webTabId, payload, () => void chrome.runtime.lastError);
    } else {
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
    // 글을 쓰기 전에 계정부터 확인한다. 세션이 끊겨 로그인 창이 떴을 때 사용자가
    // 다른 계정으로 로그인하면, 예전엔 그대로 진행돼 남의 블로그에 글이 올라갔다.
    const who = await assertBlog(tabId, job.expectedBlogId);
    if (!who.ok) throw new Error(who.error);

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
        const r = await sendToTab(tabId, { action: 'INSERT_IMAGES', images: job.images });
        assertImagesInserted(r, job.images.length);
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

// 이미지가 요청한 만큼 실제로 들어갔는지 확인한다. 아니면 throw —
// runAutomation 의 catch 가 이 건을 실패로 보고하고, 글은 준비함에 남아 다시 시도할 수 있다.
// (예전엔 반환값을 버려서, 사진이 한 장도 안 들어가도 그대로 예약 등록되고 성공으로 보고됐다)
function assertImagesInserted(res, expected) {
  if (!res) throw new Error('이미지 삽입 응답 없음 (탭이 닫혔거나 에디터가 응답하지 않음)');
  const got = res.inserted || 0;
  if (got < expected) {
    const why = (res.failed && res.failed[0] && res.failed[0].error) || '원인 불명';
    throw new Error(`이미지 ${expected}장 중 ${got}장만 삽입됨 — ${why}`);
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
      const r = await sendToTab(tabId, { action: 'INSERT_IMAGES', images: [b.image], atCaret: true });
      assertImagesInserted(r, 1);
      await sleep(400);
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
// keepAlive 알람은 backstop 일 뿐이다 — 실제 배치 중 워커 유지는 startKeepAlive()
// (25초 인터벌)가 맡는다. 알람 최소 주기 30초는 유휴 한계와 겹쳐 단독으로는 못 믿는다.
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.create('updateCheck', { periodInMinutes: 180 }); // 3시간마다
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'updateCheck') checkForUpdate();
  // keepAlive: 알람이 뜨는 것만으로 유휴 타이머가 리셋되므로 별도 처리 불필요
});
chrome.debugger.onDetach.addListener(() => { debuggerTabId = null; });

log(`백그라운드 v${VERSION} 시작`);
