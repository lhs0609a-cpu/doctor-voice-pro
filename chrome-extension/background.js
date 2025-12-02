// 백그라운드 서비스 워커
console.log('[닥터보이스] 백그라운드 서비스 워커 시작');

// 탭 업데이트 감지 - 모든 탭 변경 감시
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // 페이지 로딩 완료 시에만 처리
  if (changeInfo.status !== 'complete') return;

  const url = tab.url || '';
  console.log('[닥터보이스] 탭 로딩 완료:', tabId, url);

  // 저장된 데이터 확인
  const stored = await chrome.storage.local.get(['pendingPost', 'postOptions', 'autoPostEnabled', 'loginTabId']);

  if (!stored.autoPostEnabled || !stored.pendingPost) {
    return; // 자동 포스팅 비활성화 상태
  }

  console.log('[닥터보이스] 자동 포스팅 활성화됨, URL 확인:', url);

  // 1. 로그인 성공 감지: 네이버 메인 또는 다른 페이지로 이동
  if (stored.loginTabId === tabId) {
    // 로그인 페이지가 아닌 곳으로 이동 = 로그인 성공
    if (!url.includes('nid.naver.com/nidlogin')) {
      console.log('[닥터보이스] 로그인 성공! 글쓰기 페이지로 이동');

      // loginTabId 클리어
      await chrome.storage.local.remove(['loginTabId']);

      // 글쓰기 페이지로 이동
      await chrome.tabs.update(tabId, {
        url: 'https://blog.naver.com/GoBlogWrite.naver'
      });
      return;
    }
  }

  // 2. 블로그 글쓰기 페이지 도착 감지
  if (url.includes('blog.naver.com') && (url.includes('GoBlogWrite') || url.includes('PostWrite'))) {
    console.log('[닥터보이스] 글쓰기 페이지 도착!');

    // 에디터 로딩 대기
    await sleep(4000);

    // 글 입력 시도
    try {
      console.log('[닥터보이스] 글 입력 메시지 전송');
      await chrome.tabs.sendMessage(tabId, {
        action: 'INSERT_POST',
        data: stored.pendingPost,
        options: stored.postOptions || { useQuote: true, useHighlight: true, useImages: true }
      });

      console.log('[닥터보이스] 글 입력 성공!');
      await chrome.storage.local.set({ autoPostEnabled: false });

    } catch (e) {
      console.error('[닥터보이스] 첫 번째 시도 실패:', e.message);

      // 재시도 (content script가 아직 로드 안됐을 수 있음)
      await sleep(3000);

      try {
        console.log('[닥터보이스] 재시도...');
        await chrome.tabs.sendMessage(tabId, {
          action: 'INSERT_POST',
          data: stored.pendingPost,
          options: stored.postOptions || { useQuote: true, useHighlight: true, useImages: true }
        });
        console.log('[닥터보이스] 재시도 성공!');
        await chrome.storage.local.set({ autoPostEnabled: false });
      } catch (e2) {
        console.error('[닥터보이스] 재시도도 실패:', e2.message);
      }
    }
  }
});

// 메시지 수신 (popup에서)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스] 메시지 수신:', message);

  if (message.action === 'START_POSTING') {
    // 로그인 탭 ID 저장
    chrome.storage.local.set({ loginTabId: message.tabId });
    console.log('[닥터보이스] 로그인 탭 ID 저장:', message.tabId);
    sendResponse({ success: true });
    return true;
  }

  if (message.action === 'GET_POST_DATA') {
    chrome.storage.local.get(['pendingPost'], (result) => {
      sendResponse({ data: result.pendingPost });
    });
    return true;
  }
});

// 외부 메시지 수신 (웹페이지에서 - 원클릭 발행)
chrome.runtime.onMessageExternal.addListener(async (message, sender, sendResponse) => {
  console.log('[닥터보이스] 외부 메시지 수신:', message);
  console.log('[닥터보이스] 발신자:', sender.url);

  if (message.action === 'ONE_CLICK_PUBLISH') {
    try {
      const { postData, credentials, options } = message;

      console.log('[닥터보이스] 원클릭 발행 시작');
      console.log('[닥터보이스] 제목:', postData.title);
      console.log('[닥터보이스] 이미지 수:', postData.images?.length || 0);

      // 1. 데이터 저장
      await chrome.storage.local.set({
        pendingPost: postData,
        postOptions: options || { useQuote: true, useHighlight: true, useImages: true },
        autoPostEnabled: true
      });

      // 2. 네이버 로그인 페이지 열기
      const loginTab = await chrome.tabs.create({
        url: 'https://nid.naver.com/nidlogin.login',
        active: true
      });

      // 3. 로그인 탭 ID 저장
      await chrome.storage.local.set({ loginTabId: loginTab.id });

      // 4. 로그인 페이지 로딩 대기
      await waitForTabLoad(loginTab.id);
      await sleep(1500);

      // 5. 로그인 정보 입력
      if (credentials && credentials.id && credentials.pw) {
        await chrome.scripting.executeScript({
          target: { tabId: loginTab.id },
          func: performNaverLogin,
          args: [credentials.id, credentials.pw]
        });
      }

      sendResponse({ success: true, message: '발행 프로세스 시작됨' });

    } catch (error) {
      console.error('[닥터보이스] 원클릭 발행 실패:', error);
      sendResponse({ success: false, error: error.message });
    }
    return true;
  }

  // 기존 SET_POST_DATA 핸들러
  if (message.action === 'SET_POST_DATA') {
    chrome.storage.local.set({ pendingPost: message.data }, () => {
      console.log('[닥터보이스] 포스트 데이터 저장됨');
      sendResponse({ success: true });
    });
    return true;
  }

  // 확장 프로그램 설치 확인
  if (message.action === 'PING') {
    sendResponse({ success: true, version: '3.0.0' });
    return true;
  }
});

// 네이버 로그인 함수
function performNaverLogin(id, pw) {
  console.log('[닥터보이스] 로그인 정보 입력 시작');

  // 이미 로그인된 상태인지 확인
  const loginForm = document.querySelector('#frmNIDLogin') || document.querySelector('form[name="frmNIDLogin"]');
  if (!loginForm) {
    console.log('[닥터보이스] 로그인 폼이 없음 - 이미 로그인된 상태일 수 있음');
    // 이미 로그인된 경우 바로 블로그로 이동 시도
    return;
  }

  const idInput = document.querySelector('#id');
  const pwInput = document.querySelector('#pw');

  if (!idInput || !pwInput) {
    console.error('[닥터보이스] 로그인 입력 필드를 찾을 수 없습니다');
    // 안내 메시지 표시
    showLoginNotification('로그인 필드를 찾을 수 없습니다. 수동으로 로그인해주세요.');
    return;
  }

  // 캡챠 확인
  const captcha = document.querySelector('#captcha') || document.querySelector('.captcha_wrap');
  if (captcha) {
    console.log('[닥터보이스] 캡챠 감지됨 - 수동 로그인 필요');
    showLoginNotification('보안문자가 필요합니다. 수동으로 로그인해주세요. 로그인 후 자동으로 진행됩니다.');
    return;
  }

  // 아이디 입력
  idInput.click();
  idInput.focus();
  idInput.value = id;
  idInput.dispatchEvent(new Event('input', { bubbles: true }));
  idInput.dispatchEvent(new Event('change', { bubbles: true }));

  // 비밀번호 입력
  setTimeout(() => {
    pwInput.click();
    pwInput.focus();
    pwInput.value = pw;
    pwInput.dispatchEvent(new Event('input', { bubbles: true }));
    pwInput.dispatchEvent(new Event('change', { bubbles: true }));

    console.log('[닥터보이스] 로그인 정보 입력 완료');

    // 로그인 버튼 자동 클릭
    setTimeout(() => {
      const loginBtn = document.querySelector('.btn_login') ||
                       document.querySelector('#log\\.login') ||
                       document.querySelector('button[type="submit"]');

      if (loginBtn) {
        console.log('[닥터보이스] 로그인 버튼 클릭');
        loginBtn.click();
      } else {
        showLoginNotification('로그인 버튼을 찾을 수 없습니다. 수동으로 로그인해주세요.');
      }
    }, 500);
  }, 300);
}

// 로그인 페이지 알림 표시
function showLoginNotification(message) {
  const existing = document.querySelector('.doctorvoice-login-notification');
  if (existing) existing.remove();

  const notification = document.createElement('div');
  notification.className = 'doctorvoice-login-notification';
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white;
    padding: 16px 24px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    z-index: 999999;
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.4);
    max-width: 400px;
    text-align: center;
  `;
  notification.textContent = '⚠️ ' + message;
  document.body.appendChild(notification);
}

// 탭 로딩 대기
function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 15000);
  });
}

// 유틸리티
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 서비스 워커 유지를 위한 알람 (30초마다)
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keepAlive') {
    console.log('[닥터보이스] 서비스 워커 활성 유지');
  }
});
