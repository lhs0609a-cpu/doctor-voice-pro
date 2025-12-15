'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
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
import {
  Loader2,
  CreditCard,
  Clock,
  TrendingUp,
  FileText,
  Search,
  Key,
  AlertCircle,
  ExternalLink,
  Plus,
  Crown
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

const statusLabels: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  active: { label: '활성', variant: 'default' },
  trialing: { label: '체험 중', variant: 'secondary' },
  cancelled: { label: '취소됨', variant: 'outline' },
  expired: { label: '만료됨', variant: 'destructive' },
  past_due: { label: '연체', variant: 'destructive' },
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

  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500'
    if (percent >= 70) return 'bg-yellow-500'
    return 'bg-primary'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  const currentPlan = subscription?.plan || plans.find(p => p.id === 'free')

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">구독 관리</h1>
          <p className="text-muted-foreground">구독 현황과 사용량을 확인하세요</p>
        </div>
        <Button onClick={() => router.push('/pricing')}>
          <Crown className="mr-2 h-4 w-4" />
          플랜 변경
        </Button>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">개요</TabsTrigger>
          <TabsTrigger value="usage">사용량</TabsTrigger>
          <TabsTrigger value="payments">결제 내역</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Current Plan */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    현재 플랜
                    {subscription && (
                      <Badge variant={statusLabels[subscription.status]?.variant || 'default'}>
                        {statusLabels[subscription.status]?.label || subscription.status}
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {subscription ? (
                      <>다음 결제일: {format(new Date(subscription.current_period_end), 'yyyy년 MM월 dd일', { locale: ko })}</>
                    ) : (
                      '구독 중인 플랜이 없습니다'
                    )}
                  </CardDescription>
                </div>
                {currentPlan && (
                  <div className="text-right">
                    <p className="text-2xl font-bold">{currentPlan.name}</p>
                    {currentPlan.price_monthly > 0 && (
                      <p className="text-muted-foreground">₩{formatPrice(currentPlan.price_monthly)}/월</p>
                    )}
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {subscription?.cancel_at_period_end && (
                <div className="flex items-center gap-2 p-3 bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 rounded-lg mb-4">
                  <AlertCircle className="h-4 w-4" />
                  <span>구독이 {format(new Date(subscription.current_period_end), 'yyyy년 MM월 dd일', { locale: ko })}에 종료됩니다</span>
                </div>
              )}

              {subscription?.trial_end && new Date(subscription.trial_end) > new Date() && (
                <div className="flex items-center gap-2 p-3 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 rounded-lg mb-4">
                  <Clock className="h-4 w-4" />
                  <span>무료 체험 기간: {format(new Date(subscription.trial_end), 'yyyy년 MM월 dd일', { locale: ko })}까지</span>
                </div>
              )}

              <div className="flex gap-2">
                {subscription && subscription.status === 'active' && !subscription.cancel_at_period_end && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" disabled={cancelling}>
                        {cancelling ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
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
                )}
              </div>
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <div className="grid md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  글 생성
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {usage?.posts_used || 0}
                  <span className="text-sm font-normal text-muted-foreground">
                    / {usage?.posts_limit === -1 ? '무제한' : usage?.posts_limit || 3}
                  </span>
                </div>
                {usage && usage.posts_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.posts_used, usage.posts_limit)}
                    className="mt-2"
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  상위노출 분석
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {usage?.analysis_used || 0}
                  <span className="text-sm font-normal text-muted-foreground">
                    / {usage?.analysis_limit === -1 ? '무제한' : usage?.analysis_limit || 10}
                  </span>
                </div>
                {usage && usage.analysis_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.analysis_used, usage.analysis_limit)}
                    className="mt-2"
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  키워드 연구
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {usage?.keywords_used || 0}
                  <span className="text-sm font-normal text-muted-foreground">
                    / {usage?.keywords_limit === -1 ? '무제한' : usage?.keywords_limit || 20}
                  </span>
                </div>
                {usage && usage.keywords_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.keywords_used, usage.keywords_limit)}
                    className="mt-2"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Credits */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" />
                보유 크레딧
              </CardTitle>
              <CardDescription>
                추가 구매한 크레딧은 만료되지 않습니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground">글 생성 크레딧</p>
                  <p className="text-2xl font-bold">{credits?.post_credits || 0}개</p>
                </div>
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground">분석 크레딧</p>
                  <p className="text-2xl font-bold">{credits?.analysis_credits || 0}개</p>
                </div>
              </div>
              <Button variant="outline" className="mt-4" onClick={() => router.push('/payment/credits')}>
                <Plus className="mr-2 h-4 w-4" />
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
              {/* Posts */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="font-medium">글 생성</span>
                  <span className="text-muted-foreground">
                    {usage?.posts_used || 0} / {usage?.posts_limit === -1 ? '무제한' : usage?.posts_limit || 3}
                  </span>
                </div>
                {usage && usage.posts_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.posts_used, usage.posts_limit)}
                    className={`h-3 ${getUsageColor(getUsagePercent(usage.posts_used, usage.posts_limit))}`}
                  />
                )}
                {(usage?.extra_posts || 0) > 0 && (
                  <p className="text-sm text-muted-foreground mt-1">
                    + 추가 사용 {usage?.extra_posts}건
                  </p>
                )}
              </div>

              {/* Analysis */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="font-medium">상위노출 분석</span>
                  <span className="text-muted-foreground">
                    {usage?.analysis_used || 0} / {usage?.analysis_limit === -1 ? '무제한' : usage?.analysis_limit || 10}
                  </span>
                </div>
                {usage && usage.analysis_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.analysis_used, usage.analysis_limit)}
                    className={`h-3 ${getUsageColor(getUsagePercent(usage.analysis_used, usage.analysis_limit))}`}
                  />
                )}
                {(usage?.extra_analysis || 0) > 0 && (
                  <p className="text-sm text-muted-foreground mt-1">
                    + 추가 사용 {usage?.extra_analysis}건
                  </p>
                )}
              </div>

              {/* Keywords */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="font-medium">키워드 연구</span>
                  <span className="text-muted-foreground">
                    {usage?.keywords_used || 0} / {usage?.keywords_limit === -1 ? '무제한' : usage?.keywords_limit || 20}
                  </span>
                </div>
                {usage && usage.keywords_limit !== -1 && (
                  <Progress
                    value={getUsagePercent(usage.keywords_used, usage.keywords_limit)}
                    className={`h-3 ${getUsageColor(getUsagePercent(usage.keywords_used, usage.keywords_limit))}`}
                  />
                )}
              </div>

              {(usage?.extra_cost || 0) > 0 && (
                <div className="pt-4 border-t">
                  <div className="flex justify-between">
                    <span className="font-medium">이번 달 추가 비용</span>
                    <span className="font-bold text-primary">₩{formatPrice(usage?.extra_cost || 0)}</span>
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
                <p className="text-center text-muted-foreground py-8">
                  결제 내역이 없습니다
                </p>
              ) : (
                <div className="space-y-4">
                  {payments.map((payment) => (
                    <div
                      key={payment.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div>
                        <p className="font-medium">{payment.description}</p>
                        <p className="text-sm text-muted-foreground">
                          {payment.paid_at
                            ? format(new Date(payment.paid_at), 'yyyy년 MM월 dd일', { locale: ko })
                            : format(new Date(payment.created_at), 'yyyy년 MM월 dd일', { locale: ko })}
                        </p>
                        {payment.payment_method_detail && (
                          <p className="text-sm text-muted-foreground">
                            {payment.payment_method_detail}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="font-bold">₩{formatPrice(payment.amount)}</p>
                        <Badge
                          variant={
                            payment.status === 'completed' ? 'default' :
                            payment.status === 'refunded' ? 'secondary' :
                            'destructive'
                          }
                        >
                          {payment.status === 'completed' ? '완료' :
                           payment.status === 'refunded' ? '환불' :
                           payment.status === 'pending' ? '대기' :
                           payment.status === 'failed' ? '실패' : payment.status}
                        </Badge>
                        {payment.receipt_url && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="mt-1"
                            onClick={() => window.open(payment.receipt_url!, '_blank')}
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            영수증
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
