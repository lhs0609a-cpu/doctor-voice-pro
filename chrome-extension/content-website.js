// 닥터보이스 프로 웹사이트용 Content Script
// 확장 프로그램 ID를 웹사이트에 자동으로 전달

console.log('[닥터보이스 확장] 웹사이트 연결 스크립트 로드됨');

// 확장 프로그램 ID를 웹사이트에 알려주기
function injectExtensionId() {
  const extensionId = chrome.runtime.id;
  console.log('[닥터보이스 확장] Extension ID:', extensionId);

  // localStorage에 확장 프로그램 ID 저장
  localStorage.setItem('doctorvoice-extension-id', extensionId);

  // 웹사이트에 메시지 전송
  window.postMessage({
    type: 'DOCTORVOICE_EXTENSION_READY',
    extensionId: extensionId,
    version: '10.1.0'
  }, '*');

  // DOM에 표시용 요소 추가 (선택적)
  const indicator = document.createElement('div');
  indicator.id = 'doctorvoice-extension-indicator';
  indicator.style.cssText = 'display: none;';
  indicator.dataset.extensionId = extensionId;
  indicator.dataset.version = '10.1.0';
  document.body.appendChild(indicator);

  console.log('[닥터보이스 확장] 웹사이트에 연결 완료!');
}

// 웹사이트에서 발행 요청 수신
window.addEventListener('message', async (event) => {
  if (event.source !== window) return;

  const message = event.data;

  // 발행 데이터 전달 요청
  if (message.type === 'DOCTORVOICE_PUBLISH_REQUEST') {
    console.log('[닥터보이스 확장] 발행 요청 수신:', message.data?.title);

    try {
      // chrome.storage.local에 데이터 저장
      await chrome.storage.local.set({
        pendingPost: message.data,
        postOptions: message.options || { useQuote: true, useHighlight: true, useImages: true },
        autoPostEnabled: true
      });

      // 성공 응답
      window.postMessage({
        type: 'DOCTORVOICE_PUBLISH_RESPONSE',
        success: true,
        message: '데이터 저장 완료'
      }, '*');

      console.log('[닥터보이스 확장] 발행 데이터 저장 완료!');

    } catch (error) {
      console.error('[닥터보이스 확장] 오류:', error);
      window.postMessage({
        type: 'DOCTORVOICE_PUBLISH_RESPONSE',
        success: false,
        error: error.message
      }, '*');
    }
  }

  // 네이버 블로그 열기 요청
  if (message.type === 'DOCTORVOICE_OPEN_BLOG') {
    console.log('[닥터보이스 확장] 네이버 블로그 열기 요청');

    chrome.runtime.sendMessage({
      action: 'OPEN_NAVER_BLOG'
    });
  }
});

// 페이지 로드 완료 후 실행
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectExtensionId);
} else {
  injectExtensionId();
}

// 주기적으로 연결 상태 확인 (SPA 대응)
setInterval(() => {
  const existingIndicator = document.getElementById('doctorvoice-extension-indicator');
  if (!existingIndicator) {
    injectExtensionId();
  }
}, 3000);
