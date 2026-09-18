const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(__dirname + '/server-runner.js', 'utf8');
const grant = { apiBase: 'https://doctor-voice-pro-backend.fly.dev', jobId: 'job-1', executionToken: 'a'.repeat(48) };
function harness(storage = {}, transport = async () => ({ ok: true, json: async () => ({ title: 'test' }) })) {
  const calls = [];
  const ctx = vm.createContext({ URL, AbortSignal, setInterval: () => 1, clearInterval: () => {},
    fetch: async (url, options) => { calls.push({ url, options }); return transport(url, options); },
    chrome: {
      storage: { local: {
        get: async key => ({ [key]: structuredClone(storage[key]) }),
        set: async value => { Object.assign(storage, structuredClone(value)); },
        remove: async key => { delete storage[key]; },
      } },
      alarms: { create: () => {}, onAlarm: { addListener: () => {} } },
      runtime: { onStartup: { addListener: () => {} } },
    },
  });
  vm.runInContext(source, ctx);
  return { runner: ctx.ServerRunner, calls, storage };
}

test('rejects arbitrary API origins and credentials in URLs', () => {
  const { runner } = harness();
  for (const apiBase of ['https://evil.vercel.app', 'https://doctor-voice-pro-backend.fly.dev.evil.com', 'http://localhost.evil.com', 'https://x:y@doctor-voice-pro-backend.fly.dev']) {
    assert.throws(() => runner.validateGrant({ ...grant, apiBase }));
  }
  assert.equal(runner.validateGrant(grant).jobId, grant.jobId);
});

test('result survives lost ACK and service worker restart without rerunning editor', async () => {
  const storage = {};
  const first = harness(storage, async url => {
    if (url.endsWith('/result')) throw new Error('network lost');
    return { ok: true, json: async () => ({ title: 'test' }) };
  });
  let executions = 0;
  await assert.rejects(first.runner.start(grant, async () => {
    executions++;
    await first.runner.beforeFinalize();
    return { ok: true, url: null };
  }));
  assert.ok(storage.serverExecutionV2.report);
  const second = harness(storage);
  await second.runner.recover();
  assert.equal(executions, 1);
  assert.equal(storage.serverExecutionV2, undefined);
  const original = first.calls.find(c => c.url.endsWith('/result')).options.body;
  assert.equal(second.calls[0].options.body, original);
});

test('interrupted finalizing recovers as uncertain and removes pending editor job', async () => {
  const h = harness({ serverExecutionV2: { ...grant, stage: 'finalizing' }, pendingJob: { title: 'old' } });
  await h.runner.recover();
  const report = JSON.parse(h.calls[0].options.body);
  assert.equal(report.uncertain, true);
  assert.equal(report.release, false);
  assert.equal(h.storage.pendingJob, undefined);
});

test('simultaneous starts never run two editors', async () => {
  const h = harness();
  let finish;
  const hold = new Promise(resolve => { finish = resolve; });
  let executions = 0;
  const first = h.runner.start(grant, async () => { executions++; await hold; return { ok: false }; });
  await assert.rejects(h.runner.start(grant, async () => { executions++; }));
  finish();
  await first;
  assert.equal(executions, 1);
});

test('late finalization cannot proceed after execution ownership was cleared', async () => {
  await assert.rejects(harness().runner.beforeFinalize());
});
