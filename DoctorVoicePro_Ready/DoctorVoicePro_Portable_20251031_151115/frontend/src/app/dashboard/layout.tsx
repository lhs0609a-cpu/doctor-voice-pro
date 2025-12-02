'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { DashboardNav } from '@/components/dashboard-nav'
import { ServerStatus } from '@/components/server-status'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { user, checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth().then(() => {
      if (!user) {
        router.push('/login')
      }
    })
  }, [])

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
