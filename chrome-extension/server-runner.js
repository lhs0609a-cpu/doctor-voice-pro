// Job-scoped grants only. No web login token or browser password is stored here.
(() => {
  const KEY = 'serverExecutionV2';
  let busy = false;
  let current = null;
  const apiOrigins = new Set(['https://doctor-voice-pro-backend.fly.dev']);
  function validateGrant(grant) {
    const url = new URL(grant.apiBase);
    const local = url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname);
    if ((!apiOrigins.has(url.origin) && !local) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error('허용되지 않은 서버 주소입니다');
    }
    if (!/^[a-zA-Z0-9-]{1,64}$/.test(grant.jobId) || !/^[a-f0-9]{48}$/.test(grant.executionToken)) {
      throw new Error('잘못된 작업 권한입니다');
    }
    return { apiBase: url.origin, jobId: grant.jobId, executionToken: grant.executionToken };
  }
  async function request(state, path, data) {
    const response = await fetch(`${state.apiBase}/api/v1/campaign/execution/${state.jobId}/${path}`, {
      method: data ? 'POST' : 'GET',
      headers: { Authorization: `Bearer ${state.executionToken}`, 'Content-Type': 'application/json' },
      ...(data ? { body: JSON.stringify({ ...data, lock_token: state.executionToken }) } : {}),
      signal: AbortSignal.timeout(20000), redirect: 'error',
    });
    if (!response.ok) throw new Error(`작업 서버 응답 오류 (${response.status})`);
    return response.json();
  }
  async function save(state) { await chrome.storage.local.set({ [KEY]: state }); }
  async function deliver(state) {
    await request(state, 'result', state.report);
    await chrome.storage.local.remove(KEY);
  }
  async function recover() {
    if (busy) return;
    busy = true;
    try {
      const state = (await chrome.storage.local.get(KEY))[KEY];
      if (!state) return;
      if (!state.report) {
        state.report = { ok: false, uncertain: state.stage === 'finalizing',
          release: state.stage !== 'finalizing', message: '확장 재시작 후 작업 복구' };
        await save(state);
      }
      // Do not let EDITOR_READY replay an abandoned pendingJob.
      await chrome.storage.local.remove('pendingJob');
      await deliver(state);
    } finally { busy = false; }
  }
  async function start(grant, run) {
    if (busy) throw new Error('진행 중인 작업이 있습니다');
    busy = true;
    let timer;
    try {
      if ((await chrome.storage.local.get(KEY))[KEY]) throw new Error('보고 대기 중인 작업이 있습니다');
      current = { ...validateGrant(grant), stage: 'editing' };
      await save(current);
      const payload = await request(current, 'payload');
      await request(current, 'checkpoint', { stage: 'editing' });
      timer = setInterval(() => request(current, 'checkpoint', { stage: 'heartbeat' }).catch(() => {}), 30000);
      let out;
      try { out = await run(payload); }
      catch (error) { out = { ok: false, error: error.message }; }
      current.report = { ok: !!out?.ok, uncertain: !!out?.uncertain || (!out?.ok && current.stage === 'finalizing'),
        message: out?.error || '네이버 예약 목록 확인 필요', url: out?.url || null,
        captcha: !!out?.captcha, need_login: !!out?.needLogin };
      try {
        const url = new URL(out.url);
        const parts = url.pathname.split('/').filter(Boolean);
        if (url.origin === 'https://blog.naver.com' && parts.length === 2 && parts[0] === payload.expectedBlogId && /^\d+$/.test(parts[1])) {
          current.report.receipt_id = parts[1];
        }
      } catch (_) { /* No externally identifiable receipt: server keeps uncertain. */ }
      await save(current);
      await deliver(current);
      return out;
    } finally {
      clearInterval(timer);
      current = null;
      busy = false;
    }
  }
  async function beforeFinalize() {
    if (!current) throw new Error('실행 권한이 종료되어 발행을 중단했습니다');
    current.stage = 'finalizing';
    await save(current);
    await request(current, 'checkpoint', { stage: 'finalizing' });
  }
  globalThis.ServerRunner = { start, recover, beforeFinalize, active: () => busy, running: () => !!current, validateGrant };
  chrome.alarms.onAlarm.addListener(alarm => {
    if (alarm.name === 'server-outbox') recover().catch(() => {});
  });
  chrome.alarms.create('server-outbox', { periodInMinutes: 1 });
  chrome.runtime.onStartup.addListener(() => recover().catch(() => {}));
})();
