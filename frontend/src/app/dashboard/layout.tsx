'use client'

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
