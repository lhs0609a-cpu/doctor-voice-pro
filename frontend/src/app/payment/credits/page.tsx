'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Script from 'next/script'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
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
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

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
            onClick={() => router.push('/dashboard/subscription')}
            className="mb-6"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            구독 관리로 돌아가기
          </Button>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Credit Selection */}
            <Card>
              <CardHeader>
                <CardTitle>크레딧 구매</CardTitle>
                <CardDescription>
                  필요한 만큼 크레딧을 구매하세요. 크레딧은 만료되지 않습니다.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Current Credits */}
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground mb-2">현재 보유 크레딧</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xl font-bold">{credits?.post_credits || 0}</p>
                      <p className="text-sm text-muted-foreground">글 생성</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold">{credits?.analysis_credits || 0}</p>
                      <p className="text-sm text-muted-foreground">분석</p>
                    </div>
                  </div>
                </div>

                {/* Credit Type */}
                <div>
                  <Label className="mb-3 block">크레딧 종류</Label>
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
                        className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer"
                      >
                        <FileText className="h-6 w-6 mb-2" />
                        <span>글 생성</span>
                      </Label>
                    </div>
                    <div>
                      <RadioGroupItem value="analysis" id="analysis" className="peer sr-only" />
                      <Label
                        htmlFor="analysis"
                        className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary cursor-pointer"
                      >
                        <Search className="h-6 w-6 mb-2" />
                        <span>분석</span>
                      </Label>
                    </div>
                  </RadioGroup>
                </div>

                {/* Package Selection */}
                <div>
                  <Label className="mb-3 block">수량 선택</Label>
                  <div className="space-y-2">
                    {CREDIT_PACKAGES[creditType].map((pkg, idx) => (
                      <div
                        key={idx}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          selectedPackage === idx && !customAmount
                            ? 'border-primary bg-primary/5'
                            : 'hover:border-muted-foreground'
                        }`}
                        onClick={() => {
                          setSelectedPackage(idx)
                          setCustomAmount('')
                        }}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="font-medium">{pkg.amount}개</span>
                            {pkg.discount > 0 && (
                              <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">
                                {pkg.discount}% 할인
                              </span>
                            )}
                          </div>
                          <span className="font-bold">₩{formatPrice(pkg.price)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Custom Amount */}
                <div>
                  <Label htmlFor="custom">직접 입력</Label>
                  <div className="flex gap-2 mt-2">
                    <Input
                      id="custom"
                      type="number"
                      placeholder="수량 입력"
                      value={customAmount}
                      onChange={(e) => setCustomAmount(e.target.value)}
                      min={1}
                    />
                    <span className="flex items-center text-muted-foreground">개</span>
                  </div>
                  {customAmount && (
                    <p className="text-sm text-muted-foreground mt-1">
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
                  <CreditCard className="h-5 w-5" />
                  결제
                </CardTitle>
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

                <div className="p-4 bg-muted rounded-lg">
                  <div className="flex justify-between items-center">
                    <span>
                      {creditType === 'post' ? '글 생성' : '분석'} 크레딧 {getCurrentAmount()}개
                    </span>
                    <span className="text-xl font-bold">₩{formatPrice(getCurrentPrice())}</span>
                  </div>
                </div>

                <Button
                  className="w-full"
                  size="lg"
                  disabled={!tossLoaded || processing || getCurrentPrice() === 0}
                  onClick={handlePayment}
                >
                  {processing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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
      </div>
    </>
  )
}
