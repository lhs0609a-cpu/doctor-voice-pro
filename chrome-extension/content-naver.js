// 네이버 블로그 스마트에디터 v11.0 - 단순화 버전
console.log('[닥터보이스] v11.0 로드 - 단순화 버전');

// 페이지 로드 시 가이드 오버레이 표시
function showGuideOverlay() {
  const url = window.location.href;
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('GoBlogWrite') && !url.includes('PostWrite') && !url.includes('Redirect=Write') && !url.includes('editor')) return;

  // 기존 가이드 제거
  const existingGuide = document.querySelector('.dv-guide-overlay');
  if (existingGuide) existingGuide.remove();

  // 가이드 오버레이 생성
  const overlay = document.createElement('div');
  overlay.className = 'dv-guide-overlay';
  overlay.innerHTML = `
    <style>
      .dv-guide-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        z-index: 999998;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.3s ease;
      }
      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
      @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
      }
      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
      .dv-guide-card {
        background: white;
        border-radius: 20px;
        padding: 32px 40px;
        max-width: 480px;
        text-align: center;
        box-shadow: 0 25px 80px rgba(0,0,0,0.4);
        animation: pulse 2s ease infinite;
      }
      .dv-guide-icon {
        width: 80px;
        height: 80px;
        margin: 0 auto 20px;
        background: linear-gradient(135deg, #10b981, #059669);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 40px;
      }
      .dv-guide-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid rgba(255,255,255,0.3);
        border-top-color: white;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
      .dv-guide-title {
        font-size: 24px;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 12px;
      }
      .dv-guide-desc {
        font-size: 16px;
        color: #6b7280;
        margin-bottom: 24px;
        line-height: 1.6;
      }
      .dv-guide-steps {
        background: #f3f4f6;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: left;
        margin-bottom: 20px;
      }
      .dv-guide-step {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 0;
        font-size: 14px;
        color: #374151;
      }
      .dv-guide-step.active {
        color: #059669;
        font-weight: 600;
      }
      .dv-guide-step.done {
        color: #9ca3af;
        text-decoration: line-through;
      }
      .dv-guide-step-num {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: #e5e7eb;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: bold;
      }
      .dv-guide-step.active .dv-guide-step-num {
        background: #10b981;
        color: white;
      }
      .dv-guide-step.done .dv-guide-step-num {
        background: #9ca3af;
        color: white;
      }
      .dv-guide-btn {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        border: none;
        padding: 14px 32px;
        border-radius: 10px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
      }
      .dv-guide-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4);
      }
      .dv-guide-btn-secondary {
        background: #f3f4f6;
        color: #374151;
        margin-left: 10px;
      }
      .dv-guide-btn-secondary:hover {
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
      }
      .dv-guide-status {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-bottom: 16px;
        padding: 12px;
        background: #fef3c7;
        border-radius: 8px;
        color: #92400e;
        font-size: 14px;
      }
      .dv-guide-status.ready {
        background: #d1fae5;
        color: #065f46;
      }
      .dv-guide-status.error {
        background: #fee2e2;
        color: #991b1b;
      }
    </style>
    <div class="dv-guide-card">
      <div class="dv-guide-icon">
        <div class="dv-guide-spinner"></div>
      </div>
      <h2 class="dv-guide-title">자동 발행 준비 중...</h2>
      <p class="dv-guide-desc">잠시만 기다려주세요.<br>글과 이미지가 자동으로 입력됩니다.</p>

      <div class="dv-guide-status" id="dv-status">
        <span>⏳</span>
        <span id="dv-status-text">데이터 확인 중...</span>
      </div>

      <div class="dv-guide-steps">
        <div class="dv-guide-step done" id="step1">
          <span class="dv-guide-step-num">✓</span>
          <span>네이버 블로그 글쓰기 페이지 열기</span>
        </div>
        <div class="dv-guide-step active" id="step2">
          <span class="dv-guide-step-num">2</span>
          <span>발행 데이터 로딩 중...</span>
        </div>
        <div class="dv-guide-step" id="step3">
          <span class="dv-guide-step-num">3</span>
          <span>제목 및 본문 자동 입력</span>
        </div>
        <div class="dv-guide-step" id="step4">
          <span class="dv-guide-step-num">4</span>
          <span>이미지 자동 삽입</span>
        </div>
      </div>

      <div>
        <button class="dv-guide-btn" id="dv-start-btn" style="display:none;">
          📝 수동으로 시작하기
        </button>
        <button class="dv-guide-btn dv-guide-btn-secondary" id="dv-close-btn">
          ✕ 닫기
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // 닫기 버튼
  document.getElementById('dv-close-btn').addEventListener('click', () => {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 300);
  });

  // 수동 시작 버튼
  document.getElementById('dv-start-btn').addEventListener('click', async () => {
    const stored = await chrome.storage.local.get(['pendingPost', 'postOptions']);
    if (stored.pendingPost) {
      overlay.remove();
      handleInsertPost(stored.pendingPost, stored.postOptions || {});
    } else {
      updateGuideStatus('error', '발행할 데이터가 없습니다. 웹사이트에서 다시 시도해주세요.');
    }
  });

  return overlay;
}

// 가이드 상태 업데이트
function updateGuideStatus(status, text) {
  const statusEl = document.getElementById('dv-status');
  const statusText = document.getElementById('dv-status-text');
  const startBtn = document.getElementById('dv-start-btn');

  if (!statusEl) return;

  statusEl.className = 'dv-guide-status ' + status;
  statusText.textContent = text;

  if (status === 'ready') {
    statusEl.querySelector('span:first-child').textContent = '✅';
  } else if (status === 'error') {
    statusEl.querySelector('span:first-child').textContent = '❌';
    if (startBtn) startBtn.style.display = 'inline-block';
  }
}

// 가이드 단계 업데이트
function updateGuideStep(stepNum, status) {
  const step = document.getElementById(`step${stepNum}`);
  if (!step) return;

  step.className = 'dv-guide-step ' + status;

  if (status === 'done') {
    step.querySelector('.dv-guide-step-num').textContent = '✓';
  } else if (status === 'active') {
    step.querySelector('.dv-guide-step-num').textContent = stepNum;
  }
}

// 가이드 제거
function removeGuideOverlay() {
  const overlay = document.querySelector('.dv-guide-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 300);
  }
}

// 메시지 수신 (background.js에서)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스] 메시지 수신:', message.action);

  if (message.action === 'INSERT_POST') {
    handleInsertPost(message.data, message.options)
      .then(() => sendResponse({ success: true }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }
});

// 전자동 글 입력 및 발행 처리
async function handleInsertPost(postData, options) {
  console.log('[닥터보이스] 전자동 발행 시작');
  console.log('[닥터보이스] 제목:', postData.title);
  console.log('[닥터보이스] 이미지 URL 수:', postData.imageUrls?.length || 0);
  console.log('[닥터보이스] 이미지 Base64 수:', postData.images?.length || 0);

  // 가이드 업데이트
  updateGuideStatus('ready', '데이터 로딩 완료! 자동 입력을 시작합니다.');
  updateGuideStep(2, 'done');
  updateGuideStep(3, 'active');

  showProgressNotification('📝 전자동 발행 시작...', 0);

  try {
    // 1. 에디터 로딩 대기
    await waitForEditor();
    await sleep(2000);
    showProgressNotification('✅ 에디터 로딩 완료', 10);
    updateGuideStatus('ready', '에디터 준비 완료! 제목을 입력합니다.');

    // 2. 제목 입력
    if (postData.title) {
      await inputTitle(postData.title);
      showProgressNotification('✅ 제목 입력 완료', 20);
      updateGuideStatus('ready', '제목 입력 완료! 본문을 입력합니다.');
      await sleep(500);
    }

    // 3. 본문 입력 (이미지 URL이 있으면 함께 삽입)
    if (postData.content) {
      updateGuideStep(3, 'done');
      updateGuideStep(4, 'active');
      updateGuideStatus('ready', '본문 입력 중... 잠시만 기다려주세요.');

      // imageUrls가 있으면 본문에 이미지 URL을 <img> 태그로 포함
      const imageUrls = postData.imageUrls || [];
      await insertContentWithImages(postData.content, imageUrls, options);
      showProgressNotification('✅ 본문 및 이미지 입력 완료', 80);
      updateGuideStep(4, 'done');
      updateGuideStatus('ready', '본문 및 이미지 입력 완료!');
      await sleep(500);
    }

    // 4. Base64 이미지 업로드 (URL이 없고 Base64만 있는 경우 - fallback)
    if ((!postData.imageUrls || postData.imageUrls.length === 0) &&
        postData.images && postData.images.length > 0 && options?.useImages) {
      const totalImages = postData.images.length;
      for (let i = 0; i < totalImages; i++) {
        showProgressNotification(`📷 이미지 업로드 중... (${i + 1}/${totalImages})`, 40 + ((i + 1) / totalImages) * 40);
        await uploadSingleImageV2(postData.images[i], i);
        await sleep(1500);
      }
      showProgressNotification('✅ 이미지 업로드 완료', 80);
    }

    // 5. 잠시 대기 후 발행 버튼 자동 클릭
    showProgressNotification('🚀 발행 준비 중...', 90);
    await sleep(1500);

    // 6. 발행 버튼 클릭 (자동 발행)
    const publishSuccess = await clickPublishButton();

    // 가이드 제거
    removeGuideOverlay();

    if (publishSuccess) {
      showProgressNotification('✅ 발행 완료!', 100);
      showBigSuccessNotification('🎉 블로그 발행 완료!', '글이 성공적으로 발행되었습니다.');
    } else {
      showProgressNotification('⚠️ 발행 버튼을 직접 클릭해주세요', 95);
      showBigSuccessNotification('✅ 글 입력 완료!', '오른쪽 상단의 녹색 "발행" 버튼을 클릭하여 발행해주세요.');
    }

    // 자동 발행 플래그 해제
    await chrome.storage.local.set({ autoPostEnabled: false });

  } catch (error) {
    console.error('[닥터보이스] 전자동 발행 오류:', error);
    updateGuideStatus('error', '오류 발생: ' + error.message);
    showNotification('❌ 오류 발생: ' + error.message);
  }
}

// 발행 버튼 자동 클릭
async function clickPublishButton() {
  console.log('[닥터보이스] 발행 버튼 찾기...');

  // 메인 문서에서 찾기 (발행 버튼은 항상 메인 페이지에 있음)
  const mainDoc = document;

  // 발행 버튼 선택자들 (네이버 스마트에디터 ONE)
  const publishSelectors = [
    'button.publish_btn__Y5mLP',              // 새 클래스명
    'button[class*="publish"]',               // publish 포함
    '.se-publish-button',
    'button.se-toolbar-button-publish',
    '#publish-btn',
    'button[data-name="publish"]',
    '.btn_publish',
    'button.btn_ok',                          // 확인 버튼
    '[class*="publish_btn"]',                 // 클래스에 publish_btn 포함
    '[class*="Publish"]',                     // 대문자 Publish
  ];

  let publishBtn = null;

  // 선택자로 찾기
  for (const selector of publishSelectors) {
    publishBtn = mainDoc.querySelector(selector);
    if (publishBtn) {
      console.log('[닥터보이스] 발행 버튼 발견 (선택자):', selector);
      break;
    }
  }

  // 텍스트로 찾기
  if (!publishBtn) {
    const allButtons = mainDoc.querySelectorAll('button, a.btn, span[role="button"], a[class*="btn"]');
    for (const btn of allButtons) {
      const text = btn.textContent?.trim() || '';
      if (text === '발행' || text === '발행하기' || text === '등록' || text === '올리기') {
        publishBtn = btn;
        console.log('[닥터보이스] 발행 버튼 발견 (텍스트):', text);
        break;
      }
    }
  }

  // 오른쪽 상단의 녹색 발행 버튼 찾기
  if (!publishBtn) {
    const greenButtons = mainDoc.querySelectorAll('[style*="background"][style*="green"], [style*="#03c75a"], .btn_publish, [class*="green"]');
    for (const btn of greenButtons) {
      if (btn.textContent?.includes('발행')) {
        publishBtn = btn;
        console.log('[닥터보이스] 발행 버튼 발견 (녹색 버튼)');
        break;
      }
    }
  }

  if (!publishBtn) {
    console.log('[닥터보이스] 발행 버튼을 찾을 수 없음 - 수동으로 클릭해주세요');
    return false;
  }

  // 버튼이 보이는지 확인
  const rect = publishBtn.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    console.log('[닥터보이스] 발행 버튼이 숨겨져 있음');
    return false;
  }

  // 클릭
  console.log('[닥터보이스] 발행 버튼 클릭!');
  publishBtn.click();

  // 확인 다이얼로그가 나타날 수 있으므로 대기 후 확인 버튼도 클릭
  await sleep(1000);

  // 확인 버튼 찾기 (모달/팝업)
  const confirmSelectors = [
    '.modal button.btn_ok',
    '.popup button.confirm',
    'button[class*="confirm"]',
    '.se-popup button.ok',
  ];

  for (const selector of confirmSelectors) {
    const confirmBtn = document.querySelector(selector);
    if (confirmBtn) {
      console.log('[닥터보이스] 확인 버튼 클릭');
      confirmBtn.click();
      break;
    }
  }

  return true;
}

// 에디터 iframe 문서 찾기
function getEditorDocument() {
  // 먼저 메인 문서에서 찾기
  const mainEditor = document.querySelector('.se-documentTitle') ||
                     document.querySelector('.se-component.se-text');
  if (mainEditor) {
    console.log('[닥터보이스] 에디터: 메인 문서');
    return document;
  }

  // iframe 내부에서 찾기
  const iframes = document.querySelectorAll('iframe');
  for (const iframe of iframes) {
    try {
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
      if (iframeDoc) {
        const editor = iframeDoc.querySelector('[contenteditable="true"]') ||
                       iframeDoc.querySelector('.se-component') ||
                       iframeDoc.body;
        if (editor) {
          console.log('[닥터보이스] 에디터: iframe 내부');
          return iframeDoc;
        }
      }
    } catch (e) {
      // cross-origin 무시
    }
  }

  return document;
}

// 전역 에디터 문서 변수
let editorDoc = null;

// 자동 실행 - 데이터 확인 후 직접 처리
async function autoExecute() {
  // 메인 프레임에서만 실행 (iframe 중복 방지)
  if (window.self !== window.top) {
    console.log('[닥터보이스] iframe에서는 실행 안함');
    return;
  }

  const url = window.location.href;
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('GoBlogWrite') && !url.includes('PostWrite') && !url.includes('Redirect=Write') && !url.includes('editor')) return;

  console.log('[닥터보이스] 글쓰기 페이지 감지 (메인 프레임)');

  // 저장된 데이터 확인
  const stored = await chrome.storage.local.get(['pendingPost', 'autoPostEnabled']);

  if (stored.autoPostEnabled && stored.pendingPost) {
    console.log('[닥터보이스] 자동 발행 데이터 있음, 처리 시작');
    showGuideOverlay();
    updateGuideStatus('ready', '발행 데이터 발견! 자동 입력을 시작합니다...');

    // 에디터 로딩 대기 후 직접 처리
    try {
      await waitForEditor();
      await sleep(2000);

      // 에디터 문서 설정
      editorDoc = getEditorDocument();

      await handleInsertPost(stored.pendingPost, {});
    } catch (err) {
      console.error('[닥터보이스] 자동 발행 오류:', err);
      updateGuideStatus('error', '오류: ' + err.message);
    }
  } else {
    console.log('[닥터보이스] 자동 발행 데이터 없음');
  }
}

// 페이지 로드 후 실행
setTimeout(autoExecute, 2000);

// 에디터 로딩 대기
async function waitForEditor() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const maxAttempts = 60; // 30초 대기

    const check = () => {
      attempts++;

      // 다양한 에디터 선택자 시도
      const selectors = [
        '.se-component.se-text',
        '.se-documentTitle',
        '[contenteditable="true"]',
        '.se-content',
        '.se-main-container',
        '.se-viewer',
        '#content',
        '.blog_editor',
        'iframe[id*="editor"]',
        'iframe[name*="editor"]'
      ];

      let editor = null;
      for (const sel of selectors) {
        editor = document.querySelector(sel);
        if (editor) {
          console.log('[닥터보이스] 에디터 발견:', sel);
          break;
        }
      }

      // iframe 내부도 확인
      if (!editor) {
        const iframes = document.querySelectorAll('iframe');
        for (const iframe of iframes) {
          try {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
            if (iframeDoc) {
              editor = iframeDoc.querySelector('[contenteditable="true"]') ||
                       iframeDoc.querySelector('.se-component');
              if (editor) {
                console.log('[닥터보이스] 에디터 발견 (iframe 내부)');
                break;
              }
            }
          } catch (e) {
            // cross-origin iframe 무시
          }
        }
      }

      if (editor) {
        resolve(editor);
        return;
      }

      if (attempts >= maxAttempts) {
        console.log('[닥터보이스] 에디터 타임아웃, 강제 진행');
        resolve(null); // 타임아웃이어도 진행
        return;
      }

      setTimeout(check, 500);
    };
    check();
  });
}

// 제목 입력
async function inputTitle(title) {
  console.log('[닥터보이스] 제목 입력:', title);

  // 메인 문서에서 제목 요소 찾기 (se-fs32는 제목 폰트 크기)
  const titleSpan = document.querySelector('span.se-fs32.__se-node') ||
                    document.querySelector('.se-documentTitle span.__se-node') ||
                    document.querySelector('[class*="se-fs32"].__se-node');

  if (titleSpan) {
    // 제목 영역 클릭하여 활성화
    titleSpan.click();
    await sleep(200);

    // 직접 텍스트 삽입
    titleSpan.textContent = title;

    // 입력 이벤트 발생
    titleSpan.dispatchEvent(new Event('input', { bubbles: true }));
    titleSpan.dispatchEvent(new Event('change', { bubbles: true }));

    console.log('[닥터보이스] 제목 입력 완료 (직접 삽입)');
    return;
  }

  // 대안: 제목 문단 찾기
  const titleParagraph = document.querySelector('.se-documentTitle .se-text-paragraph');
  if (titleParagraph) {
    titleParagraph.click();
    await sleep(200);

    const innerSpan = titleParagraph.querySelector('span.__se-node');
    if (innerSpan) {
      innerSpan.textContent = title;
      innerSpan.dispatchEvent(new Event('input', { bubbles: true }));
      console.log('[닥터보이스] 제목 입력 완료 (문단 내 span)');
      return;
    }
  }

  console.warn('[닥터보이스] 제목 입력 필드 없음');
}

// 본문 붙여넣기 (클립보드 내용 사용)
async function pasteContent() {
  console.log('[닥터보이스] 본문 붙여넣기 시작');

  // 본문 영역 찾기 및 클릭
  const bodyArea = await findBodyArea();

  if (!bodyArea) {
    console.error('[닥터보이스] 본문 영역 찾기 실패');
    return;
  }

  bodyArea.click();
  await sleep(300);
  bodyArea.focus();
  await sleep(300);

  // Ctrl+V 시뮬레이션
  try {
    document.execCommand('paste');
    console.log('[닥터보이스] execCommand paste 실행');
  } catch (e) {
    console.log('[닥터보이스] execCommand paste 실패, 대체 방법 시도');

    // 키보드 이벤트로 Ctrl+V 시뮬레이션
    const pasteEvent = new KeyboardEvent('keydown', {
      key: 'v',
      code: 'KeyV',
      keyCode: 86,
      which: 86,
      ctrlKey: true,
      bubbles: true
    });
    bodyArea.dispatchEvent(pasteEvent);
  }

  await sleep(500);
  console.log('[닥터보이스] 본문 붙여넣기 완료');
}

// 본문 영역 찾기
async function findBodyArea() {
  // 1. 메인 문서에서 se-fs16 span 찾기 (본문 폰트)
  const allSpans = document.querySelectorAll('span.__se-node');
  console.log('[닥터보이스] __se-node span 개수:', allSpans.length);

  for (const span of allSpans) {
    // se-fs32는 제목이므로 제외
    if (span.classList.contains('se-fs32')) continue;
    // 제목 영역 내부면 제외
    if (span.closest('.se-documentTitle')) continue;

    console.log('[닥터보이스] 본문 영역 발견: span.__se-node (메인)');
    return span;
  }

  // 2. iframe 내부에서 찾기
  const iframes = document.querySelectorAll('iframe');
  for (const iframe of iframes) {
    try {
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
      if (iframeDoc && iframeDoc.body) {
        // contenteditable body 찾기
        if (iframeDoc.body.contentEditable === 'true' || iframeDoc.body.getAttribute('contenteditable') === 'true') {
          console.log('[닥터보이스] 본문 영역 발견: iframe body');
          return iframeDoc.body;
        }
      }
    } catch (e) {
      // cross-origin 무시
    }
  }

  // 3. 플레이스홀더의 형제 요소
  const placeholder = document.querySelector('.se-placeholder:not(.se-fs32)');
  if (placeholder) {
    const parent = placeholder.parentElement;
    const sibling = parent?.querySelector('span[id^="SE-"]');
    if (sibling) {
      console.log('[닥터보이스] 본문 영역 발견: placeholder sibling');
      return sibling;
    }
    // 부모 p 태그 반환
    if (parent?.tagName === 'P') {
      console.log('[닥터보이스] 본문 영역 발견: placeholder parent P');
      return parent;
    }
  }

  console.log('[닥터보이스] 본문 영역 찾기 실패');
  return null;
}

// V2 이미지 업로드 - 클립보드 붙여넣기 방식
async function uploadSingleImageV2(base64Data, index) {
  console.log('[닥터보이스] V2 이미지 업로드:', index + 1);

  try {
    // 에디터 본문 영역 포커스
    const bodyArea = await findBodyArea();
    if (bodyArea) {
      bodyArea.click();
      bodyArea.focus();
      await sleep(300);
    }

    // Base64를 Blob으로 변환
    const blob = base64ToBlob(base64Data);

    // 클립보드에 이미지 복사 후 붙여넣기
    try {
      const clipboardItem = new ClipboardItem({
        [blob.type]: blob
      });
      await navigator.clipboard.write([clipboardItem]);
      console.log('[닥터보이스] 클립보드에 이미지 복사됨');

      // 붙여넣기 이벤트 발생
      await sleep(300);
      document.execCommand('paste');
      console.log('[닥터보이스] 붙여넣기 완료');

      await sleep(1500); // 이미지 처리 대기
      return true;
    } catch (clipError) {
      console.log('[닥터보이스] 클립보드 방식 실패, 드래그앤드롭 시도:', clipError.message);
    }

    // 대체: 드래그앤드롭 방식
    const file = base64ToFile(base64Data, `image_${index + 1}.jpg`);
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);

    // 에디터에 드롭 이벤트
    const editorArea = document.querySelector('.se-content') ||
                       document.querySelector('.se-component-content') ||
                       document.querySelector('[contenteditable="true"]');

    if (editorArea) {
      const dropEvent = new DragEvent('drop', {
        bubbles: true,
        cancelable: true,
        dataTransfer: dataTransfer
      });
      editorArea.dispatchEvent(dropEvent);
      await sleep(1500);
      console.log('[닥터보이스] 드롭 이벤트 발생');
    }

    return true;
  } catch (e) {
    console.error('[닥터보이스] V2 이미지 업로드 실패:', e);
    return false;
  }
}

// Base64를 Blob으로 변환
function base64ToBlob(base64Data) {
  let base64 = base64Data;
  let mimeType = 'image/jpeg';

  if (base64Data.includes(',')) {
    const parts = base64Data.split(',');
    const mimeMatch = parts[0].match(/data:(.+);base64/);
    if (mimeMatch) {
      mimeType = mimeMatch[1];
    }
    base64 = parts[1];
  }

  const byteCharacters = atob(base64);
  const byteArrays = [];

  for (let offset = 0; offset < byteCharacters.length; offset += 512) {
    const slice = byteCharacters.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);

    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }

    const byteArray = new Uint8Array(byteNumbers);
    byteArrays.push(byteArray);
  }

  return new Blob(byteArrays, { type: mimeType });
}

// 진행 상황 알림 (프로그레스 바 포함)
function showProgressNotification(msg, progress) {
  const old = document.querySelector('.dv-progress-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-progress-notify';
  el.innerHTML = `
    <div style="font-size: 14px; font-weight: 600; margin-bottom: 8px;">${msg}</div>
    <div style="background: rgba(255,255,255,0.3); border-radius: 4px; height: 8px; overflow: hidden;">
      <div style="background: white; height: 100%; width: ${progress}%; transition: width 0.3s ease;"></div>
    </div>
    <div style="font-size: 11px; margin-top: 4px; opacity: 0.9;">${Math.round(progress)}% 완료</div>
  `;
  el.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 16px 24px;
    border-radius: 12px;
    min-width: 250px;
    z-index: 999999;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  `;

  document.body.appendChild(el);

  // 100% 완료 시 3초 후 제거
  if (progress >= 100) {
    setTimeout(() => el.remove(), 3000);
  }
}

// 유틸리티 함수
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function showNotification(msg) {
  const old = document.querySelector('.dv-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-notify';
  el.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 16px 24px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    z-index: 999999;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    animation: slideIn 0.3s ease;
  `;
  el.textContent = msg;

  // 애니메이션 스타일 추가
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  `;
  document.head.appendChild(style);

  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

// 큰 알림 (Ctrl+V 안내)
function showBigNotification() {
  const old = document.querySelector('.dv-big-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-big-notify';
  el.innerHTML = `
    <div style="font-size: 32px; margin-bottom: 12px;">📋</div>
    <div style="font-size: 22px; font-weight: bold; margin-bottom: 8px;">Ctrl + V</div>
    <div style="font-size: 14px; opacity: 0.95;">본문 영역을 클릭한 후 붙여넣기 하세요</div>
    <div style="font-size: 12px; margin-top: 16px; padding: 10px; background: rgba(255,255,255,0.15); border-radius: 8px;">
      <strong>📌 이미지+스타일 포함</strong><br>
      클립보드에 모든 내용이 복사되어 있습니다
    </div>
    <button id="dv-close-btn" style="
      margin-top: 16px;
      padding: 8px 24px;
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.4);
      color: white;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
    ">닫기</button>
  `;
  el.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 36px 56px;
    border-radius: 20px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.5);
    animation: popIn 0.3s ease;
  `;

  // 애니메이션 스타일
  const style = document.createElement('style');
  style.textContent = `
    @keyframes popIn {
      from { transform: translate(-50%, -50%) scale(0.8); opacity: 0; }
      to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    }
    @keyframes fadeOut {
      from { opacity: 1; }
      to { opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  document.body.appendChild(el);

  // 닫기 버튼 클릭
  const closeBtn = el.querySelector('#dv-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    });
  }

  // 키보드 이벤트 감지 (붙여넣기 후 알림 제거)
  const handleKeydown = (e) => {
    if (e.ctrlKey && e.key === 'v') {
      setTimeout(() => {
        el.style.animation = 'fadeOut 0.2s ease';
        setTimeout(() => {
          el.remove();
          showNotification('✅ 붙여넣기 완료! 확인 후 발행하세요');
        }, 200);
      }, 300);
      document.removeEventListener('keydown', handleKeydown);
    }
  };
  document.addEventListener('keydown', handleKeydown);

  // 15초 후 자동 제거
  setTimeout(() => {
    if (el.parentNode) {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    }
    document.removeEventListener('keydown', handleKeydown);
  }, 15000);
}

// 본문 삽입 (텍스트 직접 입력)
async function insertContent(content, options) {
  console.log('[닥터보이스] 본문 입력 시작');

  const bodyArea = await findBodyArea();
  if (!bodyArea) {
    console.error('[닥터보이스] 본문 영역 찾기 실패');
    return;
  }

  bodyArea.click();
  await sleep(300);
  bodyArea.focus();
  await sleep(300);

  // 텍스트를 클립보드에 복사 후 붙여넣기
  try {
    // HTML이 포함된 경우 HTML로 붙여넣기
    const htmlContent = convertToNaverHtml(content, options);

    // 클립보드에 HTML 복사
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const clipboardItem = new ClipboardItem({ 'text/html': blob, 'text/plain': new Blob([content], { type: 'text/plain' }) });
    await navigator.clipboard.write([clipboardItem]);

    // 붙여넣기
    document.execCommand('paste');
    console.log('[닥터보이스] 본문 붙여넣기 완료');
  } catch (e) {
    console.log('[닥터보이스] HTML 붙여넣기 실패, 텍스트로 시도:', e);
    // 텍스트로 대체
    await navigator.clipboard.writeText(content);
    document.execCommand('paste');
  }
}

// 직접 HTML 삽입 (iframe body에 직접)
async function insertContentDirectly(bodyEl, content, imageUrls) {
  console.log('[닥터보이스] 본문 직접 삽입 시작');

  bodyEl.focus();
  await sleep(300);

  // 본문을 문단으로 분리
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  const totalImages = imageUrls?.length || 0;

  // 이미지 균등 배치
  const imagePositions = [];
  if (totalImages > 0) {
    const interval = Math.max(1, Math.floor(paragraphs.length / (totalImages + 1)));
    for (let i = 0; i < totalImages; i++) {
      imagePositions.push(Math.min((i + 1) * interval, paragraphs.length));
    }
  }

  let html = '';
  let imageIndex = 0;

  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i].trim();
    if (!para) continue;

    html += `<p>${para.replace(/\n/g, '<br>')}</p>`;

    // 이미지 삽입 위치
    if (imageIndex < totalImages && imagePositions[imageIndex] === i + 1) {
      const imgUrl = imageUrls[imageIndex];
      html += `<p><img src="${imgUrl}" style="max-width:100%"></p>`;
      imageIndex++;
    }
  }

  // 남은 이미지
  while (imageIndex < totalImages) {
    html += `<p><img src="${imageUrls[imageIndex]}" style="max-width:100%"></p>`;
    imageIndex++;
  }

  // HTML 삽입
  bodyEl.innerHTML = html;
  console.log('[닥터보이스] 본문 직접 삽입 완료');
}

// 본문 + 이미지 URL 함께 삽입 (DOM 직접 조작 - 5MB 제한 우회)
async function insertContentWithImages(content, imageUrls, options) {
  console.log('[닥터보이스] 본문 + 이미지 URL 삽입 시작 (DOM 직접 조작)');
  console.log('[닥터보이스] 이미지 URL 개수:', imageUrls.length);

  const bodyArea = await findBodyArea();

  if (!bodyArea) {
    console.error('[닥터보이스] 본문 영역 찾기 실패');
    return;
  }

  // 본문 영역 클릭하여 활성화
  bodyArea.click();
  await sleep(300);

  // 본문을 HTML로 변환
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  const totalImages = imageUrls?.length || 0;

  // 이미지 균등 배치 계산
  const imagePositions = [];
  if (totalImages > 0) {
    const interval = Math.max(1, Math.floor(paragraphs.length / (totalImages + 1)));
    for (let i = 0; i < totalImages; i++) {
      imagePositions.push(Math.min((i + 1) * interval, paragraphs.length));
    }
  }

  // HTML 생성
  let html = '';
  let imageIndex = 0;

  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i].trim();
    if (!para) continue;

    html += para.replace(/\n/g, '<br>');

    // 이미지 삽입 위치
    if (imageIndex < totalImages && imagePositions[imageIndex] === i + 1) {
      const imgUrl = imageUrls[imageIndex];
      console.log(`[닥터보이스] 이미지 ${imageIndex + 1} 삽입: ${imgUrl.substring(0, 50)}...`);
      html += `<br><br><img src="${imgUrl}" style="max-width:100%"><br><br>`;
      imageIndex++;
    } else {
      html += '<br><br>';
    }
  }

  // 남은 이미지 추가
  while (imageIndex < totalImages) {
    html += `<img src="${imageUrls[imageIndex]}" style="max-width:100%"><br><br>`;
    imageIndex++;
  }

  // 직접 innerHTML 설정
  bodyArea.innerHTML = html;

  // 입력 이벤트 발생
  bodyArea.dispatchEvent(new Event('input', { bubbles: true }));
  bodyArea.dispatchEvent(new Event('change', { bubbles: true }));

  console.log('[닥터보이스] 본문 + 이미지 입력 완료 (직접 삽입)');
}

// 네이버 블로그용 HTML 변환
function convertToNaverHtml(content, options) {
  let html = content;

  // 줄바꿈 처리
  html = html.split('\n\n').map(para => {
    if (!para.trim()) return '';
    return `<p>${para.replace(/\n/g, '<br>')}</p>`;
  }).join('');

  // 인용구 처리 (>로 시작하는 줄)
  if (options?.useQuote) {
    html = html.replace(/<p>&gt;(.+?)<\/p>/g, '<blockquote>$1</blockquote>');
  }

  return html;
}

// 이미지 업로드 (네이버 스마트에디터 ONE 전용)
async function uploadImages(images) {
  console.log('[닥터보이스] 이미지 업로드 시작:', images.length, '개');

  for (let i = 0; i < images.length; i++) {
    const imageBase64 = images[i];
    showNotification(`📷 이미지 업로드 중... (${i + 1}/${images.length})`);

    try {
      const success = await uploadSingleImage(imageBase64, i);
      if (success) {
        console.log(`[닥터보이스] 이미지 ${i + 1} 업로드 성공`);
      } else {
        console.warn(`[닥터보이스] 이미지 ${i + 1} 업로드 실패, 다음 이미지로`);
      }
      await sleep(2000); // 이미지 간 간격 (네이버 서버 처리 시간)
    } catch (e) {
      console.error('[닥터보이스] 이미지 업로드 실패:', i, e);
    }
  }
}

// 단일 이미지 업로드 (네이버 스마트에디터 ONE)
async function uploadSingleImage(base64Data, index) {
  console.log('[닥터보이스] 이미지 업로드 시도:', index + 1);

  // 방법 1: 드래그 앤 드롭으로 에디터에 직접 이미지 삽입
  const dropSuccess = await tryDropImage(base64Data, index);
  if (dropSuccess) return true;

  // 방법 2: 사진 버튼 클릭 후 파일 선택
  const buttonSuccess = await tryButtonUpload(base64Data, index);
  if (buttonSuccess) return true;

  // 방법 3: 숨겨진 파일 input 직접 사용
  const inputSuccess = await tryHiddenInput(base64Data, index);
  if (inputSuccess) return true;

  console.error('[닥터보이스] 모든 이미지 업로드 방법 실패');
  return false;
}

// 방법 1: 드래그 앤 드롭
async function tryDropImage(base64Data, index) {
  console.log('[닥터보이스] 드래그 앤 드롭 방식 시도');

  try {
    // 에디터 영역 찾기
    const editorArea = document.querySelector('.se-component.se-text') ||
                       document.querySelector('.se-content') ||
                       document.querySelector('[contenteditable="true"]');

    if (!editorArea) {
      console.log('[닥터보이스] 에디터 영역 없음');
      return false;
    }

    // Base64를 File로 변환
    const file = base64ToFile(base64Data, `image_${index + 1}.jpg`);

    // DataTransfer 생성
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);

    // 드롭 이벤트 생성 및 발생
    const dropEvent = new DragEvent('drop', {
      bubbles: true,
      cancelable: true,
      dataTransfer: dataTransfer
    });

    editorArea.dispatchEvent(dropEvent);
    await sleep(1500);

    console.log('[닥터보이스] 드롭 이벤트 발생 완료');
    return true;
  } catch (e) {
    console.log('[닥터보이스] 드래그 앤 드롭 실패:', e.message);
    return false;
  }
}

// 방법 2: 사진 버튼 클릭 후 파일 선택
async function tryButtonUpload(base64Data, index) {
  console.log('[닥터보이스] 버튼 클릭 방식 시도');

  try {
    // 네이버 스마트에디터 ONE의 사진 버튼 선택자들
    const photoBtnSelectors = [
      'button.se-toolbar-button-image',
      '.se-toolbar-item-image',
      'button[data-name="image"]',
      'button[data-type="image"]',
      '.se-toolbar button[title*="사진"]',
      '.se-toolbar button[title*="이미지"]',
      '.se-image-toolbar-button',
      // 아이콘으로 찾기
      'button svg use[href*="image"]',
    ];

    let photoBtn = null;
    for (const selector of photoBtnSelectors) {
      photoBtn = document.querySelector(selector);
      if (photoBtn) {
        // svg use 요소인 경우 부모 button 찾기
        if (photoBtn.tagName === 'use') {
          photoBtn = photoBtn.closest('button');
        }
        console.log('[닥터보이스] 사진 버튼 발견:', selector);
        break;
      }
    }

    // 텍스트로 버튼 찾기
    if (!photoBtn) {
      photoBtn = findButtonByText('사진') || findButtonByText('이미지');
    }

    if (!photoBtn) {
      console.log('[닥터보이스] 사진 버튼 없음');
      return false;
    }

    // 버튼 클릭
    photoBtn.click();
    await sleep(1000);

    // 파일 선택 input 찾기 (팝업 내부)
    const fileInputSelectors = [
      'input[type="file"][accept*="image"]',
      '.se-popup input[type="file"]',
      '.se-image-uploader input[type="file"]',
      'input.se-file-input',
      '#image-upload-input',
    ];

    let fileInput = null;
    for (const selector of fileInputSelectors) {
      fileInput = document.querySelector(selector);
      if (fileInput) {
        console.log('[닥터보이스] 파일 input 발견:', selector);
        break;
      }
    }

    // 모든 file input 중 이미지용 찾기
    if (!fileInput) {
      const allInputs = document.querySelectorAll('input[type="file"]');
      for (const input of allInputs) {
        if (!input.accept || input.accept.includes('image')) {
          fileInput = input;
          console.log('[닥터보이스] 파일 input 발견 (일반)');
          break;
        }
      }
    }

    if (!fileInput) {
      // 팝업 닫기
      const closeBtn = document.querySelector('.se-popup-close');
      if (closeBtn) closeBtn.click();
      console.log('[닥터보이스] 파일 input 없음');
      return false;
    }

    // 파일 설정
    const file = base64ToFile(base64Data, `image_${index + 1}.jpg`);
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;

    // 이벤트 발생
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    fileInput.dispatchEvent(new Event('input', { bubbles: true }));

    await sleep(2500); // 업로드 대기

    console.log('[닥터보이스] 버튼 업로드 완료');
    return true;
  } catch (e) {
    console.log('[닥터보이스] 버튼 업로드 실패:', e.message);
    return false;
  }
}

// 방법 3: 숨겨진 파일 input 직접 사용
async function tryHiddenInput(base64Data, index) {
  console.log('[닥터보이스] 숨겨진 input 방식 시도');

  try {
    // 페이지 내 모든 파일 input 찾기
    const allFileInputs = document.querySelectorAll('input[type="file"]');
    console.log('[닥터보이스] 발견된 파일 input 수:', allFileInputs.length);

    for (const input of allFileInputs) {
      // 이미지 관련 input인지 확인
      const accept = input.accept || '';
      if (accept.includes('image') || accept === '' || accept === '*/*') {
        console.log('[닥터보이스] 이미지 input 발견, accept:', accept);

        const file = base64ToFile(base64Data, `image_${index + 1}.jpg`);
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);

        // 파일 설정
        Object.defineProperty(input, 'files', {
          value: dataTransfer.files,
          writable: true
        });

        // 여러 이벤트 발생
        input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
        input.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));

        // 커스텀 이벤트도 시도
        input.dispatchEvent(new CustomEvent('file-selected', {
          bubbles: true,
          detail: { files: dataTransfer.files }
        }));

        await sleep(2000);

        console.log('[닥터보이스] 숨겨진 input 업로드 시도 완료');
        return true;
      }
    }

    console.log('[닥터보이스] 적합한 파일 input 없음');
    return false;
  } catch (e) {
    console.log('[닥터보이스] 숨겨진 input 실패:', e.message);
    return false;
  }
}

// Base64를 File 객체로 변환
function base64ToFile(base64Data, filename) {
  // data:image/png;base64,xxxxx 형식 처리
  let base64 = base64Data;
  let mimeType = 'image/png';

  if (base64Data.includes(',')) {
    const parts = base64Data.split(',');
    const mimeMatch = parts[0].match(/data:(.+);base64/);
    if (mimeMatch) {
      mimeType = mimeMatch[1];
    }
    base64 = parts[1];
  }

  // Base64 디코딩
  const byteCharacters = atob(base64);
  const byteArrays = [];

  for (let offset = 0; offset < byteCharacters.length; offset += 512) {
    const slice = byteCharacters.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);

    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }

    const byteArray = new Uint8Array(byteNumbers);
    byteArrays.push(byteArray);
  }

  const blob = new Blob(byteArrays, { type: mimeType });
  return new File([blob], filename, { type: mimeType });
}

// 텍스트로 버튼 찾기
function findButtonByText(text) {
  const buttons = document.querySelectorAll('button, .se-toolbar-item');
  for (const btn of buttons) {
    if (btn.textContent.includes(text) || btn.getAttribute('title')?.includes(text)) {
      return btn;
    }
  }
  return null;
}

// 성공 알림 (커스텀 메시지 지원)
function showBigSuccessNotification(title = '✅ 포스팅 준비 완료!', desc = '내용을 확인하고 발행 버튼을 클릭하세요') {
  const old = document.querySelector('.dv-big-notify');
  if (old) old.remove();

  // 프로그레스 알림도 제거
  const progressNotify = document.querySelector('.dv-progress-notify');
  if (progressNotify) progressNotify.remove();

  const el = document.createElement('div');
  el.className = 'dv-big-notify';
  el.innerHTML = `
    <div style="font-size: 48px; margin-bottom: 16px;">${title.includes('🎉') ? '🎉' : '✅'}</div>
    <div style="font-size: 24px; font-weight: bold; margin-bottom: 8px;">${title.replace(/[🎉✅]/g, '').trim()}</div>
    <div style="font-size: 14px; opacity: 0.95;">${desc}</div>
    <button id="dv-close-btn" style="
      margin-top: 20px;
      padding: 10px 30px;
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.4);
      color: white;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
    ">확인</button>
  `;
  el.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    padding: 40px 60px;
    border-radius: 20px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.5);
    animation: popIn 0.3s ease;
  `;

  // 애니메이션 스타일
  const style = document.createElement('style');
  style.textContent = `
    @keyframes popIn {
      from { transform: translate(-50%, -50%) scale(0.8); opacity: 0; }
      to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    }
    @keyframes fadeOut {
      from { opacity: 1; }
      to { opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  document.body.appendChild(el);

  const closeBtn = el.querySelector('#dv-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    });
  }

  // 5초 후 자동 닫기
  setTimeout(() => {
    if (el.parentNode) {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    }
  }, 5000);
}

console.log('[닥터보이스] v11.0 초기화 완료');
