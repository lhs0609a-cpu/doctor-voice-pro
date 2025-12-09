#!/bin/bash
# =================================================================
# Doctor Voice Pro - 연결 관리 서버 실행 스크립트 (Linux/Mac)
# 포트 자동 탐색 및 연결 관리 기능 포함
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

print_header "🚀 Doctor Voice Pro 서버 시작 (연결 관리)"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Python 확인
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3을 찾을 수 없습니다!${NC}"
    echo "Python 3.8 이상을 설치해주세요."
    exit 1
fi

# 통합 실행 스크립트 실행
echo "🔍 포트 자동 탐색 및 서버 시작..."
echo ""

python3 start_with_connection.py

# 종료 코드 확인
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ 서버 시작 실패${NC}"
    exit $EXIT_CODE
fi

exit 0
