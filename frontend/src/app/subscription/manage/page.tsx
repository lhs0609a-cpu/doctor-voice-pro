'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  CreditCard, Calendar, AlertTriangle, Check, X, ChevronRight,
  RefreshCw, Shield, Clock, ExternalLink
} from 'lucide-react'
import { billingAPI, paymentAPI, type SubscriptionManage } from '@/lib/api'

export default function SubscriptionManagePage() {
  const router = useRouter()
  const [subscription, setSubscription] = useState<SubscriptionManage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelLoading, setCancelLoading] = useState(false)
  const [showCancelModal, setShowCancelModal] = useState(false)
  const [cancelType, setCancelType] = useState<'period_end' | 'immediate'>('period_end')

  useEffect(() => {
    loadSubscription()
  }, [])

  const loadSubscription = async () => {
    try {
      setLoading(true)
      const data = await billingAPI.getSubscriptionManage()
      setSubscription(data)
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('활성 구독이 없습니다.')
      } else {
        setError('구독 정보를 불러오는데 실패했습니다.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!subscription) return

    try {
      setCancelLoading(true)
      const result = await billingAPI.cancelSubscription(
        undefined,
        cancelType === 'immediate'
      )

      if (result.success) {
        alert(result.message)
        setShowCancelModal(false)
        loadSubscription()
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || '해지 처리에 실패했습니다.')
    } finally {
      setCancelLoading(false)
    }
  }

  const handleReactivate = async () => {
    try {
      const result = await billingAPI.reactivateSubscription()
      if (result.success) {
        alert(result.message)
        loadSubscription()
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || '재활성화에 실패했습니다.')
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const formatPrice = (price: number) => {
    return price.toLocaleString('ko-KR')
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-sm">활성</span>
      case 'trialing':
        return <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">무료체험 중</span>
      case 'past_due':
        return <span className="px-2 py-1 bg-red-100 text-red-800 rounded-full text-sm">결제 연체</span>
      case 'cancelled':
        return <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">해지됨</span>
      default:
        return <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">{status}</span>
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-700 mb-2">{error}</h2>
          <Link href="/pricing" className="text-blue-600 hover:underline">
            요금제 보기
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">구독 관리</h1>
              <p className="text-sm text-gray-600 mt-1">결제 수단 및 구독 상태를 관리하세요</p>
            </div>
            <Link href="/dashboard" className="text-blue-600 hover:underline text-sm">
              대시보드로 돌아가기
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* 현재 구독 정보 */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900">현재 구독</h2>
              {subscription && getStatusBadge(subscription.status)}
            </div>

            {subscription && (
              <div className="space-y-4">
                <div className="flex items-center justify-between py-3 border-b">
                  <span className="text-gray-600">플랜</span>
                  <span className="font-medium">{subscription.plan_name}</span>
                </div>

                <div className="flex items-center justify-between py-3 border-b">
                  <span className="text-gray-600">월 결제 금액</span>
                  <span className="font-medium">{formatPrice(subscription.plan_price)}원</span>
                </div>

                <div className="flex items-center justify-between py-3 border-b">
                  <span className="text-gray-600">현재 기간</span>
                  <span className="font-medium">
                    {formatDate(subscription.current_period_start)} ~ {formatDate(subscription.current_period_end)}
                  </span>
                </div>

                {subscription.is_trialing && subscription.trial_end && (
                  <div className="flex items-center justify-between py-3 border-b bg-blue-50 -mx-6 px-6">
                    <span className="text-blue-700">무료체험 종료일</span>
                    <span className="font-medium text-blue-700">{formatDate(subscription.trial_end)}</span>
                  </div>
                )}

                {subscription.next_billing_date && !subscription.cancel_at_period_end && (
                  <div className="flex items-center justify-between py-3 border-b">
                    <span className="text-gray-600">다음 결제일</span>
                    <span className="font-medium text-blue-600">{formatDate(subscription.next_billing_date)}</span>
                  </div>
                )}

                {subscription.cancel_at_period_end && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mt-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-medium text-amber-800">해지 예정</p>
                        <p className="text-sm text-amber-700 mt-1">
                          {formatDate(subscription.current_period_end)}에 구독이 해지됩니다.
                          그 전까지 서비스를 계속 이용하실 수 있습니다.
                        </p>
                        <button
                          onClick={handleReactivate}
                          className="mt-3 text-sm text-amber-800 font-medium hover:underline"
                        >
                          해지 취소하고 계속 이용하기
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 결제 수단 */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900">결제 수단</h2>
              <Link
                href="/payment/billing-setup"
                className="text-blue-600 text-sm hover:underline flex items-center gap-1"
              >
                {subscription?.has_card ? '카드 변경' : '카드 등록'}
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            {subscription?.has_card ? (
              <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                <div className="w-12 h-8 bg-gradient-to-r from-blue-600 to-blue-400 rounded flex items-center justify-center">
                  <CreditCard className="w-6 h-6 text-white" />
                </div>
                <div>
                  <p className="font-medium">{subscription.card_company}</p>
                  <p className="text-sm text-gray-500">**** **** **** {subscription.card_number_last4}</p>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <CreditCard className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 mb-4">등록된 결제 수단이 없습니다</p>
                <Link
                  href="/payment/billing-setup"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  <CreditCard className="w-4 h-4" />
                  카드 등록하기
                </Link>
              </div>
            )}
          </div>

          {/* 결제 내역 */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900">결제 내역</h2>
              <Link
                href="/payment/history"
                className="text-blue-600 text-sm hover:underline flex items-center gap-1"
              >
                전체 보기
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            <p className="text-gray-500 text-center py-4">
              결제 내역은 <Link href="/payment/history" className="text-blue-600 hover:underline">결제 내역</Link> 페이지에서 확인하실 수 있습니다.
            </p>
          </div>

          {/* 플랜 변경 */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">플랜 변경</h2>
                <p className="text-sm text-gray-500 mt-1">더 높은 플랜으로 업그레이드하세요</p>
              </div>
              <Link
                href="/pricing"
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 flex items-center gap-2"
              >
                플랜 보기
                <ExternalLink className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* 구독 해지 */}
          {subscription && !subscription.cancel_at_period_end && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">구독 해지</h2>
              <p className="text-gray-600 text-sm mb-4">
                구독을 해지하시면 현재 결제 기간 종료 후 서비스 이용이 제한됩니다.
              </p>
              <button
                onClick={() => setShowCancelModal(true)}
                className="text-red-600 hover:text-red-700 text-sm font-medium"
              >
                구독 해지하기
              </button>
            </div>
          )}

          {/* 법적 안내 */}
          <div className="bg-gray-100 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-gray-600">
                <p className="font-medium text-gray-700 mb-1">자동결제 안내</p>
                <ul className="space-y-1">
                  <li>결제 7일 전 이메일로 결제 예정 안내를 발송합니다.</li>
                  <li>해지는 언제든지 이 페이지에서 가능합니다.</li>
                  <li>
                    자세한 내용은{' '}
                    <Link href="/legal" className="text-blue-600 hover:underline">
                      이용약관
                    </Link>
                    을 확인해 주세요.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 해지 모달 */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">구독 해지</h3>

            <div className="space-y-4 mb-6">
              <label className="flex items-start gap-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50">
                <input
                  type="radio"
                  name="cancelType"
                  value="period_end"
                  checked={cancelType === 'period_end'}
                  onChange={() => setCancelType('period_end')}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium">기간 종료 시 해지</p>
                  <p className="text-sm text-gray-500">
                    {subscription && formatDate(subscription.current_period_end)}까지 서비스를 이용하고 해지됩니다.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50">
                <input
                  type="radio"
                  name="cancelType"
                  value="immediate"
                  checked={cancelType === 'immediate'}
                  onChange={() => setCancelType('immediate')}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium">즉시 해지</p>
                  <p className="text-sm text-gray-500">
                    지금 바로 해지하고 미사용 기간에 대해 일할 환불받습니다.
                  </p>
                </div>
              </label>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6">
              <p className="text-sm text-amber-800">
                해지 후에도 계정과 데이터는 30일간 보관됩니다.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowCancelModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleCancel}
                disabled={cancelLoading}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {cancelLoading ? '처리 중...' : '해지하기'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
