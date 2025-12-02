// 전역 변수
let fileData = null;
let originalContent = '';

// DOM 요소
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const fileName = document.getElementById('fileName');
const processBtn = document.getElementById('processBtn');
const downloadBtn = document.getElementById('downloadBtn');
const resultArea = document.getElementById('resultArea');

// 체크박스
const removeSpacesCheckbox = document.getElementById('removeSpaces');
const toLowerCaseCheckbox = document.getElementById('toLowerCase');
const removeSpecialCharsCheckbox = document.getElementById('removeSpecialChars');

// 통계
const originalSizeSpan = document.getElementById('originalSize');
const processedSizeSpan = document.getElementById('processedSize');
const processTimeSpan = document.getElementById('processTime');

// 파일 입력 이벤트
fileInput.addEventListener('change', handleFileSelect);

// 드래그 앤 드롭 이벤트
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

// 파일 선택 처리
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

// 파일 처리
function handleFile(file) {
    const validTypes = ['text/plain', 'text/csv', 'application/json', 'text/comma-separated-values'];
    const validExtensions = ['.txt', '.csv', '.json'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!validExtensions.includes(fileExtension) && !validTypes.includes(file.type)) {
        alert('지원하지 않는 파일 형식입니다. TXT, CSV, JSON 파일만 업로드 가능합니다.');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        originalContent = e.target.result;
        fileData = file;

        fileName.textContent = `선택된 파일: ${file.name} (${formatFileSize(file.size)})`;
        fileName.classList.add('show');

        processBtn.disabled = false;

        // 통계 업데이트
        originalSizeSpan.textContent = formatFileSize(file.size);
        processedSizeSpan.textContent = '-';
        processTimeSpan.textContent = '-';
        resultArea.value = '';
    };

    reader.readAsText(file);
}

// 데이터 처리 버튼 클릭
processBtn.addEventListener('click', processData);

function processData() {
    if (!originalContent) {
        alert('먼저 파일을 선택해주세요.');
        return;
    }

    const startTime = performance.now();

    let processed = originalContent;

    // 공백 제거
    if (removeSpacesCheckbox.checked) {
        processed = processed.replace(/\s+/g, ' ').trim();
    }

    // 소문자 변환
    if (toLowerCaseCheckbox.checked) {
        processed = processed.toLowerCase();
    }

    // 특수문자 제거
    if (removeSpecialCharsCheckbox.checked) {
        processed = processed.replace(/[^\w\sㄱ-ㅎㅏ-ㅣ가-힣]/g, '');
    }

    const endTime = performance.now();
    const processingTime = (endTime - startTime).toFixed(2);

    // 결과 표시
    resultArea.value = processed;

    // 통계 업데이트
    const processedSize = new Blob([processed]).size;
    processedSizeSpan.textContent = formatFileSize(processedSize);
    processTimeSpan.textContent = `${processingTime}ms`;

    // 다운로드 버튼 활성화
    downloadBtn.disabled = false;

    // 결과 영역으로 스크롤
    resultArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// 다운로드 버튼 클릭
downloadBtn.addEventListener('click', downloadResult);

function downloadResult() {
    const content = resultArea.value;
    if (!content) {
        alert('처리된 데이터가 없습니다.');
        return;
    }

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');

    const originalFileName = fileData ? fileData.name : 'processed.txt';
    const baseName = originalFileName.substring(0, originalFileName.lastIndexOf('.')) || originalFileName;
    const extension = originalFileName.substring(originalFileName.lastIndexOf('.')) || '.txt';

    a.href = url;
    a.download = `${baseName}_processed${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 파일 크기 포맷팅
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// 체크박스 변경 시 자동으로 다시 처리하지 않음 (사용자가 처리 버튼을 눌러야 함)
// 이것은 사용자가 여러 옵션을 변경한 후 한 번에 처리할 수 있게 함
