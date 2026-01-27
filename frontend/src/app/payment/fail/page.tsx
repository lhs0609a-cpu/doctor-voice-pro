'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { XCircle, ArrowLeft, RefreshCw, Loader2 } from 'lucide-react'

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
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4">
            <XCircle className="h-10 w-10 text-red-600" />
          </div>
          <CardTitle className="text-2xl">결제 실패</CardTitle>
          <CardDescription>
            {message}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {code && (
            <div className="bg-muted p-4 rounded-lg">
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
              <RefreshCw className="mr-2 h-4 w-4" />
              다시 시도
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => router.push('/pricing')}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              요금제 페이지로
            </Button>
          </div>

          <p className="text-sm text-center text-muted-foreground">
            문제가 계속되면 고객센터로 문의해주세요
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export default function FailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <FailContent />
    </Suspense>
  )
}
