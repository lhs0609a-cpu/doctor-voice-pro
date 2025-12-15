'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle, Loader2, ArrowRight, Receipt } from 'lucide-react'
import { paymentAPI } from '@/lib/api'
import { toast } from 'sonner'

function SuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [success, setSuccess] = useState(false)
  const [paymentInfo, setPaymentInfo] = useState<any>(null)

  useEffect(() => {
    confirmPayment()
  }, [])

  const confirmPayment = async () => {
    const paymentKey = searchParams.get('paymentKey')
    const orderId = searchParams.get('orderId')
    const amount = searchParams.get('amount')

    if (!paymentKey || !orderId || !amount) {
      toast.error('결제 정보가 올바르지 않습니다')
      router.push('/pricing')
      return
    }

    try {
      const result = await paymentAPI.confirm({
        payment_key: paymentKey,
        order_id: orderId,
        amount: parseInt(amount)
      })

      setPaymentInfo(result)
      setSuccess(true)
      toast.success('결제가 완료되었습니다!')
    } catch (error: any) {
      console.error('Payment confirmation failed:', error)
      toast.error(error.response?.data?.detail || '결제 승인에 실패했습니다')
      router.push('/payment/fail?message=' + encodeURIComponent('결제 승인에 실패했습니다'))
    } finally {
      setLoading(false)
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ko-KR').format(price)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <div className="text-center">
                <h2 className="text-xl font-semibold">결제 확인 중...</h2>
                <p className="text-muted-foreground mt-2">잠시만 기다려주세요</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!success) {
    return null
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="h-10 w-10 text-green-600" />
          </div>
          <CardTitle className="text-2xl">결제 완료!</CardTitle>
          <CardDescription>
            구독이 성공적으로 활성화되었습니다
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {paymentInfo && (
            <div className="bg-muted p-4 rounded-lg space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">결제 금액</span>
                <span className="font-semibold">₩{formatPrice(paymentInfo.amount)}</span>
              </div>
              {paymentInfo.payment_method_detail && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">결제 수단</span>
                  <span>{paymentInfo.payment_method_detail}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">상품명</span>
                <span>{paymentInfo.description}</span>
              </div>
            </div>
          )}

          {paymentInfo?.receipt_url && (
            <Button
              variant="outline"
              className="w-full"
              onClick={() => window.open(paymentInfo.receipt_url, '_blank')}
            >
              <Receipt className="mr-2 h-4 w-4" />
              영수증 보기
            </Button>
          )}

          <div className="space-y-2">
            <Button
              className="w-full"
              onClick={() => router.push('/dashboard')}
            >
              대시보드로 이동
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => router.push('/dashboard/subscription')}
            >
              구독 관리
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function SuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <SuccessContent />
    </Suspense>
  )
}
