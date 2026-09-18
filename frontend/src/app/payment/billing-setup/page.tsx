'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Script from 'next/script'
import { CreditCard, Shield, Check, AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/app-shell/page-header'
import { billingAPI, paymentAPI } from '@/lib/api'

declare global {
  interface Window {
    TossPayments: any
  }
}

export default function BillingSetupPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const subscriptionId = searchParams.get('subscription_id')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [clientKey, setClientKey] = useState<string | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [processing, setProcessing] = useState(false)

  const paymentWidgetRef = useRef<any>(null)
  const billingMethodsRendered = useRef(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const config = await paymentAPI.getConfig()
      setClientKey(config.client_key)
    } catch (err) {
      setError('결제 설정을 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const initTossPayments = async () => {
    if (!clientKey || !window.TossPayments || billingMethodsRendered.current) return

    try {
      const tossPayments = window.TossPayments(clientKey)
      const customerKey = `user_${Date.now()}`

      const widgets = tossPayments.widgets({
        customerKey,
      })

      paymentWidgetRef.current = widgets

      // 빌링 결제 수단 위젯 렌더링
      await widgets.renderPaymentMethods({
        selector: '#billing-method',
        variantKey: 'BILLING',
      })

      billingMethodsRendered.current = true
    } catch (err) {
      console.error('토스페이먼츠 초기화 오류:', err)
      setError('결제 수단 위젯을 불러오는데 실패했습니다.')
    }
  }

  const handleSubmit = async () => {
    if (!agreed) {
      alert('자동결제 동의에 체크해 주세요.')
      return
    }

    if (!paymentWidgetRef.current) {
      alert('결제 위젯이 로드되지 않았습니다. 페이지를 새로고침해 주세요.')
      return
    }

    try {
      setProcessing(true)

      // 빌링키 발급 요청
      await paymentWidgetRef.current.requestBillingAuth({
        successUrl: `${window.location.origin}/payment/billing-setup/success${subscriptionId ? `?subscription_id=${subscriptionId}` : ''}`,
        failUrl: `${window.location.origin}/payment/billing-setup/fail`,
      })
    } catch (err: any) {
      console.error('빌링키 발급 요청 오류:', err)
      setProcessing(false)
      alert(err.message || '카드 등록에 실패했습니다.')
    }
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
        onLoad={initTossPayments}
      />

      <div className="min-h-screen bg-background">
        <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
          <PageHeader
            title="결제 수단 등록"
            description="정기결제에 사용할 카드를 등록해 주세요."
            actions={
              <Button variant="ghost" size="sm" onClick={() => router.back()}>
                <ArrowLeft />
                뒤로
              </Button>
            }
          />

          {error ? (
            <div className="flex items-center gap-3 rounded-lg bg-danger-soft p-4 text-sm text-danger">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <p>{error}</p>
            </div>
          ) : (
            <>
              {/* 결제 수단 선택 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-4 w-4 text-muted-foreground" />
                    결제 수단 선택
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div id="billing-method" className="min-h-[200px]">
                    {!billingMethodsRendered.current && (
                      <div className="flex h-[200px] items-center justify-center">
                        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* 자동결제 동의 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    자동결제 동의
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-lg border bg-muted/40 p-4">
                    <div className="mb-3 text-[13px] font-medium text-muted-foreground">자동결제 안내</div>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        등록하신 결제수단으로 매월 자동 결제됩니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        결제 7일 전 이메일로 사전 안내드립니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        결제 실패 시 3일 후 재시도되며, 3회 실패 시 구독이 해지됩니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        언제든지 구독 관리 페이지에서 해지할 수 있습니다.
                      </li>
                    </ul>
                  </div>

                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="checkbox"
                      checked={agreed}
                      onChange={(e) => setAgreed(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border accent-primary"
                    />
                    <span className="text-sm text-muted-foreground">
                      위 내용을 확인하였으며,{' '}
                      <Link href="/legal" className="text-primary hover:underline" target="_blank">
                        이용약관
                      </Link>{' '}
                      및{' '}
                      <Link href="/legal" className="text-primary hover:underline" target="_blank">
                        개인정보처리방침
                      </Link>
                      에 동의하고 자동결제에 동의합니다.
                    </span>
                  </label>
                </CardContent>
              </Card>

              {/* 안내 */}
              <div className="flex items-start gap-3 rounded-lg bg-accent p-4 text-sm text-accent-foreground">
                <Shield className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <div>
                  <p className="mb-1 font-medium">안전한 결제</p>
                  <p className="text-muted-foreground">
                    카드 정보는 토스페이먼츠에서 안전하게 암호화되어 저장됩니다.
                    당사는 카드 정보를 직접 저장하지 않습니다.
                  </p>
                </div>
              </div>

              {/* 버튼 */}
              <Button
                size="lg"
                className="w-full"
                onClick={handleSubmit}
                disabled={processing || !agreed}
              >
                {processing ? (
                  <>
                    <Loader2 className="animate-spin" />
                    처리 중...
                  </>
                ) : (
                  <>
                    <CreditCard />
                    카드 등록하기
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </div>
    </>
  )
}
