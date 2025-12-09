// 네이버 블로그 스마트에디터 v8.0 - 이미지 자동 업로드 지원
console.log('[닥터보이스] v8.0 로드 - 이미지 자동 업로드 지원');

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

// 글 입력 처리
async function handleInsertPost(postData, options) {
  console.log('[닥터보이스] 글 입력 시작');
  console.log('[닥터보이스] 제목:', postData.title);
  console.log('[닥터보이스] 이미지 수:', postData.images?.length || 0);

  showNotification('📝 글 입력 시작...');

  // 1. 에디터 로딩 대기
  await waitForEditor();
  await sleep(1500);

  // 2. 제목 입력
  if (postData.title) {
    await inputTitle(postData.title);
    showNotification('✅ 제목 입력 완료');
    await sleep(500);
  }

  // 3. 본문 입력 (HTML 직접 삽입)
  if (postData.content) {
    await insertContent(postData.content, options);
    showNotification('✅ 본문 입력 완료');
    await sleep(500);
  }

  // 4. 이미지 업로드 (있는 경우)
  if (postData.images && postData.images.length > 0 && options?.useImages) {
    showNotification(`📷 이미지 업로드 중... (0/${postData.images.length})`);
    await uploadImages(postData.images);
    showNotification('✅ 이미지 업로드 완료!');
  }

  // 5. 완료 알림
  showBigSuccessNotification();
}

// 자동 실행
async function autoExecute() {
  const url = window.location.href;
  if (!url.includes('blog.naver.com')) return;
  if (!url.includes('GoBlogWrite') && !url.includes('PostWrite') && !url.includes('editor')) return;

  console.log('[닥터보이스] 글쓰기 페이지 감지');

  try {
    const stored = await chrome.storage.local.get(['pendingPost', 'autoPasteEnabled']);

    if (!stored.autoPasteEnabled || !stored.pendingPost) {
      console.log('[닥터보이스] 자동 붙여넣기 비활성화 또는 데이터 없음');
      return;
    }

    console.log('[닥터보이스] 자동 붙여넣기 시작');
    showNotification('📋 자동 붙여넣기 시작...');

    // 에디터 로딩 대기
    await waitForEditor();
    await sleep(2000);

    // 본문 영역 클릭해서 포커스
    const bodyArea = await findBodyArea();
    if (bodyArea) {
      bodyArea.click();
      bodyArea.focus();
    }

    // 완료 후 플래그 초기화
    await chrome.storage.local.set({ autoPasteEnabled: false });

    // 큰 알림으로 Ctrl+V 안내
    showBigNotification();

  } catch (err) {
    console.error('[닥터보이스] 오류:', err);
    showNotification('❌ 오류: ' + err.message);
  }
}

// 페이지 로드 후 실행
setTimeout(autoExecute, 3000);

// 에디터 로딩 대기
async function waitForEditor() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const maxAttempts = 30;

    const check = () => {
      attempts++;
      // 에디터 영역 확인
      const editor = document.querySelector('.se-component.se-text') ||
                     document.querySelector('[contenteditable="true"]');

      if (editor) {
        console.log('[닥터보이스] 에디터 발견');
        resolve(editor);
        return;
      }

      if (attempts >= maxAttempts) {
        reject(new Error('에디터 로딩 타임아웃'));
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

  // 제목 영역 클릭
  const titleArea = document.querySelector('.se-documentTitle') ||
                    document.querySelector('.se-placeholder.se-fs32')?.parentElement;

  if (titleArea) {
    titleArea.click();
    await sleep(300);
  }

  // 제목 입력 필드 찾기
  const titleInput = document.querySelector('.se-documentTitle .se-text-paragraph') ||
                     document.querySelector('.se-documentTitle [contenteditable="true"]');

  if (titleInput) {
    titleInput.click();
    titleInput.focus();
    await sleep(200);

    // 클립보드로 제목 복사 후 붙여넣기
    await navigator.clipboard.writeText(title);
    document.execCommand('paste');

    console.log('[닥터보이스] 제목 입력 완료');
  } else {
    console.warn('[닥터보이스] 제목 입력 필드 없음');
  }
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
  // 플레이스홀더 클릭 (본문 영역 활성화)
  const placeholder = document.querySelector('.se-placeholder:not(.se-fs32)');
  if (placeholder) {
    placeholder.click();
    await sleep(500);
  }

  // 본문 영역 선택자들
  const selectors = [
    '.se-component.se-text:not(.se-documentTitle) .se-text-paragraph',
    '.se-component.se-text:not(.se-documentTitle) [contenteditable="true"]',
    'span.__se-node[id^="SE-"]',
    '.se-main-container .se-text-paragraph'
  ];

  for (const sel of selectors) {
    const elements = document.querySelectorAll(sel);
    for (const el of elements) {
      if (!el.closest('.se-documentTitle')) {
        console.log('[닥터보이스] 본문 영역 발견:', sel);
        return el;
      }
    }
  }

  return null;
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

// 이미지 업로드
async function uploadImages(images) {
  console.log('[닥터보이스] 이미지 업로드 시작:', images.length, '개');

  for (let i = 0; i < images.length; i++) {
    const imageBase64 = images[i];
    showNotification(`📷 이미지 업로드 중... (${i + 1}/${images.length})`);

    try {
      await uploadSingleImage(imageBase64, i);
      await sleep(1500); // 이미지 간 간격
    } catch (e) {
      console.error('[닥터보이스] 이미지 업로드 실패:', i, e);
    }
  }
}

// 단일 이미지 업로드
async function uploadSingleImage(base64Data, index) {
  console.log('[닥터보이스] 이미지 업로드:', index + 1);

  // 1. 사진 버튼 클릭
  const photoBtn = document.querySelector('.se-toolbar-item-image') ||
                   document.querySelector('[data-name="image"]') ||
                   document.querySelector('.se-toolbar button[data-type="image"]') ||
                   findButtonByText('사진');

  if (!photoBtn) {
    console.error('[닥터보이스] 사진 버튼을 찾을 수 없습니다');
    // 대체 방법: 파일 input 직접 트리거
    await uploadViaFileInput(base64Data);
    return;
  }

  photoBtn.click();
  await sleep(800);

  // 2. 파일 선택 input 찾기
  const fileInput = document.querySelector('input[type="file"][accept*="image"]') ||
                    document.querySelector('.se-popup-add-image input[type="file"]');

  if (fileInput) {
    // base64를 File 객체로 변환
    const file = base64ToFile(base64Data, `image_${index + 1}.png`);

    // DataTransfer를 사용하여 파일 설정
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;

    // change 이벤트 발생
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    console.log('[닥터보이스] 파일 input에 이미지 설정 완료');

    await sleep(2000); // 업로드 대기
  } else {
    console.error('[닥터보이스] 파일 input을 찾을 수 없습니다');
  }

  // 팝업 닫기 (있으면)
  const closeBtn = document.querySelector('.se-popup-close') ||
                   document.querySelector('.se-popup button.cancel');
  if (closeBtn) {
    await sleep(1000);
    // closeBtn.click();
  }
}

// 파일 input으로 직접 업로드
async function uploadViaFileInput(base64Data) {
  // 숨겨진 파일 input 찾기
  const allFileInputs = document.querySelectorAll('input[type="file"]');

  for (const input of allFileInputs) {
    if (input.accept && input.accept.includes('image')) {
      const file = base64ToFile(base64Data, 'uploaded_image.png');
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      input.files = dataTransfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      console.log('[닥터보이스] 대체 방법으로 이미지 업로드 시도');
      await sleep(2000);
      return;
    }
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

// 성공 알림
function showBigSuccessNotification() {
  const old = document.querySelector('.dv-big-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-big-notify';
  el.innerHTML = `
    <div style="font-size: 48px; margin-bottom: 16px;">✅</div>
    <div style="font-size: 24px; font-weight: bold; margin-bottom: 8px;">포스팅 준비 완료!</div>
    <div style="font-size: 14px; opacity: 0.95;">내용을 확인하고 발행 버튼을 클릭하세요</div>
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

  document.body.appendChild(el);

  const closeBtn = el.querySelector('#dv-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    });
  }

  // 10초 후 자동 닫기
  setTimeout(() => {
    if (el.parentNode) {
      el.style.animation = 'fadeOut 0.2s ease';
      setTimeout(() => el.remove(), 200);
    }
  }, 10000);
}

console.log('[닥터보이스] v8.0 초기화 완료');
