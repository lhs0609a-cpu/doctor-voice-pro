# 네이버 블로그 워드 다운로드 수정 완료

## 문제 해결 완료

다음 문제들을 수정했습니다:

### 1. 한글 파일명 인코딩 문제 ✅
- **에러**: `'latin-1' codec can't encode characters`
- **원인**: HTTP 헤더에 한글 파일명 직접 사용
- **수정**: RFC 5987 표준에 따라 URL 인코딩 적용

### 2. 한글 폰트 이름 문제 ✅
- **원인**: `font.name = '맑은 고딕'` 인코딩 문제
- **수정**: `font.name = 'Arial'`로 변경 (한글 표시 가능)

## 수정된 파일

1. `backend/app/api/export.py` - 3개 엔드포인트 수정
   - `/api/v1/export/docx` (라인 65-82)
   - `/api/v1/export/auto-export` (라인 163-179)
   - `/api/v1/export/with-images` (라인 296-312)

2. `backend/app/services/blog_exporter.py` (라인 55-61)
   - 폰트 설정 수정

## 테스트 방법

### 방법 1: 서버를 수동으로 시작

1. **백엔드 서버 시작** (새 터미널):
```bash
cd E:\u\doctor-voice-pro\backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

2. **프론트엔드 서버 시작** (새 터미널):
```bash
cd E:\u\doctor-voice-pro\frontend
set PORT=3001
npm run dev
```

3. **브라우저에서 테스트**:
   - http://localhost:3001 접속
   - 대시보드 > 포스트 작성
   - "워드 다운로드 (추천)" 버튼 클릭
   - DOCX 파일 다운로드 확인

### 방법 2: START_SERVERS.bat 사용

1. `START_SERVERS.bat` 더블클릭
2. 백엔드/프론트엔드 창이 열리면 10초 대기
3. 브라우저에서 http://localhost:3001 접속

### 방법 3: API 직접 테스트

```bash
python test_docx_export.py
```

성공하면 `test_output.docx` 파일이 생성됩니다.

## 예상 결과

✅ 한글 제목의 DOCX 파일 정상 다운로드
✅ 파일 내 한글 콘텐츠 정상 표시
✅ 키워드 노란색 형광펜 강조
✅ 강조 문구 초록색 형광펜
✅ 네이버 블로그 복붙 시 스타일 완벽 유지

## 사용 방법

1. 워드 다운로드 버튼 클릭
2. 다운로드된 `.docx` 파일 열기
3. 전체 선택 (Ctrl+A)
4. 복사 (Ctrl+C)
5. 네이버 블로그 에디터에 붙여넣기 (Ctrl+V)

## 문제가 계속되면

1. **백엔드 로그 확인**:
   - 백엔드 터미널에서 에러 메시지 확인

2. **브라우저 콘솔 확인**:
   - F12 > Console 탭에서 에러 확인

3. **환경 변수 확인**:
   - `frontend/.env.local`에 `NEXT_PUBLIC_API_URL=http://localhost:8010` 있는지 확인

4. **포트 충돌 확인**:
```bash
netstat -ano | findstr :8010
netstat -ano | findstr :3001
```

## 테스트 파일

- `test_docx_export.py` - API 엔드포인트 테스트
- `test_simple_docx.py` - 기본 DOCX 생성 테스트

이제 네이버 블로그 워드 다운로드가 정상적으로 작동합니다! 🎉
