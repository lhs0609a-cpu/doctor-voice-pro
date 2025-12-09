#!/bin/bash
# =================================================================
# Doctor Voice Pro - 원클릭 설치 스크립트 (Linux/Mac)
# =================================================================
# 이 스크립트는 프로그램에 필요한 모든 것을 자동으로 설치합니다.
# =================================================================

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 헤더 출력 함수
print_header() {
    echo ""
    echo "================================================================"
    echo "  $1"
    echo "================================================================"
    echo ""
}

# 체크 결과 출력 함수
print_check() {
    local status=$1
    local message=$2

    case $status in
        "ok")
            echo -e "${GREEN}✅${NC} $message"
            ;;
        "fail")
            echo -e "${RED}❌${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}⚠️${NC}  $message"
            ;;
        "info")
            echo -e "${BLUE}ℹ️${NC}  $message"
            ;;
    esac
}

# 에러 처리
set -e
trap 'echo -e "\n${RED}❌ 설치 중 오류가 발생했습니다.${NC}"; exit 1' ERR

print_header "🚀 Doctor Voice Pro 자동 설치"

# 현재 디렉토리 저장
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "📁 프로젝트 경로: $PROJECT_ROOT"
echo ""

# =================================================================
# STEP 1: 시스템 자가 진단
# =================================================================
print_header "STEP 1/6: 시스템 자가 진단"

# Python 확인
if ! command -v python3 &> /dev/null; then
    print_check "fail" "Python3이 설치되어 있지 않습니다!"
    echo ""
    echo "Python 3.8 이상을 설치해주세요:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip"
    echo "  Mac: brew install python3"
    echo ""
    exit 1
fi

print_check "ok" "Python 확인 완료"
python3 --version

# 자가 진단 실행
echo ""
print_check "info" "자가 진단 시스템 실행 중..."
if python3 health_check.py; then
    print_check "ok" "자가 진단 통과"
else
    print_check "warning" "자가 진단에서 일부 문제가 발견되었습니다."
    read -p "계속 진행하시겠습니까? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

read -p "Press Enter to continue..."

# =================================================================
# STEP 2: 필수 디렉토리 생성
# =================================================================
print_header "STEP 2/6: 필수 디렉토리 생성"

mkdir -p logs
mkdir -p data
mkdir -p error_reports
mkdir -p backups

print_check "ok" "logs/ - 로그 파일 저장"
print_check "ok" "data/ - 데이터베이스 저장"
print_check "ok" "error_reports/ - 에러 리포트 저장"
print_check "ok" "backups/ - 백업 파일 저장"

# =================================================================
# STEP 3: Python 패키지 설치 (Backend)
# =================================================================
print_header "STEP 3/6: Backend 패키지 설치"

cd "$PROJECT_ROOT/backend"

# pip 업그레이드
print_check "info" "pip 업그레이드 중..."
python3 -m pip install --upgrade pip || true

# requirements.txt 설치
echo ""
print_check "info" "Python 패키지 설치 중... (시간이 걸릴 수 있습니다)"
python3 -m pip install -r requirements.txt

print_check "ok" "Backend 패키지 설치 완료"

# =================================================================
# STEP 4: Node.js 패키지 설치 (Frontend)
# =================================================================
print_header "STEP 4/6: Frontend 패키지 설치"

cd "$PROJECT_ROOT/frontend"

# Node.js 확인
if ! command -v node &> /dev/null; then
    print_check "warning" "Node.js가 설치되어 있지 않습니다."
    echo ""
    echo "Node.js 설치:"
    echo "  Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs"
    echo "  Mac: brew install node"
    echo ""
    echo "설치 후 실행: cd frontend && npm install"
    echo ""
else
    print_check "ok" "Node.js 확인 완료"
    node --version

    echo ""
    print_check "info" "npm 패키지 설치 중... (시간이 걸릴 수 있습니다)"
    npm install || print_check "warning" "npm 설치 중 일부 오류 발생 (계속 진행)"

    print_check "ok" "Frontend 패키지 설치 완료"
fi

# =================================================================
# STEP 5: 환경 설정 파일 생성
# =================================================================
print_header "STEP 5/6: 환경 설정"

cd "$PROJECT_ROOT/backend"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_check "info" ".env 파일 생성 중... (.env.example에서 복사)"
        cp ".env.example" ".env"
        print_check "ok" ".env 파일 생성 완료"
    else
        print_check "info" "기본 .env 파일 생성 중..."
        cat > ".env" << 'EOF'
# Database
DATABASE_URL=sqlite:///./app.db

# Security
SECRET_KEY=change-this-in-production-please-use-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys (optional)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Environment
ENVIRONMENT=development
EOF
        print_check "ok" "기본 .env 파일 생성 완료"
    fi

    echo ""
    print_check "warning" "중요: .env 파일을 열어서 다음을 설정하세요:"
    echo "   - SECRET_KEY: 보안을 위해 변경하세요"
    echo "   - ANTHROPIC_API_KEY: Claude AI 사용 시 필요"
    echo "   - OPENAI_API_KEY: OpenAI API 사용 시 필요"
    echo ""
else
    print_check "ok" ".env 파일이 이미 존재합니다."
fi

# =================================================================
# STEP 6: 데이터베이스 초기화
# =================================================================
print_header "STEP 6/6: 데이터베이스 초기화"

cd "$PROJECT_ROOT/backend"

if [ ! -f "app.db" ]; then
    print_check "info" "데이터베이스 초기화 중..."

    if [ -f "init_db.py" ]; then
        if python3 init_db.py; then
            print_check "ok" "데이터베이스 초기화 완료"
        else
            print_check "warning" "초기화 스크립트 실행 실패"
            print_check "info" "서버 시작 시 자동으로 생성됩니다."
        fi
    else
        print_check "info" "init_db.py가 없습니다."
        print_check "info" "서버 시작 시 자동으로 생성됩니다."
    fi
else
    print_check "ok" "데이터베이스가 이미 존재합니다."
fi

# =================================================================
# 실행 권한 부여
# =================================================================
echo ""
print_check "info" "실행 권한 부여..."
chmod +x "$PROJECT_ROOT/run.sh" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/install.sh" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/health_check.py" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/auto_deploy.py" 2>/dev/null || true

# =================================================================
# 설치 완료
# =================================================================
print_header "🎉 설치 완료!"

echo "다음 단계:"
echo ""
echo "1. .env 파일 확인 및 API 키 설정 (선택사항)"
echo "   위치: backend/.env"
echo ""
echo "2. 서버 실행:"
echo "   ./run.sh"
echo ""
echo "3. 브라우저에서 확인:"
echo "   Backend:  http://localhost:8010"
echo "   Frontend: http://localhost:3000"
echo ""
echo "================================================================"
echo ""

cd "$PROJECT_ROOT"

read -p "지금 서버를 시작하시겠습니까? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "서버를 시작합니다..."
    sleep 2
    ./run.sh
else
    echo ""
    echo "나중에 ./run.sh를 실행하여 서버를 시작할 수 있습니다."
fi
