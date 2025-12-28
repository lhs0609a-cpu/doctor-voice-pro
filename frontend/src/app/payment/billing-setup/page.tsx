'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Script from 'next/script'
import { CreditCard, Shield, Check, AlertTriangle, ArrowLeft } from 'lucide-react'
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <>
      <Script
        src="https://js.tosspayments.com/v2/standard"
        onLoad={initTossPayments}
      />

      <div className="min-h-screen bg-gray-50">
        {/* 헤더 */}
        <div className="bg-white border-b">
          <div className="container mx-auto px-4 py-6">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.back()}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">결제 수단 등록</h1>
                <p className="text-sm text-gray-600 mt-1">정기결제에 사용할 카드를 등록해 주세요</p>
              </div>
            </div>
          </div>
        </div>

        <div className="container mx-auto px-4 py-8">
          <div className="max-w-2xl mx-auto">
            {error ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                  <p className="text-red-800">{error}</p>
                </div>
              </div>
            ) : (
              <>
                {/* 결제 수단 선택 */}
                <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <CreditCard className="w-5 h-5" />
                    결제 수단 선택
                  </h2>

                  <div id="billing-method" className="min-h-[200px]">
                    {!billingMethodsRendered.current && (
                      <div className="flex items-center justify-center h-[200px]">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                      </div>
                    )}
                  </div>
                </div>

                {/* 자동결제 동의 */}
                <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Shield className="w-5 h-5" />
                    자동결제 동의
                  </h2>

                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <h3 className="font-medium text-gray-900 mb-3">자동결제 안내</h3>
                    <ul className="space-y-2 text-sm text-gray-600">
                      <li className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        등록하신 결제수단으로 매월 자동 결제됩니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        결제 7일 전 이메일로 사전 안내드립니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        결제 실패 시 3일 후 재시도되며, 3회 실패 시 구독이 해지됩니다.
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                        언제든지 구독 관리 페이지에서 해지할 수 있습니다.
                      </li>
                    </ul>
                  </div>

                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={agreed}
                      onChange={(e) => setAgreed(e.target.checked)}
                      className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mt-0.5"
                    />
                    <span className="text-sm text-gray-700">
                      위 내용을 확인하였으며,{' '}
                      <Link href="/legal" className="text-blue-600 hover:underline" target="_blank">
                        이용약관
                      </Link>{' '}
                      및{' '}
                      <Link href="/legal" className="text-blue-600 hover:underline" target="_blank">
                        개인정보처리방침
                      </Link>
                      에 동의하고 자동결제에 동의합니다.
                    </span>
                  </label>
                </div>

                {/* 안내 */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                  <div className="flex items-start gap-3">
                    <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium mb-1">안전한 결제</p>
                      <p>
                        카드 정보는 토스페이먼츠에서 안전하게 암호화되어 저장됩니다.
                        당사는 카드 정보를 직접 저장하지 않습니다.
                      </p>
                    </div>
                  </div>
                </div>

                {/* 버튼 */}
                <button
                  onClick={handleSubmit}
                  disabled={processing || !agreed}
                  className="w-full py-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {processing ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      처리 중...
                    </>
                  ) : (
                    <>
                      <CreditCard className="w-5 h-5" />
                      카드 등록하기
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
