// 백그라운드 서비스 워커
console.log('[닥터보이스] 백그라운드 서비스 워커 시작');

// 웹페이지에서 메시지 수신 (저장된 글 페이지에서 전송)
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스] 외부 메시지 수신:', message);

  if (message.action === 'SET_POST_DATA') {
    // 포스트 데이터 저장
    chrome.storage.local.set({ pendingPost: message.data }, () => {
      console.log('[닥터보이스] 포스트 데이터 저장됨');
      sendResponse({ success: true });
    });
    return true;
  }
});

// 내부 메시지 수신 (content script에서)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스] 내부 메시지 수신:', message);

  if (message.action === 'SAVE_POST_DATA') {
    chrome.storage.local.set({ pendingPost: message.data }, () => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (message.action === 'GET_POST_DATA') {
    chrome.storage.local.get(['pendingPost'], (result) => {
      sendResponse({ data: result.pendingPost });
    });
    return true;
  }
});

// 설치 시 안내
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[닥터보이스] 확장 프로그램 설치됨');
  }
});
