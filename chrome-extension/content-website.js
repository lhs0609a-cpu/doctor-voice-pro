// 닥터보이스 웹사이트용 Content Script v11.0 - 단순화
console.log('[닥터보이스] 웹사이트 스크립트 v11.0 로드');

const EXTENSION_ID = chrome.runtime.id;

// 확장 프로그램 연결 표시
function showExtensionConnected() {
  // localStorage에 확장 프로그램 ID 저장
  localStorage.setItem('doctorvoice-extension-id', EXTENSION_ID);

  // DOM에 연결 표시
  let indicator = document.getElementById('doctorvoice-extension-connected');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'doctorvoice-extension-connected';
    indicator.style.display = 'none';
    indicator.dataset.extensionId = EXTENSION_ID;
    document.body.appendChild(indicator);
  }

  console.log('[닥터보이스] 확장 프로그램 연결됨, ID:', EXTENSION_ID);
}

// localStorage 변화 감지해서 발행 요청 처리
function checkForPublishRequest() {
  const pendingPost = localStorage.getItem('doctorvoice-pending-post');
  const autoPublish = localStorage.getItem('doctorvoice-auto-publish');

  if (pendingPost && autoPublish === 'true') {
    console.log('[닥터보이스] 발행 요청 감지!');

    try {
      const postData = JSON.parse(pendingPost);
      console.log('[닥터보이스] 제목:', postData.title);
      console.log('[닥터보이스] 이미지:', postData.imageUrls?.length || 0, '개');

      // 플래그 초기화 (중복 방지)
      localStorage.removeItem('doctorvoice-auto-publish');

      // chrome.storage.local에 저장
      chrome.storage.local.set({
        pendingPost: postData,
        autoPostEnabled: true
      }, () => {
        console.log('[닥터보이스] chrome.storage에 저장 완료');

        // 네이버 블로그 열기
        window.open('https://blog.naver.com/GoBlogWrite.naver', '_blank');
      });

    } catch (e) {
      console.error('[닥터보이스] 발행 데이터 파싱 오류:', e);
    }
  }
}

// 초기화
showExtensionConnected();

// 1초마다 발행 요청 확인
setInterval(checkForPublishRequest, 1000);

// storage 이벤트로도 감지
window.addEventListener('storage', (e) => {
  if (e.key === 'doctorvoice-auto-publish' && e.newValue === 'true') {
    console.log('[닥터보이스] storage 이벤트로 발행 요청 감지');
    setTimeout(checkForPublishRequest, 100);
  }
});

console.log('[닥터보이스] 웹사이트 스크립트 초기화 완료');
