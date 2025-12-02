// 네이버 로그인 감지 및 자동 이동 스크립트
console.log('[닥터보이스] 로그인 감지 스크립트 로드됨');

// 저장된 포스트 데이터가 있는지 확인
async function checkPendingPost() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['pendingPost', 'autoPostEnabled'], (result) => {
      resolve(result);
    });
  });
}

// 로그인 상태 확인
function isLoggedIn() {
  // 네이버 메인 페이지에서 로그인 상태 확인
  const loginArea = document.querySelector('.MyView-module__link_login___HpHMW');
  const logoutBtn = document.querySelector('.MyView-module__link_logout___HLmhi');
  const profileArea = document.querySelector('.MyView-module__item_my___Uw5Ym');
  const blogLink = document.querySelector('a[href*="blog.naver.com"]');

  // 로그인 버튼이 없거나, 로그아웃 버튼/프로필이 있으면 로그인된 상태
  return !loginArea || logoutBtn || profileArea || blogLink;
}

// 로그인 성공 감지 (로그인 페이지에서)
function detectLoginSuccess() {
  const url = window.location.href;

  // 로그인 페이지에서 리다이렉트 감지
  if (url.includes('nid.naver.com')) {
    // 로그인 폼이 없어지면 로그인 성공
    const loginForm = document.querySelector('#frmNIDLogin, .login_form, #login_form');

    if (!loginForm) {
      console.log('[닥터보이스] 로그인 성공 감지 (폼 없음)');
      return true;
    }

    // 에러 메시지가 없고, 리다이렉트 중이면 성공
    const errorMsg = document.querySelector('.error_message, .err_msg');
    if (!errorMsg) {
      // 페이지가 변경되는지 확인
      return false;
    }
  }

  return false;
}

// 블로그 글쓰기 페이지로 이동
async function goToBlogWrite() {
  const { pendingPost, autoPostEnabled } = await checkPendingPost();

  if (pendingPost && autoPostEnabled) {
    console.log('[닥터보이스] 저장된 포스트 있음, 글쓰기 페이지로 이동');
    showNotification('블로그 글쓰기 페이지로 이동합니다...');

    setTimeout(() => {
      window.location.href = 'https://blog.naver.com/GoBlogWrite.naver';
    }, 1500);

    return true;
  }

  return false;
}

// 알림 표시
function showNotification(message) {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 16px 24px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    z-index: 999999;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);

  setTimeout(() => notification.remove(), 3000);
}

// 메인 로직
async function main() {
  const url = window.location.href;

  // 네이버 메인 페이지에서 로그인 상태 확인
  if (url.includes('www.naver.com') || url === 'https://naver.com/') {
    console.log('[닥터보이스] 네이버 메인 페이지 감지');

    // 잠시 대기 후 로그인 상태 확인
    setTimeout(async () => {
      if (isLoggedIn()) {
        console.log('[닥터보이스] 로그인 상태 확인됨');
        await goToBlogWrite();
      }
    }, 1000);
  }

  // 로그인 페이지에서 로그인 성공 감지
  if (url.includes('nid.naver.com')) {
    console.log('[닥터보이스] 로그인 페이지 감지');

    // URL 변경 감지 (로그인 성공 시 리다이렉트)
    let lastUrl = url;
    const observer = new MutationObserver(async () => {
      if (window.location.href !== lastUrl) {
        lastUrl = window.location.href;
        console.log('[닥터보이스] URL 변경 감지:', lastUrl);

        // 로그인 성공 후 리다이렉트된 경우
        if (!lastUrl.includes('nid.naver.com')) {
          await goToBlogWrite();
        }
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // 페이지 언로드 시에도 확인
    window.addEventListener('beforeunload', async () => {
      const { pendingPost, autoPostEnabled } = await checkPendingPost();
      if (pendingPost && autoPostEnabled) {
        // storage에 이동 플래그 저장
        chrome.storage.local.set({ shouldNavigateToWrite: true });
      }
    });
  }
}

// 페이지 로드 시 실행
if (document.readyState === 'complete') {
  main();
} else {
  window.addEventListener('load', main);
}

// 히스토리 변경 감지 (SPA 대응)
window.addEventListener('popstate', main);
