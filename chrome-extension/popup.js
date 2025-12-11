// 팝업 스크립트 - 닥터보이스 프로 v8.0 - 자동 발행 방식
document.addEventListener('DOMContentLoaded', async () => {
  const statusCard = document.getElementById('statusCard');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');
  const btnFetchPosts = document.getElementById('btnFetchPosts');
  const btnPost = document.getElementById('btnPost');
  const btnCopyOnly = document.getElementById('btnCopyOnly');
  const postList = document.getElementById('postList');

  let savedPosts = [];
  let selectedPost = null;

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
        setStatus('success', '준비 완료', `${posts.length}개의 글 - 선택 후 복사하세요`);
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
        btnPost.disabled = false;
        btnCopyOnly.disabled = false;

        const title = selectedPost.title || (selectedPost.suggested_titles && selectedPost.suggested_titles[0]) || '(제목 없음)';
        setStatus('success', '글 선택됨', `"${title}" - 발행 버튼을 클릭하세요`);
      });
    });
  }

  // 자동 발행 버튼 (네이버 로그인 → 자동 입력)
  btnPost.addEventListener('click', async () => {
    if (!selectedPost) {
      setStatus('error', '오류', '발행할 글을 선택하세요');
      return;
    }

    const title = selectedPost.title || (selectedPost.suggested_titles && selectedPost.suggested_titles[0]) || '';
    const content = selectedPost.content || selectedPost.generated_content || '';
    const images = selectedPost.images || [];

    try {
      setStatus('warning', '준비 중...', '네이버 로그인 페이지로 이동합니다...');
      btnPost.textContent = '🔄 이동 중...';
      btnPost.disabled = true;

      // 데이터 저장 (content-naver.js에서 사용)
      await chrome.storage.local.set({
        pendingPost: {
          title: title,
          content: content,
          images: images
        },
        postOptions: { useQuote: true, useHighlight: true, useImages: true },
        autoPostEnabled: true
      });

      // 네이버 로그인 페이지로 이동 (로그인 후 자동으로 글쓰기 페이지로 리다이렉트)
      const tab = await chrome.tabs.create({
        url: 'https://nid.naver.com/nidlogin.login?url=https://blog.naver.com/GoBlogWrite.naver',
        active: true
      });

      // 로그인 탭 ID 저장 (로그인 완료 후 자동 감지용)
      await chrome.storage.local.set({ loginTabId: tab.id });

      setStatus('success', '✅ 이동 완료!', '로그인 후 자동으로 글이 입력됩니다');

    } catch (error) {
      console.error('Post error:', error);
      setStatus('error', '발행 실패', '다시 시도해주세요');
      btnPost.textContent = '🚀 네이버 블로그 발행';
      btnPost.disabled = false;
    }
  });

  // 클립보드만 복사 버튼 (수동 붙여넣기용)
  btnCopyOnly.addEventListener('click', async () => {
    if (!selectedPost) {
      setStatus('error', '오류', '복사할 글을 선택하세요');
      return;
    }

    const title = selectedPost.title || (selectedPost.suggested_titles && selectedPost.suggested_titles[0]) || '';
    const content = selectedPost.content || selectedPost.generated_content || '';
    const images = selectedPost.images || [];

    try {
      setStatus('warning', '준비 중...', '클립보드에 복사하는 중...');

      // 이미지가 있으면 HTML 형식으로 복사 (이미지 포함)
      if (images.length > 0) {
        const html = await createHtmlWithImages(title, content, images);
        await copyHtmlToClipboard(html, title + '\n\n' + content);
      } else {
        // 이미지 없으면 텍스트만 복사
        await navigator.clipboard.writeText(title + '\n\n' + content);
      }

      // 데이터 저장 (content-naver.js에서 사용)
      await chrome.storage.local.set({
        pendingPost: {
          title: title,
          content: content,
          images: images
        },
        autoPasteEnabled: true
      });

      setStatus('success', '✅ 복사 완료!', '네이버 블로그에서 Ctrl+V로 붙여넣기 하세요');

      // 네이버 블로그 글쓰기 페이지로 이동
      chrome.tabs.create({
        url: 'https://blog.naver.com/GoBlogWrite.naver',
        active: true
      });

    } catch (error) {
      console.error('Clipboard error:', error);
      setStatus('error', '복사 실패', '다시 시도해주세요');
    }
  });

  // 이미지 포함 HTML 생성
  async function createHtmlWithImages(title, content, images) {
    const paragraphs = content.split('\n').filter(p => p.trim());
    let html = `<h2>${escapeHtml(title)}</h2>`;

    // 이미지 배치 간격 계산
    const imageInterval = Math.max(1, Math.floor(paragraphs.length / (images.length + 1)));
    let imageIndex = 0;

    for (let i = 0; i < paragraphs.length; i++) {
      html += `<p>${escapeHtml(paragraphs[i])}</p>`;

      // 이미지 삽입
      if (imageIndex < images.length && (i + 1) % imageInterval === 0) {
        const imgSrc = images[imageIndex];
        html += `<p><img src="${imgSrc}" style="max-width:100%;height:auto;"></p>`;
        imageIndex++;
      }
    }

    // 남은 이미지 추가
    while (imageIndex < images.length) {
      html += `<p><img src="${images[imageIndex]}" style="max-width:100%;height:auto;"></p>`;
      imageIndex++;
    }

    return html;
  }

  // HTML을 클립보드에 복사 (이미지 포함)
  async function copyHtmlToClipboard(html, plainText) {
    try {
      const blob = new Blob([html], { type: 'text/html' });
      const textBlob = new Blob([plainText], { type: 'text/plain' });

      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': blob,
          'text/plain': textBlob
        })
      ]);
      console.log('HTML clipboard copy success');
    } catch (e) {
      console.log('HTML clipboard failed, falling back to text:', e);
      await navigator.clipboard.writeText(plainText);
    }
  }

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

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
});
