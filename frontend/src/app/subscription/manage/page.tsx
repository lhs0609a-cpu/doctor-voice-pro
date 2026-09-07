'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { CreditCard, AlertTriangle, ChevronRight, Shield, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { billingAPI, type SubscriptionManage } from '@/lib/api'

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
        return <Pill tone="ok">활성</Pill>
      case 'trialing':
        return <Pill tone="accent">무료체험 중</Pill>
      case 'past_due':
        return <Pill tone="danger">결제 연체</Pill>
      case 'cancelled':
        return <Pill tone="muted">해지됨</Pill>
      default:
        return <Pill tone="muted">{status}</Pill>
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <EmptyState
            icon={<AlertTriangle className="h-8 w-8" />}
            title={error}
            description="요금제를 선택하면 구독을 시작할 수 있습니다."
            action={
              <Button asChild>
                <Link href="/pricing">요금제 보기</Link>
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <PageHeader
          title="구독 관리"
          description="결제 수단과 구독 상태를 관리하세요"
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/dashboard">대시보드로 돌아가기</Link>
            </Button>
          }
        />

        {/* 현재 구독 정보 */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>현재 구독</CardTitle>
            {subscription && getStatusBadge(subscription.status)}
          </CardHeader>
          {subscription && (
            <CardContent className="space-y-4">
              <div className="divide-y text-sm">
                <div className="flex items-center justify-between py-3">
                  <span className="text-muted-foreground">플랜</span>
                  <span className="font-medium">{subscription.plan_name}</span>
                </div>

                <div className="flex items-center justify-between py-3">
                  <span className="text-muted-foreground">월 결제 금액</span>
                  <span className="font-medium tabular-nums">{formatPrice(subscription.plan_price)}원</span>
                </div>

                <div className="flex items-center justify-between py-3">
                  <span className="text-muted-foreground">현재 기간</span>
                  <span className="font-medium tabular-nums">
                    {formatDate(subscription.current_period_start)} ~ {formatDate(subscription.current_period_end)}
                  </span>
                </div>

                {subscription.is_trialing && subscription.trial_end && (
                  <div className="flex items-center justify-between py-3">
                    <span className="text-primary">무료체험 종료일</span>
                    <span className="font-medium tabular-nums text-primary">{formatDate(subscription.trial_end)}</span>
                  </div>
                )}

                {subscription.next_billing_date && !subscription.cancel_at_period_end && (
                  <div className="flex items-center justify-between py-3">
                    <span className="text-muted-foreground">다음 결제일</span>
                    <span className="font-medium tabular-nums text-primary">{formatDate(subscription.next_billing_date)}</span>
                  </div>
                )}
              </div>

              {subscription.cancel_at_period_end && (
                <div className="rounded-lg bg-warning-soft p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-warning">해지 예정</p>
                      <p className="text-sm text-muted-foreground">
                        {formatDate(subscription.current_period_end)}에 구독이 해지됩니다.
                        그 전까지 서비스를 계속 이용하실 수 있습니다.
                      </p>
                      <Button variant="outline" size="sm" className="mt-2" onClick={handleReactivate}>
                        해지 취소하고 계속 이용하기
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* 결제 수단 */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>결제 수단</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/payment/billing-setup">
                {subscription?.has_card ? '카드 변경' : '카드 등록'}
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {subscription?.has_card ? (
              <div className="flex items-center gap-4 rounded-lg border bg-muted/40 p-4">
                <div className="flex h-9 w-12 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <CreditCard className="h-5 w-5" />
                </div>
                <div className="text-sm">
                  <p className="font-medium">{subscription.card_company}</p>
                  <p className="tabular-nums text-muted-foreground">**** **** **** {subscription.card_number_last4}</p>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={<CreditCard className="h-8 w-8" />}
                title="등록된 결제 수단이 없습니다"
                description="카드를 등록하면 자동으로 결제됩니다."
                action={
                  <Button asChild>
                    <Link href="/payment/billing-setup">
                      <CreditCard className="h-4 w-4" />
                      카드 등록하기
                    </Link>
                  </Button>
                }
              />
            )}
          </CardContent>
        </Card>

        {/* 결제 내역 */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>결제 내역</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/payment/history">
                전체 보기
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <p className="py-2 text-center text-sm text-muted-foreground">
              결제 내역은 <Link href="/payment/history" className="text-primary hover:underline">결제 내역</Link> 페이지에서 확인하실 수 있습니다.
            </p>
          </CardContent>
        </Card>

        {/* 플랜 변경 */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <div className="space-y-1.5">
              <CardTitle>플랜 변경</CardTitle>
              <CardDescription>더 높은 플랜으로 업그레이드하세요</CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/pricing">
                플랜 보기
                <ExternalLink className="h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
        </Card>

        {/* 구독 해지 */}
        {subscription && !subscription.cancel_at_period_end && (
          <Card>
            <CardHeader>
              <CardTitle>구독 해지</CardTitle>
              <CardDescription>
                구독을 해지하시면 현재 결제 기간 종료 후 서비스 이용이 제한됩니다.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={() => setShowCancelModal(true)}>
                구독 해지하기
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 법적 안내 */}
        <div className="rounded-xl bg-muted p-4">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
            <div className="text-sm text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">자동결제 안내</p>
              <ul className="space-y-1">
                <li>결제 7일 전 이메일로 결제 예정 안내를 발송합니다.</li>
                <li>해지는 언제든지 이 페이지에서 가능합니다.</li>
                <li>
                  자세한 내용은{' '}
                  <Link href="/legal" className="text-primary hover:underline">
                    이용약관
                  </Link>
                  을 확인해 주세요.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* 해지 모달 */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="surface w-full max-w-md space-y-4 p-6" role="dialog" aria-modal="true" aria-labelledby="cancel-title">
            <h3 id="cancel-title" className="section-title">구독 해지</h3>

            <div className="space-y-3">
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/40">
                <input
                  type="radio"
                  name="cancelType"
                  value="period_end"
                  checked={cancelType === 'period_end'}
                  onChange={() => setCancelType('period_end')}
                  className="mt-1 accent-primary"
                />
                <div className="text-sm">
                  <p className="font-medium">기간 종료 시 해지</p>
                  <p className="text-muted-foreground">
                    {subscription && formatDate(subscription.current_period_end)}까지 서비스를 이용하고 해지됩니다.
                  </p>
                </div>
              </label>

              <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/40">
                <input
                  type="radio"
                  name="cancelType"
                  value="immediate"
                  checked={cancelType === 'immediate'}
                  onChange={() => setCancelType('immediate')}
                  className="mt-1 accent-primary"
                />
                <div className="text-sm">
                  <p className="font-medium">즉시 해지</p>
                  <p className="text-muted-foreground">
                    지금 바로 해지하고 미사용 기간에 대해 일할 환불받습니다.
                  </p>
                </div>
              </label>
            </div>

            <div className="rounded-lg bg-warning-soft p-3">
              <p className="text-sm text-warning">
                해지 후에도 계정과 데이터는 30일간 보관됩니다.
              </p>
            </div>

            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setShowCancelModal(false)}>
                취소
              </Button>
              <Button variant="destructive" className="flex-1" onClick={handleCancel} disabled={cancelLoading}>
                {cancelLoading ? '처리 중...' : '해지하기'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
