'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { CheckCircle, CreditCard, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/app-shell/logo'
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
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
          <p className="text-sm text-muted-foreground">카드를 등록하고 있습니다...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex justify-center">
            <Logo href="/" />
          </div>
          <Card>
            <CardHeader className="items-center text-center">
              <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft text-danger">
                <CreditCard className="h-6 w-6" />
              </div>
              <CardTitle>카드 등록 실패</CardTitle>
              <CardDescription>{error}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button asChild className="w-full">
                <Link href="/payment/billing-setup">다시 시도하기</Link>
              </Button>
              <Button asChild variant="outline" className="w-full">
                <Link href="/dashboard">대시보드로 이동</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

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
            <CardTitle>카드 등록 완료</CardTitle>
            <CardDescription>결제 수단이 성공적으로 등록되었습니다.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {cardInfo && (
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center justify-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-primary">
                    <CreditCard className="h-4 w-4" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">{cardInfo.company}</p>
                    <p className="text-sm tabular-nums text-muted-foreground">{cardInfo.number}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Button asChild className="w-full">
                <Link href="/subscription/manage">
                  구독 관리로 이동
                  <ArrowRight />
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full">
                <Link href="/dashboard">대시보드로 이동</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function BillingSuccessPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    }>
      <BillingSuccessContent />
    </Suspense>
  )
}
