# 블로그 복붙용 문서 다운로드 기능 가이드

## 개요

AI가 생성한 콘텐츠를 **네이버 블로그, 티스토리 등에 바로 복붙**할 수 있도록 워드 문서(.docx) 또는 HTML로 내보내는 기능입니다.

### 주요 기능

✅ **자동 스타일링**
- AI가 중요 키워드 자동 강조 (빨간색 + 볼드)
- 핵심 문구 하이라이트 (형광펜 효과)
- 인용구, 제목, 리스트 자동 포맷팅

✅ **이미지 자동 배치**
- 문맥에 맞는 위치에 이미지 삽입
- 캡션 자동 추가

✅ **100% 스타일 유지**
- 워드 복사 → 블로그 붙여넣기 시 모든 스타일 유지
- 색상, 강조, 인용구 완벽 재현

---

## 사용 방법

### 방법 1: 워드 문서 다운로드 (추천 ⭐)

가장 완벽한 방법입니다. 네이버, 티스토리 모두 100% 호환됩니다.

#### 1단계: 워드 문서 생성

```typescript
// 프론트엔드에서 ExportButtons 컴포넌트 사용
import { ExportButtons } from '@/components/post/export-buttons'

<ExportButtons
  content={generatedPost.rewritten_content}
  title={generatedPost.suggested_titles[0]}
  keywords={generatedPost.keywords}
  emphasisPhrases={['6개월마다', '정기 검진']}
/>
```

또는 API 직접 호출:

```bash
POST /api/v1/export/docx
Content-Type: application/json

{
  "content": "치아 건강을 위해서는 정기적인 검진이 중요합니다...",
  "title": "치과 정기검진의 중요성",
  "keywords": ["검진", "치료", "예방"],
  "emphasis_phrases": ["6개월마다", "정기 검진"],
  "images": [
    {
      "position": 150,
      "path": "/path/to/image.jpg",
      "caption": "치과 검진 장면",
      "width": 5
    }
  ]
}
```

#### 2단계: 블로그에 복붙

1. 다운로드된 `.docx` 파일 열기
2. **전체 선택** (Ctrl+A / Cmd+A)
3. **복사** (Ctrl+C / Cmd+C)
4. 블로그 에디터에서 **붙여넣기** (Ctrl+V / Cmd+V)

**결과**: 색상, 강조, 인용구, 이미지 모두 완벽하게 붙여넣어집니다! ✨

---

### 방법 2: HTML 복사

네이버 블로그 HTML 모드에서 사용할 수 있습니다.

```bash
POST /api/v1/export/html

{
  "content": "치아 건강을 위해서는...",
  "title": "치과 정기검진의 중요성",
  "keywords": ["검진", "치료"]
}
```

**응답:**
```json
{
  "html": "<h2><b>치과 정기검진의 중요성</b></h2>...",
  "usage": "네이버 블로그 HTML 모드에 붙여넣기"
}
```

**사용법:**
1. HTML 복사
2. 네이버 블로그에서 "HTML 모드" 전환
3. 붙여넣기

**주의**: 일부 스타일이 제한될 수 있습니다. **워드 문서 방식 권장**

---

### 방법 3: AI 자동 강조 (실험적)

AI가 자동으로 키워드와 강조점을 분석합니다.

```bash
POST /api/v1/export/auto-export?content=콘텐츠&title=제목
```

AI가 다음을 자동으로 수행:
- 중요 키워드 추출
- 강조할 문구 선정
- 의료 용어 감지
- 자동 스타일 적용

---

## 스타일링 규칙

### 1. 키워드 강조

```
입력: keywords: ["검진", "치료", "예방"]
출력: 빨간색(#FF6B6B) + 볼드
```

### 2. 하이라이트 문구

```
입력: emphasis_phrases: ["6개월마다", "반드시"]
출력: 노란 형광펜 + 볼드
```

### 3. 인용구

```
입력: > 전문의의 조언: 정기 검진이 중요합니다
출력: 왼쪽 파란 테두리 + 회색 배경
```

### 4. 제목

```
입력: ## 소제목
출력: 18pt 볼드 + 회색(#34495E)
```

### 5. 리스트

```
입력:
- 항목 1
- 항목 2

출력: 불릿 리스트
```

---

## 이미지 배치

### 이미지 데이터 형식

```typescript
interface ImageData {
  position: number      // 텍스트 위치 (글자 수)
  url?: string          // 이미지 URL (base64 지원)
  path?: string         // 로컬 파일 경로
  caption?: string      // 이미지 캡션
  width?: number        // 이미지 너비 (인치, 기본 5)
}
```

### 예시

```json
{
  "images": [
    {
      "position": 150,
      "url": "data:image/jpeg;base64,/9j/4AAQ...",
      "caption": "치아 구조 설명",
      "width": 5
    },
    {
      "position": 500,
      "path": "/uploads/dental-clinic.jpg",
      "caption": "본원 진료실",
      "width": 6
    }
  ]
}
```

**이미지 삽입 규칙:**
- `position`: 해당 위치 근처 문단 사이에 삽입
- 이미지가 없으면 캡션만 텍스트로 표시
- 자동으로 적절한 간격 유지

---

## 프론트엔드 통합

### 컴포넌트 사용

```tsx
'use client'

import { ExportButtons } from '@/components/post/export-buttons'

export default function PostPreview({ post }: { post: Post }) {
  return (
    <div>
      {/* 생성된 콘텐츠 표시 */}
      <div className="prose">
        {post.rewritten_content}
      </div>

      {/* 내보내기 버튼 */}
      <ExportButtons
        content={post.rewritten_content}
        title={post.suggested_titles[0]}
        keywords={post.keywords}
        emphasisPhrases={extractEmphasis(post.rewritten_content)}
        onExportSuccess={() => {
          console.log('Export completed!')
        }}
      />
    </div>
  )
}
```

### Props

| Prop | Type | 설명 |
|------|------|------|
| `content` | `string` | 본문 내용 (필수) |
| `title` | `string` | 글 제목 |
| `keywords` | `string[]` | 강조할 키워드 |
| `emphasisPhrases` | `string[]` | 하이라이트할 문구 |
| `onExportSuccess` | `() => void` | 다운로드 성공 콜백 |

---

## 백엔드 API

### 엔드포인트

#### 1. 워드 문서 생성

```
POST /api/v1/export/docx
```

**Request Body:**
```json
{
  "content": "string (required)",
  "title": "string (optional)",
  "keywords": ["string"],
  "emphasis_phrases": ["string"],
  "images": [ImageData]
}
```

**Response:**
- Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- 파일 다운로드

#### 2. HTML 생성

```
POST /api/v1/export/html
```

**Response:**
```json
{
  "html": "<h2>...</h2>",
  "usage": "사용법 설명"
}
```

#### 3. AI 자동 강조

```
POST /api/v1/export/auto-export?content=텍스트&title=제목
```

**Response:** DOCX 파일 다운로드

---

## 실제 사용 예시

### 예시 1: 기본 사용

```typescript
const post = {
  title: "치아 건강 관리법",
  content: "정기적인 검진이 중요합니다. 6개월마다 스케일링을 받으세요.",
  keywords: ["검진", "스케일링"],
}

// 워드 다운로드
await fetch('/api/v1/export/docx', {
  method: 'POST',
  body: JSON.stringify({
    content: post.content,
    title: post.title,
    keywords: post.keywords,
  })
})
```

**결과 워드 파일:**
- "검진", "스케일링" → 빨간색 볼드
- "6개월마다" → 자동 감지하여 형광펜

### 예시 2: 이미지 포함

```typescript
await fetch('/api/v1/export/docx', {
  method: 'POST',
  body: JSON.stringify({
    content: longContent,
    title: "임플란트 시술 가이드",
    keywords: ["임플란트", "시술"],
    images: [
      {
        position: 200,
        path: '/uploads/implant-before.jpg',
        caption: '시술 전',
        width: 5
      },
      {
        position: 800,
        path: '/uploads/implant-after.jpg',
        caption: '시술 후',
        width: 5
      }
    ]
  })
})
```

---

## 색상 팔레트

기본 제공 색상:

| 용도 | 색상 코드 | RGB |
|------|----------|-----|
| Primary (키워드) | `#FF6B6B` | (255, 107, 107) 빨강 |
| Secondary | `#4A90E2` | (74, 144, 226) 파랑 |
| Success | `#22C55E` | (34, 197, 94) 초록 |
| Warning | `#FBFB24` | (251, 191, 36) 노랑 |
| Info | `#A855F7` | (168, 85, 247) 보라 |

---

## 문제 해결

### Q: 워드에서 복사했는데 스타일이 안 붙어요

**A:** 다음을 확인하세요:
1. 워드 파일을 제대로 열었는지
2. "전체 선택" (Ctrl+A) 후 복사했는지
3. 블로그 에디터가 "기본 모드"인지 (HTML 모드 X)
4. 브라우저 캐시 삭제 후 재시도

### Q: 이미지가 안 나와요

**A:**
- 이미지는 base64 인코딩 또는 서버 접근 가능한 경로여야 합니다
- 로컬 경로는 백엔드 서버에서 접근 가능해야 합니다

### Q: 네이버 블로그에서 색상이 다르게 나와요

**A:**
- 워드 방식 사용 시 100% 유지됩니다
- HTML 방식은 네이버 정책에 따라 일부 제한될 수 있습니다

---

## 향후 개선 예정

- [ ] AI가 자동으로 이미지 배치 위치 추천
- [ ] 다양한 색상 테마 지원
- [ ] PDF 내보내기
- [ ] 마크다운 + 이미지 폴더 다운로드
- [ ] 브랜드 색상 커스터마이징

---

## 기술 스택

- **Backend**: FastAPI + python-docx
- **Frontend**: Next.js + TypeScript
- **파일 형식**: DOCX (Office Open XML), HTML5

---

## 라이선스

MIT License
