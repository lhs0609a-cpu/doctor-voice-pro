'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
import {
  Loader2,
  CreditCard,
  Clock,
  FileText,
  Search,
  Key,
  AlertCircle,
  ExternalLink,
  Plus,
  Crown,
  Check,
} from 'lucide-react'
import {
  subscriptionAPI,
  paymentAPI,
  type Subscription,
  type UsageSummary,
  type UserCredit,
  type Plan,
  type Payment
} from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const statusLabels: Record<string, { label: string; tone: Tone }> = {
  active: { label: '활성', tone: 'ok' },
  trialing: { label: '체험 중', tone: 'accent' },
  cancelled: { label: '취소됨', tone: 'muted' },
  expired: { label: '만료됨', tone: 'danger' },
  past_due: { label: '연체', tone: 'danger' },
}

const paymentStatus: Record<string, { label: string; tone: Tone }> = {
  completed: { label: '완료', tone: 'ok' },
  refunded: { label: '환불', tone: 'muted' },
  pending: { label: '대기', tone: 'warn' },
  failed: { label: '실패', tone: 'danger' },
}

export default function SubscriptionPage() {
  const router = useRouter()
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [credits, setCredits] = useState<UserCredit | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [subData, usageData, creditsData, paymentsData, plansData] = await Promise.all([
        subscriptionAPI.getCurrentSubscription(),
        subscriptionAPI.getUsage(),
        subscriptionAPI.getCredits(),
        paymentAPI.getHistory(),
        subscriptionAPI.getPlans()
      ])

      setSubscription(subData)
      setUsage(usageData)
      setCredits(creditsData)
      setPayments(paymentsData)
      setPlans(plansData)
    } catch (error) {
      console.error('Failed to load subscription data:', error)
      toast.error('데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  const handleCancelSubscription = async () => {
    setCancelling(true)
    try {
      const result = await subscriptionAPI.cancel()
      toast.success(result.message)
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '구독 취소에 실패했습니다')
    } finally {
      setCancelling(false)
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ko-KR').format(price)
  }

  const getUsagePercent = (used: number, limit: number) => {
    if (limit === -1) return 0 // 무제한
    if (limit === 0) return 100
    return Math.min((used / limit) * 100, 100)
  }

  const getUsageTone = (percent: number): Tone | undefined => {
    if (percent >= 90) return 'danger'
    if (percent >= 70) return 'warn'
    return undefined
  }

  const formatLimit = (limit: number | undefined, fallback: number) =>
    limit === -1 ? '무제한' : limit || fallback

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  const currentPlan = subscription?.plan || plans.find(p => p.id === 'free')

  const planFeatures = currentPlan
    ? [
        `글 생성 월 ${formatLimit(currentPlan.posts_per_month, 0)}건`,
        `상위노출 분석 월 ${formatLimit(currentPlan.analysis_per_month, 0)}건`,
        `키워드 연구 월 ${formatLimit(currentPlan.keywords_per_month, 0)}건`,
        ...(currentPlan.has_advanced_analytics ? ['고급 분석'] : []),
        ...(currentPlan.has_priority_support ? ['우선 지원'] : []),
        ...(currentPlan.has_api_access ? ['API 접근'] : []),
        ...(currentPlan.has_team_features ? ['팀 기능'] : []),
      ]
    : []

  const usageRows = [
    { key: 'posts', label: '글 생성', icon: FileText, used: usage?.posts_used || 0, limit: usage?.posts_limit, fallback: 3, extra: usage?.extra_posts || 0 },
    { key: 'analysis', label: '상위노출 분석', icon: Search, used: usage?.analysis_used || 0, limit: usage?.analysis_limit, fallback: 10, extra: usage?.extra_analysis || 0 },
    { key: 'keywords', label: '키워드 연구', icon: Key, used: usage?.keywords_used || 0, limit: usage?.keywords_limit, fallback: 20, extra: 0 },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="구독 관리"
        description="구독 현황과 사용량을 확인하세요."
        actions={
          <Button onClick={() => router.push('/pricing')}>
            <Crown className="h-4 w-4" />
            플랜 변경
          </Button>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">개요</TabsTrigger>
          <TabsTrigger value="usage">사용량</TabsTrigger>
          <TabsTrigger value="payments">결제 내역</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Current Plan */}
          <Card className="border-primary ring-1 ring-primary">
            <CardHeader>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="eyebrow mb-1">현재 플랜</div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    {currentPlan?.name || '-'}
                    {subscription && (
                      <Pill tone={statusLabels[subscription.status]?.tone || 'muted'}>
                        {statusLabels[subscription.status]?.label || subscription.status}
                      </Pill>
                    )}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {subscription ? (
                      <>다음 결제일: {format(new Date(subscription.current_period_end), 'yyyy년 MM월 dd일', { locale: ko })}</>
                    ) : (
                      '구독 중인 플랜이 없습니다'
                    )}
                  </CardDescription>
                </div>
                {currentPlan && (
                  <div className="sm:text-right">
                    <div className="kpi">
                      {currentPlan.price_monthly > 0 ? `₩${formatPrice(currentPlan.price_monthly)}` : '무료'}
                    </div>
                    {currentPlan.price_monthly > 0 && (
                      <p className="text-[13px] text-muted-foreground">월 결제</p>
                    )}
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {planFeatures.length > 0 && (
                <ul className="grid gap-2 text-sm sm:grid-cols-2">
                  {planFeatures.map(feature => (
                    <li key={feature} className="flex items-center gap-2">
                      <Check className="h-4 w-4 shrink-0 text-success" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              )}

              {subscription?.cancel_at_period_end && (
                <div className="flex items-center gap-2 rounded-lg bg-warning-soft p-3 text-sm text-warning">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>구독이 {format(new Date(subscription.current_period_end), 'yyyy년 MM월 dd일', { locale: ko })}에 종료됩니다</span>
                </div>
              )}

              {subscription?.trial_end && new Date(subscription.trial_end) > new Date() && (
                <div className="flex items-center gap-2 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
                  <Clock className="h-4 w-4 shrink-0 text-primary" />
                  <span>무료 체험 기간: {format(new Date(subscription.trial_end), 'yyyy년 MM월 dd일', { locale: ko })}까지</span>
                </div>
              )}

              {subscription && subscription.status === 'active' && !subscription.cancel_at_period_end && (
                <div className="flex gap-2">
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="sm" disabled={cancelling}>
                        {cancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                        구독 취소
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>구독을 취소하시겠습니까?</AlertDialogTitle>
                        <AlertDialogDescription>
                          구독을 취소하면 현재 결제 기간이 끝난 후 무료 플랜으로 전환됩니다.
                          남은 기간 동안은 계속 프리미엄 기능을 사용할 수 있습니다.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>취소</AlertDialogCancel>
                        <AlertDialogAction onClick={handleCancelSubscription}>
                          구독 취소
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <div className="grid gap-4 md:grid-cols-3">
            {usageRows.map(row => {
              const percent = getUsagePercent(row.used, row.limit ?? row.fallback)
              return (
                <StatTile
                  key={row.key}
                  label={row.label}
                  icon={<row.icon className="h-4 w-4" />}
                  tone={row.limit !== -1 ? getUsageTone(percent) : undefined}
                  value={
                    <>
                      {row.used}
                      <span className="ml-1 text-sm font-normal text-muted-foreground">
                        / {formatLimit(row.limit, row.fallback)}
                      </span>
                    </>
                  }
                  hint={
                    usage && row.limit !== -1
                      ? <Progress value={percent} className="mt-1 h-1.5" />
                      : '무제한'
                  }
                />
              )
            })}
          </div>

          {/* Credits */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-muted-foreground" />
                보유 크레딧
              </CardTitle>
              <CardDescription>
                추가 구매한 크레딧은 만료되지 않습니다
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border bg-muted/40 p-4">
                  <p className="text-[13px] font-medium text-muted-foreground">글 생성 크레딧</p>
                  <p className="kpi mt-1">{credits?.post_credits || 0}<span className="ml-0.5 text-sm font-normal text-muted-foreground">개</span></p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-4">
                  <p className="text-[13px] font-medium text-muted-foreground">분석 크레딧</p>
                  <p className="kpi mt-1">{credits?.analysis_credits || 0}<span className="ml-0.5 text-sm font-normal text-muted-foreground">개</span></p>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => router.push('/payment/credits')}>
                <Plus className="h-4 w-4" />
                크레딧 구매
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Usage Tab */}
        <TabsContent value="usage" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>이번 달 사용량</CardTitle>
              <CardDescription>
                {new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long' })} 사용 현황
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {usageRows.map(row => {
                const percent = getUsagePercent(row.used, row.limit ?? row.fallback)
                const tone = getUsageTone(percent)
                return (
                  <div key={row.key}>
                    <div className="mb-2 flex justify-between text-sm">
                      <span className="font-medium">{row.label}</span>
                      <span className={`tabular-nums ${tone === 'danger' ? 'text-danger' : tone === 'warn' ? 'text-warning' : 'text-muted-foreground'}`}>
                        {row.used} / {formatLimit(row.limit, row.fallback)}
                      </span>
                    </div>
                    {usage && row.limit !== -1 && (
                      <Progress
                        value={percent}
                        className={`h-2 ${tone === 'danger' ? '[&>div]:bg-danger' : tone === 'warn' ? '[&>div]:bg-warning' : ''}`}
                      />
                    )}
                    {row.extra > 0 && (
                      <p className="mt-1 text-sm tabular-nums text-muted-foreground">
                        + 추가 사용 {row.extra}건
                      </p>
                    )}
                  </div>
                )
              })}

              {(usage?.extra_cost || 0) > 0 && (
                <div className="border-t pt-4">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">이번 달 추가 비용</span>
                    <span className="font-semibold tabular-nums text-primary">₩{formatPrice(usage?.extra_cost || 0)}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Payments Tab */}
        <TabsContent value="payments" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>결제 내역</CardTitle>
              <CardDescription>최근 결제 및 청구 내역</CardDescription>
            </CardHeader>
            <CardContent>
              {payments.length === 0 ? (
                <EmptyState
                  icon={<CreditCard className="h-8 w-8" />}
                  title="결제 내역이 없습니다"
                  description="유료 플랜을 시작하면 결제 내역이 여기에 표시됩니다."
                  action={
                    <Button variant="outline" size="sm" onClick={() => router.push('/pricing')}>
                      플랜 살펴보기
                    </Button>
                  }
                />
              ) : (
                <div className="rounded-lg border">
                  {payments.map((payment) => {
                    const status = paymentStatus[payment.status]
                    return (
                      <ListRow key={payment.id}>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{payment.description}</p>
                          <p className="text-xs text-muted-foreground">
                            {payment.paid_at
                              ? format(new Date(payment.paid_at), 'yyyy년 MM월 dd일', { locale: ko })
                              : format(new Date(payment.created_at), 'yyyy년 MM월 dd일', { locale: ko })}
                            {payment.payment_method_detail && ` · ${payment.payment_method_detail}`}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <Pill tone={status?.tone || 'danger'}>
                            {status?.label || payment.status}
                          </Pill>
                          <p className="w-24 text-right font-semibold tabular-nums">₩{formatPrice(payment.amount)}</p>
                          {payment.receipt_url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(payment.receipt_url!, '_blank')}
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              영수증
                            </Button>
                          )}
                        </div>
                      </ListRow>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
