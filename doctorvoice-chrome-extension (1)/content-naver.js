// 네이버 블로그 에디터 자동 입력 스크립트
console.log('[닥터보이스] 네이버 블로그 콘텐츠 스크립트 로드됨');

// 메시지 수신
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'INSERT_POST') {
    console.log('[닥터보이스] 포스트 삽입 요청 수신:', message);
    insertPost(message.data, message.options)
      .then(() => sendResponse({ success: true }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // 비동기 응답
  }
});

async function insertPost(data, options) {
  console.log('[닥터보이스] 포스트 삽입 시작:', data, options);

  // 에디터 로딩 대기
  await waitForEditor();

  // 1. 제목 입력
  await insertTitle(data.title || '');

  // 2. 본문 입력
  await insertContent(data.content || '', data.images || [], options);

  // 3. 임시저장 (옵션)
  if (options.saveDraft) {
    await saveDraft();
  }

  console.log('[닥터보이스] 포스트 삽입 완료');
}

// 에디터 로딩 대기
async function waitForEditor() {
  const maxWait = 10000;
  const startTime = Date.now();

  while (Date.now() - startTime < maxWait) {
    // 스마트에디터 iframe 확인
    const editorFrame = document.querySelector('iframe#mainFrame') ||
                        document.querySelector('iframe[name="mainFrame"]');

    if (editorFrame) {
      const innerDoc = editorFrame.contentDocument || editorFrame.contentWindow?.document;
      if (innerDoc) {
        const seFrame = innerDoc.querySelector('iframe#se2_iframe') ||
                        innerDoc.querySelector('iframe.se2_iframe');
        if (seFrame) {
          console.log('[닥터보이스] 에디터 프레임 발견');
          return;
        }
      }
    }

    // 새 에디터 (SE ONE) 확인
    const seOne = document.querySelector('.se-component-content');
    if (seOne) {
      console.log('[닥터보이스] SE ONE 에디터 발견');
      return;
    }

    await sleep(500);
  }

  console.warn('[닥터보이스] 에디터 로딩 타임아웃, 계속 진행...');
}

// 제목 입력
async function insertTitle(title) {
  console.log('[닥터보이스] 제목 입력:', title);

  // 방법 1: 메인 프레임 내부에서 찾기
  const mainFrame = document.querySelector('iframe#mainFrame') ||
                    document.querySelector('iframe[name="mainFrame"]');

  if (mainFrame) {
    const innerDoc = mainFrame.contentDocument || mainFrame.contentWindow?.document;
    if (innerDoc) {
      // 제목 입력 필드 찾기
      const titleInput = innerDoc.querySelector('#post-title-inp') ||
                         innerDoc.querySelector('input[name="post.title"]') ||
                         innerDoc.querySelector('.se-title-text') ||
                         innerDoc.querySelector('[placeholder*="제목"]');

      if (titleInput) {
        titleInput.value = title;
        titleInput.dispatchEvent(new Event('input', { bubbles: true }));
        titleInput.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('[닥터보이스] 제목 입력 완료 (iframe 내부)');
        return;
      }
    }
  }

  // 방법 2: SE ONE 에디터
  const seOneTitle = document.querySelector('.se-title-text') ||
                     document.querySelector('[data-placeholder*="제목"]');
  if (seOneTitle) {
    seOneTitle.textContent = title;
    seOneTitle.dispatchEvent(new Event('input', { bubbles: true }));
    console.log('[닥터보이스] 제목 입력 완료 (SE ONE)');
    return;
  }

  // 방법 3: 직접 제목 입력 필드
  const directTitle = document.querySelector('#post-title-inp') ||
                      document.querySelector('input[name="title"]');
  if (directTitle) {
    directTitle.value = title;
    directTitle.dispatchEvent(new Event('input', { bubbles: true }));
    console.log('[닥터보이스] 제목 입력 완료 (직접)');
  }
}

// 본문 입력
async function insertContent(content, images, options) {
  console.log('[닥터보이스] 본문 입력 시작');

  // 콘텐츠를 HTML로 변환
  const htmlContent = convertToNaverHtml(content, images, options);

  // 메인 프레임 접근
  const mainFrame = document.querySelector('iframe#mainFrame') ||
                    document.querySelector('iframe[name="mainFrame"]');

  if (mainFrame) {
    const innerDoc = mainFrame.contentDocument || mainFrame.contentWindow?.document;
    if (innerDoc) {
      // 스마트에디터 2.0 iframe 찾기
      const seFrame = innerDoc.querySelector('iframe#se2_iframe') ||
                      innerDoc.querySelector('iframe.se2_iframe') ||
                      innerDoc.querySelector('iframe[id*="SmartEditor"]');

      if (seFrame) {
        const seDoc = seFrame.contentDocument || seFrame.contentWindow?.document;
        if (seDoc) {
          const editArea = seDoc.body || seDoc.querySelector('.se2_inputarea');
          if (editArea) {
            editArea.innerHTML = htmlContent;
            console.log('[닥터보이스] 본문 입력 완료 (SE2)');
            return;
          }
        }
      }

      // SE ONE 에디터 찾기
      const seOneContent = innerDoc.querySelector('.se-component-content') ||
                           innerDoc.querySelector('.se-main-container');
      if (seOneContent) {
        // SE ONE은 다른 방식으로 입력해야 함
        await insertToSeOne(innerDoc, htmlContent);
        return;
      }
    }
  }

  // 직접 SE ONE 접근
  const directSeOne = document.querySelector('.se-component-content');
  if (directSeOne) {
    await insertToSeOne(document, htmlContent);
    return;
  }

  console.warn('[닥터보이스] 에디터를 찾을 수 없음, 클립보드에 복사');
  await copyToClipboard(htmlContent);
}

// SE ONE 에디터에 입력
async function insertToSeOne(doc, htmlContent) {
  console.log('[닥터보이스] SE ONE 에디터에 입력');

  // 본문 편집 영역 클릭하여 활성화
  const editableArea = doc.querySelector('.se-component-content [contenteditable="true"]') ||
                       doc.querySelector('.se-section-text');

  if (editableArea) {
    editableArea.focus();
    editableArea.innerHTML = htmlContent;

    // 입력 이벤트 발생
    editableArea.dispatchEvent(new Event('input', { bubbles: true }));
    editableArea.dispatchEvent(new Event('change', { bubbles: true }));

    console.log('[닥터보이스] SE ONE 본문 입력 완료');
  } else {
    console.warn('[닥터보이스] SE ONE 편집 영역 없음');
  }
}

// 콘텐츠를 네이버 블로그 HTML로 변환
function convertToNaverHtml(content, images, options) {
  let html = '';

  // 문단 분리
  const paragraphs = content.split('\n\n').filter(p => p.trim());

  paragraphs.forEach((para, index) => {
    para = para.trim();
    if (!para) return;

    // 중요 문장 감지 (느낌표, 추천, 만족 등)
    const isImportant = /[!]{2,}|추천|만족|최고|대박|완전|진짜/.test(para);

    // 인용구 적용 (첫 문단 또는 중요 문장)
    if (options.useQuote && (index === 0 || (isImportant && index % 4 === 0))) {
      html += `<div class="se-module se-module-oglink">
        <blockquote class="se-quote" style="border-left: 4px solid #667eea; padding: 12px 16px; margin: 16px 0; background: #f8f9ff;">
          <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.8;">${escapeHtml(para)}</p>
        </blockquote>
      </div>`;
    }
    // 배경색 강조
    else if (options.useHighlight && isImportant) {
      html += `<div class="se-module se-module-text">
        <p style="background: linear-gradient(to bottom, transparent 60%, #fef3c7 60%); display: inline; font-size: 15px; line-height: 2;">${escapeHtml(para)}</p>
      </div>`;
    }
    // 일반 문단
    else {
      html += `<div class="se-module se-module-text">
        <p style="font-size: 15px; line-height: 2; color: #374151; margin-bottom: 16px;">${escapeHtml(para)}</p>
      </div>`;
    }

    // 이미지 삽입 (적절한 위치에)
    if (options.useImages && images.length > 0) {
      const imgIndex = Math.floor(index / (paragraphs.length / images.length));
      if (index > 0 && index % Math.ceil(paragraphs.length / images.length) === 0 && images[imgIndex]) {
        html += `<div class="se-module se-module-image" style="text-align: center; margin: 24px 0;">
          <img src="${escapeHtml(images[imgIndex])}" alt="" style="max-width: 100%; height: auto; border-radius: 8px;">
        </div>`;
      }
    }
  });

  return html;
}

// HTML 이스케이프
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 임시저장
async function saveDraft() {
  console.log('[닥터보이스] 임시저장 시도');

  await sleep(1000);

  // 메인 프레임 내부에서 저장 버튼 찾기
  const mainFrame = document.querySelector('iframe#mainFrame') ||
                    document.querySelector('iframe[name="mainFrame"]');

  if (mainFrame) {
    const innerDoc = mainFrame.contentDocument || mainFrame.contentWindow?.document;
    if (innerDoc) {
      const saveBtn = innerDoc.querySelector('#btn_save') ||
                      innerDoc.querySelector('button[data-testid="save-button"]') ||
                      innerDoc.querySelector('.se-toolbar-button-save') ||
                      innerDoc.querySelector('[class*="save"]');

      if (saveBtn) {
        saveBtn.click();
        console.log('[닥터보이스] 임시저장 버튼 클릭');
        return;
      }
    }
  }

  // 직접 저장 버튼 찾기
  const directSaveBtn = document.querySelector('.btn_save') ||
                        document.querySelector('[class*="save-btn"]');
  if (directSaveBtn) {
    directSaveBtn.click();
    console.log('[닥터보이스] 임시저장 버튼 클릭 (직접)');
  }
}

// 클립보드에 복사
async function copyToClipboard(html) {
  try {
    await navigator.clipboard.writeText(html);
    alert('[닥터보이스] 에디터를 찾을 수 없어 클립보드에 복사했습니다.\n에디터에서 Ctrl+V로 붙여넣기 하세요.');
  } catch (e) {
    console.error('[닥터보이스] 클립보드 복사 실패:', e);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
