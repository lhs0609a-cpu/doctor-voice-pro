// 팝업 스크립트 - 닥터보이스 프로 v11.0 - 단순화 버전
document.addEventListener('DOMContentLoaded', async () => {
  const statusIcon = document.getElementById('statusIcon');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');
  const btnPublish = document.getElementById('btnPublish');
  const btnOpenSite = document.getElementById('btnOpenSite');
  const postPreview = document.getElementById('postPreview');
  const postTitle = document.getElementById('postTitle');
  const postLength = document.getElementById('postLength');
  const postImages = document.getElementById('postImages');

  // 저장된 데이터 확인
  checkPendingPost();

  // 발행 버튼 클릭
  btnPublish.addEventListener('click', async () => {
    const stored = await chrome.storage.local.get(['pendingPost', 'postOptions']);

    if (!stored.pendingPost) {
      setStatus('error', '❌', '발행할 글 없음', '웹사이트에서 글을 선택해주세요');
      return;
    }

    // 자동 발행 활성화
    await chrome.storage.local.set({ autoPostEnabled: true });

    // 네이버 블로그 글쓰기 페이지로 이동
    const tab = await chrome.tabs.create({
      url: 'https://blog.naver.com/GoBlogWrite.naver',
      active: true
    });

    // 탭 ID 저장
    await chrome.storage.local.set({ blogTabId: tab.id });

    setStatus('ready', '✅', '발행 시작!', '네이버 블로그에서 글이 자동 입력됩니다');

    // 팝업 닫기
    setTimeout(() => window.close(), 1000);
  });

  // 웹사이트 열기 버튼
  btnOpenSite.addEventListener('click', () => {
    chrome.tabs.create({
      url: 'https://doctor-voice-pro-ghwi.vercel.app/dashboard/saved',
      active: true
    });
  });

  // 저장된 발행 데이터 확인
  async function checkPendingPost() {
    try {
      const stored = await chrome.storage.local.get(['pendingPost', 'postOptions']);

      if (stored.pendingPost && stored.pendingPost.title) {
        // 발행할 글이 있음
        const post = stored.pendingPost;

        postPreview.style.display = 'block';
        postTitle.textContent = post.title || '(제목 없음)';
        postLength.textContent = (post.content?.length || 0) + '자';
        postImages.textContent = '이미지 ' + (post.imageUrls?.length || post.images?.length || 0) + '개';

        setStatus('ready', '✅', '발행 준비 완료!', '아래 버튼을 클릭하여 발행하세요');
        btnPublish.disabled = false;
      } else {
        // 발행할 글 없음 - 웹사이트에서 localStorage 확인
        await checkWebsiteData();
      }
    } catch (error) {
      console.error('데이터 확인 오류:', error);
      setStatus('error', '⚠️', '오류 발생', '다시 시도해주세요');
    }
  }

  // 웹사이트의 localStorage에서 데이터 가져오기
  async function checkWebsiteData() {
    try {
      const tabs = await chrome.tabs.query({});

      // 닥터보이스 프로 탭 찾기
      const doctorVoiceTab = tabs.find(tab =>
        tab.url && (
          tab.url.includes('localhost') ||
          tab.url.includes('vercel.app') ||
          tab.url.includes('doctor-voice')
        )
      );

      if (!doctorVoiceTab) {
        setStatus('waiting', '⏳', '대기 중', '닥터보이스 프로 웹사이트를 열어주세요');
        return;
      }

      // localStorage에서 발행 대기 데이터 확인
      const result = await chrome.scripting.executeScript({
        target: { tabId: doctorVoiceTab.id },
        func: () => {
          const pending = localStorage.getItem('doctorvoice-pending-post');
          return pending ? JSON.parse(pending) : null;
        }
      });

      const pendingPost = result?.[0]?.result;

      if (pendingPost && pendingPost.title) {
        // 데이터를 chrome.storage에 저장
        await chrome.storage.local.set({
          pendingPost: pendingPost,
          postOptions: { useQuote: true, useHighlight: true, useImages: true }
        });

        postPreview.style.display = 'block';
        postTitle.textContent = pendingPost.title || '(제목 없음)';
        postLength.textContent = (pendingPost.content?.length || 0) + '자';
        postImages.textContent = '이미지 ' + (pendingPost.imageUrls?.length || pendingPost.images?.length || 0) + '개';

        setStatus('ready', '✅', '발행 준비 완료!', '아래 버튼을 클릭하여 발행하세요');
        btnPublish.disabled = false;
      } else {
        setStatus('waiting', '⏳', '대기 중', '웹사이트에서 "네이버 블로그에 발행" 클릭');
      }

    } catch (error) {
      console.log('웹사이트 데이터 확인 실패:', error);
      setStatus('waiting', '⏳', '대기 중', '웹사이트에서 글을 선택해주세요');
    }
  }

  // 상태 업데이트
  function setStatus(type, icon, title, desc) {
    statusIcon.className = 'status-icon ' + type;
    statusIcon.textContent = icon;
    statusTitle.textContent = title;
    statusDesc.innerHTML = desc;
  }
});
