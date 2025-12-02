// 팝업 스크립트 - 네이버 자동 로그인 및 포스팅
document.addEventListener('DOMContentLoaded', async () => {
  // DOM 요소
  const statusCard = document.getElementById('statusCard');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');
  const progress = document.getElementById('progress');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const btnFetchPosts = document.getElementById('btnFetchPosts');
  const btnPost = document.getElementById('btnPost');
  const postsCard = document.getElementById('postsCard');
  const postList = document.getElementById('postList');
  const optionsCard = document.getElementById('optionsCard');
  const naverId = document.getElementById('naverId');
  const naverPw = document.getElementById('naverPw');
  const saveLogin = document.getElementById('saveLogin');

  let savedPosts = [];
  let selectedPost = null;

  // 저장된 로그인 정보 로드
  const stored = await chrome.storage.local.get(['naverCredentials', 'savedPosts']);
  if (stored.naverCredentials) {
    naverId.value = stored.naverCredentials.id || '';
    naverPw.value = stored.naverCredentials.pw || '';
    saveLogin.checked = true;
  }

  // 저장된 글 불러오기 버튼
  btnFetchPosts.addEventListener('click', async () => {
    const id = naverId.value.trim();
    const pw = naverPw.value.trim();

    if (!id || !pw) {
      setStatus('error', '오류', '네이버 아이디와 비밀번호를 입력하세요');
      return;
    }

    // 로그인 정보 저장 옵션
    if (saveLogin.checked) {
      await chrome.storage.local.set({
        naverCredentials: { id, pw }
      });
    } else {
      await chrome.storage.local.remove(['naverCredentials']);
    }

    btnFetchPosts.disabled = true;
    showProgress(true);
    updateProgress(10, '닥터보이스 프로에서 저장된 글 불러오는 중...');

    try {
      // 닥터보이스 프로 탭에서 저장된 글 가져오기
      const posts = await fetchSavedPostsFromDoctorVoice();

      if (posts && posts.length > 0) {
        savedPosts = posts;
        displayPosts(posts);
        postsCard.style.display = 'block';
        updateProgress(100, '저장된 글 불러오기 완료!');
        setStatus('success', '불러오기 완료', `${posts.length}개의 저장된 글을 찾았습니다`);
      } else {
        setStatus('warning', '저장된 글 없음', '닥터보이스 프로에 저장된 글이 없습니다');
      }
    } catch (error) {
      console.error('Error fetching posts:', error);
      setStatus('error', '오류 발생', error.message || '저장된 글을 불러올 수 없습니다');
    }

    btnFetchPosts.disabled = false;
    setTimeout(() => showProgress(false), 1500);
  });

  // 저장된 글 목록 표시
  function displayPosts(posts) {
    if (!posts || posts.length === 0) {
      postList.innerHTML = '<div class="no-posts">저장된 글이 없습니다</div>';
      return;
    }

    postList.innerHTML = posts.map((post, index) => `
      <div class="post-item" data-index="${index}">
        <div class="post-item-title">${post.title || post.suggested_titles?.[0] || '(제목 없음)'}</div>
        <div class="post-item-meta">
          ${(post.content || post.generated_content || '').length}자 ·
          ${new Date(post.savedAt || Date.now()).toLocaleDateString('ko-KR')}
        </div>
      </div>
    `).join('');

    // 클릭 이벤트 추가
    postList.querySelectorAll('.post-item').forEach(item => {
      item.addEventListener('click', () => {
        postList.querySelectorAll('.post-item').forEach(i => i.classList.remove('selected'));
        item.classList.add('selected');

        const index = parseInt(item.dataset.index);
        selectedPost = savedPosts[index];

        optionsCard.style.display = 'block';
        btnPost.disabled = false;

        setStatus('success', '글 선택됨', `"${selectedPost.title || selectedPost.suggested_titles?.[0] || '(제목 없음)'}"`);
      });
    });
  }

  // 포스팅 버튼
  btnPost.addEventListener('click', async () => {
    if (!selectedPost) {
      setStatus('error', '오류', '포스팅할 글을 선택하세요');
      return;
    }

    const id = naverId.value.trim();
    const pw = naverPw.value.trim();

    if (!id || !pw) {
      setStatus('error', '오류', '네이버 로그인 정보를 입력하세요');
      return;
    }

    const options = {
      useQuote: document.getElementById('optQuote').checked,
      useHighlight: document.getElementById('optHighlight').checked,
      useImages: document.getElementById('optImages').checked,
      saveDraft: document.getElementById('optDraft').checked
    };

    btnPost.disabled = true;
    showProgress(true);

    try {
      // 1단계: 네이버 로그인
      updateProgress(10, '네이버 로그인 중...');
      const loginTab = await chrome.tabs.create({
        url: 'https://nid.naver.com/nidlogin.login',
        active: true
      });

      await waitForTabLoad(loginTab.id);
      await sleep(1000);

      // 로그인 스크립트 실행
      await chrome.scripting.executeScript({
        target: { tabId: loginTab.id },
        func: performNaverLogin,
        args: [id, pw]
      });

      updateProgress(30, '로그인 처리 중...');
      await sleep(3000);

      // 2단계: 블로그 글쓰기 페이지로 이동
      updateProgress(50, '블로그 글쓰기 페이지 열기...');
      await chrome.tabs.update(loginTab.id, {
        url: 'https://blog.naver.com/PostWriteForm.naver'
      });

      await waitForTabLoad(loginTab.id);
      await sleep(3000);

      // 3단계: 글 작성
      updateProgress(70, '글 입력 중...');

      const postData = {
        title: selectedPost.title || selectedPost.suggested_titles?.[0] || '',
        content: selectedPost.content || selectedPost.generated_content || '',
        images: selectedPost.images || []
      };

      await chrome.tabs.sendMessage(loginTab.id, {
        action: 'INSERT_POST',
        data: postData,
        options: options
      });

      updateProgress(100, '포스팅 완료!');
      setStatus('success', '포스팅 완료', '네이버 블로그 탭에서 내용을 확인하세요');

    } catch (error) {
      console.error('Posting error:', error);
      setStatus('error', '오류 발생', error.message || '포스팅 중 오류가 발생했습니다');
    }

    btnPost.disabled = false;
    setTimeout(() => showProgress(false), 2000);
  });

  // 닥터보이스 프로에서 저장된 글 가져오기
  async function fetchSavedPostsFromDoctorVoice() {
    // 현재 열린 닥터보이스 프로 탭 찾기
    const tabs = await chrome.tabs.query({});
    let doctorVoiceTab = tabs.find(tab =>
      tab.url && (
        tab.url.includes('doctor-voice-pro') ||
        tab.url.includes('localhost:3000') ||
        tab.url.includes('localhost:3001') ||
        tab.url.includes('vercel.app')
      )
    );

    if (!doctorVoiceTab) {
      // 닥터보이스 프로 탭이 없으면 새로 열기
      doctorVoiceTab = await chrome.tabs.create({
        url: 'https://frontend-pmpb971xv-fewfs-projects-83cc0821.vercel.app/dashboard/saved',
        active: false
      });
      await waitForTabLoad(doctorVoiceTab.id);
      await sleep(2000);
    }

    // localStorage에서 저장된 글 가져오기
    const result = await chrome.scripting.executeScript({
      target: { tabId: doctorVoiceTab.id },
      func: () => {
        const saved = localStorage.getItem('saved-posts');
        return saved ? JSON.parse(saved) : [];
      }
    });

    return result?.[0]?.result || [];
  }

  // 유틸리티 함수들
  function setStatus(type, title, desc) {
    statusCard.className = `card status-card ${type}`;
    statusTitle.textContent = title;
    statusDesc.textContent = desc;
  }

  function showProgress(show) {
    progress.classList.toggle('active', show);
  }

  function updateProgress(percent, text) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = text;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function waitForTabLoad(tabId) {
    return new Promise((resolve) => {
      const listener = (updatedTabId, changeInfo) => {
        if (updatedTabId === tabId && changeInfo.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);

      // 타임아웃 설정
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }, 30000);
    });
  }
});

// 네이버 로그인 함수 (content script에서 실행됨)
function performNaverLogin(id, pw) {
  return new Promise((resolve, reject) => {
    try {
      const idInput = document.querySelector('#id');
      const pwInput = document.querySelector('#pw');
      const loginBtn = document.querySelector('.btn_login') || document.querySelector('#log\\.login');

      if (idInput && pwInput) {
        // 입력 필드 클리어
        idInput.value = '';
        pwInput.value = '';

        // 아이디 입력 (천천히)
        idInput.focus();
        idInput.value = id;
        idInput.dispatchEvent(new Event('input', { bubbles: true }));

        setTimeout(() => {
          // 비밀번호 입력
          pwInput.focus();
          pwInput.value = pw;
          pwInput.dispatchEvent(new Event('input', { bubbles: true }));

          setTimeout(() => {
            // 로그인 버튼 클릭
            if (loginBtn) {
              loginBtn.click();
            }
            resolve(true);
          }, 500);
        }, 500);
      } else {
        reject(new Error('로그인 폼을 찾을 수 없습니다'));
      }
    } catch (e) {
      reject(e);
    }
  });
}
