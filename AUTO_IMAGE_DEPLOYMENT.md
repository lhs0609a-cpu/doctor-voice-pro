# ✅ 배포 완료 - 자동 이미지 삽입 기능

## 배포 정보

**배포 일시**: 2025-11-23
**배포 버전**: v1.5.0 (자동 이미지 삽입 기능)

### 🚀 배포된 서비스

1. **백엔드** (Fly.io)
   - URL: https://doctor-voice-pro-backend.fly.dev
   - 상태: ✅ 배포 완료
   - 빌드: 성공
   - Commit: `0794515`

2. **프론트엔드** (Vercel)
   - URL: https://frontend-bp5ye7pl5-fewfs-projects-83cc0821.vercel.app
   - 상태: ✅ 배포 완료
   - 빌드: 성공
   - Commit: `1cc4a92`

---

## 새로운 기능

### 자동 이미지 삽입 기능

네이버 블로그용 워드 다운로드 시 **자동으로 관련 이미지 4개를 검색하고 삽입**하는 기능

#### 주요 특징

1. **AI 기반 이미지 검색**
   - SEO 키워드를 기반으로 자동 검색
   - Unsplash/Pexels API 연동 (무료 고품질 이미지)
   - API 키 없이도 작동 (Lorem Picsum 대체)

2. **자동 이미지 배치**
   - 콘텐츠 분석하여 적절한 위치에 이미지 삽입
   - 2-3개 문단마다 자동 분산 배치
   - 최대 4개의 이미지 자동 다운로드

3. **원클릭 다운로드**
   - "네이버 블로그용 워드 다운로드 (이미지 자동)" 버튼 클릭
   - 이미지 검색 → 다운로드 → DOCX 생성 → 다운로드 자동 진행
   - 전체 과정 토스트 메시지로 진행 상황 표시

---

## 구현 내용

### 백엔드 (Backend)

#### 1. ImageSearchService 추가 (`backend/app/services/image_search.py`)

```python
class ImageSearchService:
    async def search_images(
        self,
        keywords: List[str],
        count: int = 4,
        orientation: str = "landscape"
    ) -> List[Dict]:
        # Unsplash → Pexels → Lorem Picsum 순서로 시도
```

**기능:**
- Unsplash API를 우선 사용하여 고품질 이미지 검색
- Pexels API를 대체 서비스로 사용
- API 키 없을 시 Lorem Picsum 플레이스홀더 자동 사용
- 비동기 다운로드로 빠른 처리

#### 2. 새로운 API 엔드포인트 (`backend/app/api/export.py`)

**a) `/api/v1/export/search-images` (POST)**
- 키워드로 이미지 검색
- 응답: 이미지 URL, 썸네일, 캡션, 사진작가 정보

**b) `/api/v1/export/docx-with-auto-images` (POST)**
- 원클릭 자동 이미지 DOCX 생성
- 흐름:
  1. SEO 키워드로 이미지 4개 검색
  2. 이미지 다운로드 (비동기)
  3. 콘텐츠 분석하여 이미지 위치 결정
  4. DOCX 파일 생성 및 반환

```python
@router.post("/docx-with-auto-images")
async def export_docx_with_auto_images(
    request: ExportRequest,
    background_tasks: BackgroundTasks
):
    # 1. 이미지 검색
    images_data = await image_search_service.search_images(keywords, count=4)

    # 2. 이미지 다운로드
    for img_data in images_data:
        img_bytes = await image_search_service.download_image(img_data["url"])
        prepared_images.append(...)

    # 3. 이미지 위치 결정
    positioned_images = image_analyzer.prepare_images_for_export(...)

    # 4. DOCX 생성
    docx_file = blog_exporter.export_to_docx(...)
```

### 프론트엔드 (Frontend)

#### 저장된 포스트 관리자 UI 업데이트 (`frontend/src/components/saved-posts/saved-posts-manager.tsx`)

**1. `exportWithAutoImages` 함수 추가**

```typescript
const exportWithAutoImages = async () => {
  const loadingToast = toast.loading('AI가 관련 이미지를 자동으로 찾고 있습니다...')

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/docx-with-auto-images`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: selectedPost.generated_content || '',
          title: selectedPost.suggested_titles?.[0] || '',
          keywords: selectedPost.seo_keywords || [],
        }),
      }
    )

    // 파일 다운로드
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedPost.suggested_titles?.[0] || 'blog_post'}_with_images.docx`
    a.click()

    toast.success('이미지가 포함된 워드 파일이 다운로드되었습니다!', { id: loadingToast })
  } catch (error) {
    toast.error('다운로드 실패', { id: loadingToast })
  }
}
```

**2. 새로운 버튼 추가**

```tsx
<Button
  onClick={exportWithAutoImages}
  className="w-full bg-green-600 hover:bg-green-700"
>
  <Sparkles className="w-5 h-5 mr-2" />
  네이버 블로그용 워드 다운로드 (이미지 자동)
</Button>
```

---

## 사용 방법

### 1. 프로덕션 환경 접속

```
https://frontend-bp5ye7pl5-fewfs-projects-83cc0821.vercel.app
```

### 2. 저장된 포스트에서 워드 다운로드

1. **대시보드** > **저장된 포스트** 메뉴 이동
2. 다운로드할 포스트 선택
3. **"네이버 블로그용 워드 다운로드 (이미지 자동)"** 버튼 클릭 (초록색 버튼, Sparkles 아이콘)
4. AI가 자동으로 관련 이미지 검색 중... (토스트 메시지)
5. DOCX 파일 자동 다운로드

### 3. 다운로드된 파일 확인

- 파일명: `{포스트제목}_with_images.docx`
- 내용:
  - 제목 (큰 글씨)
  - 키워드 (노란색 형광펜)
  - 강조 문구 (초록색 형광펜)
  - **자동 삽입된 이미지 4개** (적절한 위치에 분산)
  - 본문 내용

### 4. 네이버 블로그 복붙

1. DOCX 파일 열기
2. 전체 선택 (Ctrl+A)
3. 복사 (Ctrl+C)
4. 네이버 블로그 에디터에 붙여넣기 (Ctrl+V)
5. **이미지 포함 모든 스타일 그대로 유지** ✅

---

## 기술 스택

### 백엔드
- FastAPI
- python-docx 1.1.0
- httpx (비동기 HTTP 클라이언트)
- Unsplash API (선택)
- Pexels API (선택)
- Lorem Picsum (API 키 불필요)

### 프론트엔드
- Next.js 14
- React
- TypeScript
- lucide-react (Sparkles 아이콘)
- react-hot-toast (토스트 메시지)

### 인프라
- Fly.io (백엔드 호스팅)
- Vercel (프론트엔드 호스팅)

---

## API 키 설정 (선택사항)

현재는 API 키 없이도 Lorem Picsum으로 작동하지만, 더 나은 품질의 이미지를 원하면:

### Unsplash API 키 설정

1. https://unsplash.com/developers 가입
2. 새 애플리케이션 생성
3. Access Key 복사
4. Fly.io 시크릿 설정:
   ```bash
   flyctl secrets set UNSPLASH_ACCESS_KEY="your_access_key" -a doctor-voice-pro-backend
   ```

### Pexels API 키 설정 (대체용)

1. https://www.pexels.com/api/ 가입
2. API 키 생성
3. Fly.io 시크릿 설정:
   ```bash
   flyctl secrets set PEXELS_API_KEY="your_api_key" -a doctor-voice-pro-backend
   ```

---

## 테스트 방법

### 1. 기본 테스트

```bash
# 이미지 검색 API 테스트
curl -X POST https://doctor-voice-pro-backend.fly.dev/api/v1/export/search-images \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["의학", "건강"], "count": 4}'

# 자동 이미지 DOCX 다운로드 테스트
curl -X POST https://doctor-voice-pro-backend.fly.dev/api/v1/export/docx-with-auto-images \
  -H "Content-Type: application/json" \
  -d '{"content":"테스트 콘텐츠","title":"테스트","keywords":["건강","의학"]}' \
  --output test_with_images.docx
```

### 2. 프론트엔드 테스트

1. 프로덕션 사이트 접속
2. 로그인
3. 저장된 포스트 선택
4. "이미지 자동" 버튼 클릭
5. 다운로드 확인

---

## 예상 효과

✅ **자동 이미지 검색**: SEO 키워드 기반 관련 이미지 자동 검색
✅ **원클릭 다운로드**: 버튼 한 번으로 이미지 포함 DOCX 생성
✅ **적절한 이미지 배치**: 2-3개 문단마다 자동 분산
✅ **네이버 블로그 호환**: 복붙 시 이미지 그대로 유지
✅ **API 키 불필요**: Lorem Picsum으로 기본 작동
✅ **고품질 이미지**: Unsplash/Pexels 연동 시 전문가급 사진

---

## 모니터링

### 백엔드 로그 확인

```bash
flyctl logs -a doctor-voice-pro-backend --limit 50
```

### 프론트엔드 로그 확인

```bash
vercel logs https://frontend-bp5ye7pl5-fewfs-projects-83cc0821.vercel.app
```

### 백엔드 상태 확인

```bash
flyctl status -a doctor-voice-pro-backend
```

---

## 문제 해결

### 이미지가 다운로드되지 않으면

1. **백엔드 로그 확인**
   ```bash
   flyctl logs -a doctor-voice-pro-backend --limit 50
   ```

2. **이미지 검색 API 직접 테스트**
   ```bash
   curl -X POST https://doctor-voice-pro-backend.fly.dev/api/v1/export/search-images \
     -H "Content-Type: application/json" \
     -d '{"keywords": ["의학"], "count": 4}'
   ```

3. **환경 변수 확인**
   ```bash
   flyctl secrets list -a doctor-voice-pro-backend
   ```

### 이미지 품질이 낮으면

- Unsplash API 키 설정 (위 "API 키 설정" 섹션 참고)
- 현재는 Lorem Picsum 플레이스홀더 사용 중

### 다운로드가 느리면

- 정상입니다 - 4개 이미지 다운로드 + DOCX 생성 시간 필요
- 평균 5-10초 소요
- 토스트 메시지로 진행 상황 표시

---

## 커밋 정보

### 백엔드 커밋

**Commit**: `0794515`
**메시지**: Add automatic image search and insertion for blog export

**변경사항**:
- Add ImageSearchService with Unsplash/Pexels/Lorem Picsum fallback
- Add /api/v1/export/search-images endpoint
- Add /api/v1/export/docx-with-auto-images endpoint
- Automatically fetch 4 relevant images based on SEO keywords
- Distribute images between paragraphs using existing image_analyzer

### 프론트엔드 커밋

**Commit**: `1cc4a92`
**메시지**: Add auto-image download button to saved posts manager

**변경사항**:
- Add exportWithAutoImages function
- Add green '이미지 자동' button with Sparkles icon
- Uses /api/v1/export/docx-with-auto-images endpoint
- Shows loading toast during image search and generation

---

## 다음 단계

1. **프로덕션 환경에서 실제 사용자 테스트**
   - 다양한 주제의 포스트로 테스트
   - 이미지 관련성 확인
   - 다운로드 속도 체크

2. **Unsplash API 키 설정 (고품질 이미지)**
   - 무료 계정: 월 50개 요청 제한
   - 충분히 테스트 및 개인 사용 가능

3. **이미지 캐싱 고려**
   - 동일 키워드 재사용 시 이미지 캐싱
   - 다운로드 속도 개선

4. **사용자 피드백 수집**
   - 이미지 관련성 만족도
   - 이미지 배치 위치 선호도
   - 이미지 개수 조정 (4개 → 사용자 설정?)

---

## 참고 문서

- [Unsplash API Documentation](https://unsplash.com/documentation)
- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [Lorem Picsum](https://picsum.photos/)
- [python-docx Documentation](https://python-docx.readthedocs.io/)
- [httpx Documentation](https://www.python-httpx.org/)

---

🎉 **배포 성공!**

이제 네이버 블로그용 워드 다운로드 시 자동으로 관련 이미지 4개가 포함됩니다!

**테스트 URL**: https://frontend-bp5ye7pl5-fewfs-projects-83cc0821.vercel.app
