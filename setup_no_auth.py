"""
로그인 없이 사용 가능하도록 설정
"""

import os
import sys
from pathlib import Path

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'


def setup_backend_no_auth():
    """백엔드 인증 우회 설정"""
    print("  백엔드 인증 우회 설정...")

    # deps.py 백업 및 수정
    deps_file = BACKEND_DIR / 'app' / 'api' / 'deps.py'
    deps_backup = BACKEND_DIR / 'app' / 'api' / 'deps.py.backup'

    # 백업 생성
    if not deps_backup.exists():
        with open(deps_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(deps_backup, 'w', encoding='utf-8') as f:
            f.write(content)

    # 인증 우회 버전 작성
    no_auth_content = '''"""
API Dependencies
공통 의존성 함수들 (로그인 불필요 버전)
"""

from typing import Optional
from uuid import UUID
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import User


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    현재 로그인한 사용자 가져오기 (로그인 불필요)

    로그인 없이도 사용 가능하도록 None을 반환합니다.
    """
    return None


async def get_current_active_user(
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    활성화된 사용자만 허용 (로그인 불필요)

    로그인 없이도 사용 가능하도록 None을 반환합니다.
    """
    return None
'''

    with open(deps_file, 'w', encoding='utf-8') as f:
        f.write(no_auth_content)

    print("    ✓ 백엔드 인증 우회 완료")


def setup_frontend_no_auth():
    """프론트엔드 로그인 체크 제거"""
    print("  프론트엔드 로그인 체크 제거...")

    # 1. 메인 페이지를 /dashboard/create로 리다이렉트
    page_file = FRONTEND_DIR / 'src' / 'app' / 'page.tsx'
    page_backup = FRONTEND_DIR / 'src' / 'app' / 'page.tsx.backup'

    if not page_backup.exists():
        with open(page_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(page_backup, 'w', encoding='utf-8') as f:
            f.write(content)

    page_content = """'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function HomePage() {
  const router = useRouter()

  useEffect(() => {
    // 바로 글작성 페이지로 리다이렉트
    router.push('/dashboard/create')
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  )
}
"""

    with open(page_file, 'w', encoding='utf-8') as f:
        f.write(page_content)

    print("    ✓ 메인 페이지 리다이렉트 설정")

    # 2. Dashboard layout에서 로그인 체크 제거
    layout_file = FRONTEND_DIR / 'src' / 'app' / 'dashboard' / 'layout.tsx'
    layout_backup = FRONTEND_DIR / 'src' / 'app' / 'dashboard' / 'layout.tsx.backup'

    if not layout_backup.exists():
        with open(layout_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(layout_backup, 'w', encoding='utf-8') as f:
            f.write(content)

    layout_content = """'use client'

import { DashboardNav } from '@/components/dashboard-nav'
import { ServerStatus } from '@/components/server-status'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // 로그인 체크 제거 - 누구나 접근 가능

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <DashboardNav />
      <main className="container mx-auto px-4 py-8">{children}</main>
      <ServerStatus />
    </div>
  )
}
"""

    with open(layout_file, 'w', encoding='utf-8') as f:
        f.write(layout_content)

    print("    ✓ Dashboard 로그인 체크 제거")


def restore_auth():
    """인증 설정 복원"""
    print("인증 설정 복원 중...")

    # 백엔드 복원
    deps_file = BACKEND_DIR / 'app' / 'api' / 'deps.py'
    deps_backup = BACKEND_DIR / 'app' / 'api' / 'deps.py.backup'

    if deps_backup.exists():
        with open(deps_backup, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(deps_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ 백엔드 복원 완료")

    # 프론트엔드 복원
    page_file = FRONTEND_DIR / 'src' / 'app' / 'page.tsx'
    page_backup = FRONTEND_DIR / 'src' / 'app' / 'page.tsx.backup'

    if page_backup.exists():
        with open(page_backup, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ 메인 페이지 복원 완료")

    layout_file = FRONTEND_DIR / 'src' / 'app' / 'dashboard' / 'layout.tsx'
    layout_backup = FRONTEND_DIR / 'src' / 'app' / 'dashboard' / 'layout.tsx.backup'

    if layout_backup.exists():
        with open(layout_backup, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(layout_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ Dashboard 복원 완료")

    print("\n인증 설정이 복원되었습니다.")


def main():
    """메인 함수"""
    print("\n로그인 없이 사용 가능하도록 설정 중...\n")

    setup_backend_no_auth()
    setup_frontend_no_auth()

    print("\n✓ 로그인 없이 사용 설정 완료!")
    print("\n이제 http://localhost:3001/ 접속 시")
    print("자동으로 /dashboard/create (글작성 페이지)로 이동합니다.\n")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        restore_auth()
    else:
        main()
