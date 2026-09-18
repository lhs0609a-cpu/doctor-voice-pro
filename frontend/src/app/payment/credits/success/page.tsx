'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/app-shell/logo'
import { CheckCircle, ArrowRight, Receipt, CreditCard } from 'lucide-react'
import { paymentAPI } from '@/lib/api'
import { toast } from 'sonner'

function CreditsSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [success, setSuccess] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    confirmPayment()
  }, [])

  const confirmPayment = async () => {
    const paymentKey = searchParams.get('paymentKey')
    const orderId = searchParams.get('orderId')
    const amount = searchParams.get('amount')

    if (!paymentKey || !orderId || !amount) {
      toast.error('결제 정보가 올바르지 않습니다')
      router.push('/payment/credits')
      return
    }

    try {
      const confirmResult = await paymentAPI.confirmCreditPurchase({
        payment_key: paymentKey,
        order_id: orderId,
        amount: parseInt(amount)
      })

      setResult(confirmResult)
      setSuccess(true)
      toast.success('크레딧이 충전되었습니다!')
    } catch (error: any) {
      console.error('Payment confirmation failed:', error)
      toast.error(error.response?.data?.detail || '결제 승인에 실패했습니다')
      router.push('/payment/fail?message=' + encodeURIComponent('결제 승인에 실패했습니다'))
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex justify-center">
            <Logo href="/" />
          </div>
          <Card>
            <CardContent className="flex flex-col items-center gap-4 p-5 text-center">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
              <div>
                <div className="text-[15px] font-semibold">결제 확인 중...</div>
                <p className="mt-1 text-sm text-muted-foreground">잠시만 기다려주세요</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (!success) return null

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <Logo href="/" />
        </div>
        <Card>
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-success">
              <CheckCircle className="h-6 w-6" />
            </div>
            <CardTitle>크레딧 충전 완료</CardTitle>
            <CardDescription>
              크레딧이 성공적으로 충전되었습니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {result && (
              <div className="space-y-2 rounded-lg border bg-muted/40 p-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">크레딧 종류</span>
                  <span className="font-medium">
                    {result.credit_type === 'post' ? '글 생성' : '분석'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">충전 수량</span>
                  <span className="font-medium tabular-nums">+{result.credit_added}개</span>
                </div>
                <div className="flex justify-between border-t pt-2">
                  <span className="text-muted-foreground">현재 잔액</span>
                  <span className="font-semibold tabular-nums text-primary">{result.new_balance}개</span>
                </div>
              </div>
            )}

            {result?.receipt_url && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={() => window.open(result.receipt_url, '_blank')}
              >
                <Receipt />
                영수증 보기
              </Button>
            )}

            <div className="space-y-2">
              <Button
                className="w-full"
                onClick={() => router.push('/dashboard')}
              >
                대시보드로 이동
                <ArrowRight />
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => router.push('/dashboard/subscription')}
              >
                <CreditCard />
                구독 관리
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function CreditsSuccessPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    }>
      <CreditsSuccessContent />
    </Suspense>
  )
}
