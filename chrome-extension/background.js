// 백그라운드 서비스 워커 v11.0 - 단순화 버전
console.log('[닥터보이스] 백그라운드 v11.0 시작');

// 전역 변수로 발행 데이터 저장
let pendingPostData = null;

// 외부 메시지 수신 (웹페이지에서)
chrome.runtime.onMessageExternal.addListener(async (message, sender, sendResponse) => {
  console.log('[닥터보이스] 외부 메시지:', message.action);

  if (message.action === 'PING') {
    sendResponse({ success: true, version: '11.0.0' });
    return true;
  }

  // 발행 데이터 저장 및 블로그 열기
  if (message.action === 'PUBLISH_TO_BLOG') {
    console.log('[닥터보이스] 발행 요청:', message.data?.title);

    // 데이터 저장
    pendingPostData = message.data;
    await chrome.storage.local.set({
      pendingPost: message.data,
      autoPostEnabled: true
    });

    console.log('[닥터보이스] 데이터 저장 완료, 블로그 열기');

    // 네이버 블로그 열기
    chrome.tabs.create({
      url: 'https://blog.naver.com/GoBlogWrite.naver',
      active: true
    });

    sendResponse({ success: true });
    return true;
  }
});

// 내부 메시지 수신 (content script에서)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스] 내부 메시지:', message.action);

  if (message.action === 'GET_POST_DATA') {
    // 저장된 데이터 반환
    chrome.storage.local.get(['pendingPost', 'autoPostEnabled'], (result) => {
      console.log('[닥터보이스] 데이터 요청 응답:', result.pendingPost ? '있음' : '없음');
      sendResponse({
        success: true,
        data: result.pendingPost,
        autoPostEnabled: result.autoPostEnabled
      });
    });
    return true; // 비동기 응답
  }

  if (message.action === 'CLEAR_POST_DATA') {
    pendingPostData = null;
    chrome.storage.local.set({ pendingPost: null, autoPostEnabled: false });
    sendResponse({ success: true });
    return true;
  }
});

// 탭 업데이트 감지
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;

  const url = tab.url || '';
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('Write') && !url.includes('editor')) return;

  console.log('[닥터보이스] 블로그 글쓰기 페이지 감지');

  // 저장된 데이터 확인
  const stored = await chrome.storage.local.get(['pendingPost', 'autoPostEnabled']);

  if (stored.autoPostEnabled && stored.pendingPost) {
    console.log('[닥터보이스] 자동 발행 시작!');

    // 잠시 대기 후 content script에 메시지 전송
    setTimeout(async () => {
      try {
        await chrome.tabs.sendMessage(tabId, {
          action: 'INSERT_POST',
          data: stored.pendingPost
        });
        console.log('[닥터보이스] 글 입력 메시지 전송 완료');
      } catch (e) {
        console.log('[닥터보이스] 메시지 전송 실패, 재시도...', e.message);
        // 재시도
        setTimeout(async () => {
          try {
            await chrome.tabs.sendMessage(tabId, {
              action: 'INSERT_POST',
              data: stored.pendingPost
            });
          } catch (e2) {
            console.log('[닥터보이스] 재시도도 실패:', e2.message);
          }
        }, 2000);
      }
    }, 3000);
  }
});

// 서비스 워커 유지
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {});
