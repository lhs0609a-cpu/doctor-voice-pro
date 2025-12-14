// 백그라운드 서비스 워커 v13.2 - 다중 입력 방식 (insertText → IME → char)
console.log('[닥터보이스] 백그라운드 v13.2 시작 - 다중 입력 방식');

// 전역 변수
let pendingPostData = null;
let currentDebuggerTabId = null;

// 외부 메시지 수신 (웹페이지에서)
chrome.runtime.onMessageExternal.addListener(async (message, sender, sendResponse) => {
  console.log('[닥터보이스] 외부 메시지:', message.action);

  if (message.action === 'PING') {
    sendResponse({ success: true, version: '13.2.0' });
    return true;
  }

  if (message.action === 'PUBLISH_TO_BLOG') {
    console.log('[닥터보이스] 발행 요청:', message.data?.title);

    pendingPostData = message.data;
    await chrome.storage.local.set({
      pendingPost: message.data,
      autoPostEnabled: true
    });

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
    chrome.storage.local.get(['pendingPost', 'autoPostEnabled'], (result) => {
      sendResponse({
        success: true,
        data: result.pendingPost,
        autoPostEnabled: result.autoPostEnabled
      });
    });
    return true;
  }

  if (message.action === 'CLEAR_POST_DATA') {
    pendingPostData = null;
    chrome.storage.local.set({ pendingPost: null, autoPostEnabled: false });
    sendResponse({ success: true });
    return true;
  }

  // 완전자동 입력 요청
  if (message.action === 'AUTO_TYPE') {
    const tabId = sender.tab.id;
    console.log('[닥터보이스] AUTO_TYPE 요청, tabId:', tabId);
    console.log('[닥터보이스] 제목:', message.title?.substring(0, 30));
    console.log('[닥터보이스] 본문 길이:', message.content?.length);

    autoTypeWithDebugger(tabId, message.title, message.content, message.titlePos, message.bodyPos)
      .then((result) => {
        console.log('[닥터보이스] AUTO_TYPE 완료:', result);
        sendResponse({ success: true, result });
      })
      .catch((err) => {
        console.error('[닥터보이스] AUTO_TYPE 실패:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }
});

// 완전자동 입력 (Input.insertText 방식 - 클립보드 불필요, 즉시 삽입!)
async function autoTypeWithDebugger(tabId, title, content, titlePos, bodyPos) {
  console.log('[닥터보이스] === 완전자동 입력 시작 (insertText 방식) ===');

  try {
    // 1. debugger 연결
    console.log('[닥터보이스] 1단계: debugger 연결');
    await attachDebugger(tabId);

    // 2. 제목 입력: 클릭 → 클립보드 복사 → Ctrl+V
    console.log('[닥터보이스] 2단계: 제목 클릭');
    await clickAt(tabId, titlePos.x, titlePos.y);
    await sleep(300);

    console.log('[닥터보이스] 3단계: 제목 입력');
    await insertText(tabId, title);
    await sleep(200);

    // 3. 본문 입력: 클릭 → 직접 삽입
    console.log('[닥터보이스] 4단계: 본문 클릭');
    await clickAt(tabId, bodyPos.x, bodyPos.y);
    await sleep(300);

    console.log('[닥터보이스] 5단계: 본문 입력');
    await insertText(tabId, content);
    await sleep(200);

    // 4. debugger 연결 해제
    console.log('[닥터보이스] 6단계: debugger 해제');
    await detachDebugger(tabId);

    console.log('[닥터보이스] === 완전자동 입력 완료! ===');
    return { success: true };

  } catch (error) {
    console.error('[닥터보이스] 오류:', error);
    try { await detachDebugger(tabId); } catch (e) {}
    throw error;
  }
}

// 텍스트 입력 (IME 방식 - 한글 호환)
async function insertText(tabId, text) {
  console.log('[닥터보이스] 텍스트 삽입 시작, 길이:', text.length);

  // 먼저 Input.insertText 시도
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Input.insertText', {
      text: text
    });
    console.log('[닥터보이스] insertText 완료');
    return;
  } catch (e) {
    console.log('[닥터보이스] insertText 실패, 대체 방식 시도:', e.message);
  }

  // 실패 시 IME 방식으로 시도
  try {
    // IME composition 시작
    await chrome.debugger.sendCommand({ tabId }, 'Input.imeSetComposition', {
      text: text,
      selectionStart: text.length,
      selectionEnd: text.length
    });
    await sleep(50);

    // IME 확정
    await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    });
    await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    });

    console.log('[닥터보이스] IME 방식 완료');
    return;
  } catch (e) {
    console.log('[닥터보이스] IME 방식 실패:', e.message);
  }

  // 최종 대안: 문자 단위 입력 (빠른 속도)
  console.log('[닥터보이스] 문자 단위 입력 시작');
  const startTime = Date.now();

  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    if (char === '\n') {
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'keyDown',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13
      });
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'keyUp',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13
      });
    } else {
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'char',
        text: char
      });
    }

    // 100자마다 진행률 표시
    if (i > 0 && i % 100 === 0) {
      const progress = Math.round((i / text.length) * 100);
      console.log(`[닥터보이스] 입력 진행: ${progress}%`);
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`[닥터보이스] 문자 단위 입력 완료 (${elapsed}초)`);
}

// 클릭
async function clickAt(tabId, x, y) {
  console.log('[닥터보이스] 클릭:', x, y);

  await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: x,
    y: y,
    button: 'left',
    clickCount: 1
  });

  await sleep(50);

  await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: x,
    y: y,
    button: 'left',
    clickCount: 1
  });

  console.log('[닥터보이스] 클릭 완료');
}

// 텍스트 입력
async function typeText(tabId, text) {
  console.log('[닥터보이스] 타이핑 시작, 길이:', text.length);

  const startTime = Date.now();

  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    if (char === '\n') {
      // Enter 키
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'keyDown',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13
      });
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'keyUp',
        key: 'Enter',
        code: 'Enter',
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13
      });
    } else {
      // 일반 문자 - char 이벤트로 직접 입력
      await chrome.debugger.sendCommand({ tabId }, 'Input.dispatchKeyEvent', {
        type: 'char',
        text: char
      });
    }

    // 진행상황 로그 (10% 단위)
    if (text.length > 100 && i > 0 && i % Math.floor(text.length / 10) === 0) {
      const progress = Math.round((i / text.length) * 100);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`[닥터보이스] 타이핑 진행: ${progress}% (${elapsed}초)`);
    }

    // 속도 조절 (50자마다 약간 대기)
    if (i > 0 && i % 50 === 0) {
      await sleep(10);
    }
  }

  const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`[닥터보이스] 타이핑 완료! (${totalTime}초)`);
}

// debugger 연결
async function attachDebugger(tabId) {
  // 이미 연결되어 있으면 먼저 해제
  if (currentDebuggerTabId) {
    try {
      await detachDebugger(currentDebuggerTabId);
    } catch (e) {}
  }

  return new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, '1.3', () => {
      if (chrome.runtime.lastError) {
        console.error('[닥터보이스] debugger 연결 실패:', chrome.runtime.lastError.message);
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        currentDebuggerTabId = tabId;
        console.log('[닥터보이스] debugger 연결됨, tabId:', tabId);
        resolve();
      }
    });
  });
}

// debugger 연결 해제
async function detachDebugger(tabId) {
  return new Promise((resolve) => {
    chrome.debugger.detach({ tabId }, () => {
      if (chrome.runtime.lastError) {
        console.log('[닥터보이스] debugger 해제 경고:', chrome.runtime.lastError.message);
      }
      currentDebuggerTabId = null;
      console.log('[닥터보이스] debugger 연결 해제됨');
      resolve();
    });
  });
}

// sleep
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// debugger 연결 해제 감지
chrome.debugger.onDetach.addListener((source, reason) => {
  console.log('[닥터보이스] debugger 연결 해제됨:', reason);
  currentDebuggerTabId = null;
});

// 탭 업데이트 감지
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;

  const url = tab.url || '';
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('Write') && !url.includes('editor')) return;

  console.log('[닥터보이스] 블로그 글쓰기 페이지 감지, tabId:', tabId);

  const stored = await chrome.storage.local.get(['pendingPost', 'autoPostEnabled']);

  if (stored.autoPostEnabled && stored.pendingPost) {
    console.log('[닥터보이스] 자동 발행 데이터 있음!');

    setTimeout(async () => {
      try {
        await chrome.tabs.sendMessage(tabId, {
          action: 'INSERT_POST',
          data: stored.pendingPost
        });
        console.log('[닥터보이스] INSERT_POST 메시지 전송 완료');
      } catch (e) {
        console.log('[닥터보이스] 메시지 전송 실패:', e.message);
        // 재시도
        setTimeout(async () => {
          try {
            await chrome.tabs.sendMessage(tabId, {
              action: 'INSERT_POST',
              data: stored.pendingPost
            });
          } catch (e2) {
            console.log('[닥터보이스] 재시도 실패:', e2.message);
          }
        }, 2000);
      }
    }, 3000);
  }
});

// 서비스 워커 유지
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {});
