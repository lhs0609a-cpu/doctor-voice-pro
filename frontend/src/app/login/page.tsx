'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/store/auth'
import { Sparkles, Mail, Lock, Loader2, CheckCircle2, XCircle } from 'lucide-react'

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

  // 백엔드 연결 확인 (주기적으로 계속 체크)
  useEffect(() => {
    const checkBackend = async () => {
      // Get URL from localStorage first, then env, then default
      const storedUrl = localStorage.getItem('BACKEND_URL')
      const apiUrl = storedUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010'
      setBackendUrl(apiUrl)

      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        })

        if (response.ok) {
          if (backendStatus !== 'connected') {
            console.log('백엔드 연결 성공:', apiUrl)
          }
          setBackendStatus('connected')
        } else {
          setBackendStatus('disconnected')
        }
      } catch (error) {
        console.error('백엔드 연결 확인 중:', error)
        setBackendStatus('disconnected')
      }
    }

    // 즉시 확인
    checkBackend()

    // 5초마다 재확인 (더 자주)
    const interval = setInterval(checkBackend, 5000)
    return () => clearInterval(interval)
  }, [backendStatus])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login({ email, password })
      router.push('/dashboard')
    } catch (error) {
      // Error is handled in store
    }
  }

  const handleAdminLogin = async () => {
    setEmail('admin@doctorvoice.com')
    setPassword('admin123!@#')
    try {
      console.log('관리자 로그인 시도...')
      console.log('백엔드 URL:', process.env.NEXT_PUBLIC_API_URL)
      await login({
        email: 'admin@doctorvoice.com',
        password: 'admin123!@#'
      })
      console.log('관리자 로그인 성공!')

      // localStorage에 제대로 저장되었는지 확인
      const userStr = localStorage.getItem('user')
      const token = localStorage.getItem('access_token')
      console.log('저장된 사용자:', userStr)
      console.log('저장된 토큰:', token)

      if (userStr && token) {
        const user = JSON.parse(userStr)
        if (user.is_admin) {
          console.log('관리자 확인됨, 페이지 이동...')
          window.location.href = '/admin'
        } else {
          alert('관리자 권한이 없습니다.')
        }
      } else {
        alert('로그인 데이터 저장 실패')
      }
    } catch (error) {
      console.error('관리자 로그인 실패:', error)
      alert('로그인에 실패했습니다. 다시 시도해주세요.')
    }
  }

  // 백엔드 연결 테스트
  const testBackendConnection = async (url: string): Promise<boolean> => {
    try {
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })
      return response.ok
    } catch {
      return false
    }
  }

  // 자동 포트 감지 및 동기화 (연결될 때까지 계속 시도)
  const handleAutoSync = async () => {
    setIsSyncing(true)
    setSyncMessage('백엔드 서버 검색 중...')

    const commonPorts = [8010, 8000, 8001, 8002, 8003, 8011, 8012, 8020, 9000, 9001, 5000, 5001]
    const maxRetries = 5  // 전체 스캔을 5번 반복

    for (let retry = 0; retry < maxRetries; retry++) {
      if (retry > 0) {
        setSyncMessage(`재시도 중 (${retry + 1}/${maxRetries})... 잠시만 기다려주세요`)
        await new Promise(resolve => setTimeout(resolve, 3000))
      }

      for (const port of commonPorts) {
        const testUrl = `http://localhost:${port}`
        setSyncMessage(`포트 ${port} 확인 중... (${retry + 1}/${maxRetries})`)

        const isConnected = await testBackendConnection(testUrl)
        if (isConnected) {
          // 연결 성공! localStorage에 저장
          localStorage.setItem('BACKEND_URL', testUrl)
          setBackendUrl(testUrl)
          setBackendStatus('connected')
          setSyncMessage(`✓ 연결 성공: ${testUrl}`)
          setIsSyncing(false)

          // 5초 후 메시지 제거
          setTimeout(() => setSyncMessage(''), 5000)
          return
        }

        // 각 포트 체크 사이에 짧은 대기
        await new Promise(resolve => setTimeout(resolve, 300))
      }
    }

    // 모든 시도 실패
    setSyncMessage('❌ 백엔드 서버를 찾을 수 없습니다.\n\n해결 방법:\n1. "설치및실행.bat" 파일을 실행해주세요\n2. 수동 설정으로 백엔드 URL을 직접 입력하세요')
    setIsSyncing(false)
  }

  // 수동 URL 설정
  const handleManualSync = async () => {
    if (!customUrl.trim()) {
      alert('백엔드 URL을 입력해주세요')
      return
    }

    setIsSyncing(true)
    setSyncMessage('연결 테스트 중...')

    const isConnected = await testBackendConnection(customUrl)
    if (isConnected) {
      localStorage.setItem('BACKEND_URL', customUrl)
      setBackendUrl(customUrl)
      setBackendStatus('connected')
      setSyncMessage(`✓ 연결 성공: ${customUrl}`)
      setShowUrlInput(false)
    } else {
      setSyncMessage(`❌ 연결 실패: ${customUrl}`)
    }

    setIsSyncing(false)
    setTimeout(() => setSyncMessage(''), 3000)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <Sparkles className="h-8 w-8 text-blue-600" />
          <span className="font-bold text-2xl">닥터보이스 프로</span>
        </Link>

        {/* Backend Status */}
        <div className="mb-4 p-3 rounded-lg border bg-white shadow-sm">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">백엔드 서버</span>
            <div className="flex items-center gap-2">
              {backendStatus === 'checking' && (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                  <span className="text-gray-500">확인 중...</span>
                </>
              )}
              {backendStatus === 'connected' && (
                <>
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span className="text-green-600 font-medium">연결됨</span>
                </>
              )}
              {backendStatus === 'disconnected' && (
                <>
                  <XCircle className="h-4 w-4 text-red-500" />
                  <span className="text-red-600 font-medium">연결 안됨</span>
                </>
              )}
            </div>
          </div>
          <div className="mt-1 text-xs text-gray-500">
            {backendUrl}
          </div>

          {/* Auto Sync Buttons */}
          <div className="mt-3 flex gap-2">
            <Button
              onClick={handleAutoSync}
              disabled={isSyncing}
              size="sm"
              className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {isSyncing ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  검색 중...
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-3 w-3" />
                  자동 동기화
                </>
              )}
            </Button>
            <Button
              onClick={() => setShowUrlInput(!showUrlInput)}
              disabled={isSyncing}
              size="sm"
              variant="outline"
            >
              수동 설정
            </Button>
          </div>

          {/* Manual URL Input */}
          {showUrlInput && (
            <div className="mt-3 space-y-2">
              <Input
                type="text"
                placeholder="http://localhost:8000"
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                className="text-sm"
              />
              <Button
                onClick={handleManualSync}
                disabled={isSyncing}
                size="sm"
                className="w-full"
              >
                연결 테스트
              </Button>
            </div>
          )}

          {/* Sync Message */}
          {syncMessage && (
            <div className={`mt-2 text-xs p-2 rounded ${
              syncMessage.includes('✓')
                ? 'bg-green-50 text-green-700 border border-green-200'
                : syncMessage.includes('❌')
                ? 'bg-red-50 text-red-700 border border-red-200'
                : 'bg-blue-50 text-blue-700 border border-blue-200'
            }`}>
              {syncMessage}
            </div>
          )}
        </div>

        {/* Login Card */}
        <Card className="border-0 shadow-xl">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">로그인</CardTitle>
            <CardDescription>
              계정에 로그인하여 블로그 작성을 시작하세요
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-600 text-sm">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">이메일</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="doctor@example.com"
                    className="pl-10"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">비밀번호</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    className="pl-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    로그인 중...
                  </>
                ) : (
                  '로그인'
                )}
              </Button>
            </form>

            <div className="mt-6 text-center text-sm">
              <span className="text-muted-foreground">계정이 없으신가요? </span>
              <Link href="/register" className="text-blue-600 hover:underline font-medium">
                회원가입
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Demo Account Info */}
        <div className="mt-4 p-4 rounded-lg bg-blue-50 border border-blue-200 text-sm">
          <p className="font-medium text-blue-900 mb-2">테스트 계정</p>
          <p className="text-blue-700">
            이메일: test@example.com<br />
            비밀번호: password123
          </p>
        </div>

        {/* Admin Login Button */}
        <div className="mt-4">
          <Button
            onClick={handleAdminLogin}
            disabled={isLoading}
            className="w-full bg-purple-600 hover:bg-purple-700"
            variant="outline"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                로그인 중...
              </>
            ) : (
              '관리자로 로그인하기'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
