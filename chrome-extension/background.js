// 백그라운드 서비스 워커 - v10.2 자동 데이터 동기화 버전
console.log('[닥터보이스] 백그라운드 서비스 워커 시작 v10.2');

// 닥터보이스 사이트에서 localStorage 데이터 가져오기
async function syncDataFromWebsite() {
  try {
    const tabs = await chrome.tabs.query({});
    const doctorVoiceTab = tabs.find(tab =>
      tab.url && (
        tab.url.includes('localhost:3000') ||
        tab.url.includes('localhost:3001') ||
        tab.url.includes('doctor-voice-pro') ||
        tab.url.includes('vercel.app')
      )
    );

    if (!doctorVoiceTab) {
      console.log('[닥터보이스] 웹사이트 탭 없음');
      return null;
    }

    const result = await chrome.scripting.executeScript({
      target: { tabId: doctorVoiceTab.id },
      func: () => {
        const pending = localStorage.getItem('doctorvoice-pending-post');
        const autoPublish = localStorage.getItem('doctorvoice-auto-publish');
        // 데이터 읽은 후 플래그 초기화
        if (autoPublish) localStorage.removeItem('doctorvoice-auto-publish');
        return { post: pending ? JSON.parse(pending) : null, autoPublish: autoPublish === 'true' };
      }
    });

    const data = result?.[0]?.result;
    if (data?.post && data.post.title) {
      console.log('[닥터보이스] 웹사이트에서 데이터 동기화:', data.post.title);
      await chrome.storage.local.set({
        pendingPost: data.post,
        postOptions: { useQuote: true, useHighlight: true, useImages: true },
        autoPostEnabled: true
      });
      return data.post;
    }
    return null;
  } catch (e) {
    console.log('[닥터보이스] 데이터 동기화 실패:', e.message);
    return null;
  }
}

// 탭 업데이트 감지 - 블로그 글쓰기 페이지 도착 시 자동 입력
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // 페이지 로딩 완료 시에만 처리
  if (changeInfo.status !== 'complete') return;

  const url = tab.url || '';

  // 블로그 글쓰기 페이지인지 확인
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('GoBlogWrite') && !url.includes('PostWrite') && !url.includes('Redirect=Write') && !url.includes('editor')) return;

  console.log('[닥터보이스] 블로그 글쓰기 페이지 감지:', url);

  // 먼저 웹사이트에서 최신 데이터 동기화 시도
  await syncDataFromWebsite();

  // 저장된 데이터 확인
  const stored = await chrome.storage.local.get(['pendingPost', 'postOptions', 'autoPostEnabled']);

  if (!stored.autoPostEnabled || !stored.pendingPost) {
    console.log('[닥터보이스] 자동 포스팅 비활성화 또는 데이터 없음');
    return;
  }

  console.log('[닥터보이스] 자동 글 입력 시작!');

  // 에디터 로딩 대기 (네이버 에디터가 느림)
  await sleep(4000);

  // 글 입력 시도
  try {
    await chrome.tabs.sendMessage(tabId, {
      action: 'INSERT_POST',
      data: stored.pendingPost,
      options: stored.postOptions || { useQuote: true, useHighlight: true, useImages: true }
    });

    console.log('[닥터보이스] 글 입력 성공!');

    // 자동 발행 비활성화 (한번만 실행)
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
});

// 외부 메시지 수신 (웹페이지에서)
chrome.runtime.onMessageExternal.addListener(async (message, sender, sendResponse) => {
  console.log('[닥터보이스] 외부 메시지 수신:', message.action);

  // PING - 확장 프로그램 설치 확인
  if (message.action === 'PING') {
    sendResponse({ success: true, version: '10.1.0' });
    return true;
  }

  // 포스트 데이터 설정
  if (message.action === 'SET_POST_DATA') {
    await chrome.storage.local.set({
      pendingPost: message.data,
      postOptions: message.options || { useQuote: true, useHighlight: true, useImages: true },
      autoPostEnabled: true
    });
    console.log('[닥터보이스] 포스트 데이터 저장됨:', message.data.title);
    sendResponse({ success: true });
    return true;
  }

  // 원클릭 발행 (웹사이트에서 바로 발행 시작)
  if (message.action === 'ONE_CLICK_PUBLISH') {
    try {
      const { postData, options } = message;

      console.log('[닥터보이스] 원클릭 발행 시작:', postData.title);

      // 데이터 저장
      await chrome.storage.local.set({
        pendingPost: postData,
        postOptions: options || { useQuote: true, useHighlight: true, useImages: true },
        autoPostEnabled: true
      });

      // 네이버 블로그 글쓰기 페이지 열기
      await chrome.tabs.create({
        url: 'https://blog.naver.com/GoBlogWrite.naver',
        active: true
      });

      sendResponse({ success: true, message: '발행 프로세스 시작됨' });

    } catch (error) {
      console.error('[닥터보이스] 원클릭 발행 실패:', error);
      sendResponse({ success: false, error: error.message });
    }
    return true;
  }
});

// 유틸리티
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 서비스 워커 유지를 위한 알람
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keepAlive') {
    console.log('[닥터보이스] 서비스 워커 활성 유지');
  }
});
