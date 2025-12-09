# 닥터보이스 프로 - 빠른 시작 가이드

## 🚀 5분 안에 실행하기

### 전제 조건

1. **Node.js 18+** 설치 ([다운로드](https://nodejs.org/))
2. **Python 3.11+** 설치 ([다운로드](https://www.python.org/downloads/))
3. **Anthropic API Key** 발급 ([가입](https://console.anthropic.com/))

---

## 옵션 1: Docker 사용 (추천) 🐳

### 1. Docker Desktop 설치
- Windows: https://docs.docker.com/desktop/install/windows-install/
- Mac: https://docs.docker.com/desktop/install/mac-install/

### 2. 환경 변수 설정
```bash
# backend/.env 파일 열기
notepad doctor-voice-pro\backend\.env

# ANTHROPIC_API_KEY 값 입력
ANTHROPIC_API_KEY=your_actual_key_here
```

### 3. 실행
```bash
cd doctor-voice-pro
docker-compose up -d
```

### 4. 마이그레이션
```bash
docker exec -it doctorvoice-backend bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
exit
```

### 5. 프론트엔드 실행
```bash
cd frontend
npm install
npm run dev
```

**완료!** http://localhost:3000 접속

---

## 옵션 2: 로컬 실행 (Docker 없이) 🖥️

### 1. PostgreSQL & Redis 설치

#### Windows (chocolatey 사용)
```powershell
choco install postgresql redis
```

#### Mac (homebrew 사용)
```bash
brew install postgresql@15 redis
brew services start postgresql@15
brew services start redis
```

### 2. 데이터베이스 생성
```bash
# PostgreSQL 접속
psql -U postgres

# 데이터베이스 생성
CREATE DATABASE doctorvoice;
CREATE USER doctorvoice WITH PASSWORD 'doctorvoice123';
GRANT ALL PRIVILEGES ON DATABASE doctorvoice TO doctorvoice;
\q
```

### 3. 백엔드 설정 및 실행

```bash
cd doctor-voice-pro/backend

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 가상환경 활성화 (Mac/Linux)
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# .env 파일 수정
# DATABASE_URL, ANTHROPIC_API_KEY 등 설정

# 마이그레이션
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload
```

백엔드 실행 확인: http://localhost:8000/docs

### 4. 프론트엔드 실행

```bash
# 새 터미널 열기
cd doctor-voice-pro/frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

프론트엔드 실행 확인: http://localhost:3000

---

## ✅ 실행 확인

### 1. 백엔드 API 확인
- http://localhost:8000/docs - Swagger UI
- http://localhost:8000/health - Health Check

### 2. 프론트엔드 확인
- http://localhost:3000 - 랜딩 페이지
- http://localhost:3000/login - 로그인
- http://localhost:3000/register - 회원가입

---

## 🎯 첫 사용 가이드

### 1. 회원가입
```
이메일: test@example.com
비밀번호: password123
이름: 김정형
병원명: 서울정형외과
진료과목: 정형외과
```

### 2. 로그인 후 대시보드 접속

### 3. 글 작성 페이지로 이동

### 4. 원본 의료 정보 입력
```
퇴행성 관절염은 관절 연골의 손상으로 발생합니다.
주요 증상은 통증, 부종, 관절 운동 제한입니다.
치료 방법으로는 약물치료, 물리치료, 수술적 치료가 있습니다.
```

### 5. 각색 설정
- 각색 레벨: 4 (행동 촉구형)
- 프레임워크: AIDA
- 길이: 보통

### 6. "블로그 생성하기" 클릭

### 7. 결과 확인!
- AI가 생성한 블로그 글
- 설득력 점수
- 의료법 준수 여부
- 추천 해시태그
- SEO 키워드

---

## 🔧 문제 해결

### 백엔드가 실행되지 않을 때

1. **PostgreSQL 연결 실패**
   ```bash
   # DATABASE_URL 확인
   # backend/.env 파일에서 DB 정보 확인
   ```

2. **Anthropic API 오류**
   ```bash
   # API 키 확인
   # backend/.env에서 ANTHROPIC_API_KEY 확인
   ```

3. **포트 충돌**
   ```bash
   # 다른 포트 사용
   uvicorn app.main:app --port 8001
   ```

### 프론트엔드가 실행되지 않을 때

1. **API 연결 실패**
   ```bash
   # frontend/.env.local 확인
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

2. **의존성 설치 오류**
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

---

## 📚 주요 API 엔드포인트

### 인증
- `POST /api/v1/auth/register` - 회원가입
- `POST /api/v1/auth/login` - 로그인
- `GET /api/v1/auth/me` - 현재 사용자 정보

### 포스팅
- `POST /api/v1/posts/` - 포스팅 생성 (핵심!)
- `GET /api/v1/posts/` - 포스팅 목록
- `POST /api/v1/posts/{id}/rewrite` - 재작성

### 프로필
- `GET /api/v1/profiles/me` - 프로필 조회
- `PUT /api/v1/profiles/me` - 프로필 수정

---

## 🎨 UI 기능

### 구현된 페이지
- ✅ 랜딩 페이지 (트렌디한 디자인)
- ✅ 로그인/회원가입
- ✅ 대시보드 (통계, 최근 포스팅)
- ✅ AI 글 작성 페이지 (핵심 기능!)
- ⏳ 포스팅 관리
- ⏳ 프로필 설정

### 주요 기능
- 🤖 AI 자동 각색 (Claude 3.5 Sonnet)
- 🛡️ 의료법 자동 검증
- 📊 설득력 점수 분석
- 🔍 SEO 최적화
- #️⃣ 해시태그 자동 생성

---

## 💡 팁

### 1. 좋은 원본 콘텐츠 작성법
- 의학적 사실을 명확하게
- 최소 300자 이상 작성
- 증상, 원인, 치료 순서로 구성

### 2. 설득력 높이기
- 각색 레벨 4-5 사용
- AIDA 또는 PAS 프레임워크 추천
- 스토리텔링 요소 추가

### 3. SEO 최적화
- 키워드 2-3개 자연스럽게 포함
- 제목에 핵심 키워드 포함
- 해시태그 10-15개 활용

---

## 📞 지원

- 문제 발생 시: GitHub Issues
- 문의: [이메일 주소]

**즐거운 블로그 작성 되세요! 🎉**
