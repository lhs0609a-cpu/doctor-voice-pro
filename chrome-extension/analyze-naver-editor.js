// 네이버 스마트에디터 ONE 내부 API 분석 스크립트
// 브라우저 콘솔에서 실행하세요

console.log('=== 네이버 에디터 분석 시작 ===');

// 1. window 객체에서 에디터 관련 변수 찾기
console.log('\n1. Window 전역 변수 검색:');
const editorKeywords = ['editor', 'Editor', 'SE', 'smart', 'Smart', 'naver', 'Naver', 'blog', 'Blog'];
const foundVars = [];

for (const key in window) {
  for (const keyword of editorKeywords) {
    if (key.toLowerCase().includes(keyword.toLowerCase())) {
      foundVars.push(key);
      console.log(`  - window.${key}:`, typeof window[key]);
    }
  }
}

// 2. SE로 시작하는 전역 변수 (네이버 에디터는 SE- 접두사 사용)
console.log('\n2. SE 관련 전역 변수:');
for (const key in window) {
  if (key.startsWith('SE') || key.startsWith('se')) {
    console.log(`  - window.${key}:`, typeof window[key], window[key]);
  }
}

// 3. __NEXT_DATA__ 또는 __NUXT__ (프레임워크 데이터)
console.log('\n3. 프레임워크 데이터:');
if (window.__NEXT_DATA__) console.log('  - __NEXT_DATA__ 발견');
if (window.__NUXT__) console.log('  - __NUXT__ 발견');
if (window.__REDUX_DEVTOOLS_EXTENSION__) console.log('  - Redux 발견');

// 4. React 컴포넌트 찾기
console.log('\n4. React 컴포넌트 검색:');
const findReactComponent = (element) => {
  for (const key in element) {
    if (key.startsWith('__reactInternalInstance') || key.startsWith('__reactFiber')) {
      return element[key];
    }
  }
  return null;
};

const titleEl = document.querySelector('.se-component.se-documentTitle');
const bodyEl = document.querySelector('.se-component.se-text:not(.se-documentTitle)');

if (titleEl) {
  const reactInstance = findReactComponent(titleEl);
  if (reactInstance) {
    console.log('  - 제목 React 컴포넌트 발견:', reactInstance);
  }
}

if (bodyEl) {
  const reactInstance = findReactComponent(bodyEl);
  if (reactInstance) {
    console.log('  - 본문 React 컴포넌트 발견:', reactInstance);
  }
}

// 5. iframe 내부 검색
console.log('\n5. iframe 내부 검색:');
const iframes = document.querySelectorAll('iframe');
iframes.forEach((iframe, i) => {
  try {
    const iframeWin = iframe.contentWindow;
    const iframeDoc = iframe.contentDocument;

    console.log(`  iframe[${i}]:`, iframe.id || iframe.name || '(no id)');

    // iframe 내부의 전역 변수
    for (const key in iframeWin) {
      if (key.startsWith('SE') || key.includes('editor') || key.includes('Editor')) {
        console.log(`    - ${key}:`, typeof iframeWin[key]);
        if (typeof iframeWin[key] === 'object' && iframeWin[key] !== null) {
          console.log(`      methods:`, Object.keys(iframeWin[key]).slice(0, 10));
        }
      }
    }

    // iframe 내부 React
    const iframeTitleEl = iframeDoc?.querySelector('.se-component.se-documentTitle');
    if (iframeTitleEl) {
      const reactInstance = findReactComponent(iframeTitleEl);
      if (reactInstance) {
        console.log('    - iframe 내 React 컴포넌트 발견');
      }
    }
  } catch (e) {
    console.log(`  iframe[${i}]: cross-origin 접근 불가`);
  }
});

// 6. 커스텀 이벤트 리스너 확인
console.log('\n6. 에디터 이벤트 시스템:');
const seCanvas = document.querySelector('.se-canvas');
if (seCanvas) {
  console.log('  - se-canvas 발견');
  // 이벤트 리스너 확인은 Chrome DevTools에서 getEventListeners() 사용
}

// 7. 에디터 인스턴스 찾기 (일반적인 패턴)
console.log('\n7. 에디터 인스턴스 패턴 검색:');
const commonEditorPatterns = [
  'editorInstance',
  'blogEditor',
  'smartEditor',
  'seEditor',
  'CKEDITOR',
  'tinymce',
  'Quill',
  'editor',
  'Editor'
];

for (const pattern of commonEditorPatterns) {
  if (window[pattern]) {
    console.log(`  - window.${pattern} 발견:`, window[pattern]);
  }
}

// 8. document에 연결된 에디터 데이터
console.log('\n8. document 데이터 속성:');
const allElements = document.querySelectorAll('[data-compid], [data-editor], [data-instance]');
allElements.forEach((el, i) => {
  if (i < 5) {
    console.log(`  - ${el.tagName}.${el.className.split(' ')[0]}:`, el.dataset);
  }
});

// 9. MutationObserver로 에디터 변경 감지 테스트
console.log('\n9. 에디터 변경 감지 테스트:');
console.log('  - 텍스트 입력 후 DOM 변경 확인하려면 아래 코드 실행:');
console.log(`
const observer = new MutationObserver((mutations) => {
  mutations.forEach((m) => {
    console.log('변경:', m.type, m.target.nodeName, m.target.className);
  });
});
const target = document.querySelector('.se-content') || document.body;
observer.observe(target, { childList: true, subtree: true, characterData: true });
`);

// 10. 에디터 API 직접 호출 테스트
console.log('\n10. 에디터 API 호출 테스트:');
console.log('  아래 코드들을 시도해보세요:');
console.log(`
// React 상태 접근 시도
const el = document.querySelector('.se-text-paragraph span');
const reactKey = Object.keys(el).find(k => k.startsWith('__reactFiber'));
if (reactKey) {
  const fiber = el[reactKey];
  console.log('React Fiber:', fiber);
  console.log('Props:', fiber?.memoizedProps);
  console.log('State:', fiber?.memoizedState);
}
`);

console.log('\n=== 분석 완료 ===');
console.log('위 결과를 공유해주시면 API 호출 방법을 찾아드리겠습니다.');
