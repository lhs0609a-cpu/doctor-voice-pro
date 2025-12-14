'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/store/auth'
import {
  Sparkles, Mail, Lock, Loader2, CheckCircle2, XCircle,
  Image, Clock, TrendingUp, FileText, Zap, ArrowRight,
  Bot, PenTool, BarChart3
} from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading, error } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [backendUrl, setBackendUrl] = useState('')
  const [customUrl, setCustomUrl] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [syncMessage, setSyncMessage] = useState('')

  // 백엔드 연결 확인
  useEffect(() => {
    const checkBackend = async () => {
      const storedUrl = localStorage.getItem('BACKEND_URL')
      const apiUrl = storedUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010'
      setBackendUrl(apiUrl)

      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        })

        if (response.ok) {
          setBackendStatus('connected')
        } else {
          setBackendStatus('disconnected')
        }
      } catch (error) {
        setBackendStatus('disconnected')
      }
    }

    checkBackend()
    const interval = setInterval(checkBackend, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login({ email, password })
      router.push('/dashboard')
    } catch (error) {
      // Error handled in store
    }
  }

  const handleAdminLogin = async () => {
    setEmail('admin@doctorvoice.com')
    setPassword('admin123!@#')
    try {
      await login({ email: 'admin@doctorvoice.com', password: 'admin123!@#' })
      const userStr = localStorage.getItem('user')
      const token = localStorage.getItem('access_token')
      if (userStr && token) {
        const user = JSON.parse(userStr)
        if (user.is_admin) {
          window.location.href = '/admin'
        }
      }
    } catch (error) {
      alert('로그인에 실패했습니다.')
    }
  }

  const testBackendConnection = async (url: string): Promise<boolean> => {
    try {
      const response = await fetch(`${url}/health`, { method: 'GET' })
      return response.ok
    } catch {
      return false
    }
  }

  const handleAutoSync = async () => {
    setIsSyncing(true)
    setSyncMessage('백엔드 서버 검색 중...')
    const commonPorts = [8010, 8000, 8001, 8002, 8003, 8011, 8012, 8020, 9000, 9001, 5000, 5001]

    for (const port of commonPorts) {
      const testUrl = `http://localhost:${port}`
      setSyncMessage(`포트 ${port} 확인 중...`)
      const isConnected = await testBackendConnection(testUrl)
      if (isConnected) {
        localStorage.setItem('BACKEND_URL', testUrl)
        setBackendUrl(testUrl)
        setBackendStatus('connected')
        setSyncMessage(`연결 성공: ${testUrl}`)
        setIsSyncing(false)
        setTimeout(() => setSyncMessage(''), 3000)
        return
      }
      await new Promise(resolve => setTimeout(resolve, 200))
    }

    setSyncMessage('백엔드 서버를 찾을 수 없습니다')
    setIsSyncing(false)
  }

  const handleManualSync = async () => {
    if (!customUrl.trim()) return
    setIsSyncing(true)
    const isConnected = await testBackendConnection(customUrl)
    if (isConnected) {
      localStorage.setItem('BACKEND_URL', customUrl)
      setBackendUrl(customUrl)
      setBackendStatus('connected')
      setShowUrlInput(false)
    }
    setIsSyncing(false)
  }

  const features = [
    {
      icon: <Bot className="h-6 w-6" />,
      title: "AI 글 자동 생성",
      description: "AI가 전문적인 블로그 글을 자동으로 작성합니다"
    },
    {
      icon: <Image className="h-6 w-6" />,
      title: "이미지 자동 생성",
      description: "글에 맞는 고품질 이미지를 AI가 자동으로 생성합니다"
    },
    {
      icon: <Zap className="h-6 w-6" />,
      title: "네이버 블로그 자동 발행",
      description: "원클릭으로 네이버 블로그에 자동으로 발행됩니다"
    },
    {
      icon: <BarChart3 className="h-6 w-6" />,
      title: "SEO 최적화",
      description: "검색엔진 최적화된 글로 상위 노출을 노립니다"
    }
  ]

  const stats = [
    { value: "10,000+", label: "생성된 글" },
    { value: "500+", label: "활성 사용자" },
    { value: "95%", label: "만족도" },
    { value: "24/7", label: "자동 발행" }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="flex min-h-screen">
        {/* 왼쪽: 제품 소개 영역 */}
        <div className="hidden lg:flex lg:w-3/5 flex-col justify-between p-12 text-white relative overflow-hidden">
          {/* 배경 효과 */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-purple-600/20 to-pink-600/20" />
          <div className="absolute top-0 left-0 w-96 h-96 bg-blue-500/30 rounded-full filter blur-3xl" />
          <div className="absolute bottom-0 right-0 w-96 h-96 bg-purple-500/30 rounded-full filter blur-3xl" />

          <div className="relative z-10">
            {/* 로고 */}
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <span className="font-bold text-3xl">닥터보이스 프로</span>
            </div>
            <p className="text-sm text-gray-400 mb-12">by 플라톤마케팅</p>

            {/* 메인 카피 */}
            <div className="mb-12">
              <h1 className="text-5xl font-bold leading-tight mb-6">
                AI가 작성하고<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                  자동으로 발행하는
                </span><br />
                블로그 자동화 솔루션
              </h1>
              <p className="text-xl text-gray-300 leading-relaxed">
                AI가 전문적인 블로그 글을 작성하고,<br />
                네이버 블로그에 이미지까지 자동으로 발행합니다.<br />
                <strong className="text-white">하루 10분으로 블로그 운영을 자동화하세요.</strong>
              </p>
              <p className="mt-4 text-sm text-gray-400">
                플라톤마케팅이 개발한 블로그 자동화 솔루션
              </p>
            </div>

            {/* 기능 그리드 */}
            <div className="grid grid-cols-2 gap-4 mb-12">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="p-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/10 hover:bg-white/15 transition-all"
                >
                  <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg w-fit mb-3">
                    {feature.icon}
                  </div>
                  <h3 className="font-semibold text-lg mb-1">{feature.title}</h3>
                  <p className="text-sm text-gray-400">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* 하단 통계 */}
          <div className="relative z-10">
            <div className="flex items-center gap-8 p-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10">
              {stats.map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                    {stat.value}
                  </div>
                  <div className="text-sm text-gray-400">{stat.label}</div>
                </div>
              ))}
            </div>
            <div className="mt-6 text-center">
              <p className="text-sm text-gray-500">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400 font-semibold">플라톤마케팅</span>
                에서 개발한 AI 블로그 자동화 솔루션
              </p>
            </div>
          </div>
        </div>

        {/* 오른쪽: 로그인 영역 */}
        <div className="w-full lg:w-2/5 flex flex-col justify-center p-8 lg:p-12 bg-white">
          {/* 모바일 로고 */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="flex items-center gap-2 mb-1">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <span className="font-bold text-xl">닥터보이스 프로</span>
            </div>
            <span className="text-xs text-gray-400">by 플라톤마케팅</span>
          </div>

          {/* 백엔드 상태 (축소) */}
          <div className="mb-6 p-3 rounded-lg border bg-gray-50 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">서버 상태</span>
              <div className="flex items-center gap-2">
                {backendStatus === 'connected' ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="text-green-600 font-medium">연결됨</span>
                  </>
                ) : backendStatus === 'disconnected' ? (
                  <>
                    <XCircle className="h-4 w-4 text-red-500" />
                    <span className="text-red-600 font-medium">연결 안됨</span>
                    <Button size="sm" variant="ghost" onClick={handleAutoSync} disabled={isSyncing}>
                      {isSyncing ? <Loader2 className="h-3 w-3 animate-spin" /> : '재연결'}
                    </Button>
                  </>
                ) : (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                    <span className="text-gray-500">확인 중...</span>
                  </>
                )}
              </div>
            </div>
            {syncMessage && (
              <div className="mt-2 text-xs text-gray-500">{syncMessage}</div>
            )}
          </div>

          {/* 로그인 폼 */}
          <div className="mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">로그인</h2>
            <p className="text-gray-600">
              계정에 로그인하여 AI 블로그 자동화를 시작하세요
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">이메일</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  id="email"
                  type="email"
                  placeholder="your@email.com"
                  className="pl-10 h-12"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">비밀번호</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-10 h-12"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-12 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  로그인 중...
                </>
              ) : (
                <>
                  로그인
                  <ArrowRight className="ml-2 h-5 w-5" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-gray-500">계정이 없으신가요? </span>
            <Link href="/register" className="text-blue-600 hover:underline font-semibold">
              무료로 시작하기
            </Link>
          </div>

          {/* 구분선 */}
          <div className="my-8 flex items-center gap-4">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-sm text-gray-400">또는</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          {/* 관리자 버튼 */}
          <div className="space-y-3">
            <Button
              onClick={handleAdminLogin}
              variant="ghost"
              className="w-full h-11 text-gray-500 hover:text-purple-600"
              disabled={isLoading}
            >
              관리자 로그인
            </Button>
          </div>

          {/* 하단 정보 */}
          <div className="mt-8 pt-6 border-t border-gray-100">
            <p className="text-center text-xs text-gray-400 mb-3">
              로그인하면 서비스 이용약관 및 개인정보처리방침에 동의하게 됩니다.
            </p>
            <p className="text-center text-xs text-gray-500 mb-2">
              닥터보이스 프로는 <span className="font-semibold text-purple-600">플라톤마케팅</span>에서 개발했습니다.
            </p>
            <p className="text-center text-xs text-gray-400">
              &copy; 2024 플라톤마케팅. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
