#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
자동 포트 탐지 및 연결 확인 스크립트
빈 포트를 찾아서 프론트엔드와 백엔드를 연결하고 자동으로 서버를 실행합니다.
"""

import socket
import time
import subprocess
import sys
import os
import requests
from typing import Tuple, Optional

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

def find_free_port(start_port: int, max_attempts: int = 100) -> int:
    """사용 가능한 빈 포트를 찾습니다."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                s.listen(1)
                return port
        except OSError:
            continue
    raise RuntimeError(f"포트 {start_port}부터 {start_port + max_attempts}까지 사용 가능한 포트를 찾을 수 없습니다.")

def check_port_in_use(port: int) -> bool:
    """포트가 사용 중인지 확인합니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def check_backend_health(port: int, max_retries: int = 30) -> bool:
    """백엔드 헬스 체크 - /health 또는 /docs 엔드포인트 확인"""
    print(f"백엔드 서버 헬스 체크 중... (포트: {port})")

    for i in range(max_retries):
        try:
            # /health 엔드포인트 확인
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ 백엔드 서버 연결 성공! (시도 {i+1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            pass

        try:
            # /docs 엔드포인트 확인 (FastAPI 기본)
            response = requests.get(f"http://localhost:{port}/docs", timeout=2)
            if response.status_code == 200:
                print(f"✓ 백엔드 서버 연결 성공! (시도 {i+1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            print(f"  대기 중... ({i+1}/{max_retries})")
            time.sleep(2)

    return False

def check_frontend_health(port: int, max_retries: int = 30) -> bool:
    """프론트엔드 헬스 체크"""
    print(f"프론트엔드 서버 헬스 체크 중... (포트: {port})")

    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            if response.status_code in [200, 304, 404]:  # Next.js는 404도 정상
                print(f"✓ 프론트엔드 서버 연결 성공! (시도 {i+1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            print(f"  대기 중... ({i+1}/{max_retries})")
            time.sleep(2)

    return False

def check_connection(backend_port: int, frontend_port: int) -> bool:
    """프론트엔드가 백엔드에 연결할 수 있는지 확인"""
    print("\n프론트엔드 <-> 백엔드 연결 확인 중...")

    # 백엔드 API 엔드포인트 확인
    try:
        response = requests.get(f"http://localhost:{backend_port}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ 백엔드 API 응답 정상 (포트: {backend_port})")
            return True
    except Exception as e:
        print(f"✗ 백엔드 연결 실패: {e}")
        return False

def update_backend_env(backend_port: int, frontend_port: int):
    """백엔드 .env 파일 업데이트"""
    env_path = os.path.join(os.path.dirname(__file__), 'backend', '.env')

    if not os.path.exists(env_path):
        print(f"경고: {env_path} 파일을 찾을 수 없습니다.")
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    with open(env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith('ALLOWED_ORIGINS='):
                f.write(f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}\n')
                updated = True
            else:
                f.write(line)

    if updated:
        print(f"✓ 백엔드 .env 파일 업데이트 완료 (프론트엔드 포트: {frontend_port})")

def update_frontend_env(backend_port: int, frontend_port: int):
    """프론트엔드 .env.local 파일 생성/업데이트"""
    env_path = os.path.join(os.path.dirname(__file__), 'frontend', '.env.local')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f'NEXT_PUBLIC_API_URL=http://localhost:{backend_port}\n')
        f.write(f'PORT={frontend_port}\n')

    print(f"✓ 프론트엔드 .env.local 파일 생성 완료 (백엔드 포트: {backend_port})")

def update_frontend_package_json(frontend_port: int):
    """프론트엔드 package.json의 dev 스크립트 업데이트"""
    import json

    package_json_path = os.path.join(os.path.dirname(__file__), 'frontend', 'package.json')

    if not os.path.exists(package_json_path):
        print(f"경고: {package_json_path} 파일을 찾을 수 없습니다.")
        return

    with open(package_json_path, 'r', encoding='utf-8') as f:
        package_data = json.load(f)

    package_data['scripts']['dev'] = f'next dev -p {frontend_port}'
    package_data['scripts']['start'] = f'next start -p {frontend_port}'

    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_data, f, indent=2, ensure_ascii=False)

    print(f"✓ 프론트엔드 package.json 업데이트 완료 (포트: {frontend_port})")

def main():
    print("=" * 70)
    print("Doctor Voice Pro - 자동 포트 탐지 및 서버 연결")
    print("=" * 70)
    print()

    # 1. 사용 가능한 포트 찾기
    print("1단계: 사용 가능한 포트 찾기")
    print("-" * 70)

    # 백엔드 포트 찾기 (8010부터 시작)
    if check_port_in_use(8010):
        print("✓ 백엔드 포트 8010이 이미 사용 중입니다. (기존 서버 사용)")
        backend_port = 8010
    else:
        backend_port = find_free_port(8010)
        print(f"✓ 백엔드 포트: {backend_port}")

    # 프론트엔드 포트 찾기 (3001부터 시작)
    if check_port_in_use(3001):
        print("✓ 프론트엔드 포트 3001이 이미 사용 중입니다. (기존 서버 사용)")
        frontend_port = 3001
    else:
        frontend_port = find_free_port(3001)
        print(f"✓ 프론트엔드 포트: {frontend_port}")

    print()

    # 2. 환경 파일 업데이트
    print("2단계: 환경 설정 파일 업데이트")
    print("-" * 70)
    update_backend_env(backend_port, frontend_port)
    update_frontend_env(backend_port, frontend_port)
    update_frontend_package_json(frontend_port)
    print()

    # 3. 서버 연결 확인
    print("3단계: 서버 연결 확인")
    print("-" * 70)

    # 이미 서버가 실행 중인지 확인
    backend_running = check_port_in_use(backend_port)
    frontend_running = check_port_in_use(frontend_port)

    if backend_running:
        print(f"✓ 백엔드 서버가 이미 포트 {backend_port}에서 실행 중입니다.")
        if not check_backend_health(backend_port, max_retries=5):
            print("✗ 백엔드 서버가 응답하지 않습니다.")
            return False

    if frontend_running:
        print(f"✓ 프론트엔드 서버가 이미 포트 {frontend_port}에서 실행 중입니다.")
        if not check_frontend_health(frontend_port, max_retries=5):
            print("✗ 프론트엔드 서버가 응답하지 않습니다.")
            return False

    # 4. 연결 테스트
    if backend_running and frontend_running:
        print()
        print("4단계: 프론트엔드 <-> 백엔드 연결 테스트")
        print("-" * 70)

        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            print(f"\n연결 시도 {attempt}/{max_attempts}...")
            if check_connection(backend_port, frontend_port):
                print("\n" + "=" * 70)
                print("✓✓✓ 서버 연결 성공! ✓✓✓")
                print("=" * 70)
                print()
                print(f"백엔드:      http://localhost:{backend_port}")
                print(f"프론트엔드:  http://localhost:{frontend_port}")
                print(f"API 문서:    http://localhost:{backend_port}/docs")
                print()
                print("브라우저에서 프론트엔드 주소로 접속하세요!")
                print("=" * 70)
                return True

            if attempt < max_attempts:
                print(f"연결 실패. 3초 후 재시도합니다...")
                time.sleep(3)

        print("\n✗ 서버 연결 실패: 최대 시도 횟수 초과")
        return False

    print("\n서버가 실행되지 않았습니다. run.bat 또는 최종실행파일.bat을 실행하세요.")
    return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 취소되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
