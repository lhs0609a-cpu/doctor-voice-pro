import os

# Chrome extension directory
ext_dir = r"E:\u\doctor-voice-pro\chrome-extension"
os.makedirs(os.path.join(ext_dir, "icons"), exist_ok=True)

# popup.html
popup_html = '''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>닥터보이스 프로</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 360px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 400px; }
    .container { padding: 20px; }
    .header { text-align: center; color: white; margin-bottom: 20px; }
    .header h1 { font-size: 18px; margin-bottom: 4px; }
    .header p { font-size: 12px; opacity: 0.9; }
    .status-card { background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .status-card.success { border-left: 4px solid #10b981; }
    .status-card.warning { border-left: 4px solid #f59e0b; }
    .status-card.error { border-left: 4px solid #ef4444; }
    .status-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .status-desc { font-size: 12px; color: #666; }
    .post-info { background: #f8fafc; border-radius: 8px; padding: 12px; margin-top: 12px; display: none; }
    .post-title { font-weight: 600; font-size: 13px; margin-bottom: 8px; color: #1e293b; }
    .post-meta { display: flex; gap: 12px; font-size: 11px; color: #64748b; }
    .options { background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    .options h3 { font-size: 13px; margin-bottom: 12px; color: #334155; }
    .option-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 12px; }
    .option-item input[type="checkbox"] { width: 16px; height: 16px; accent-color: #7c3aed; }
    .btn { width: 100%; padding: 12px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; margin-bottom: 8px; }
    .btn-primary { background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%); color: white; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary { background: white; color: #7c3aed; border: 1px solid #e2e8f0; }
    .progress { display: none; margin-top: 12px; }
    .progress.active { display: block; }
    .progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
    .progress-fill { height: 100%; background: linear-gradient(90deg, #7c3aed, #6366f1); width: 0%; transition: width 0.3s; }
    .progress-text { font-size: 11px; color: #64748b; margin-top: 6px; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>닥터보이스 프로</h1><p>네이버 블로그 자동 포스팅</p></div>
    <div id="statusCard" class="status-card warning">
      <div id="statusTitle" class="status-title">대기 중</div>
      <div id="statusDesc" class="status-desc">저장된 글 페이지에서 포스팅할 글을 선택하세요</div>
      <div id="postInfo" class="post-info">
        <div id="postTitle" class="post-title"></div>
        <div class="post-meta"><span id="postLength">0자</span><span id="postImages">이미지 0개</span></div>
      </div>
    </div>
    <div class="options">
      <h3>포스팅 옵션</h3>
      <label class="option-item"><input type="checkbox" id="optQuote" checked><span>인용구 자동 삽입</span></label>
      <label class="option-item"><input type="checkbox" id="optHighlight" checked><span>중요 부분 강조</span></label>
      <label class="option-item"><input type="checkbox" id="optImages" checked><span>이미지 자동 삽입</span></label>
      <label class="option-item"><input type="checkbox" id="optDraft"><span>임시저장으로 저장</span></label>
    </div>
    <button id="btnPost" class="btn btn-primary" disabled>네이버 블로그에 포스팅하기</button>
    <button id="btnOpenBlog" class="btn btn-secondary">네이버 블로그 글쓰기 열기</button>
    <div id="progress" class="progress">
      <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
      <div id="progressText" class="progress-text">준비 중...</div>
    </div>
  </div>
  <script src="popup.js"></script>
</body>
</html>'''

with open(os.path.join(ext_dir, "popup.html"), "w", encoding="utf-8") as f:
    f.write(popup_html)

# content-naver.js
content_naver_js = '''// 네이버 블로그 콘텐츠 스크립트
console.log('[닥터보이스 프로] 네이버 블로그 콘텐츠 스크립트 로드됨');

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[닥터보이스 프로] 메시지 수신:', message);
  if (message.action === 'INSERT_POST') {
    insertPost(message.data, message.options)
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }
});

async function insertPost(data, options) {
  await waitForEditor();
  await insertTitle(data.title);
  await insertContent(data.content, options);
  if (options.saveDraft) await saveDraft();
}

function waitForEditor() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const titleInput = document.querySelector('.se-title-textarea') || document.querySelector('#post-title-inp');
      const editor = document.querySelector('.se-content') || document.querySelector('#post-editor');
      if (titleInput || editor) resolve();
      else if (attempts >= 30) reject(new Error('에디터를 찾을 수 없습니다'));
      else setTimeout(check, 500);
    };
    check();
  });
}

async function insertTitle(title) {
  if (!title) return;
  const titleInput = document.querySelector('.se-title-textarea') || document.querySelector('#post-title-inp');
  if (titleInput) {
    titleInput.focus();
    titleInput.value = title;
    titleInput.dispatchEvent(new Event('input', { bubbles: true }));
  }
  await sleep(300);
}

async function insertContent(content, options) {
  if (!content) return;
  const contentArea = document.querySelector('.se-content') || document.querySelector('#post-editor');
  if (!contentArea) return;
  contentArea.click();
  await sleep(300);
  const htmlContent = convertToNaverHtml(content, options);
  try {
    document.execCommand('insertHTML', false, htmlContent);
  } catch (e) {
    const editableArea = contentArea.querySelector('[contenteditable="true"]') || contentArea;
    if (editableArea) {
      editableArea.innerHTML = htmlContent;
      editableArea.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }
}

function convertToNaverHtml(content, options) {
  const paragraphs = content.split('\\n').filter(p => p.trim());
  let html = '';
  paragraphs.forEach((para, index) => {
    const trimmed = para.trim();
    if (!trimmed) return;
    if (options.useQuote && index > 0 && index % 6 === 0) {
      html += `<blockquote style="background:#f8f9fa;border-left:4px solid #7c3aed;padding:16px;margin:16px 0;font-style:italic;">${trimmed}</blockquote>`;
    } else if (options.useHighlight && ['중요','핵심','포인트','추천','필수','꿀팁'].some(kw => trimmed.includes(kw))) {
      html += `<p style="background:linear-gradient(120deg,#f0e6ff 0%,#e6f0ff 100%);padding:12px 16px;border-radius:8px;margin:12px 0;">${trimmed}</p>`;
    } else {
      html += `<p style="margin:12px 0;line-height:1.8;">${trimmed}</p>`;
    }
  });
  return html;
}

async function saveDraft() {
  const saveBtn = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('임시저장'));
  if (saveBtn) { saveBtn.click(); await sleep(1000); }
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }'''

with open(os.path.join(ext_dir, "content-naver.js"), "w", encoding="utf-8") as f:
    f.write(content_naver_js)

# background.js
background_js = '''// 백그라운드 서비스 워커
console.log('[닥터보이스 프로] 백그라운드 스크립트 시작');

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.storage.local.set({ settings: { useQuote: true, useHighlight: true, useImages: true, saveDraft: false } });
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && (tab.url.includes('doctor-voice-pro') || tab.url.includes('localhost'))) {
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => localStorage.getItem('doctorvoice-pending-post')
    }).then((results) => {
      if (results?.[0]?.result) {
        chrome.storage.local.set({ pendingPost: JSON.parse(results[0].result) });
      }
    }).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_POST_DATA') {
    chrome.storage.local.get(['pendingPost'], (result) => sendResponse(result.pendingPost || null));
    return true;
  }
  if (message.type === 'CLEAR_POST_DATA') {
    chrome.storage.local.remove(['pendingPost'], () => sendResponse({ success: true }));
    return true;
  }
});'''

with open(os.path.join(ext_dir, "background.js"), "w", encoding="utf-8") as f:
    f.write(background_js)

# content.css
content_css = '''.doctorvoice-content { font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; }
.doctorvoice-content p { margin: 12px 0; }
.doctorvoice-content blockquote { background: #f8f9fa; border-left: 4px solid #7c3aed; padding: 16px; margin: 16px 0; font-style: italic; }
.doctorvoice-content .highlight { background: linear-gradient(120deg, #f0e6ff 0%, #e6f0ff 100%); padding: 12px 16px; border-radius: 8px; }
.doctorvoice-content img { max-width: 100%; height: auto; border-radius: 8px; margin: 16px 0; }'''

with open(os.path.join(ext_dir, "content.css"), "w", encoding="utf-8") as f:
    f.write(content_css)

print("Extension files created successfully!")
print(f"Files in {ext_dir}:")
for f in os.listdir(ext_dir):
    print(f"  - {f}")
