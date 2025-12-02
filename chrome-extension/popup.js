// 팝업 스크립트 - 닥터보이스 프로 저장된 글 → 네이버 블로그 포스팅
document.addEventListener('DOMContentLoaded', async () => {
  const statusCard = document.getElementById('statusCard');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');
  const progress = document.getElementById('progress');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const btnFetchPosts = document.getElementById('btnFetchPosts');
  const btnPost = document.getElementById('btnPost');
  const postList = document.getElementById('postList');
  const optionsCard = document.getElementById('optionsCard');
  const loginCard = document.getElementById('loginCard');
  const naverId = document.getElementById('naverId');
  const naverPw = document.getElementById('naverPw');
  const saveLogin = document.getElementById('saveLogin');

  let savedPosts = [];
  let selectedPost = null;

  // 저장된 로그인 정보 로드
  const stored = await chrome.storage.local.get(['naverCredentials']);
  if (stored.naverCredentials) {
    naverId.value = stored.naverCredentials.id || '';
    naverPw.value = stored.naverCredentials.pw || '';
    saveLogin.checked = true;
  }

  // 페이지 로드 시 자동으로 저장된 글 불러오기
  autoLoadPosts();

  // 자동 불러오기 함수
  async function autoLoadPosts() {
    try {
      setStatus('warning', '불러오는 중...', '저장된 글을 확인하고 있습니다');
      const posts = await fetchSavedPostsFromDoctorVoice();

      if (posts && posts.length > 0) {
        savedPosts = posts;
        displayPosts(posts);
        setStatus('success', '준비 완료', `${posts.length}개의 글 - 선택하세요`);
      } else {
        postList.innerHTML = '<div class="no-posts">저장된 글이 없습니다<br><small>닥터보이스 프로에서 글을 저장하세요</small></div>';
        setStatus('warning', '저장된 글 없음', '닥터보이스 프로에서 글을 저장하세요');
      }
    } catch (error) {
      console.log('Auto load error:', error);
      postList.innerHTML = '<div class="no-posts">닥터보이스 프로 탭을 열어주세요<br><small>localhost 또는 vercel.app</small></div>';
      setStatus('warning', '연결 필요', '닥터보이스 프로 탭을 열고 새로고침');
    }
  }

  // 새로고침 버튼
  btnFetchPosts.addEventListener('click', async () => {
    btnFetchPosts.disabled = true;
    btnFetchPosts.textContent = '불러오는 중...';
    await autoLoadPosts();
    btnFetchPosts.disabled = false;
    btnFetchPosts.textContent = '새로고침';
  });

  // 저장된 글 목록 표시
  function displayPosts(posts) {
    if (!posts || posts.length === 0) {
      postList.innerHTML = '<div class="no-posts">저장된 글이 없습니다</div>';
      return;
    }

    postList.innerHTML = posts.map((post, index) => {
      const title = post.title || (post.suggested_titles && post.suggested_titles[0]) || '(제목 없음)';
      const content = post.content || post.generated_content || '';
      const date = post.savedAt ? new Date(post.savedAt).toLocaleDateString('ko-KR') : '';

      return `
        <div class="post-item" data-index="${index}">
          <div class="post-item-title">${escapeHtml(title)}</div>
          <div class="post-item-meta">${content.length}자 · ${date}</div>
        </div>
      `;
    }).join('');

    // 클릭 이벤트 추가
    postList.querySelectorAll('.post-item').forEach(item => {
      item.addEventListener('click', () => {
        postList.querySelectorAll('.post-item').forEach(i => i.classList.remove('selected'));
        item.classList.add('selected');

        const index = parseInt(item.dataset.index);
        selectedPost = savedPosts[index];

        loginCard.style.display = 'block';
        optionsCard.style.display = 'block';
        btnPost.disabled = false;

        const title = selectedPost.title || (selectedPost.suggested_titles && selectedPost.suggested_titles[0]) || '(제목 없음)';
        setStatus('success', '글 선택됨', `"${title}"`);
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

    // 로그인 정보 저장
    if (saveLogin.checked) {
      await chrome.storage.local.set({ naverCredentials: { id, pw } });
    }

    const options = {
      useQuote: document.getElementById('optQuote').checked,
      useHighlight: document.getElementById('optHighlight').checked,
      saveDraft: document.getElementById('optDraft').checked,
      useImages: true
    };

    // 포스트 데이터 준비 - selectedPost에서 직접 가져옴 (이미지 포함)
    const postData = {
      title: selectedPost.title || (selectedPost.suggested_titles && selectedPost.suggested_titles[0]) || '',
      content: selectedPost.content || selectedPost.generated_content || '',
      images: selectedPost.images || [] // localStorage에서 가져온 이미지 Base64 데이터
    };

    console.log('Post data prepared:', postData.title, 'images:', postData.images?.length || 0);

    btnPost.disabled = true;
    showProgress(true);

    try {
      // 1. 데이터 저장 (background에서 사용)
      updateProgress(10, '데이터 저장 중...');
      await chrome.storage.local.set({
        pendingPost: postData,
        postOptions: options,
        autoPostEnabled: true
      });

      // 2. 네이버 로그인 페이지 열기
      updateProgress(20, '네이버 로그인 페이지 열기...');
      const loginTab = await chrome.tabs.create({
        url: 'https://nid.naver.com/nidlogin.login',
        active: true
      });

      // 3. 탭 로딩 대기
      await waitForTabLoad(loginTab.id);
      await sleep(1500);

      // 4. background에 탭 ID 전달
      updateProgress(30, '로그인 정보 입력 중...');
      chrome.runtime.sendMessage({
        action: 'START_POSTING',
        tabId: loginTab.id
      });

      // 5. 로그인 정보 입력
      await chrome.scripting.executeScript({
        target: { tabId: loginTab.id },
        func: performNaverLogin,
        args: [id, pw]
      });

      updateProgress(50, '로그인 버튼 클릭 후 자동 진행됩니다');
      setStatus('success', '로그인 대기 중', '로그인 완료 후 자동으로 글쓰기 페이지로 이동합니다');

      // 팝업은 여기서 닫혀도 됨 - background가 나머지 처리
      setTimeout(() => {
        showProgress(false);
        btnPost.disabled = false;
      }, 3000);

    } catch (error) {
      console.error('Posting error:', error);
      setStatus('error', '오류 발생', error.message || '포스팅 중 오류가 발생했습니다');
      btnPost.disabled = false;
      showProgress(false);
    }
  });

  // 닥터보이스 프로에서 저장된 글 가져오기
  async function fetchSavedPostsFromDoctorVoice() {
    const tabs = await chrome.tabs.query({});
    console.log('Found tabs:', tabs.length);

    // 닥터보이스 프로 탭 찾기
    const doctorVoiceTab = tabs.find(tab =>
      tab.url && (
        tab.url.includes('localhost') ||
        tab.url.includes('vercel.app') ||
        tab.url.includes('doctor-voice')
      )
    );

    if (!doctorVoiceTab) {
      throw new Error('닥터보이스 프로 탭이 열려있지 않습니다');
    }

    console.log('Found tab:', doctorVoiceTab.url);

    // localStorage에서 저장된 글 가져오기
    const result = await chrome.scripting.executeScript({
      target: { tabId: doctorVoiceTab.id },
      func: () => {
        const saved = localStorage.getItem('saved-posts');
        console.log('saved-posts:', saved);
        if (!saved) {
          return [];
        }
        return JSON.parse(saved);
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

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
      // 타임아웃
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }, 15000);
    });
  }
});

// 네이버 로그인 함수 (로그인 페이지에서 실행)
function performNaverLogin(id, pw) {
  console.log('[닥터보이스] 로그인 정보 입력 시작');

  // 입력 필드 찾기
  const idInput = document.querySelector('#id');
  const pwInput = document.querySelector('#pw');

  if (!idInput || !pwInput) {
    console.error('[닥터보이스] 로그인 입력 필드를 찾을 수 없습니다');
    return;
  }

  // 아이디 입력 (클릭 → 포커스 → 값 설정 → 이벤트)
  idInput.click();
  idInput.focus();
  idInput.value = id;
  idInput.dispatchEvent(new Event('input', { bubbles: true }));
  idInput.dispatchEvent(new Event('change', { bubbles: true }));
  idInput.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));

  // 비밀번호 입력 (약간의 딜레이 후)
  setTimeout(() => {
    pwInput.click();
    pwInput.focus();
    pwInput.value = pw;
    pwInput.dispatchEvent(new Event('input', { bubbles: true }));
    pwInput.dispatchEvent(new Event('change', { bubbles: true }));
    pwInput.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));

    console.log('[닥터보이스] 로그인 정보 입력 완료');

    // 로그인 버튼 자동 클릭 시도
    setTimeout(() => {
      const loginBtn = document.querySelector('.btn_login') ||
                       document.querySelector('#log\\.login') ||
                       document.querySelector('button[type="submit"]') ||
                       document.querySelector('input[type="submit"]');

      if (loginBtn) {
        console.log('[닥터보이스] 로그인 버튼 클릭');
        loginBtn.click();
      } else {
        console.log('[닥터보이스] 로그인 버튼을 찾을 수 없음 - 수동 클릭 필요');
      }
    }, 500);
  }, 300);
}
