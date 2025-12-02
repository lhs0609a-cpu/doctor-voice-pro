#!/bin/bash
# =================================================================
# Doctor Voice Pro - 서버 실행 스크립트 (Linux/Mac)
# =================================================================

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo "================================================================"
    echo "  $1"
    echo "================================================================"
    echo ""
}

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

print_header "🚀 Doctor Voice Pro 서버 시작"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 간단한 헬스 체크
print_check "info" "간단한 시스템 체크..."
if python3 health_check.py --no-auto-fix > /dev/null 2>&1; then
    print_check "ok" "시스템 정상"
else
    print_check "warning" "시스템 체크에서 문제가 발견되었습니다."
    echo ""
    read -p "상세 진단을 실행하시겠습니까? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 health_check.py
        echo ""
        read -p "Press Enter to continue..."
    fi
fi

print_header "서버 시작 중..."

echo "Backend:  http://localhost:8010"
echo "Frontend: http://localhost:3000"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""
echo "================================================================"

# PID 파일 경로
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

# 기존 프로세스 정리 함수
cleanup() {
    echo ""
    print_check "info" "서버 종료 중..."

    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            kill "$BACKEND_PID" 2>/dev/null || true
        fi
        rm -f "$BACKEND_PID_FILE"
    fi

    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            kill "$FRONTEND_PID" 2>/dev/null || true
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    print_check "ok" "서버 종료 완료"
    exit 0
}

# Ctrl+C 시그널 처리
trap cleanup SIGINT SIGTERM

# Backend 시작
echo "🔵 Backend 서버 시작 중..."
cd "$PROJECT_ROOT/backend"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$BACKEND_PID_FILE"

# 잠시 대기
sleep 5

# Backend 확인
if kill -0 "$BACKEND_PID" 2>/dev/null; then
    print_check "ok" "Backend 서버 실행 중 (PID: $BACKEND_PID)"
else
    print_check "fail" "Backend 서버 시작 실패"
    echo "로그 확인: $PROJECT_ROOT/logs/backend.log"
    exit 1
fi

# Frontend 시작
echo ""
echo "🟢 Frontend 서버 시작 중..."
cd "$PROJECT_ROOT/frontend"
npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$FRONTEND_PID_FILE"

# 잠시 대기
sleep 5

# Frontend 확인
if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    print_check "ok" "Frontend 서버 실행 중 (PID: $FRONTEND_PID)"
else
    print_check "fail" "Frontend 서버 시작 실패"
    echo "로그 확인: $PROJECT_ROOT/logs/frontend.log"
    cleanup
    exit 1
fi

print_header "✅ 서버가 시작되었습니다!"

echo "브라우저에서 다음 주소로 접속하세요:"
echo "  http://localhost:3000"
echo ""
echo "Backend API 문서:"
echo "  http://localhost:8010/docs"
echo ""
echo "로그 파일:"
echo "  Backend:  $PROJECT_ROOT/logs/backend.log"
echo "  Frontend: $PROJECT_ROOT/logs/frontend.log"
echo ""
echo "서버를 중지하려면 Ctrl+C를 누르세요."
echo "================================================================"
echo ""

# 브라우저 자동 열기 (Mac/Linux에 따라 다름)
sleep 3
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac
    open http://localhost:3000 2>/dev/null || true
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open http://localhost:3000 2>/dev/null || true
fi

# 대기 (Ctrl+C 입력 대기)
wait
