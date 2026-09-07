'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Script from 'next/script'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill } from '@/components/app-shell/ui-kit'
import { Loader2, ArrowLeft, CreditCard, FileText, Search, Shield } from 'lucide-react'
import { paymentAPI, subscriptionAPI, type UserCredit } from '@/lib/api'
import { toast } from 'sonner'

declare global {
  interface Window {
    TossPayments: any
  }
}

const CREDIT_PACKAGES = {
  post: [
    { amount: 10, price: 4500, discount: 10 },
    { amount: 30, price: 12000, discount: 20 },
    { amount: 100, price: 35000, discount: 30 },
  ],
  analysis: [
    { amount: 50, price: 4500, discount: 10 },
    { amount: 200, price: 16000, discount: 20 },
    { amount: 500, price: 35000, discount: 30 },
  ],
}

export default function CreditsPurchasePage() {
  const router = useRouter()
  const [creditType, setCreditType] = useState<'post' | 'analysis'>('post')
  const [selectedPackage, setSelectedPackage] = useState(0)
  const [customAmount, setCustomAmount] = useState('')
  const [credits, setCredits] = useState<UserCredit | null>(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [tossLoaded, setTossLoaded] = useState(false)
  const paymentWidgetRef = useRef<any>(null)

  useEffect(() => {
    loadCredits()
  }, [])

  const loadCredits = async () => {
    try {
      const data = await subscriptionAPI.getCredits()
      setCredits(data)
    } catch (error) {
      console.error('Failed to load credits:', error)
    } finally {
      setLoading(false)
    }
  }

  const getCurrentPrice = () => {
    if (customAmount) {
      const amount = parseInt(customAmount)
      if (isNaN(amount) || amount <= 0) return 0
      const pricePerCredit = creditType === 'post' ? 500 : 100
      return amount * pricePerCredit
    }
    return CREDIT_PACKAGES[creditType][selectedPackage].price
  }

  const getCurrentAmount = () => {
    if (customAmount) {
      const amount = parseInt(customAmount)
      return isNaN(amount) ? 0 : amount
    }
    return CREDIT_PACKAGES[creditType][selectedPackage].amount
  }

  const initTossPayments = async () => {
    if (!tossLoaded || !window.TossPayments) return

    try {
      const config = await paymentAPI.getConfig()
      const tossPayments = window.TossPayments(config.client_key)

      paymentWidgetRef.current = tossPayments.widgets({
        customerKey: `user_${Date.now()}`,
      })

      const price = getCurrentPrice()
      if (price > 0) {
        await paymentWidgetRef.current.setAmount({
          currency: 'KRW',
          value: price,
        })

        await paymentWidgetRef.current.renderPaymentMethods({
          selector: '#payment-method',
          variantKey: 'DEFAULT',
        })

        await paymentWidgetRef.current.renderAgreement({
          selector: '#agreement',
          variantKey: 'AGREEMENT',
        })
      }
    } catch (error) {
      console.error('Failed to init TossPayments:', error)
    }
  }

  useEffect(() => {
    if (tossLoaded) {
      initTossPayments()
    }
  }, [tossLoaded])

  useEffect(() => {
    if (tossLoaded && paymentWidgetRef.current) {
      const price = getCurrentPrice()
      if (price > 0) {
        paymentWidgetRef.current.setAmount({
          currency: 'KRW',
          value: price,
        })
      }
    }
  }, [creditType, selectedPackage, customAmount])

  const handlePayment = async () => {
    const amount = getCurrentAmount()
    const price = getCurrentPrice()

    if (amount <= 0 || price <= 0) {
      toast.error('올바른 수량을 입력해주세요')
      return
    }

    if (!paymentWidgetRef.current) {
      toast.error('결제 시스템이 준비되지 않았습니다')
      return
    }

    setProcessing(true)
    try {
      // 크레딧 구매 정보 생성
      const purchaseInfo = await paymentAPI.purchaseCredits(creditType, amount)

      // 토스페이먼츠 결제 요청
      await paymentWidgetRef.current.requestPayment({
        orderId: purchaseInfo.order_id,
        orderName: purchaseInfo.order_name,
        successUrl: `${window.location.origin}/payment/credits/success`,
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
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <>
      <Script
        src="https://js.tosspayments.com/v2/standard"
        onLoad={() => setTossLoaded(true)}
      />

      <div className="min-h-screen bg-background">
        <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
          <PageHeader
            title="크레딧 구매"
            description="필요한 만큼 크레딧을 구매하세요. 크레딧은 만료되지 않습니다."
            actions={
              <Button variant="ghost" size="sm" onClick={() => router.push('/dashboard/subscription')}>
                <ArrowLeft />
                구독 관리로 돌아가기
              </Button>
            }
          />

          {/* Credit Selection */}
          <Card>
            <CardHeader>
              <CardTitle>크레딧 선택</CardTitle>
              <CardDescription>크레딧 종류와 수량을 고르세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Current Credits */}
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="mb-3 text-[13px] font-medium text-muted-foreground">현재 보유 크레딧</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="kpi">{credits?.post_credits || 0}</div>
                    <div className="text-xs text-muted-foreground">글 생성</div>
                  </div>
                  <div>
                    <div className="kpi">{credits?.analysis_credits || 0}</div>
                    <div className="text-xs text-muted-foreground">분석</div>
                  </div>
                </div>
              </div>

              {/* Credit Type */}
              <div>
                <Label className="mb-2 block text-[13px] font-medium text-muted-foreground">크레딧 종류</Label>
                <RadioGroup
                  value={creditType}
                  onValueChange={(v: string) => {
                    setCreditType(v as 'post' | 'analysis')
                    setSelectedPackage(0)
                    setCustomAmount('')
                  }}
                  className="grid grid-cols-2 gap-4"
                >
                  <div>
                    <RadioGroupItem value="post" id="post" className="peer sr-only" />
                    <Label
                      htmlFor="post"
                      className="flex cursor-pointer flex-col items-center justify-between rounded-lg border bg-card p-4 text-sm transition-colors hover:bg-muted/40 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-accent peer-data-[state=checked]:text-accent-foreground [&:has([data-state=checked])]:border-primary"
                    >
                      <FileText className="mb-2 h-5 w-5" />
                      <span>글 생성</span>
                    </Label>
                  </div>
                  <div>
                    <RadioGroupItem value="analysis" id="analysis" className="peer sr-only" />
                    <Label
                      htmlFor="analysis"
                      className="flex cursor-pointer flex-col items-center justify-between rounded-lg border bg-card p-4 text-sm transition-colors hover:bg-muted/40 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-accent peer-data-[state=checked]:text-accent-foreground [&:has([data-state=checked])]:border-primary"
                    >
                      <Search className="mb-2 h-5 w-5" />
                      <span>분석</span>
                    </Label>
                  </div>
                </RadioGroup>
              </div>

              {/* Package Selection */}
              <div>
                <Label className="mb-2 block text-[13px] font-medium text-muted-foreground">수량 선택</Label>
                <div className="space-y-2">
                  {CREDIT_PACKAGES[creditType].map((pkg, idx) => (
                    <div
                      key={idx}
                      className={`cursor-pointer rounded-lg border p-4 text-sm transition-colors ${
                        selectedPackage === idx && !customAmount
                          ? 'border-primary bg-accent'
                          : 'hover:bg-muted/40'
                      }`}
                      onClick={() => {
                        setSelectedPackage(idx)
                        setCustomAmount('')
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-medium tabular-nums">{pkg.amount}개</span>
                          {pkg.discount > 0 && (
                            <Pill tone="accent">{pkg.discount}% 할인</Pill>
                          )}
                        </div>
                        <span className="font-semibold tabular-nums">₩{formatPrice(pkg.price)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Custom Amount */}
              <div>
                <Label htmlFor="custom" className="text-[13px] font-medium text-muted-foreground">직접 입력</Label>
                <div className="mt-2 flex items-center gap-2">
                  <Input
                    id="custom"
                    type="number"
                    placeholder="수량 입력"
                    value={customAmount}
                    onChange={(e) => setCustomAmount(e.target.value)}
                    min={1}
                    className="tabular-nums"
                  />
                  <span className="text-sm text-muted-foreground">개</span>
                </div>
                {customAmount && (
                  <p className="mt-1 text-sm tabular-nums text-muted-foreground">
                    예상 금액: ₩{formatPrice(getCurrentPrice())}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Payment */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-muted-foreground" />
                결제
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!tossLoaded ? (
                <div className="flex h-40 items-center justify-center">
                  <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                </div>
              ) : (
                <>
                  <div id="payment-method" className="min-h-[200px]" />
                  <div id="agreement" />
                </>
              )}

              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="tabular-nums">
                    {creditType === 'post' ? '글 생성' : '분석'} 크레딧 {getCurrentAmount()}개
                  </span>
                  <span className="text-lg font-semibold tabular-nums">₩{formatPrice(getCurrentPrice())}</span>
                </div>
              </div>

              <Button
                className="w-full tabular-nums"
                size="lg"
                disabled={!tossLoaded || processing || getCurrentPrice() === 0}
                onClick={handlePayment}
              >
                {processing ? (
                  <>
                    <Loader2 className="animate-spin" />
                    결제 처리 중...
                  </>
                ) : (
                  <>₩{formatPrice(getCurrentPrice())} 결제하기</>
                )}
              </Button>

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>안전한 결제가 보장됩니다</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
