'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Logo } from '@/components/app-shell/logo'
import { useAuthStore } from '@/store/auth'
import { Mail, Lock, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading, error } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login({ email, password })
      // 로그인 후 관리자인지 확인하여 적절한 페이지로 이동
      const userStr = localStorage.getItem('user')
      if (userStr) {
        try {
          const user = JSON.parse(userStr)
          if (user.is_admin) {
            router.push('/admin')
          } else {
            router.push('/dashboard')
          }
        } catch {
          // JSON 파싱 실패 시 기본 대시보드로 이동
          router.push('/dashboard')
        }
      } else {
        router.push('/dashboard')
      }
    } catch (error) {
      // Error handled in store
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <Logo href="/" />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>로그인</CardTitle>
            <CardDescription>계정에 로그인하고 블로그 자동화를 시작하세요</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">이메일</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="your@email.com"
                    className="pl-9"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">비밀번호</Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    className="pl-9"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" />
                    로그인 중...
                  </>
                ) : (
                  '로그인'
                )}
              </Button>
            </form>

            <p className="text-center text-sm text-muted-foreground">
              계정이 없으신가요?{' '}
              <Link href="/register" className="font-medium text-primary hover:underline">
                무료로 시작하기
              </Link>
            </p>
          </CardContent>
        </Card>

        <div className="space-y-2 text-center text-xs text-muted-foreground">
          <p>
            로그인하면{' '}
            <Link href="/legal" className="text-primary hover:underline">서비스 이용약관</Link>
            {' '}및{' '}
            <Link href="/legal" className="text-primary hover:underline">개인정보처리방침</Link>
            에 동의하게 됩니다.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link href="/legal" className="hover:text-primary">이용약관</Link>
            <span aria-hidden="true">·</span>
            <Link href="/legal" className="hover:text-primary">개인정보처리방침</Link>
            <span aria-hidden="true">·</span>
            <Link href="/legal" className="hover:text-primary">면책조항</Link>
          </div>
          <p>
            닥터보이스 프로는 <span className="font-medium text-foreground">플라톤마케팅</span>에서 개발했습니다.
          </p>
          <p>&copy; 2024 플라톤마케팅. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}
