'use client'

import { useEffect, useState, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Script from 'next/script'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Loader2, CreditCard, ArrowLeft, Shield, CheckCircle } from 'lucide-react'
import { subscriptionAPI, paymentAPI, type Plan } from '@/lib/api'
import { toast } from 'sonner'

declare global {
  interface Window {
    TossPayments: any
  }
}

function CheckoutContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const planId = searchParams.get('plan')

  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [tossLoaded, setTossLoaded] = useState(false)
  const paymentWidgetRef = useRef<any>(null)

  useEffect(() => {
    if (!planId) {
      router.push('/pricing')
      return
    }
    loadPlan()
  }, [planId])

  const loadPlan = async () => {
    try {
      const plans = await subscriptionAPI.getPlans()
      const selectedPlan = plans.find(p => p.id === planId)
      if (!selectedPlan) {
        toast.error('플랜을 찾을 수 없습니다')
        router.push('/pricing')
        return
      }
      setPlan(selectedPlan)
    } catch (error) {
      console.error('Failed to load plan:', error)
      toast.error('플랜 정보를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  const initTossPayments = async () => {
    if (!plan || !tossLoaded || !window.TossPayments) return

    try {
      const config = await paymentAPI.getConfig()
      const tossPayments = window.TossPayments(config.client_key)

      paymentWidgetRef.current = tossPayments.widgets({
        customerKey: `user_${Date.now()}`,
      })

      await paymentWidgetRef.current.setAmount({
        currency: 'KRW',
        value: plan.price_monthly,
      })

      await paymentWidgetRef.current.renderPaymentMethods({
        selector: '#payment-method',
        variantKey: 'DEFAULT',
      })

      await paymentWidgetRef.current.renderAgreement({
        selector: '#agreement',
        variantKey: 'AGREEMENT',
      })
    } catch (error) {
      console.error('Failed to init TossPayments:', error)
      toast.error('결제 시스템 초기화에 실패했습니다')
    }
  }

  useEffect(() => {
    if (tossLoaded && plan) {
      initTossPayments()
    }
  }, [tossLoaded, plan])

  const handlePayment = async () => {
    if (!plan || !paymentWidgetRef.current) return

    setProcessing(true)
    try {
      // 1. 백엔드에 결제 의도 생성
      const intent = await paymentAPI.createIntent({
        amount: plan.price_monthly,
        order_name: `${plan.name} 플랜 구독`,
        metadata: { plan_id: plan.id }
      })

      // 2. 구독 생성 (pending 상태)
      const subscription = await subscriptionAPI.subscribe(plan.id, 'card')

      // 3. 토스페이먼츠 결제 요청
      await paymentWidgetRef.current.requestPayment({
        orderId: intent.order_id,
        orderName: `${plan.name} 플랜 구독`,
        successUrl: `${window.location.origin}/payment/success?subscription_id=${subscription.id}`,
        failUrl: `${window.location.origin}/payment/fail`,
      })
    } catch (error: any) {
      console.error('Payment error:', error)
      toast.error(error.message || '결제 요청에 실패했습니다')
      setProcessing(false)
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ko-KR').format(price)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!plan) return null

  return (
    <>
      <Script
        src="https://js.tosspayments.com/v2/standard"
        onLoad={() => setTossLoaded(true)}
      />

      <div className="min-h-screen bg-muted/30 py-8">
        <div className="container mx-auto px-4 max-w-4xl">
          <Button
            variant="ghost"
            onClick={() => router.push('/pricing')}
            className="mb-6"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            요금제로 돌아가기
          </Button>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Order Summary */}
            <Card>
              <CardHeader>
                <CardTitle>주문 요약</CardTitle>
                <CardDescription>선택한 플랜을 확인하세요</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center p-4 bg-muted rounded-lg">
                  <div>
                    <h3 className="font-semibold">{plan.name} 플랜</h3>
                    <p className="text-sm text-muted-foreground">{plan.description}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold">₩{formatPrice(plan.price_monthly)}</p>
                    <p className="text-sm text-muted-foreground">/월</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-medium">포함된 기능</h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    <li className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      월 글 생성 {plan.posts_per_month === -1 ? '무제한' : `${plan.posts_per_month}회`}
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      상위노출 분석 {plan.analysis_per_month === -1 ? '무제한' : `${plan.analysis_per_month}회`}
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      키워드 연구 {plan.keywords_per_month === -1 ? '무제한' : `${plan.keywords_per_month}회`}
                    </li>
                  </ul>
                </div>

                <div className="border-t pt-4">
                  <div className="flex justify-between items-center">
                    <span className="font-medium">총 결제 금액</span>
                    <span className="text-2xl font-bold text-primary">
                      ₩{formatPrice(plan.price_monthly)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    * 7일 무료 체험 후 자동 결제됩니다
                  </p>
                </div>

                <div className="flex items-center gap-2 text-sm text-muted-foreground bg-green-50 dark:bg-green-900/20 p-3 rounded-lg">
                  <Shield className="h-4 w-4 text-green-600" />
                  <span>안전한 결제가 보장됩니다</span>
                </div>
              </CardContent>
            </Card>

            {/* Payment Method */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  결제 수단
                </CardTitle>
                <CardDescription>결제 수단을 선택하세요</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!tossLoaded ? (
                  <div className="flex items-center justify-center h-40">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : (
                  <>
                    <div id="payment-method" className="min-h-[200px]" />
                    <div id="agreement" />
                  </>
                )}

                <Button
                  className="w-full"
                  size="lg"
                  disabled={!tossLoaded || processing}
                  onClick={handlePayment}
                >
                  {processing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      결제 처리 중...
                    </>
                  ) : (
                    <>₩{formatPrice(plan.price_monthly)} 결제하기</>
                  )}
                </Button>

                <p className="text-xs text-center text-muted-foreground">
                  결제를 진행하면 이용약관 및 개인정보처리방침에 동의하는 것으로 간주됩니다.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </>
  )
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <CheckoutContent />
    </Suspense>
  )
}
