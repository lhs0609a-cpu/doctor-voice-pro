// 팝업 - 닥터보이스 프로 v15 · 실시간 연동 신호등 + 자동 업데이트
const SITE_URL = 'https://doctor-voice-pro-ghwi.vercel.app/dashboard/saved';

document.addEventListener('DOMContentLoaded', () => {
  const VERSION = chrome.runtime.getManifest().version;
  document.getElementById('verText').textContent = 'v' + VERSION;

  document.getElementById('btnOpenSite').addEventListener('click', () => {
    chrome.tabs.create({ url: SITE_URL, active: true });
  });
  document.getElementById('btnRefresh').addEventListener('click', () => refresh(VERSION));

  // 네이버 자동로그인 계정 저장/삭제
  document.getElementById('btnSaveCred').addEventListener('click', saveCred);
  document.getElementById('btnClearCred').addEventListener('click', clearCred);

  refresh(VERSION);
  refreshCredStatus();
});

function setCredStatus(text) {
  const el = document.getElementById('credStatus');
  if (el) el.textContent = text;
}

function refreshCredStatus() {
  chrome.runtime.sendMessage({ action: 'GET_CRED' }, (r) => {
    if (chrome.runtime.lastError) { setCredStatus('저장된 계정: 확인 불가'); return; }
    const has = r && r.ok && r.cred && r.cred.id;
    setCredStatus(has ? ('저장된 계정: ' + maskId(r.cred.id)) : '저장된 계정: 없음');
  });
}

function maskId(id) {
  if (!id) return '';
  if (id.length <= 3) return id[0] + '**';
  return id.slice(0, 3) + '*'.repeat(Math.max(2, id.length - 3));
}

function saveCred() {
  const id = document.getElementById('credId').value.trim();
  const pw = document.getElementById('credPw').value;
  if (!id || !pw) { setCredStatus('아이디와 비밀번호를 모두 입력하세요.'); return; }
  chrome.runtime.sendMessage({ action: 'SAVE_CRED', id, pw }, (r) => {
    if (chrome.runtime.lastError || !r || !r.ok) { setCredStatus('저장 실패'); return; }
    document.getElementById('credPw').value = '';
    setCredStatus('저장됨: ' + maskId(id));
  });
}

function clearCred() {
  chrome.runtime.sendMessage({ action: 'CLEAR_CRED' }, () => {
    document.getElementById('credId').value = '';
    document.getElementById('credPw').value = '';
    setCredStatus('저장된 계정: 없음');
  });
}

async function refresh(VERSION) {
  const site = await checkSiteTab();
  const upd = await checkUpdate();
  render(VERSION, site, upd);
}

// 닥터보이스 웹사이트 탭이 열려 있는가
async function checkSiteTab() {
  try {
    const tabs = await chrome.tabs.query({});
    const found = tabs.find((t) => t.url && (
      t.url.includes('doctor-voice-pro') || t.url.includes('vercel.app') || t.url.includes('localhost')
    ));
    return !!found;
  } catch (e) { return false; }
}

// 업데이트 정보 (캐시 우선, 없으면 즉시 조회)
async function checkUpdate() {
  try {
    const stored = await chrome.storage.local.get('updateInfo');
    let info = stored.updateInfo;
    if (!info || !info.checkedAt || Date.now() - info.checkedAt > 30 * 60 * 1000) {
      // background 에 최신 확인 요청
      info = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: 'CHECK_UPDATE' }, (res) => {
          if (chrome.runtime.lastError || !res) resolve(info || {});
          else resolve(res);
        });
      });
    }
    return info || {};
  } catch (e) { return {}; }
}

function setDot(id, cls) { document.getElementById(id).className = 'dot ' + cls; }
function setVal(id, txt) { document.getElementById(id).textContent = txt; }

function render(VERSION, siteConnected, upd) {
  const updateAvailable = !!upd.updateAvailable;
  const latest = upd.latest || VERSION;

  // 체크리스트
  setDot('dotExt', 'ok'); setVal('valExt', '정상');
  setDot('dotSite', siteConnected ? 'ok' : 'off');
  setVal('valSite', siteConnected ? '연결됨' : '열려 있지 않음');
  setDot('dotVer', updateAvailable ? 'warn' : 'ok');
  setVal('valVer', updateAvailable ? 'v' + latest + ' 있음' : '최신 (v' + VERSION + ')');

  // 신호등 요약
  const light = document.getElementById('beaconLight');
  const title = document.getElementById('beaconTitle');
  const desc = document.getElementById('beaconDesc');

  if (updateAvailable) {
    light.className = 'light amber';
    title.textContent = '업데이트가 필요합니다';
    desc.textContent = 'v' + VERSION + ' → v' + latest + ' · 아래에서 새 버전을 받으세요';
  } else if (siteConnected) {
    light.className = 'light green';
    title.textContent = '실시간 연동 중';
    desc.textContent = '발행 준비 완료 — 웹에서 발행 버튼을 누르세요';
  } else {
    light.className = 'light amber';
    title.textContent = '웹사이트를 열어주세요';
    desc.textContent = '닥터보이스 프로에 접속하면 자동 연동됩니다';
  }

  // 업데이트 카드
  const card = document.getElementById('updateCard');
  if (updateAvailable) {
    card.classList.add('show');
    document.getElementById('updateNotes').textContent = upd.notes || '새로운 기능과 안정성 개선이 포함되어 있습니다.';
    const btn = document.getElementById('btnUpdate');
    if (upd.downloadUrl) btn.href = upd.downloadUrl;
  } else {
    card.classList.remove('show');
  }
}
