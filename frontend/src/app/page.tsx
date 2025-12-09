'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'

export default function HomePage() {
  const router = useRouter()
  const { user } = useAuthStore()

  useEffect(() => {
    // 로그인 상태 확인
    if (user) {
      // 로그인된 경우 대시보드로 이동
      router.push('/dashboard')
    } else {
      // 로그인되지 않은 경우 로그인 페이지로 이동
      router.push('/login')
    }
  }, [router, user])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  )
}
