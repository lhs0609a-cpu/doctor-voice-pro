'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Pill } from '@/components/app-shell/ui-kit'
import { Logo } from '@/components/app-shell/logo'
import { Check, Sparkles, Zap, Building2, Loader2, Clock, TrendingUp, PiggyBank, FileText } from 'lucide-react'
import { subscriptionAPI, type Plan, type Subscription } from '@/lib/api'
import { toast } from 'sonner'

const planIcons: Record<string, React.ReactNode> = {
  free: <Zap className="h-4 w-4" />,
  starter: <Sparkles className="h-4 w-4" />,
  pro: <Sparkles className="h-4 w-4" />,
  business: <Building2 className="h-4 w-4" />,
}

const roiStats = [
  { icon: <Clock className="h-4 w-4" />, value: '20+', label: '시간/월 절약', hint: '글 작성 시간' },
  { icon: <PiggyBank className="h-4 w-4" />, value: '90%', label: '비용 절감', hint: '대행사 대비' },
  { icon: <FileText className="h-4 w-4" />, value: '10x', label: '콘텐츠 생산', hint: '생산량 증가' },
  { icon: <TrendingUp className="h-4 w-4" />, value: '상위', label: '노출 최적화', hint: 'SEO 자동 분석' },
]

const faqs = [
  {
    q: '언제든지 플랜을 변경할 수 있나요?',
    a: '네, 언제든지 업그레이드하거나 다운그레이드할 수 있습니다. 업그레이드 시 즉시 적용되며, 다운그레이드는 다음 결제일부터 적용됩니다.',
  },
  {
    q: '환불 정책은 어떻게 되나요?',
    a: '결제 후 7일 이내 미사용 시 전액 환불이 가능합니다. 사용량이 있는 경우 남은 기간에 대해 일할 계산하여 환불해 드립니다.',
  },
  {
    q: '한도를 초과하면 어떻게 되나요?',
    a: '한도 초과 시 추가 크레딧을 구매하거나 상위 플랜으로 업그레이드할 수 있습니다. 크레딧은 만료되지 않으며 언제든지 사용 가능합니다.',
  },
]

export default function PricingPage() {
  const router = useRouter()
  const [plans, setPlans] = useState<Plan[]>([])
  const [currentSubscription, setCurrentSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [subscribing, setSubscribing] = useState<string | null>(null)
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    setIsLoggedIn(!!token)
    loadData(!!token)
  }, [])

  const loadData = async (loggedIn: boolean) => {
    try {
      const plansData = await subscriptionAPI.getPlans()
      setPlans(plansData)

      if (loggedIn) {
        const subscription = await subscriptionAPI.getCurrentSubscription()
        setCurrentSubscription(subscription)
      }
    } catch {
      toast.error('요금제 정보를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  const handleSubscribe = async (planId: string) => {
    if (!isLoggedIn) {
      router.push('/login?redirect=/pricing')
      return
    }

    const plan = plans.find(p => p.id === planId)
    if (!plan) return

    // 무료 플랜은 바로 구독
    if (plan.price_monthly === 0) {
      setSubscribing(planId)
      try {
        await subscriptionAPI.subscribe(planId)
        toast.success('무료 플랜이 활성화되었습니다!')
        router.push('/dashboard')
      } catch (error: any) {
        toast.error(error.response?.data?.detail || '구독에 실패했습니다')
      } finally {
        setSubscribing(null)
      }
      return
    }

    // 유료 플랜은 결제 페이지로 이동
    router.push(`/payment/checkout?plan=${planId}`)
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ko-KR').format(price)
  }

  const formatLimit = (limit: number) => {
    if (limit === -1) return '무제한'
    return `${limit}회`
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl space-y-12 px-4 py-10">
        {/* Header */}
        <div className="flex flex-col items-center gap-6 text-center">
          <Logo href="/" />
          <div>
            <div className="eyebrow mb-2">요금제</div>
            <h1 className="text-2xl font-semibold tracking-tight">요금제 선택</h1>
            <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">
              의료 마케팅에 최적화된 AI 블로그 작성 도구를 시작하세요.
              모든 플랜에서 7일 무료 체험을 제공합니다.
            </p>
          </div>
        </div>

        {/* ROI 시각화 섹션 */}
        <div className="surface mx-auto max-w-4xl p-6 sm:p-8">
          <h2 className="section-title mb-6 text-center">닥터보이스로 얼마나 절약할 수 있을까요?</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {roiStats.map((stat) => (
              <div key={stat.label} className="rounded-lg border bg-muted/40 p-4 text-center">
                <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-primary">
                  {stat.icon}
                </div>
                <div className="kpi">{stat.value}</div>
                <div className="mt-1 text-sm text-foreground">{stat.label}</div>
                <div className="text-xs text-muted-foreground">{stat.hint}</div>
              </div>
            ))}
          </div>

          {/* 비용 비교 */}
          <div className="mt-6 border-t pt-6">
            <div className="flex flex-col items-center justify-center gap-2 text-sm sm:flex-row sm:gap-4">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">마케팅 대행사</span>
                <span className="tabular-nums text-muted-foreground line-through">월 100~300만원</span>
              </div>
              <span className="hidden text-muted-foreground sm:inline">→</span>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">닥터보이스</span>
                <span className="font-semibold tabular-nums text-success">월 9,900원부터</span>
              </div>
            </div>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const isCurrentPlan = currentSubscription?.plan_id === plan.id
            const isPro = plan.id === 'pro'

            const features: string[] = [
              `월 글 생성 ${formatLimit(plan.posts_per_month)}`,
              `상위노출 분석 ${formatLimit(plan.analysis_per_month)}`,
              `키워드 연구 ${formatLimit(plan.keywords_per_month)}`,
            ]
            if (plan.has_advanced_analytics) features.push('고급 분석 기능')
            if (plan.has_api_access) features.push('API 액세스')
            if (plan.has_priority_support) features.push('우선 지원')
            if (plan.has_team_features) features.push('팀 협업 기능')

            return (
              <Card
                key={plan.id}
                className={`relative flex flex-col ${isPro ? 'border-primary ring-1 ring-primary' : ''}`}
              >
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Pill tone="accent">추천</Pill>
                  </div>
                )}

                <CardHeader>
                  <div className="mb-2 flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-primary">
                      {planIcons[plan.id]}
                    </div>
                    <CardTitle>{plan.name}</CardTitle>
                  </div>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>

                <CardContent className="flex-1 space-y-4">
                  <div>
                    <div className="flex items-baseline gap-1">
                      <span className="kpi">
                        {plan.price_monthly === 0 ? '무료' : `₩${formatPrice(plan.price_monthly)}`}
                      </span>
                      {plan.price_monthly > 0 && (
                        <span className="text-sm text-muted-foreground">/월</span>
                      )}
                    </div>
                    {plan.price_yearly > 0 && (
                      <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                        연간 결제 시 ₩{formatPrice(Math.round(plan.price_yearly / 12))}/월
                      </p>
                    )}
                  </div>

                  <ul className="space-y-2.5 text-sm">
                    {features.map((feature) => (
                      <li key={feature} className="flex items-center gap-2">
                        <Check className="h-4 w-4 shrink-0 text-success" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>

                <CardFooter>
                  <Button
                    className="w-full"
                    variant={isPro ? 'default' : 'outline'}
                    disabled={isCurrentPlan || subscribing === plan.id}
                    onClick={() => handleSubscribe(plan.id)}
                  >
                    {subscribing === plan.id ? (
                      <>
                        <Loader2 className="animate-spin" />
                        처리 중...
                      </>
                    ) : isCurrentPlan ? (
                      '현재 플랜'
                    ) : plan.price_monthly === 0 ? (
                      '무료로 시작'
                    ) : (
                      '시작하기'
                    )}
                  </Button>
                </CardFooter>
              </Card>
            )
          })}
        </div>

        {/* FAQ */}
        <div className="mx-auto max-w-2xl">
          <h2 className="section-title mb-4 text-center">자주 묻는 질문</h2>
          <div className="space-y-3">
            {faqs.map((faq) => (
              <div key={faq.q} className="surface p-5">
                <h3 className="text-sm font-semibold">{faq.q}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
