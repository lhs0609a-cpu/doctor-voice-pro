# 네이버 블로그 워드 다운로드 - 이미지 미포함 문제 분석

## 문제 상황
워드 파일(.docx)은 다운로드되지만, 사용자가 넣은 이미지가 포함되지 않음

## 원인 분석

### 1. ExportButtons 컴포넌트 (frontend/src/components/post/export-buttons.tsx:39)
```typescript
body: JSON.stringify({
  content,
  title,
  keywords,
  emphasis_phrases: emphasisPhrases,
  images: [], // ❌ 이미지는 나중에 추가 가능 (빈 배열)
}),
```
**문제**: 백엔드 API에 빈 이미지 배열을 전송

### 2. Create Page의 Word 다운로드 (frontend/src/app/dashboard/create/page.tsx:327-440)
- `docx` 라이브러리를 직접 사용
- 텍스트만 포함, 이미지 처리 없음

## 이미지가 없는 이유

### 시나리오 1: ExportButtons 사용 시
1. 사용자가 포스트에 이미지를 포함해서 작성
2. "워드 다운로드" 버튼 클릭
3. `images: []` 빈 배열로 API 호출
4. 백엔드는 이미지 없이 DOCX 생성

### 시나리오 2: Create Page에서 직접 다운로드 시
1. AI가 텍스트 콘텐츠 생성
2. "Word 저장" 버튼 클릭 (1306번 라인)
3. `handleDownloadWord` 함수 실행
4. 이미지 처리 로직 없음

## 해결 방안

### 방안 1: ExportButtons에 이미지 전달 (권장)

**필요한 수정:**

1. **ExportButtons 인터페이스 확장**
```typescript
interface ExportButtonsProps {
  content: string
  title?: string
  keywords?: string[]
  emphasisPhrases?: string[]
  images?: Array<{url: string, caption?: string}>  // 추가
  onExportSuccess?: () => void
}
```

2. **content에서 이미지 추출**
```typescript
const exportToDocx = async () => {
  // 콘텐츠에서 이미지 URL 추출
  const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g
  const extractedImages = []
  let match

  while ((match = imgRegex.exec(content)) !== null) {
    extractedImages.push({
      caption: match[1] || '',
      url: match[2],
      position: match.index,
    })
  }

  // API 호출 시 이미지 포함
  body: JSON.stringify({
    content,
    title,
    keywords,
    emphasis_phrases: emphasisPhrases,
    images: extractedImages,  // ✅ 추출한 이미지 전송
  }),
}
```

3. **백엔드는 이미 이미지 처리 가능**
- `blog_exporter.py`는 이미지 처리 로직 보유
- `_add_image_to_doc` 메서드 존재 (219번 라인)

### 방안 2: 이미지 폴더 업로드 사용

백엔드의 `/api/v1/export/with-images` 엔드포인트 활용:
- 사용자가 이미지 폴더를 직접 업로드
- AI가 자동으로 적절한 위치에 배치

### 방안 3: Create Page 개선

`handleDownloadWord` 함수에서 `ExportButtons`의 백엔드 API 사용:
```typescript
const handleDownloadWord = async () => {
  // docx 라이브러리 대신 백엔드 API 호출
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/docx`, {
    method: 'POST',
    body: JSON.stringify({
      content: generatedPost.generated_content,
      title: generatedPost.title,
      keywords: generatedPost.content_analysis?.keywords,
      images: [],  // 이미지 추출 로직 추가 필요
    }),
  })
}
```

## 권장 구현 순서

1. ✅ **ExportButtons에 이미지 추출 로직 추가**
   - 마크다운 이미지 패턴 파싱
   - HTML img 태그 파싱
   - base64 이미지 지원

2. ✅ **저장된 포스트에서 ExportButtons 사용**
   - 저장된 포스트 상세 페이지
   - 이미지 포함된 콘텐츠 전달

3. ✅ **Create Page 통합**
   - `handleDownloadWord`를 백엔드 API로 변경
   - 일관된 이미지 처리

## 테스트 방법

1. 이미지가 포함된 포스트 작성
2. "워드 다운로드" 버튼 클릭
3. DOCX 파일 열어서 이미지 확인
4. 네이버 블로그에 복붙 시 이미지 유지 확인

## 다음 단계

1. 먼저 어디서 워드를 다운로드하시는지 확인 필요
   - 포스트 작성 페이지? (create)
   - 저장된 포스트 페이지? (saved)
   - 포스트 상세 페이지? (posts/[id])

2. 이미지 형식 확인
   - 마크다운 이미지? `![alt](url)`
   - HTML 이미지? `<img src="url">`
   - base64 인코딩?

3. 적절한 해결 방안 선택 및 구현
