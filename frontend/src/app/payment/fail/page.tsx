'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/app-shell/logo'
import { XCircle, ArrowLeft, RefreshCw } from 'lucide-react'

function FailContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // 메시지 길이 제한 및 기본값 설정
  const rawMessage = searchParams.get('message')
  const message = rawMessage
    ? rawMessage.slice(0, 200) // 최대 200자 제한
    : '결제 처리 중 문제가 발생했습니다'
  const code = searchParams.get('code')?.slice(0, 50) // 코드도 길이 제한

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <Logo href="/" />
        </div>
        <Card>
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft text-danger">
              <XCircle className="h-6 w-6" />
            </div>
            <CardTitle>결제 실패</CardTitle>
            <CardDescription>
              {message}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {code && (
              <div className="rounded-lg border bg-muted/40 p-4">
                <p className="text-sm text-muted-foreground">
                  오류 코드: <code className="font-mono">{code}</code>
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Button
                className="w-full"
                onClick={() => {
                  // 히스토리가 없으면 pricing 페이지로 이동
                  if (window.history.length > 1) {
                    router.back()
                  } else {
                    router.push('/pricing')
                  }
                }}
              >
                <RefreshCw />
                다시 시도
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => router.push('/pricing')}
              >
                <ArrowLeft />
                요금제 페이지로
              </Button>
            </div>

            <p className="text-center text-sm text-muted-foreground">
              문제가 계속되면 고객센터로 문의해주세요
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function FailPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    }>
      <FailContent />
    </Suspense>
  )
}
