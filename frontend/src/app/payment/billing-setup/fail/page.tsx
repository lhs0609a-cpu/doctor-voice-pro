'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { XCircle, ArrowLeft, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/app-shell/logo'

function BillingFailContent() {
  const searchParams = useSearchParams()
  const message = searchParams.get('message')
  const code = searchParams.get('code')

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
            <CardTitle>카드 등록 실패</CardTitle>
            <CardDescription>
              {message || '카드 등록 중 오류가 발생했습니다.'}
            </CardDescription>
            {code && (
              <p className="text-xs text-muted-foreground">
                오류 코드: <code className="font-mono">{code}</code>
              </p>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-warning-soft p-4 text-left text-sm">
              <p className="mb-2 font-medium text-warning">확인해 주세요</p>
              <ul className="space-y-1 text-muted-foreground">
                <li>• 카드 정보가 정확한지 확인해 주세요.</li>
                <li>• 카드 한도가 충분한지 확인해 주세요.</li>
                <li>• 해외결제 또는 온라인결제가 차단되어 있지 않은지 확인해 주세요.</li>
              </ul>
            </div>

            <div className="space-y-2">
              <Button asChild className="w-full">
                <Link href="/payment/billing-setup">
                  <RefreshCw />
                  다시 시도하기
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full">
                <Link href="/subscription/manage">
                  <ArrowLeft />
                  구독 관리로 돌아가기
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function BillingFailPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    }>
      <BillingFailContent />
    </Suspense>
  )
}
