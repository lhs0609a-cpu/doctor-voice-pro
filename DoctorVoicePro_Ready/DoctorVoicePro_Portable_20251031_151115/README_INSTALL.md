# 📦 Doctor Voice Pro 설치 가이드

초보자도 쉽게 따라할 수 있는 단계별 설치 가이드입니다.

---

## 📋 목차

- [시스템 요구사항](#-시스템-요구사항)
- [빠른 시작 (원클릭 설치)](#-빠른-시작-원클릭-설치)
- [수동 설치](#-수동-설치)
- [설정](#-설정)
- [실행](#-실행)
- [문제 해결](#-문제-해결)
- [고급 기능](#-고급-기능)

---

## 💻 시스템 요구사항

### 필수 요구사항

| 항목 | 요구사항 |
|------|---------|
| 운영 체제 | Windows 10+, macOS 10.15+, Ubuntu 20.04+ |
| Python | 3.8 이상 |
| Node.js | 16.0 이상 |
| 메모리 | 최소 2GB (4GB 권장) |
| 디스크 공간 | 최소 1GB |

### 선택 사항

- **Anthropic API Key**: AI 블로그 생성 기능
- **OpenAI API Key**: 추가 AI 기능 (선택)
- **Naver Blog API**: 네이버 블로그 자동 발행

---

## 🚀 빠른 시작 (원클릭 설치)

가장 쉬운 설치 방법입니다.

### Windows 사용자

1. **install.bat 실행**
   ```
   install.bat 파일을 더블클릭하세요
   ```

2. **화면의 지시사항을 따라 진행**
   - Python 버전 확인
   - 패키지 자동 설치
   - 환경 설정 생성
   - 데이터베이스 초기화

3. **완료!**
   - 설치 완료 후 `run.bat`을 실행하여 서버를 시작하세요

### Mac/Linux 사용자

1. **터미널 열기**
   - Mac: `Cmd + Space` → "터미널" 입력
   - Linux: `Ctrl + Alt + T`

2. **실행 권한 부여 및 설치**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **화면의 지시사항 따르기**

4. **완료!**
   ```bash
   ./run.sh
   ```

---

## 🔧 수동 설치

자동 설치가 실패한 경우 수동으로 설치할 수 있습니다.

### STEP 1: Python 설치 확인

```bash
# Windows (CMD 또는 PowerShell)
python --version

# Mac/Linux
python3 --version
```

**결과가 "Python 3.8" 이상이어야 합니다.**

Python이 없다면 설치하세요:
- Windows: https://www.python.org/downloads/
- Mac: `brew install python3`
- Ubuntu: `sudo apt-get install python3 python3-pip`

### STEP 2: Node.js 설치 확인

```bash
node --version
npm --version
```

**Node.js 16 이상이어야 합니다.**

Node.js가 없다면 설치하세요:
- Windows/Mac: https://nodejs.org/
- Ubuntu:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ```

### STEP 3: 프로젝트 다운로드

```bash
# Git을 사용하는 경우
git clone <repository-url>
cd doctor-voice-pro

# 또는 ZIP 파일을 다운로드하여 압축 해제
```

### STEP 4: Backend 패키지 설치

```bash
# 프로젝트 루트에서 실행
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**시간이 걸릴 수 있습니다 (5-10분)**

### STEP 5: Frontend 패키지 설치

```bash
# 프로젝트 루트에서 실행
cd frontend
npm install
```

**시간이 걸릴 수 있습니다 (3-5분)**

### STEP 6: 환경 설정 파일 생성

```bash
cd backend
cp .env.example .env
```

또는 수동으로 `backend/.env` 파일 생성:

```env
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key-here-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ENVIRONMENT=development
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

---

## ⚙️ 설정

### API 키 설정 (선택사항)

AI 기능을 사용하려면 API 키가 필요합니다.

#### 1. Anthropic Claude API 키 발급

1. https://console.anthropic.com/ 접속
2. 계정 생성 또는 로그인
3. API Keys → Create Key
4. 발급받은 키를 복사

#### 2. .env 파일에 추가

`backend/.env` 파일을 텍스트 에디터로 열고:

```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

#### 3. 서버 재시작

설정을 변경한 후에는 서버를 재시작해야 합니다.

### SECRET_KEY 변경 (중요!)

보안을 위해 SECRET_KEY를 변경하세요:

```bash
# 랜덤 키 생성
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

생성된 키를 `backend/.env`의 SECRET_KEY에 넣으세요.

---

## 🎯 실행

### 방법 1: 실행 스크립트 사용 (권장)

**Windows:**
```bash
run.bat
```

**Mac/Linux:**
```bash
./run.sh
```

### 방법 2: 수동 실행

**Backend 실행:**
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

**Frontend 실행 (새 터미널):**
```bash
cd frontend
npm run dev
```

### 접속

- **Frontend (사용자 인터페이스)**: http://localhost:3000
- **Backend API 문서**: http://localhost:8010/docs
- **Backend 관리**: http://localhost:8010/admin

### 종료

- Windows: 각 창에서 `Ctrl + C`
- Mac/Linux: 터미널에서 `Ctrl + C`

---

## 🔍 문제 해결

### 일반적인 문제

#### 1. "Python을 찾을 수 없습니다"

**원인**: Python이 설치되지 않았거나 PATH에 없음

**해결:**
- Python 재설치 시 "Add Python to PATH" 체크
- 또는 환경 변수에 Python 경로 추가

#### 2. "패키지 설치 실패"

**원인**: 인터넷 연결 문제 또는 권한 문제

**해결:**
```bash
# 관리자 권한으로 재시도
# Windows: 명령 프롬프트를 관리자로 실행
# Mac/Linux: sudo 사용

python -m pip install -r backend/requirements.txt --no-cache-dir
```

#### 3. "포트가 이미 사용 중입니다"

**원인**: 다른 프로그램이 포트 8010 또는 3000 사용 중

**해결:**

**Windows:**
```cmd
# 포트 사용 프로세스 확인
netstat -ano | findstr :8010

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID> /F
```

**Mac/Linux:**
```bash
# 포트 사용 프로세스 확인
lsof -i :8010

# 프로세스 종료
kill -9 <PID>
```

#### 4. "데이터베이스 연결 실패"

**원인**: 데이터베이스 파일이 없거나 권한 문제

**해결:**
```bash
# 자가 진단 실행
python health_check.py

# 데이터베이스 수동 생성 (backend 폴더에서)
python -c "from app.database import init_db; init_db()"
```

#### 5. "모듈을 찾을 수 없습니다"

**원인**: 패키지 설치가 완료되지 않음

**해결:**
```bash
cd backend
python -m pip install -r requirements.txt --upgrade
```

### 자가 진단 도구 사용

문제가 있을 때 먼저 자가 진단을 실행하세요:

```bash
python health_check.py
```

자가 진단은 다음을 확인합니다:
- ✅ Python 버전
- ✅ 필수 패키지 설치
- ✅ Node.js & npm
- ✅ 데이터베이스
- ✅ 환경 설정 파일
- ✅ 포트 사용 가능 여부
- ✅ 디스크 공간
- ✅ 메모리

**자동 수정 기능:**
- 누락된 패키지 자동 설치
- .env 파일 자동 생성
- 데이터베이스 자동 초기화

### 에러 리포트

에러가 발생하면 자동으로 `error_reports/` 폴더에 상세 리포트가 생성됩니다:

```
error_reports/
├── 20251030_143052_ConnectionError.txt
├── 20251030_143052_ConnectionError.json
└── ...
```

리포트 파일을 열면:
- 📅 에러 발생 시각
- 🖥️ 시스템 정보
- ❌ 에러 상세 정보
- 🔍 원인 분석
- 💡 해결 방법
- 📋 Claude에게 복사할 수 있는 형식

---

## 🎁 고급 기능

### 자동 배포

새 버전으로 프로젝트를 복사할 때:

```bash
# 패치 버전 증가 (1.0.0 → 1.0.1)
python auto_deploy.py

# 마이너 버전 증가 (1.0.0 → 1.1.0)
python auto_deploy.py --minor

# 메이저 버전 증가 (1.0.0 → 2.0.0)
python auto_deploy.py --major

# 변경사항과 함께
python auto_deploy.py -m "버그 수정" -m "새 기능 추가"
```

자동으로:
- ✅ 버전 번호 증가
- ✅ 새 폴더에 프로젝트 복사
- ✅ CHANGELOG 업데이트
- ✅ 필요한 디렉토리 생성

### 시스템 모니터링

성능 모니터링, 백업, 로그 관리:

```bash
# 성능 리포트
python system_monitor.py --monitor

# 백업 생성
python system_monitor.py --backup

# 백업 목록 조회
python system_monitor.py --list-backups

# 로그 로테이션
python system_monitor.py --rotate-logs

# 자동 모니터링 시작
python system_monitor.py --auto
```

**자동 기능:**
- 📊 성능 메트릭 수집 (CPU, 메모리)
- 💾 일일 자동 백업
- 📝 로그 파일 자동 분할 (10MB 초과 시)
- ⚠️ 리소스 경고 (CPU/메모리 80% 초과)

### 백업 및 복원

**수동 백업:**
```bash
python system_monitor.py --backup
```

백업 내용:
- 데이터베이스 (*.db)
- 환경 설정 (.env)
- 업로드된 파일

백업 파일 위치: `backups/backup_YYYYMMDD_HHMMSS.tar.gz`

**복원:**
1. `backups/` 폴더에서 원하는 백업 파일 찾기
2. 압축 해제
3. 필요한 파일을 프로젝트 폴더에 복사

---

## 📞 지원

### 문서

- [메인 README](README.md)
- [API 문서](http://localhost:8010/docs)
- [변경 이력](CHANGELOG.md)

### 도구

| 도구 | 용도 | 명령어 |
|------|------|--------|
| 자가 진단 | 시스템 체크 | `python health_check.py` |
| 자동 배포 | 버전 관리 | `python auto_deploy.py` |
| 시스템 모니터 | 성능/백업 | `python system_monitor.py` |

### 에러 해결 프로세스

1. **자가 진단 실행**
   ```bash
   python health_check.py
   ```

2. **에러 리포트 확인**
   ```
   error_reports/ 폴더 확인
   ```

3. **Claude에게 문의**
   - 에러 리포트의 "Claude에게 붙여넣기용" 섹션 복사
   - Claude에게 전달하여 해결책 받기

---

## ✅ 체크리스트

설치가 완료되었는지 확인하세요:

- [ ] Python 3.8 이상 설치됨
- [ ] Node.js 16 이상 설치됨
- [ ] Backend 패키지 설치 완료
- [ ] Frontend 패키지 설치 완료
- [ ] `.env` 파일 생성됨
- [ ] `SECRET_KEY` 변경함
- [ ] (선택) API 키 설정함
- [ ] 서버가 정상 실행됨
- [ ] http://localhost:3000 접속 가능
- [ ] 로그인 가능

---

## 🎓 다음 단계

설치가 완료되었다면:

1. **계정 생성**: http://localhost:3000/register
2. **블로그 작성**: AI를 이용한 블로그 포스팅
3. **프로필 설정**: 전문 분야 및 스타일 설정
4. **네이버 연동**: 자동 발행 설정 (선택)

---

## 📝 참고사항

- 이 프로그램은 로컬(컴퓨터)에서 실행됩니다
- 인터넷 연결이 필요합니다 (AI API 사용 시)
- 데이터는 컴퓨터에 저장됩니다
- 백업을 정기적으로 하세요

---

**설치 중 문제가 있으신가요?**

`health_check.py`를 실행하여 자동 진단 받으세요!

```bash
python health_check.py
```
