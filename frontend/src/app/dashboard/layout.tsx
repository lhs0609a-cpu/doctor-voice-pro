'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { DashboardNav } from '@/components/dashboard-nav'
import { useAuthStore } from '@/store/auth'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { user } = useAuthStore()

  useEffect(() => {
    // 로그인 체크
    if (!user) {
      router.push('/login')
    }
  }, [user, router])

  // 로그인하지 않은 경우 로딩 표시
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex flex-col">
      <DashboardNav />
      <main className="container mx-auto px-4 py-8 flex-1">{children}</main>

      {/* 푸터 */}
      <footer className="bg-white border-t mt-auto">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <Link href="/legal" className="hover:text-blue-600">이용약관</Link>
              <span className="text-gray-300">|</span>
              <Link href="/legal" className="hover:text-blue-600">개인정보처리방침</Link>
              <span className="text-gray-300">|</span>
              <Link href="/legal" className="hover:text-blue-600">면책조항</Link>
              <span className="text-gray-300">|</span>
              <Link href="/legal" className="hover:text-blue-600">법적고지</Link>
            </div>
            <div className="text-xs text-gray-400 text-center md:text-right">
              <p>
                본 서비스에서 생성된 콘텐츠의 사용에 대한 법적 책임은 이용자에게 있습니다.
              </p>
              <p className="mt-1">
                &copy; 2024 <span className="text-purple-600 font-medium">플라톤마케팅</span>. All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
