// 네이버 블로그 스마트에디터 v13.5 - content script에서 직접 DOM 조작
console.log('[닥터보이스] v13.5 로드 - content script 직접 DOM 조작');

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

// 완전자동 글 입력 처리 (debugger API)
async function handleInsertPost(postData, options) {
  console.log('[닥터보이스] 완전자동 발행 시작 v13.0');
  console.log('[닥터보이스] 제목:', postData.title);
  console.log('[닥터보이스] 이미지 URL 수:', postData.imageUrls?.length || 0);

  // 가이드 오버레이 제거
  removeGuideOverlay();
  showProgressNotification('📝 완전자동 입력 준비 중...', 0);

  try {
    // 1. 에디터 로딩 대기
    await waitForEditor();
    await sleep(2000);
    showProgressNotification('✅ 에디터 로딩 완료', 20);

    // 2. iframe과 에디터 문서 찾기
    const editorInfo = findEditorIframe();
    if (!editorInfo) {
      throw new Error('에디터를 찾을 수 없습니다');
    }

    console.log('[닥터보이스] 에디터 발견:', editorInfo.type);

    // 3. 제목/본문 영역 위치 계산
    const positions = getElementPositions(editorInfo);
    if (!positions) {
      throw new Error('입력 영역을 찾을 수 없습니다');
    }

    console.log('[닥터보이스] 제목 위치:', positions.title);
    console.log('[닥터보이스] 본문 위치:', positions.body);

    // 4. 텍스트 정리
    let cleanTitle = postData.title.replace(/^["']|["']$/g, '').trim();
    let cleanContent = formatContentForBlog(postData.content);
    cleanContent = cleanContent.replace(/^["']|["']$/g, '').trim();

    showProgressNotification('⌨️ 자동 입력 중... (잠시 기다려주세요)', 40);

    // 5. content script에서 직접 DOM 조작으로 입력
    console.log('[닥터보이스] DOM 직접 조작 시작...');

    // 제목 입력
    const titleResult = await insertTextDirectly(editorInfo, 'title', cleanTitle);
    console.log('[닥터보이스] 제목 입력 결과:', titleResult);
    showProgressNotification('⌨️ 제목 입력 완료, 본문 입력 중...', 60);

    await sleep(500);

    // 본문 입력
    const bodyResult = await insertTextDirectly(editorInfo, 'body', cleanContent);
    console.log('[닥터보이스] 본문 입력 결과:', bodyResult);

    if (titleResult.success && bodyResult.success) {
      showProgressNotification('✅ 입력 완료!', 100);
      await sleep(500);
      showBigSuccessNotification('✅ 완전자동 입력 완료!', '내용을 확인하고 발행 버튼을 클릭하세요');
    } else {
      throw new Error(titleResult.error || bodyResult.error || '입력 실패');
    }

    // 자동 발행 플래그 해제
    await chrome.storage.local.set({ autoPostEnabled: false });

  } catch (error) {
    console.error('[닥터보이스] 발행 오류:', error);
    showNotification('❌ 오류 발생: ' + error.message);
  }
}

// DOM 직접 조작으로 텍스트 입력 (content script에서 직접 실행)
async function insertTextDirectly(editorInfo, type, text) {
  const { doc } = editorInfo;

  try {
    // 요소 찾기
    let targetEl;
    if (type === 'title') {
      const titleComponent = doc.querySelector('.se-component.se-documentTitle');
      targetEl = titleComponent?.querySelector('.se-text-paragraph');
    } else {
      const bodyComponents = doc.querySelectorAll('.se-component.se-text');
      for (const comp of bodyComponents) {
        if (!comp.classList.contains('se-documentTitle') && !comp.closest('.se-documentTitle')) {
          targetEl = comp.querySelector('.se-text-paragraph');
          if (targetEl) break;
        }
      }
    }

    if (!targetEl) {
      return { success: false, error: `${type} 요소를 찾을 수 없습니다` };
    }

    console.log(`[닥터보이스] ${type} 요소 찾음:`, targetEl);

    // 1. 요소에 포커스
    targetEl.focus();
    await sleep(100);

    // 2. 기존 내용 전체 선택
    const selection = doc.getSelection();
    const range = doc.createRange();
    range.selectNodeContents(targetEl);
    selection.removeAllRanges();
    selection.addRange(range);
    await sleep(50);

    // 3. 방법 1: execCommand 시도
    let success = doc.execCommand('insertText', false, text);
    console.log(`[닥터보이스] execCommand 결과: ${success}`);

    if (!success) {
      // 4. 방법 2: textContent 직접 설정 + 이벤트 트리거
      console.log('[닥터보이스] execCommand 실패, textContent 방식 시도');

      // span 요소 찾기 또는 생성
      let spanEl = targetEl.querySelector('span');
      if (!spanEl) {
        spanEl = doc.createElement('span');
        targetEl.appendChild(spanEl);
      }
      spanEl.textContent = text;

      // React 이벤트 트리거
      const inputEvent = new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: text
      });
      targetEl.dispatchEvent(inputEvent);
      spanEl.dispatchEvent(inputEvent);
    }

    // 5. blur 이벤트로 저장 트리거
    await sleep(100);
    targetEl.dispatchEvent(new Event('blur', { bubbles: true }));

    return { success: true, method: success ? 'execCommand' : 'textContent' };

  } catch (error) {
    console.error(`[닥터보이스] ${type} 입력 오류:`, error);
    return { success: false, error: error.message };
  }
}

// 제목/본문 영역 위치 계산 (화면 기준 절대 좌표)
function getElementPositions(editorInfo) {
  const { doc, iframe } = editorInfo;

  // 제목 영역 찾기
  const titleComponent = doc.querySelector('.se-component.se-documentTitle');
  if (!titleComponent) {
    console.error('[닥터보이스] 제목 컴포넌트 없음');
    return null;
  }

  const titleParagraph = titleComponent.querySelector('.se-text-paragraph');
  if (!titleParagraph) {
    console.error('[닥터보이스] 제목 paragraph 없음');
    return null;
  }

  // 본문 영역 찾기
  const bodyComponents = doc.querySelectorAll('.se-component.se-text');
  let bodyParagraph = null;

  for (const comp of bodyComponents) {
    if (!comp.classList.contains('se-documentTitle') && !comp.closest('.se-documentTitle')) {
      bodyParagraph = comp.querySelector('.se-text-paragraph');
      if (bodyParagraph) break;
    }
  }

  if (!bodyParagraph) {
    console.error('[닥터보이스] 본문 paragraph 없음');
    return null;
  }

  // 위치 계산
  const titleRect = titleParagraph.getBoundingClientRect();
  const bodyRect = bodyParagraph.getBoundingClientRect();

  let titleX = titleRect.left + titleRect.width / 2;
  let titleY = titleRect.top + titleRect.height / 2;
  let bodyX = bodyRect.left + bodyRect.width / 2;
  let bodyY = bodyRect.top + bodyRect.height / 2;

  // 현재 스크립트가 iframe 내부에서 실행 중인지 확인
  let frameOffsetX = 0;
  let frameOffsetY = 0;

  try {
    if (window !== window.top) {
      // iframe 내부에서 실행 중 - frameElement로 위치 계산
      const frameEl = window.frameElement;
      if (frameEl) {
        const frameRect = frameEl.getBoundingClientRect();
        frameOffsetX = frameRect.left;
        frameOffsetY = frameRect.top;
        console.log('[닥터보이스] frameElement 오프셋:', frameOffsetX, frameOffsetY);
      }
    }
  } catch (e) {
    // cross-origin인 경우 무시
    console.log('[닥터보이스] 프레임 오프셋 계산 실패 (cross-origin)');
  }

  // iframe 내부인 경우 iframe 오프셋 추가 (findEditorIframe에서 찾은 경우)
  if (iframe) {
    const iframeRect = iframe.getBoundingClientRect();
    frameOffsetX += iframeRect.left;
    frameOffsetY += iframeRect.top;
    console.log('[닥터보이스] 추가 iframe 오프셋:', iframeRect.left, iframeRect.top);
  }

  titleX += frameOffsetX;
  titleY += frameOffsetY;
  bodyX += frameOffsetX;
  bodyY += frameOffsetY;

  console.log('[닥터보이스] 최종 제목 좌표:', titleX, titleY);
  console.log('[닥터보이스] 최종 본문 좌표:', bodyX, bodyY);

  return {
    title: { x: Math.round(titleX), y: Math.round(titleY) },
    body: { x: Math.round(bodyX), y: Math.round(bodyY) }
  };
}

// Ctrl+V 붙여넣기 단계 안내
function showPasteStep(title, desc, content) {
  return new Promise((resolve) => {
    // 기존 알림 제거
    const old = document.querySelector('.dv-paste-step');
    if (old) old.remove();

    const preview = content.length > 50 ? content.substring(0, 50) + '...' : content;

    const el = document.createElement('div');
    el.className = 'dv-paste-step';
    el.innerHTML = `
      <div style="font-size: 32px; margin-bottom: 12px;">📋</div>
      <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">${title}</div>
      <div style="font-size: 14px; opacity: 0.9; margin-bottom: 16px;">${desc}</div>
      <div style="
        background: rgba(0,0,0,0.4);
        padding: 20px 32px;
        border-radius: 12px;
        margin-bottom: 20px;
      ">
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 3px;">Ctrl + V</div>
        <div style="font-size: 13px; margin-top: 8px; opacity: 0.8;">키보드에서 눌러주세요</div>
      </div>
      <div style="
        background: rgba(255,255,255,0.1);
        padding: 10px 16px;
        border-radius: 8px;
        font-size: 12px;
        max-width: 280px;
        word-break: break-all;
        margin-bottom: 16px;
      ">
        <span style="opacity: 0.6;">클립보드:</span> ${preview}
      </div>
      <button class="dv-skip-btn" style="
        background: rgba(255,255,255,0.2);
        border: 1px solid rgba(255,255,255,0.3);
        color: white;
        padding: 8px 20px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 13px;
      ">건너뛰기</button>
    `;
    el.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      color: white;
      padding: 32px 40px;
      border-radius: 20px;
      text-align: center;
      z-index: 999999;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      animation: popIn 0.3s ease;
    `;

    // 애니메이션 스타일
    if (!document.querySelector('#dv-paste-style')) {
      const style = document.createElement('style');
      style.id = 'dv-paste-style';
      style.textContent = `
        @keyframes popIn {
          from { transform: translate(-50%, -50%) scale(0.8); opacity: 0; }
          to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
      `;
      document.head.appendChild(style);
    }

    document.body.appendChild(el);

    // Ctrl+V 감지
    const handlePaste = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        document.removeEventListener('keydown', handlePaste);
        el.innerHTML = `
          <div style="font-size: 48px;">✅</div>
          <div style="font-size: 18px; margin-top: 12px;">붙여넣기 완료!</div>
        `;
        setTimeout(() => {
          el.remove();
          resolve();
        }, 800);
      }
    };
    document.addEventListener('keydown', handlePaste);

    // 건너뛰기 버튼
    el.querySelector('.dv-skip-btn').addEventListener('click', () => {
      document.removeEventListener('keydown', handlePaste);
      el.remove();
      resolve();
    });
  });
}

// iframe과 에디터 문서 찾기
function findEditorIframe() {
  // 메인 문서에서 직접 찾기
  const mainTitle = document.querySelector('.se-component.se-documentTitle');
  if (mainTitle) {
    return { doc: document, win: window, type: 'main' };
  }

  // iframe에서 찾기
  const iframes = document.querySelectorAll('iframe');
  for (const iframe of iframes) {
    try {
      const iframeDoc = iframe.contentDocument;
      const iframeWin = iframe.contentWindow;
      if (iframeDoc) {
        const titleEl = iframeDoc.querySelector('.se-component.se-documentTitle');
        if (titleEl) {
          return { doc: iframeDoc, win: iframeWin, iframe: iframe, type: 'iframe' };
        }
      }
    } catch (e) {
      // cross-origin 무시
    }
  }

  return null;
}

// 제목 자동 입력 (클립보드 복사 후 수동 Ctrl+V 안내)
async function autoInsertTitle(title, editorInfo) {
  const { doc, win, iframe } = editorInfo;
  console.log('[닥터보이스] 제목 입력 시작:', title);

  // 제목에서 불필요한 따옴표 제거
  let cleanTitle = title.replace(/^["']|["']$/g, '').trim();
  console.log('[닥터보이스] 정리된 제목:', cleanTitle);

  // 제목 영역 찾기
  const titleComponent = doc.querySelector('.se-component.se-documentTitle');
  if (!titleComponent) {
    console.error('[닥터보이스] 제목 컴포넌트 없음');
    return false;
  }

  const titleParagraph = titleComponent.querySelector('.se-text-paragraph');
  if (!titleParagraph) {
    console.error('[닥터보이스] 제목 paragraph 없음');
    return false;
  }

  // 1. 클립보드에 텍스트 복사
  try {
    await navigator.clipboard.writeText(cleanTitle);
    console.log('[닥터보이스] 제목 클립보드 복사 완료');
  } catch (e) {
    console.error('[닥터보이스] 클립보드 복사 실패:', e.message);
    return false;
  }

  // 2. 제목 영역 직접 클릭하여 포커스
  titleParagraph.click();
  await sleep(100);
  titleParagraph.focus();
  await sleep(100);

  // 3. Selection 설정
  const selection = doc.getSelection();
  const range = doc.createRange();
  range.selectNodeContents(titleParagraph);
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);

  console.log('[닥터보이스] 제목 영역 포커스 완료');
  return true; // 클립보드 복사 성공
}

// 본문 자동 입력 (클립보드 복사 후 수동 Ctrl+V 안내)
async function autoInsertBody(content, editorInfo) {
  const { doc, win, iframe } = editorInfo;
  console.log('[닥터보이스] 본문 입력 시작');

  // 본문 컴포넌트 찾기
  const bodyComponents = doc.querySelectorAll('.se-component.se-text');
  let bodyComponent = null;

  for (const comp of bodyComponents) {
    if (!comp.classList.contains('se-documentTitle') && !comp.closest('.se-documentTitle')) {
      bodyComponent = comp;
      break;
    }
  }

  if (!bodyComponent) {
    console.error('[닥터보이스] 본문 컴포넌트 없음');
    return false;
  }

  const bodyParagraph = bodyComponent.querySelector('.se-text-paragraph');
  if (!bodyParagraph) {
    console.error('[닥터보이스] 본문 paragraph 없음');
    return false;
  }

  // 본문 포맷팅 (따옴표 제거 포함)
  let formattedContent = formatContentForBlog(content);
  formattedContent = formattedContent.replace(/^["']|["']$/g, '').trim();

  // 1. 클립보드에 텍스트 복사
  try {
    await navigator.clipboard.writeText(formattedContent);
    console.log('[닥터보이스] 본문 클립보드 복사 완료, 길이:', formattedContent.length);
  } catch (e) {
    console.error('[닥터보이스] 클립보드 복사 실패:', e.message);
    return false;
  }

  // 2. 본문 영역 직접 클릭하여 포커스
  bodyParagraph.click();
  await sleep(100);
  bodyParagraph.focus();
  await sleep(100);

  // 3. Selection 설정
  const selection = doc.getSelection();
  const range = doc.createRange();
  range.selectNodeContents(bodyParagraph);
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);

  console.log('[닥터보이스] 본문 영역 포커스 완료');
  return true; // 클립보드 복사 성공
}

// 요소에 텍스트 입력 (execCommand 방식)
async function insertTextToElement(element, text, doc, win) {
  console.log('[닥터보이스] insertTextToElement 시작, 텍스트 길이:', text.length);

  // 1. 요소 클릭 및 포커스
  element.click();
  await sleep(100);
  element.focus();
  await sleep(100);

  // 2. 전체 선택 (기존 내용 삭제를 위해)
  doc.execCommand('selectAll', false, null);
  await sleep(50);

  // 3. 삭제
  doc.execCommand('delete', false, null);
  await sleep(50);

  // 4. 텍스트 입력 시도 - execCommand 우선
  console.log('[닥터보이스] execCommand insertText 시도');
  const insertResult = doc.execCommand('insertText', false, text);
  console.log('[닥터보이스] insertText 결과:', insertResult);

  if (insertResult) {
    await sleep(100);
    // 이벤트 발생
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
    return true;
  }

  // 5. execCommand 실패시 직접 입력
  console.log('[닥터보이스] 직접 텍스트 노드 삽입');

  // span.__se-node 찾거나 생성
  let targetSpan = element.querySelector('span.__se-node');
  if (!targetSpan) {
    targetSpan = doc.createElement('span');
    targetSpan.className = '__se-node';
    element.appendChild(targetSpan);
  }

  // 텍스트 설정
  targetSpan.textContent = text;

  // 이벤트 발생
  element.dispatchEvent(new Event('focus', { bubbles: true }));
  element.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, inputType: 'insertText', data: text }));
  element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
  element.dispatchEvent(new Event('change', { bubbles: true }));

  await sleep(100);
  return targetSpan.textContent.length > 0;
}

// 모든 입력 방법 시도 (React 호환 방식 우선)
async function tryAllInsertMethods(element, text, doc, win) {
  console.log('[닥터보이스] v12.2 입력 시도 시작');
  console.log('[닥터보이스] 텍스트 길이:', text.length);

  // 요소 활성화 및 포커스
  element.click();
  await sleep(100);
  element.focus();
  await sleep(100);

  // 방법 1: React 호환 InputEvent 방식 (가장 효과적)
  console.log('[닥터보이스] 방법1: React InputEvent 방식');
  try {
    const success = await insertWithReactEvents(element, text, doc);
    if (success) {
      console.log('[닥터보이스] 방법1 성공!');
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] 방법1 실패:', e.message);
  }

  // 방법 2: 한 글자씩 키 입력 시뮬레이션
  console.log('[닥터보이스] 방법2: 키 입력 시뮬레이션');
  try {
    const success = await insertCharByChar(element, text, doc);
    if (success) {
      console.log('[닥터보이스] 방법2 성공!');
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] 방법2 실패:', e.message);
  }

  // 방법 3: execCommand insertText
  console.log('[닥터보이스] 방법3: execCommand insertText');
  try {
    element.focus();
    const selection = doc.getSelection();
    const range = doc.createRange();
    range.selectNodeContents(element);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);

    const insertResult = doc.execCommand('insertText', false, text);
    console.log('[닥터보이스] insertText 결과:', insertResult);
    await sleep(200);

    if (element.textContent.includes(text.substring(0, 20))) {
      console.log('[닥터보이스] 방법3 성공!');
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] 방법3 실패:', e.message);
  }

  // 방법 4: ClipboardEvent 발생
  console.log('[닥터보이스] 방법4: ClipboardEvent');
  try {
    element.focus();
    await sleep(100);

    const dataTransfer = new DataTransfer();
    dataTransfer.setData('text/plain', text);

    const pasteEvent = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: dataTransfer
    });

    element.dispatchEvent(pasteEvent);
    await sleep(300);

    if (element.textContent.includes(text.substring(0, 20))) {
      console.log('[닥터보이스] 방법4 성공!');
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] 방법4 실패:', e.message);
  }

  // 방법 5: 직접 입력 + 이벤트 (최후의 수단)
  console.log('[닥터보이스] 방법5: 직접 DOM 조작');
  try {
    element.textContent = text;
    dispatchInputEvents(element, text);

    element.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
    element.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: text }));

    await sleep(200);
    console.log('[닥터보이스] 방법5 완료 (텍스트 길이:', element.textContent.length, ')');
    return element.textContent.length > 10;
  } catch (e) {
    console.log('[닥터보이스] 방법5 실패:', e.message);
  }

  console.log('[닥터보이스] 모든 방법 실패');
  return false;
}

// React 호환 InputEvent 방식으로 입력
async function insertWithReactEvents(element, text, doc) {
  console.log('[닥터보이스] React InputEvent 방식 시작');

  // 요소 포커스
  element.focus();
  await sleep(50);

  // 캐럿을 요소 끝에 위치
  const selection = doc.getSelection();
  const range = doc.createRange();
  range.selectNodeContents(element);
  range.collapse(false); // 끝에 위치
  selection.removeAllRanges();
  selection.addRange(range);

  // beforeinput 이벤트 발생 (React가 주로 사용)
  const beforeInputEvent = new InputEvent('beforeinput', {
    bubbles: true,
    cancelable: true,
    inputType: 'insertText',
    data: text
  });
  element.dispatchEvent(beforeInputEvent);

  // 텍스트 직접 삽입
  const textNode = doc.createTextNode(text);
  range.insertNode(textNode);

  // input 이벤트 발생
  const inputEvent = new InputEvent('input', {
    bubbles: true,
    inputType: 'insertText',
    data: text
  });
  element.dispatchEvent(inputEvent);

  await sleep(100);

  // 성공 여부 확인
  const success = element.textContent.includes(text.substring(0, 20));
  console.log('[닥터보이스] React InputEvent 결과:', success);
  return success;
}

// 한 글자씩 키 입력 시뮬레이션 (청크 단위)
async function insertCharByChar(element, text, doc) {
  console.log('[닥터보이스] 키 입력 시뮬레이션 시작');

  element.focus();
  await sleep(50);

  // 캐럿 위치 설정
  const selection = doc.getSelection();
  const range = doc.createRange();
  range.selectNodeContents(element);
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);

  // 청크 단위로 입력 (성능 최적화)
  const chunkSize = 50;
  const chunks = [];
  for (let i = 0; i < text.length; i += chunkSize) {
    chunks.push(text.substring(i, i + chunkSize));
  }

  console.log('[닥터보이스] 청크 수:', chunks.length);

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];

    // Composition 이벤트 시작
    element.dispatchEvent(new CompositionEvent('compositionstart', {
      bubbles: true,
      data: ''
    }));

    // Composition 업데이트
    element.dispatchEvent(new CompositionEvent('compositionupdate', {
      bubbles: true,
      data: chunk
    }));

    // beforeinput 이벤트
    element.dispatchEvent(new InputEvent('beforeinput', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertCompositionText',
      data: chunk
    }));

    // 텍스트 노드 삽입
    const textNode = doc.createTextNode(chunk);
    const currentRange = selection.getRangeAt(0);
    currentRange.insertNode(textNode);
    currentRange.setStartAfter(textNode);
    currentRange.setEndAfter(textNode);
    selection.removeAllRanges();
    selection.addRange(currentRange);

    // input 이벤트
    element.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertCompositionText',
      data: chunk
    }));

    // Composition 종료
    element.dispatchEvent(new CompositionEvent('compositionend', {
      bubbles: true,
      data: chunk
    }));

    // 진행상황 표시 (10% 단위)
    if (i % Math.ceil(chunks.length / 10) === 0) {
      const progress = Math.round((i / chunks.length) * 100);
      console.log('[닥터보이스] 입력 진행:', progress + '%');
    }

    // 짧은 대기 (UI 업데이트 허용)
    if (i % 5 === 0) await sleep(10);
  }

  await sleep(100);
  const success = element.textContent.includes(text.substring(0, 20));
  console.log('[닥터보이스] 키 입력 시뮬레이션 결과:', success);
  return success;
}

// 입력 이벤트 발생
function dispatchInputEvents(element, text) {
  const events = [
    new Event('focus', { bubbles: true }),
    new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }),
    new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }),
    new Event('change', { bubbles: true }),
    new Event('blur', { bubbles: true }),
    new Event('focus', { bubbles: true })
  ];

  for (const event of events) {
    try {
      element.dispatchEvent(event);
    } catch (e) {}
  }

  // 부모 요소에도 이벤트 발생
  const parent = element.closest('.se-component');
  if (parent) {
    parent.dispatchEvent(new Event('input', { bubbles: true }));
    parent.dispatchEvent(new CustomEvent('change', { bubbles: true }));
  }
}

// 블로그용 텍스트 포맷팅 (HTML 없이 텍스트만)
function formatContentForBlog(content) {
  let result = content;

  // 1. > 인용구를 ━━ 구분선으로 강조
  result = result.replace(/^>\s*(.+)$/gm, '\n━━━━━━━━━━━━━━━━\n💬 $1\n━━━━━━━━━━━━━━━━\n');

  // 2. 핵심 문장에 이모지 추가
  const keyPhrases = ['핵심은', '결론은', '요점은', '비결은', '포인트는', '기억하세요', '명심하세요'];
  for (const phrase of keyPhrases) {
    result = result.replace(new RegExp(`(${phrase}.{0,100}[.!?])`, 'g'), '\n⭐ $1 ⭐\n');
  }

  // 3. 줄바꿈 정리 (가독성 향상)
  result = result
    .replace(/\n{4,}/g, '\n\n\n')  // 과도한 줄바꿈 제거
    .replace(/([.!?])\s+/g, '$1\n\n')  // 문장 끝에 줄바꿈 추가
    .trim();

  console.log('[닥터보이스] 텍스트 포맷팅 완료');
  return result;
}

// 본문 입력 단계
async function startBodyInput(postData, doc) {
  // 본문을 읽기 좋게 정리 (HTML 없이 텍스트만)
  const formattedContent = formatContentForBlog(postData.content);

  // 일반 텍스트로 클립보드에 복사
  await navigator.clipboard.writeText(formattedContent);

  // 본문 영역 클릭하여 포커스
  const bodyComponents = doc.querySelectorAll('.se-component.se-text');
  for (const comp of bodyComponents) {
    if (comp.classList.contains('se-documentTitle')) continue;
    if (comp.closest('.se-documentTitle')) continue;

    const bodyParagraph = comp.querySelector('.se-text-paragraph');
    if (bodyParagraph) {
      simulateRealClick(bodyParagraph);
      await sleep(300);
      bodyParagraph.focus();
      break;
    }
  }

  // 간단한 안내 표시
  showSimplePasteGuide('본문', postData.content, async () => {
    // 이미지가 있으면 이미지 안내
    if (postData.imageUrls && postData.imageUrls.length > 0) {
      await sleep(500);
      showImageGuide(postData.imageUrls);
    } else {
      // 완료
      showFinalSuccess();
    }
  });
}

// 이미지 안내
function showImageGuide(imageUrls) {
  const old = document.querySelector('.dv-step-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-step-notify';
  el.innerHTML = `
    <div style="font-size: 40px; margin-bottom: 12px;">🖼️</div>
    <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">3단계: 이미지 추가</div>
    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 16px;">
      이미지 ${imageUrls.length}개를 추가해주세요
    </div>
    <div style="background: rgba(255,255,255,0.15); padding: 12px; border-radius: 8px; margin-bottom: 16px; text-align: left; max-height: 150px; overflow-y: auto;">
      ${imageUrls.map((url, i) => `
        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
          <span style="background: white; color: #333; padding: 2px 8px; border-radius: 4px; font-size: 12px;">${i+1}</span>
          <button class="dv-copy-img-btn" data-url="${url}" style="
            background: white;
            color: #333;
            border: none;
            padding: 4px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
          ">URL 복사</button>
        </div>
      `).join('')}
    </div>
    <div style="font-size: 13px; opacity: 0.9; margin-bottom: 16px;">
      💡 상단 도구모음에서 <strong>"사진"</strong> 버튼 클릭 → <strong>"URL"</strong> 탭 선택 → URL 붙여넣기
    </div>
    <button id="dv-done-btn" style="
      background: white;
      color: #333;
      border: none;
      padding: 12px 32px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 15px;
      font-weight: 600;
    ">✅ 완료</button>
  `;
  el.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #8b5cf6, #6d28d9);
    color: white;
    padding: 28px 36px;
    border-radius: 16px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.4);
    max-width: 400px;
  `;

  document.body.appendChild(el);

  // URL 복사 버튼들
  el.querySelectorAll('.dv-copy-img-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(btn.dataset.url);
      btn.textContent = '✅ 복사됨!';
      setTimeout(() => btn.textContent = 'URL 복사', 2000);
    });
  });

  // 완료 버튼
  document.getElementById('dv-done-btn').addEventListener('click', () => {
    el.remove();
    showFinalSuccess();
  });
}

// 최종 완료 알림
function showFinalSuccess() {
  const old = document.querySelector('.dv-step-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-step-notify';
  el.innerHTML = `
    <div style="font-size: 48px; margin-bottom: 12px;">🎉</div>
    <div style="font-size: 22px; font-weight: bold; margin-bottom: 8px;">입력 완료!</div>
    <div style="font-size: 14px; opacity: 0.95; margin-bottom: 20px;">
      내용을 확인하고 오른쪽 상단의<br>
      <strong style="color: #4ade80;">녹색 "발행" 버튼</strong>을 클릭하세요
    </div>
    <button id="dv-final-close" style="
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.4);
      color: white;
      padding: 10px 30px;
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
    padding: 36px 48px;
    border-radius: 20px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.4);
  `;

  document.body.appendChild(el);

  document.getElementById('dv-final-close').addEventListener('click', () => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 200);
  });

  // 5초 후 자동 닫기
  setTimeout(() => {
    if (el.parentNode) {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 200);
    }
  }, 5000);
}

// 단계별 알림 표시
function showStepNotification(step, desc, instruction, preview, onPaste) {
  const old = document.querySelector('.dv-step-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-step-notify';
  el.innerHTML = `
    <div style="font-size: 40px; margin-bottom: 12px;">📋</div>
    <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">${step}</div>
    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 16px;">${desc}</div>

    <div style="
      background: rgba(0,0,0,0.3);
      padding: 16px 24px;
      border-radius: 12px;
      margin-bottom: 16px;
    ">
      <div style="font-size: 28px; font-weight: bold; letter-spacing: 2px;">Ctrl + V</div>
      <div style="font-size: 12px; margin-top: 4px; opacity: 0.8;">${instruction}</div>
    </div>

    <div style="
      background: rgba(255,255,255,0.1);
      padding: 12px;
      border-radius: 8px;
      font-size: 12px;
      text-align: left;
      max-height: 60px;
      overflow: hidden;
      margin-bottom: 16px;
    ">
      <div style="opacity: 0.7;">미리보기:</div>
      <div style="margin-top: 4px;">${preview}</div>
    </div>

    <button id="dv-skip-btn" style="
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.3);
      color: white;
      padding: 8px 20px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
    ">건너뛰기</button>
  `;
  el.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white;
    padding: 28px 36px;
    border-radius: 16px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.4);
    max-width: 380px;
    animation: popIn 0.3s ease;
  `;

  // 애니메이션 스타일
  const style = document.createElement('style');
  style.textContent = `
    @keyframes popIn {
      from { transform: translate(-50%, -50%) scale(0.9); opacity: 0; }
      to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    }
  `;
  document.head.appendChild(style);

  document.body.appendChild(el);

  // Ctrl+V 감지
  const handleKeydown = async (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
      document.removeEventListener('keydown', handleKeydown);
      el.innerHTML = `
        <div style="font-size: 40px;">✅</div>
        <div style="font-size: 18px; margin-top: 8px;">붙여넣기 완료!</div>
      `;
      await sleep(800);
      el.remove();
      if (onPaste) onPaste();
    }
  };
  document.addEventListener('keydown', handleKeydown);

  // 건너뛰기 버튼
  document.getElementById('dv-skip-btn').addEventListener('click', () => {
    document.removeEventListener('keydown', handleKeydown);
    el.remove();
    if (onPaste) onPaste();
  });
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

// 실제 마우스 클릭 시뮬레이션
function simulateRealClick(element) {
  const rect = element.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  const mousedownEvent = new MouseEvent('mousedown', {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y
  });

  const mouseupEvent = new MouseEvent('mouseup', {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y
  });

  const clickEvent = new MouseEvent('click', {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y
  });

  element.dispatchEvent(mousedownEvent);
  element.dispatchEvent(mouseupEvent);
  element.dispatchEvent(clickEvent);
}

// 에디터 document 가져오기 (메인 또는 iframe)
function getActiveEditorDocument() {
  // 먼저 메인 문서에서 확인
  if (document.querySelector('.se-component.se-documentTitle')) {
    console.log('[닥터보이스] 에디터: 메인 문서');
    return document;
  }

  // iframe 내부에서 찾기
  const iframes = document.querySelectorAll('iframe');
  for (const iframe of iframes) {
    try {
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
      if (iframeDoc && iframeDoc.querySelector('.se-component.se-documentTitle')) {
        console.log('[닥터보이스] 에디터: iframe 내부');
        return iframeDoc;
      }
    } catch (e) {
      // cross-origin 무시
    }
  }

  // 찾지 못하면 전역 editorDoc 사용
  if (editorDoc) {
    console.log('[닥터보이스] 에디터: 전역 editorDoc 사용');
    return editorDoc;
  }

  console.log('[닥터보이스] 에디터: 기본 document 사용');
  return document;
}

// 제목 입력 (execCommand insertText 방식)
async function inputTitle(title) {
  console.log('[닥터보이스] 제목 입력:', title);

  const doc = getActiveEditorDocument();
  const win = doc.defaultView || window;

  // 제목 영역 찾기
  const titleComponent = doc.querySelector('.se-component.se-documentTitle');
  if (!titleComponent) {
    console.warn('[닥터보이스] 제목 컴포넌트 찾기 실패');
    return false;
  }

  const titleParagraph = titleComponent.querySelector('.se-text-paragraph');
  if (!titleParagraph) {
    console.warn('[닥터보이스] 제목 paragraph 찾기 실패');
    return false;
  }

  // 제목 span 찾기
  let titleSpan = titleComponent.querySelector('span.se-fs32.__se-node') ||
                  titleComponent.querySelector('span.__se-node');

  // 방법 1: execCommand insertText (가장 효과적인 방법)
  const execSuccess = await tryExecCommandInsert(titleParagraph, titleSpan, title, doc);
  if (execSuccess) {
    console.log('[닥터보이스] 제목 execCommand insertText 성공');
    return true;
  }

  // 방법 2: 한 글자씩 입력 시뮬레이션
  const typeSuccess = await tryTypeText(titleParagraph, titleSpan, title, doc);
  if (typeSuccess) {
    console.log('[닥터보이스] 제목 글자별 입력 성공');
    return true;
  }

  // 방법 3: Selection + insertText
  const selectionSuccess = await trySelectionInsert(titleParagraph, titleSpan, title, doc);
  if (selectionSuccess) {
    console.log('[닥터보이스] 제목 Selection 삽입 성공');
    return true;
  }

  console.log('[닥터보이스] 제목 자동 입력 실패');
  return false;
}

// execCommand insertText 시도
async function tryExecCommandInsert(paragraph, span, text, doc) {
  try {
    const targetEl = span || paragraph;

    // 요소 클릭하여 활성화
    simulateRealClick(paragraph);
    await sleep(200);

    if (span) {
      simulateRealClick(span);
      await sleep(100);
    }

    // 포커스
    targetEl.focus();
    await sleep(100);

    // 기존 내용 선택 (있으면)
    const selection = doc.getSelection();
    const range = doc.createRange();
    range.selectNodeContents(targetEl);
    selection.removeAllRanges();
    selection.addRange(range);
    await sleep(50);

    // execCommand insertText 실행
    const result = doc.execCommand('insertText', false, text);
    console.log('[닥터보이스] execCommand insertText 결과:', result);

    if (result) {
      // 입력 이벤트 발생
      targetEl.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: false,
        inputType: 'insertText',
        data: text
      }));
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] execCommand insertText 실패:', e.message);
  }
  return false;
}

// 한 글자씩 타이핑 시뮬레이션
async function tryTypeText(paragraph, span, text, doc) {
  try {
    const targetEl = span || paragraph;

    // 요소 활성화
    simulateRealClick(paragraph);
    await sleep(200);
    if (span) {
      simulateRealClick(span);
      await sleep(100);
    }
    targetEl.focus();
    await sleep(100);

    // 기존 내용 삭제
    const selection = doc.getSelection();
    const range = doc.createRange();
    range.selectNodeContents(targetEl);
    selection.removeAllRanges();
    selection.addRange(range);
    doc.execCommand('delete', false, null);
    await sleep(100);

    // 한 글자씩 입력
    for (const char of text) {
      // keydown
      targetEl.dispatchEvent(new KeyboardEvent('keydown', {
        key: char,
        code: 'Key' + char.toUpperCase(),
        bubbles: true,
        cancelable: true
      }));

      // beforeinput
      targetEl.dispatchEvent(new InputEvent('beforeinput', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: char
      }));

      // 실제 텍스트 삽입
      doc.execCommand('insertText', false, char);

      // input
      targetEl.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: false,
        inputType: 'insertText',
        data: char
      }));

      // keyup
      targetEl.dispatchEvent(new KeyboardEvent('keyup', {
        key: char,
        code: 'Key' + char.toUpperCase(),
        bubbles: true
      }));

      // 짧은 지연 (타이핑 속도 시뮬레이션)
      await sleep(5);
    }

    console.log('[닥터보이스] 글자별 입력 완료');
    return true;
  } catch (e) {
    console.log('[닥터보이스] 글자별 입력 실패:', e.message);
  }
  return false;
}

// Selection API로 텍스트 삽입
async function trySelectionInsert(paragraph, span, text, doc) {
  try {
    const targetEl = span || paragraph;

    // 포커스 및 선택
    simulateRealClick(paragraph);
    await sleep(200);
    targetEl.focus();

    const selection = doc.getSelection();
    const range = doc.createRange();

    // 텍스트 노드 생성 및 삽입
    range.selectNodeContents(targetEl);
    selection.removeAllRanges();
    selection.addRange(range);

    // 선택된 내용 삭제
    range.deleteContents();

    // 새 텍스트 노드 삽입
    const textNode = doc.createTextNode(text);
    range.insertNode(textNode);

    // 커서를 텍스트 끝으로
    range.setStartAfter(textNode);
    range.setEndAfter(textNode);
    selection.removeAllRanges();
    selection.addRange(range);

    // 입력 이벤트
    targetEl.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertText',
      data: text
    }));

    console.log('[닥터보이스] Selection 삽입 완료');
    return true;
  } catch (e) {
    console.log('[닥터보이스] Selection 삽입 실패:', e.message);
  }
  return false;
}

// React Fiber를 통한 상태 업데이트 시도
async function tryReactStateUpdate(element, text, doc) {
  if (!element) return false;

  try {
    // React Fiber 키 찾기
    const reactKey = Object.keys(element).find(k =>
      k.startsWith('__reactFiber') ||
      k.startsWith('__reactInternalInstance') ||
      k.startsWith('__reactProps')
    );

    if (!reactKey) {
      console.log('[닥터보이스] React Fiber 없음');
      return false;
    }

    const fiber = element[reactKey];
    console.log('[닥터보이스] React Fiber 발견:', reactKey);

    // stateNode에서 setState 찾기
    if (fiber.stateNode && typeof fiber.stateNode.setState === 'function') {
      console.log('[닥터보이스] setState 발견, 호출 시도');
      fiber.stateNode.setState({ text: text, value: text });
      return true;
    }

    // memoizedProps에서 onChange 찾기
    if (fiber.memoizedProps) {
      const props = fiber.memoizedProps;
      console.log('[닥터보이스] React Props:', Object.keys(props));

      if (typeof props.onChange === 'function') {
        console.log('[닥터보이스] onChange 호출');
        props.onChange({ target: { value: text } });
        return true;
      }

      if (typeof props.onInput === 'function') {
        console.log('[닥터보이스] onInput 호출');
        props.onInput({ target: { value: text } });
        return true;
      }
    }

    // 부모 Fiber에서 찾기
    let current = fiber.return;
    let depth = 0;
    while (current && depth < 10) {
      if (current.stateNode && current.stateNode.props) {
        const props = current.stateNode.props;
        if (typeof props.onChange === 'function') {
          console.log('[닥터보이스] 부모 onChange 발견');
          props.onChange({ target: { value: text } });
          return true;
        }
      }
      current = current.return;
      depth++;
    }

  } catch (e) {
    console.log('[닥터보이스] React 상태 업데이트 실패:', e.message);
  }

  return false;
}

// 네이버 에디터 내부 API 호출 시도
async function tryNaverEditorAPI(component, text, type, win) {
  try {
    // 전역 에디터 인스턴스 찾기
    const editorPatterns = [
      'SE', 'seEditor', 'smartEditor', 'blogEditor', 'editor', 'Editor',
      '__EDITOR__', 'EDITOR_INSTANCE', 'editorInstance'
    ];

    for (const pattern of editorPatterns) {
      if (win[pattern]) {
        console.log('[닥터보이스] 전역 에디터 발견:', pattern);
        const editor = win[pattern];

        // 일반적인 에디터 메서드 시도
        const methods = ['setContent', 'setValue', 'insertText', 'setText', 'setHTML',
                        'setTitle', 'setBody', 'insert', 'write', 'paste'];

        for (const method of methods) {
          if (typeof editor[method] === 'function') {
            console.log('[닥터보이스] 메서드 발견:', method);
            try {
              editor[method](text);
              return true;
            } catch (e) {
              console.log('[닥터보이스] 메서드 호출 실패:', method);
            }
          }
        }

        // 중첩된 객체 탐색
        for (const key in editor) {
          if (typeof editor[key] === 'object' && editor[key] !== null) {
            for (const method of methods) {
              if (typeof editor[key][method] === 'function') {
                console.log('[닥터보이스] 중첩 메서드 발견:', key + '.' + method);
                try {
                  editor[key][method](text);
                  return true;
                } catch (e) {}
              }
            }
          }
        }
      }
    }

    // 컴포넌트 ID로 에디터 접근 시도
    const compId = component.getAttribute('data-compid');
    if (compId && win.SE && win.SE.editor) {
      console.log('[닥터보이스] 컴포넌트 ID로 접근:', compId);
      const compEditor = win.SE.editor.getComponent?.(compId);
      if (compEditor) {
        console.log('[닥터보이스] 컴포넌트 에디터 발견');
        if (typeof compEditor.setValue === 'function') {
          compEditor.setValue(text);
          return true;
        }
      }
    }

  } catch (e) {
    console.log('[닥터보이스] 네이버 API 호출 실패:', e.message);
  }

  return false;
}

// 직접 텍스트 노드 교체 + 이벤트 발생
async function tryDirectTextInsert(element, text, doc) {
  if (!element) return false;

  try {
    // 기존 텍스트 노드 제거하고 새로 생성
    const textNode = doc.createTextNode(text);

    // 플레이스홀더 제거
    const placeholder = element.closest('.se-module-text')?.querySelector('.se-placeholder');
    if (placeholder) {
      placeholder.style.display = 'none';
    }

    // 기존 내용 제거
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }

    // 새 텍스트 노드 추가
    element.appendChild(textNode);

    // 다양한 이벤트 발생
    const events = [
      new Event('focus', { bubbles: true }),
      new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }),
      new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }),
      new Event('change', { bubbles: true }),
      new Event('blur', { bubbles: true })
    ];

    for (const event of events) {
      element.dispatchEvent(event);
      await sleep(50);
    }

    // 커스텀 이벤트도 시도
    element.dispatchEvent(new CustomEvent('se-text-change', { bubbles: true, detail: { text } }));
    element.dispatchEvent(new CustomEvent('contentchange', { bubbles: true, detail: { text } }));

    console.log('[닥터보이스] 직접 삽입 완료');
    return true;

  } catch (e) {
    console.log('[닥터보이스] 직접 삽입 실패:', e.message);
  }

  return false;
}

// 붙여넣기 시뮬레이션
async function simulatePaste(doc, targetElement, text) {
  const win = doc.defaultView || window;

  // 포커스 확인
  targetElement.focus();
  await sleep(100);

  // 방법 1: execCommand paste (보안상 대부분 차단됨)
  try {
    const pasteResult = doc.execCommand('paste');
    if (pasteResult) {
      console.log('[닥터보이스] execCommand paste 성공');
      return true;
    }
  } catch (e) {
    console.log('[닥터보이스] execCommand paste 실패');
  }

  // 방법 2: ClipboardEvent 직접 생성
  try {
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', text);

    const pasteEvent = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: clipboardData
    });

    targetElement.dispatchEvent(pasteEvent);
    console.log('[닥터보이스] ClipboardEvent 발생');
    await sleep(200);

    // 입력 이벤트도 발생
    targetElement.dispatchEvent(new InputEvent('beforeinput', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertFromPaste',
      data: text
    }));

    targetElement.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertFromPaste',
      data: text
    }));

    return true;
  } catch (e) {
    console.log('[닥터보이스] ClipboardEvent 실패:', e.message);
  }

  // 방법 3: Ctrl+V 키보드 이벤트
  try {
    const keydownEvent = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'v',
      code: 'KeyV',
      keyCode: 86,
      which: 86,
      ctrlKey: true,
      metaKey: false
    });

    targetElement.dispatchEvent(keydownEvent);
    await sleep(100);

    const keyupEvent = new KeyboardEvent('keyup', {
      bubbles: true,
      cancelable: true,
      key: 'v',
      code: 'KeyV',
      keyCode: 86,
      which: 86,
      ctrlKey: true
    });

    targetElement.dispatchEvent(keyupEvent);
    console.log('[닥터보이스] Ctrl+V 키보드 이벤트 발생');

    return true;
  } catch (e) {
    console.log('[닥터보이스] 키보드 이벤트 실패:', e.message);
  }

  return false;
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
  console.log('[닥터보이스] 본문 영역 찾기 시작');

  // 메인 문서에서 먼저 찾기
  let bodySpan = findBodySpanInDocument(document);

  // 메인 문서에 없으면 editorDoc에서 찾기
  if (!bodySpan && editorDoc && editorDoc !== document) {
    bodySpan = findBodySpanInDocument(editorDoc);
  }

  if (bodySpan) {
    return bodySpan;
  }

  console.log('[닥터보이스] 본문 영역 찾기 실패');
  return null;
}

// 특정 문서에서 본문 span 찾기
function findBodySpanInDocument(doc) {
  // 1. .se-module-text 중 제목이 아닌 것에서 span 찾기
  const bodyModules = doc.querySelectorAll('.se-module-text');

  for (const module of bodyModules) {
    // 제목 영역 내부면 제외
    if (module.closest('.se-section-documentTitle')) continue;
    // se-title-text 클래스면 제외
    if (module.classList.contains('se-title-text')) continue;

    const bodySpan = module.querySelector('span.se-fs16.__se-node') ||
                     module.querySelector('span[id^="SE-"].__se-node:not(.se-fs32)');
    if (bodySpan) {
      console.log('[닥터보이스] 본문 영역 발견 (module):', bodySpan.id);
      return bodySpan;
    }
  }

  // 2. se-fs16 span 직접 찾기 (제목 영역 제외)
  const fs16Spans = doc.querySelectorAll('span.se-fs16.__se-node');
  for (const span of fs16Spans) {
    if (!span.closest('.se-section-documentTitle')) {
      console.log('[닥터보이스] 본문 영역 발견 (se-fs16):', span.id);
      return span;
    }
  }

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

// 본문 + 이미지 URL 함께 삽입 (execCommand insertText 방식)
async function insertContentWithImages(content, imageUrls, options) {
  console.log('[닥터보이스] 본문 + 이미지 URL 삽입 시작');
  console.log('[닥터보이스] 이미지 URL 개수:', imageUrls.length);

  const doc = getActiveEditorDocument();
  const win = doc.defaultView || window;

  // 본문 컴포넌트 찾기 (제목이 아닌 se-text 컴포넌트)
  const bodyComponents = doc.querySelectorAll('.se-component.se-text');
  let bodyComponent = null;

  for (const comp of bodyComponents) {
    if (comp.classList.contains('se-documentTitle')) continue;
    if (comp.closest('.se-documentTitle')) continue;
    bodyComponent = comp;
    break;
  }

  if (!bodyComponent) {
    console.error('[닥터보이스] 본문 컴포넌트 찾기 실패');
    return false;
  }

  console.log('[닥터보이스] 본문 컴포넌트 발견:', bodyComponent.id);

  const bodyParagraph = bodyComponent.querySelector('.se-text-paragraph');
  if (!bodyParagraph) {
    console.error('[닥터보이스] 본문 paragraph 찾기 실패');
    return false;
  }

  // 본문 span 찾기
  let bodySpan = bodyComponent.querySelector('span[contenteditable="true"].__se-node') ||
                 bodyComponent.querySelector('span.se-fs16.__se-node') ||
                 bodyComponent.querySelector('span.__se-node');

  // 플레이스홀더 숨기기
  const placeholders = bodyComponent.querySelectorAll('.se-placeholder');
  placeholders.forEach(p => p.style.display = 'none');

  // 방법 1: execCommand insertText (가장 효과적인 방법)
  const execSuccess = await tryExecCommandInsert(bodyParagraph, bodySpan, content, doc);
  if (execSuccess) {
    console.log('[닥터보이스] 본문 execCommand insertText 성공');
    return true;
  }

  // 방법 2: 짧은 본문은 글자별 입력 시도 (긴 본문은 시간이 너무 오래 걸림)
  if (content.length < 500) {
    const typeSuccess = await tryTypeText(bodyParagraph, bodySpan, content, doc);
    if (typeSuccess) {
      console.log('[닥터보이스] 본문 글자별 입력 성공');
      return true;
    }
  }

  // 방법 3: Selection + insertText
  const selectionSuccess = await trySelectionInsert(bodyParagraph, bodySpan, content, doc);
  if (selectionSuccess) {
    console.log('[닥터보이스] 본문 Selection 삽입 성공');
    return true;
  }

  console.log('[닥터보이스] 본문 자동 입력 실패');

  // 이미지 URL 처리
  if (imageUrls && imageUrls.length > 0) {
    console.log('[닥터보이스] 이미지 URL', imageUrls.length, '개');
  }

  return false;
}

// 실제 편집 가능한 본문 영역 찾기
async function findEditableBodyArea() {
  console.log('[닥터보이스] 편집 가능한 본문 영역 찾기');

  // 요소가 화면에 보이는지 확인하는 함수
  function isVisible(el) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();

    // 화면 밖에 있는 요소 제외 (left: -9999px 같은 숨겨진 요소)
    if (rect.left < -1000 || rect.top < -1000) return false;
    if (style.display === 'none') return false;
    if (style.visibility === 'hidden') return false;
    if (rect.width === 0 || rect.height === 0) return false;

    return true;
  }

  // 1. 네이버 스마트에디터 본문 영역 직접 찾기 (가장 우선)
  // 본문 텍스트 컴포넌트 찾기 (제목 영역 제외)
  const textComponents = document.querySelectorAll('.se-component.se-text');
  for (const comp of textComponents) {
    // 제목 영역 제외
    if (comp.closest('.se-section-documentTitle')) continue;

    // se-text-paragraph 찾기
    const paragraph = comp.querySelector('.se-text-paragraph');
    if (paragraph && isVisible(paragraph)) {
      console.log('[닥터보이스] 본문 se-text-paragraph 발견');
      return paragraph;
    }
  }

  // 2. se-section (섹션)에서 본문 찾기
  const sections = document.querySelectorAll('.se-section');
  for (const section of sections) {
    // 제목 섹션 제외
    if (section.classList.contains('se-section-documentTitle')) continue;

    const paragraph = section.querySelector('.se-text-paragraph');
    if (paragraph && isVisible(paragraph)) {
      console.log('[닥터보이스] 본문 섹션 paragraph 발견');
      return paragraph;
    }
  }

  // 3. 보이는 contenteditable 찾기 (숨겨진 클립보드 헬퍼 제외)
  const editables = document.querySelectorAll('[contenteditable="true"]');
  for (const el of editables) {
    // 제목 영역 제외
    if (el.closest('.se-section-documentTitle') || el.closest('.se-documentTitle')) continue;

    // 숨겨진 요소 제외
    if (!isVisible(el)) {
      console.log('[닥터보이스] 숨겨진 contenteditable 스킵');
      continue;
    }

    console.log('[닥터보이스] 보이는 contenteditable 발견:', el.className);
    return el;
  }

  // 4. iframe 내부에서 찾기
  const iframes = document.querySelectorAll('iframe');
  for (const iframe of iframes) {
    try {
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
      if (!iframeDoc) continue;

      // iframe body가 contenteditable인 경우
      if (iframeDoc.body && iframeDoc.body.getAttribute('contenteditable') === 'true') {
        console.log('[닥터보이스] iframe body contenteditable 발견');
        return iframeDoc.body;
      }
    } catch (e) {
      // cross-origin 무시
    }
  }

  // 5. 마지막 시도: .se-content 내부의 텍스트 영역
  const seContent = document.querySelector('.se-content');
  if (seContent) {
    const textPara = seContent.querySelector('.se-text-paragraph:not(.se-section-documentTitle .se-text-paragraph)');
    if (textPara) {
      console.log('[닥터보이스] se-content 내 paragraph 발견');
      return textPara;
    }
  }

  console.log('[닥터보이스] 편집 가능한 본문 영역 찾기 실패');
  return null;
}

// 대체 방법: span 요소에 직접 입력
async function insertContentFallback(content, imageUrls) {
  console.log('[닥터보이스] 대체 방법으로 본문 입력');

  const bodyArea = await findBodyArea();
  if (!bodyArea) {
    console.error('[닥터보이스] 본문 영역 완전히 찾기 실패');
    return;
  }

  // span을 contenteditable로 만들기
  bodyArea.setAttribute('contenteditable', 'true');
  bodyArea.click();
  await sleep(200);
  bodyArea.focus();
  await sleep(200);

  // 본문 HTML 생성
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  let html = paragraphs.map(p => p.replace(/\n/g, '<br>')).join('<br><br>');

  // 이미지 추가
  if (imageUrls && imageUrls.length > 0) {
    html += '<br><br>';
    for (const url of imageUrls) {
      html += `<img src="${url}" style="max-width:100%"><br><br>`;
    }
  }

  // execCommand로 삽입
  document.execCommand('selectAll', false, null);
  document.execCommand('insertHTML', false, html);

  bodyArea.dispatchEvent(new InputEvent('input', { bubbles: true }));
  console.log('[닥터보이스] 대체 방법 입력 완료');
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

// 수동 붙여넣기 안내 알림
function showManualPasteNotification(title, content) {
  const old = document.querySelector('.dv-manual-paste');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-manual-paste';
  el.innerHTML = `
    <div style="font-size: 48px; margin-bottom: 16px;">📋</div>
    <div style="font-size: 22px; font-weight: bold; margin-bottom: 12px;">수동 입력이 필요합니다</div>
    <div style="font-size: 14px; opacity: 0.95; margin-bottom: 20px;">
      보안 정책으로 인해 자동 입력이 제한되었습니다.<br>
      아래 단계를 따라주세요:
    </div>
    <div style="background: rgba(255,255,255,0.15); padding: 16px; border-radius: 10px; text-align: left; margin-bottom: 20px;">
      <div style="margin-bottom: 10px;"><strong>1️⃣ 제목 입력:</strong> 제목 영역 클릭 → <kbd style="background:#fff;color:#333;padding:2px 6px;border-radius:4px;">Ctrl+V</kbd></div>
      <div style="margin-bottom: 10px;"><strong>2️⃣ 제목 복사:</strong> 아래 버튼 클릭</div>
      <button id="dv-copy-title" style="
        background: white;
        color: #333;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 13px;
        margin-bottom: 10px;
      ">📋 제목 복사하기</button>
      <div style="margin-top: 10px;"><strong>3️⃣ 본문 입력:</strong> 본문 영역 클릭 → <kbd style="background:#fff;color:#333;padding:2px 6px;border-radius:4px;">Ctrl+V</kbd></div>
      <button id="dv-copy-content" style="
        background: white;
        color: #333;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 13px;
        margin-top: 10px;
      ">📋 본문 복사하기</button>
    </div>
    <button id="dv-close-manual" style="
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.4);
      color: white;
      padding: 10px 30px;
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
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white;
    padding: 32px 40px;
    border-radius: 20px;
    text-align: center;
    z-index: 999999;
    box-shadow: 0 15px 50px rgba(0,0,0,0.5);
    max-width: 450px;
  `;

  document.body.appendChild(el);

  // 제목 복사 버튼
  document.getElementById('dv-copy-title').addEventListener('click', async () => {
    await navigator.clipboard.writeText(title);
    document.getElementById('dv-copy-title').textContent = '✅ 제목 복사됨!';
  });

  // 본문 복사 버튼
  document.getElementById('dv-copy-content').addEventListener('click', async () => {
    await navigator.clipboard.writeText(content);
    document.getElementById('dv-copy-content').textContent = '✅ 본문 복사됨!';
  });

  // 닫기 버튼
  document.getElementById('dv-close-manual').addEventListener('click', () => {
    el.remove();
  });
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

console.log('[닥터보이스] v12.0 초기화 완료');
