'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { XCircle, CreditCard, ArrowLeft, RefreshCw } from 'lucide-react'

function BillingFailContent() {
  const searchParams = useSearchParams()
  const message = searchParams.get('message')
  const code = searchParams.get('code')

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <XCircle className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">카드 등록 실패</h1>
          <p className="text-gray-600 mb-2">
            {message || '카드 등록 중 오류가 발생했습니다.'}
          </p>
          {code && (
            <p className="text-sm text-gray-500 mb-6">
              오류 코드: {code}
            </p>
          )}

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-left">
            <p className="text-sm text-amber-800 font-medium mb-2">확인해 주세요</p>
            <ul className="text-sm text-amber-700 space-y-1">
              <li>• 카드 정보가 정확한지 확인해 주세요.</li>
              <li>• 카드 한도가 충분한지 확인해 주세요.</li>
              <li>• 해외결제 또는 온라인결제가 차단되어 있지 않은지 확인해 주세요.</li>
            </ul>
          </div>

          <div className="space-y-3">
            <Link
              href="/payment/billing-setup"
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <RefreshCw className="w-4 h-4" />
              다시 시도하기
            </Link>
            <Link
              href="/subscription/manage"
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              <ArrowLeft className="w-4 h-4" />
              구독 관리로 돌아가기
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function BillingFailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <BillingFailContent />
    </Suspense>
  )
}
