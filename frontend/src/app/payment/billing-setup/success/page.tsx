'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { CheckCircle, CreditCard, ArrowRight } from 'lucide-react'
import { billingAPI } from '@/lib/api'

function BillingSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const authKey = searchParams.get('authKey')
  const subscriptionId = searchParams.get('subscription_id')

  const [loading, setLoading] = useState(true)
  const [success, setSuccess] = useState(false)
  const [cardInfo, setCardInfo] = useState<{ company: string; number: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (authKey) {
      setupBillingKey()
    } else {
      setError('인증 정보가 없습니다.')
      setLoading(false)
    }
  }, [authKey])

  const setupBillingKey = async () => {
    try {
      const result = await billingAPI.setupCard(authKey!, subscriptionId || undefined)

      if (result.success) {
        setSuccess(true)
        setCardInfo({
          company: result.card_company || '',
          number: result.card_number || '',
        })
      } else {
        setError(result.message || '카드 등록에 실패했습니다.')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '카드 등록에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">카드를 등록하고 있습니다...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md w-full mx-4">
          <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CreditCard className="w-8 h-8 text-red-600" />
            </div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">카드 등록 실패</h1>
            <p className="text-gray-600 mb-6">{error}</p>
            <Link
              href="/payment/billing-setup"
              className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              다시 시도하기
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">카드 등록 완료</h1>
          <p className="text-gray-600 mb-6">결제 수단이 성공적으로 등록되었습니다.</p>

          {cardInfo && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-center gap-3">
                <div className="w-10 h-6 bg-gradient-to-r from-blue-600 to-blue-400 rounded flex items-center justify-center">
                  <CreditCard className="w-4 h-4 text-white" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-gray-900">{cardInfo.company}</p>
                  <p className="text-sm text-gray-500">{cardInfo.number}</p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <Link
              href="/subscription/manage"
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              구독 관리로 이동
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/dashboard"
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              대시보드로 이동
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function BillingSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <BillingSuccessContent />
    </Suspense>
  )
}
