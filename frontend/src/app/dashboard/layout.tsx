'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardNav } from '@/components/dashboard-nav'
import { ServerStatus } from '@/components/server-status'
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <DashboardNav />
      <main className="container mx-auto px-4 py-8">{children}</main>
      <ServerStatus />
    </div>
  )
}
