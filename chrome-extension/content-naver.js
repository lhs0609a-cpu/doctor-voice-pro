// 네이버 블로그 스마트에디터 v6.0 - 개선된 텍스트 입력
console.log('[닥터보이스] v6.0 로드');

// 자동 실행
async function autoExecute() {
  const url = window.location.href;
  if (!url.includes('blog.naver.com') ||
      (!url.includes('GoBlogWrite') && !url.includes('PostWrite') && !url.includes('editor'))) {
    return;
  }

  console.log('[닥터보이스] 글쓰기 페이지 감지');

  try {
    const stored = await chrome.storage.local.get(['pendingPost', 'postOptions', 'autoPostEnabled']);

    console.log('[닥터보이스] autoPostEnabled:', stored.autoPostEnabled);
    console.log('[닥터보이스] pendingPost:', !!stored.pendingPost);

    if (stored.pendingPost) {
      console.log('[닥터보이스] 제목:', stored.pendingPost.title);
      console.log('[닥터보이스] 본문 길이:', stored.pendingPost.content?.length);
    }

    if (stored.autoPostEnabled && stored.pendingPost) {
      showNotification('자동 포스팅 시작...');

      // 에디터 대기 - 더 긴 시간
      await waitFor('.se-component.se-text', 30000);
      await sleep(4000);

      await insertPost(stored.pendingPost, stored.postOptions || {});
      await chrome.storage.local.set({ autoPostEnabled: false });
    }
  } catch (err) {
    console.error('[닥터보이스] 오류:', err);
    showNotification('오류: ' + err.message);
  }
}

setTimeout(autoExecute, 3000);

// 메시지 수신
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'INSERT_POST') {
    insertPost(msg.data, msg.options)
      .then(() => sendResponse({ success: true }))
      .catch(e => sendResponse({ success: false, error: e.message }));
    return true;
  }
});

// 메인 함수
async function insertPost(data, options) {
  console.log('[닥터보이스] === insertPost 시작 ===');
  console.log('[닥터보이스] 제목:', data.title);
  console.log('[닥터보이스] 본문:', data.content?.substring(0, 200));

  // 1. 제목 입력
  if (data.title) {
    await inputTitle(data.title);
    await sleep(1500);
  }

  // 2. 본문 입력
  if (data.content) {
    await inputContentV6(data.content, data.images);
  }

  showNotification('✅ 완료!');
}

// 제목 입력
async function inputTitle(title) {
  console.log('[닥터보이스] 제목 입력:', title);

  const titleEl = document.querySelector('.se-documentTitle .se-text-paragraph');
  if (!titleEl) {
    console.error('[닥터보이스] 제목 요소 없음');
    return;
  }

  titleEl.click();
  await sleep(300);
  titleEl.focus();
  await sleep(300);

  // execCommand로 입력
  let success = document.execCommand('insertText', false, title);
  console.log('[닥터보이스] 제목 execCommand:', success);

  if (!success) {
    titleEl.textContent = title;
    titleEl.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

// 본문 입력 v6 - 클립보드 방식
async function inputContentV6(content, images) {
  console.log('[닥터보이스] === 본문 입력 v6 시작 ===');
  console.log('[닥터보이스] 전체 내용 길이:', content.length);

  // 먼저 본문 영역 클릭하여 활성화
  await activateEditor();
  await sleep(1000);

  // 문단 분리
  const paragraphs = content.split(/\n+/).filter(p => p.trim());
  console.log('[닥터보이스] 문단 수:', paragraphs.length);

  // 이미지 위치 계산
  let imageIndex = 0;
  const imgPositions = [];
  if (images?.length) {
    const interval = Math.max(1, Math.floor(paragraphs.length / (images.length + 1)));
    for (let i = 0; i < images.length; i++) {
      imgPositions.push((i + 1) * interval);
    }
    console.log('[닥터보이스] 이미지 위치:', imgPositions);
  }

  // 각 문단 입력
  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i].trim();
    if (!para) continue;

    console.log(`[닥터보이스] 문단 ${i+1}/${paragraphs.length}: ${para.substring(0, 50)}...`);
    showNotification(`입력 중... ${i+1}/${paragraphs.length}`);

    // 에디터 활성화
    const editorEl = await activateEditor();
    if (!editorEl) {
      console.error('[닥터보이스] 에디터 활성화 실패!');
      continue;
    }

    // 텍스트 입력 시도 (여러 방법)
    const inputSuccess = await tryInputText(para);
    console.log(`[닥터보이스] 입력 결과: ${inputSuccess}`);

    // 줄바꿈 (Enter 키)
    await pressEnter();
    await sleep(500);

    // 이미지 삽입
    if (imgPositions.includes(i) && images && imageIndex < images.length) {
      await inputImage(images[imageIndex]);
      imageIndex++;
      await sleep(2000);
    }
  }

  // 남은 이미지
  while (images && imageIndex < images.length) {
    await inputImage(images[imageIndex]);
    imageIndex++;
    await sleep(2000);
  }

  console.log('[닥터보이스] 본문 입력 완료');
}

// 에디터 활성화
async function activateEditor() {
  // 플레이스홀더 클릭 시도
  const placeholder = document.querySelector('.se-placeholder');
  if (placeholder) {
    console.log('[닥터보이스] 플레이스홀더 클릭');
    placeholder.click();
    await sleep(500);
  }

  // 본문 영역 찾기
  const selectors = [
    '.se-component.se-text.se-l-default .se-text-paragraph',
    '.se-component.se-text .se-text-paragraph',
    '.se-text-paragraph[contenteditable="true"]',
    '.se-main-container .se-text-paragraph',
    '[contenteditable="true"]'
  ];

  for (const sel of selectors) {
    const elements = document.querySelectorAll(sel);
    if (elements.length > 0) {
      // 제목이 아닌 본문 영역 선택
      for (const el of elements) {
        if (!el.closest('.se-documentTitle')) {
          console.log('[닥터보이스] 본문 영역 발견:', sel);
          el.click();
          await sleep(200);
          el.focus();
          await sleep(200);
          return el;
        }
      }
    }
  }

  console.error('[닥터보이스] 본문 영역 찾기 실패!');
  return null;
}

// 텍스트 입력 시도 (여러 방법)
async function tryInputText(text) {
  // 방법 1: execCommand insertText
  try {
    const result = document.execCommand('insertText', false, text);
    if (result) {
      console.log('[닥터보이스] 방법1 성공: execCommand');
      return 'execCommand';
    }
  } catch(e) {
    console.log('[닥터보이스] 방법1 실패:', e.message);
  }

  // 방법 2: 클립보드 API + paste
  try {
    await navigator.clipboard.writeText(text);
    const pasted = document.execCommand('paste');
    if (pasted) {
      console.log('[닥터보이스] 방법2 성공: clipboard paste');
      return 'clipboard';
    }
  } catch(e) {
    console.log('[닥터보이스] 방법2 실패:', e.message);
  }

  // 방법 3: InputEvent
  try {
    const activeEl = document.activeElement;
    if (activeEl && activeEl.isContentEditable) {
      const inputEvent = new InputEvent('beforeinput', {
        inputType: 'insertText',
        data: text,
        bubbles: true,
        cancelable: true
      });
      activeEl.dispatchEvent(inputEvent);

      const inputEvent2 = new InputEvent('input', {
        inputType: 'insertText',
        data: text,
        bubbles: true
      });
      activeEl.dispatchEvent(inputEvent2);
      console.log('[닥터보이스] 방법3 시도: InputEvent');
    }
  } catch(e) {
    console.log('[닥터보이스] 방법3 실패:', e.message);
  }

  // 방법 4: Selection API로 텍스트 노드 삽입
  try {
    const sel = window.getSelection();
    if (sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(text);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.collapse(true);
      sel.removeAllRanges();
      sel.addRange(range);

      // input 이벤트 발생
      const activeEl = document.activeElement;
      if (activeEl) {
        activeEl.dispatchEvent(new Event('input', { bubbles: true }));
        activeEl.dispatchEvent(new Event('change', { bubbles: true }));
      }
      console.log('[닥터보이스] 방법4 성공: Selection API');
      return 'selection';
    }
  } catch(e) {
    console.log('[닥터보이스] 방법4 실패:', e.message);
  }

  // 방법 5: innerHTML/textContent 직접 수정
  try {
    const bodyEl = document.querySelector('.se-component.se-text .se-text-paragraph:not(.se-documentTitle .se-text-paragraph)');
    if (bodyEl) {
      // 기존 내용에 추가
      const newSpan = document.createElement('span');
      newSpan.textContent = text;
      bodyEl.appendChild(newSpan);
      bodyEl.dispatchEvent(new Event('input', { bubbles: true }));
      console.log('[닥터보이스] 방법5 성공: DOM 직접 수정');
      return 'dom';
    }
  } catch(e) {
    console.log('[닥터보이스] 방법5 실패:', e.message);
  }

  // 방법 6: 키보드 이벤트 시뮬레이션
  try {
    const activeEl = document.activeElement;
    if (activeEl) {
      for (const char of text) {
        const keydownEvent = new KeyboardEvent('keydown', {
          key: char,
          code: `Key${char.toUpperCase()}`,
          charCode: char.charCodeAt(0),
          keyCode: char.charCodeAt(0),
          which: char.charCodeAt(0),
          bubbles: true
        });
        activeEl.dispatchEvent(keydownEvent);

        const keypressEvent = new KeyboardEvent('keypress', {
          key: char,
          charCode: char.charCodeAt(0),
          keyCode: char.charCodeAt(0),
          which: char.charCodeAt(0),
          bubbles: true
        });
        activeEl.dispatchEvent(keypressEvent);

        const keyupEvent = new KeyboardEvent('keyup', {
          key: char,
          code: `Key${char.toUpperCase()}`,
          charCode: char.charCodeAt(0),
          keyCode: char.charCodeAt(0),
          which: char.charCodeAt(0),
          bubbles: true
        });
        activeEl.dispatchEvent(keyupEvent);
      }
      console.log('[닥터보이스] 방법6 시도: 키보드 이벤트');
      return 'keyboard';
    }
  } catch(e) {
    console.log('[닥터보이스] 방법6 실패:', e.message);
  }

  console.error('[닥터보이스] 모든 입력 방법 실패');
  return false;
}

// Enter 키 입력
async function pressEnter() {
  try {
    // execCommand로 줄바꿈
    document.execCommand('insertParagraph', false, null);
  } catch(e) {
    // 키보드 이벤트로 Enter
    const activeEl = document.activeElement;
    if (activeEl) {
      const enterEvent = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true
      });
      activeEl.dispatchEvent(enterEvent);
    }
  }
}

// 이미지 입력
async function inputImage(imageData) {
  if (!imageData) return;

  console.log('[닥터보이스] 이미지 삽입');

  // 본문 클릭
  await activateEditor();
  await sleep(300);

  // 사진 버튼 찾기
  const photoBtn = document.querySelector('[data-name="image"]') ||
                   document.querySelector('.se-toolbar button[title*="사진"]') ||
                   document.querySelector('.se-toolbar-item-image');

  if (!photoBtn) {
    console.warn('[닥터보이스] 사진 버튼 없음');
    return;
  }

  photoBtn.click();
  await sleep(1500);

  // 파일 input
  const fileInput = document.querySelector('input[type="file"][accept*="image"]') ||
                    document.querySelector('input[type="file"]');

  if (fileInput) {
    try {
      const file = await createFile(imageData);
      if (file) {
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        await sleep(3000);
      }
    } catch(e) {
      console.error('[닥터보이스] 이미지 업로드 실패:', e);
    }
  }

  // 팝업 닫기
  const closeBtn = document.querySelector('.se-popup-close');
  if (closeBtn) closeBtn.click();
}

// 파일 생성
async function createFile(data) {
  try {
    let blob;
    if (data.startsWith('data:') || data.startsWith('http')) {
      const res = await fetch(data);
      blob = await res.blob();
    } else {
      const bin = atob(data);
      const arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      blob = new Blob([arr], { type: 'image/jpeg' });
    }
    return new File([blob], `img_${Date.now()}.jpg`, { type: 'image/jpeg' });
  } catch(e) {
    return null;
  }
}

// 유틸
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function waitFor(selector, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (Date.now() - start > timeout) return reject(new Error('Timeout: ' + selector));
      setTimeout(check, 500);
    };
    check();
  });
}

function showNotification(msg) {
  const old = document.querySelector('.dv-notify');
  if (old) old.remove();

  const el = document.createElement('div');
  el.className = 'dv-notify';
  el.style.cssText = `
    position:fixed; top:20px; right:20px;
    background:linear-gradient(135deg,#667eea,#764ba2);
    color:white; padding:16px 24px; border-radius:12px;
    font-size:14px; z-index:999999;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  `;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

console.log('[닥터보이스] v6.0 초기화 완료');
