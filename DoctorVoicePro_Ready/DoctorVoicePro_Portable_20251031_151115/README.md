# 닥터보이스 프로 (DoctorVoice Pro)

의료 블로그 자동 각색 SaaS 플랫폼

## 개요

닥터보이스 프로는 의료 정보를 원장님의 개성있는 말투로 자동 변환하여, 신뢰도 높고 설득력 있는 네이버 블로그 포스팅을 생성하는 AI 기반 플랫폼입니다.

### 핵심 기능

- **AI 자동 각색**: Claude 3.5 Sonnet을 활용한 고품질 콘텐츠 생성
- **원장님 스타일 학습**: 개인화된 말투와 글쓰기 스타일 재현
- **의료법 자동 검증**: 위반 표현 자동 탐지 및 수정
- **설득력 분석**: 6가지 지표 기반 설득력 점수 계산
- **SEO 최적화**: 네이버 검색 최적화된 키워드 및 해시태그 자동 생성

## 기술 스택

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15 + Redis
- **ORM**: SQLAlchemy 2.0 (Async)
- **AI**: Claude 3.5 Sonnet API (Anthropic)
- **Migration**: Alembic

### Frontend (예정)
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Deployment**: AWS (예정)

## 설치 및 실행

### 사전 요구사항

- Docker & Docker Compose
- Anthropic API Key (Claude)

### 1. 프로젝트 클론

```bash
git clone <repository-url>
cd doctor-voice-pro
```

### 2. 환경 변수 설정

```bash
# backend/.env 파일 편집
cd backend
cp .env.example .env

# ANTHROPIC_API_KEY 설정 (필수)
# 나머지 값들은 로컬 개발용 기본값 사용
```

### 3. Docker로 실행

```bash
# 프로젝트 루트 디렉토리에서
docker-compose up -d
```

### 4. 데이터베이스 마이그레이션

```bash
# 백엔드 컨테이너 접속
docker exec -it doctorvoice-backend bash

# 마이그레이션 생성 및 적용
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 5. API 접속

- **API 문서**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API 사용 예시

### 1. 회원가입

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com",
    "password": "password123",
    "name": "김정형",
    "hospital_name": "서울정형외과",
    "specialty": "정형외과"
  }'
```

### 2. 로그인

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com",
    "password": "password123"
  }'
```

### 3. 포스팅 생성

```bash
curl -X POST "http://localhost:8000/api/v1/posts/" \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "original_content": "퇴행성 관절염은 관절 연골의 손상으로 발생합니다. 주요 증상은 통증, 부종, 관절 운동 제한입니다. 치료 방법으로는 약물치료, 물리치료, 수술적 치료가 있습니다.",
    "persuasion_level": 4,
    "framework": "AIDA",
    "target_length": 1500
  }'
```

## 프로젝트 구조

```
doctor-voice-pro/
├── backend/
│   ├── app/
│   │   ├── api/              # API 라우터
│   │   ├── core/             # 핵심 설정
│   │   ├── db/               # 데이터베이스
│   │   ├── models/           # SQLAlchemy 모델
│   │   ├── schemas/          # Pydantic 스키마
│   │   ├── services/         # 비즈니스 로직
│   │   └── main.py           # FastAPI 앱
│   ├── alembic/              # DB 마이그레이션
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── frontend/ (예정)
├── docker-compose.yml
└── README.md
```

## 핵심 서비스 모듈

### 1. AI 각색 엔진 (`ai_rewrite_engine.py`)
- Claude API 기반 콘텐츠 각색
- 4가지 설득 프레임워크 (AIDA, PAS, STORY, QA)
- 5단계 각색 레벨

### 2. 의료법 검증 (`medical_law_checker.py`)
- 절대적 표현 탐지
- 비교 우위 표현 탐지
- 과장 광고 필터링
- 자동 대체 표현 제안

### 3. 설득력 점수 계산 (`persuasion_scorer.py`)
- 스토리텔링 분석
- 데이터/근거 활용도
- 감정 공감 요소
- 권위/전문성 신호
- 사회적 증거
- CTA 명확성

### 4. SEO 최적화 (`seo_optimizer.py`)
- 의학 용어 추출
- 검색 키워드 생성
- 해시태그 자동 생성
- 메타 설명 생성

## 개발 가이드

### 로컬 개발 (Docker 없이)

```bash
# Python 가상환경 생성
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# PostgreSQL & Redis 실행 (별도)
# 또는 Docker Compose로 DB만 실행
docker-compose up -d db redis

# 개발 서버 실행
uvicorn app.main:app --reload
```

### 새로운 API 엔드포인트 추가

1. `app/api/` 에 새 라우터 파일 생성
2. `app/api/__init__.py` 에 라우터 등록
3. 필요시 `app/models/`, `app/schemas/` 에 모델/스키마 추가

### 데이터베이스 마이그레이션

```bash
# 새 마이그레이션 생성
alembic revision --autogenerate -m "Description"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

## 라이선스

Proprietary - All rights reserved

## 문의

프로젝트 관련 문의: [이메일 주소]
