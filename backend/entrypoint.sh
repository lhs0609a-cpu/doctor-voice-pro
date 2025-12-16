#!/bin/bash
set -e

echo "======================================"
echo "Doctor Voice Pro - 서버 시작"
echo "======================================"

# 데이터베이스 디렉토리 권한 확인
if [ -d "/data" ]; then
    echo "✓ /data 디렉토리 존재"
    ls -la /data
else
    echo "⚠ /data 디렉토리 없음"
fi

# 데이터베이스 초기화
echo ""
echo "데이터베이스 초기화 중..."
python init_db.py

# 서버 시작
echo ""
echo "======================================"
echo "uvicorn 서버 시작..."
echo "======================================"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
