'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, Sparkles, Zap, Building2, Loader2 } from 'lucide-react'
import { subscriptionAPI, type Plan, type Subscription } from '@/lib/api'
import { toast } from 'sonner'

const planIcons: Record<string, React.ReactNode> = {
  free: <Zap className="h-6 w-6" />,
  starter: <Sparkles className="h-6 w-6" />,
  pro: <Sparkles className="h-6 w-6 text-primary" />,
  business: <Building2 className="h-6 w-6" />,
}

const planColors: Record<string, string> = {
  free: 'border-gray-200',
  starter: 'border-blue-200',
  pro: 'border-primary ring-2 ring-primary',
  business: 'border-purple-200',
}

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
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20 py-12">
      <div className="container mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4">요금제 선택</h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            의료 마케팅에 최적화된 AI 블로그 작성 도구를 시작하세요.
            모든 플랜에서 7일 무료 체험을 제공합니다.
          </p>
        </div>

        {/* Plans Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
          {plans.map((plan) => {
            const isCurrentPlan = currentSubscription?.plan_id === plan.id
            const isPro = plan.id === 'pro'

            return (
              <Card
                key={plan.id}
                className={`relative ${planColors[plan.id] || ''} ${isPro ? 'scale-105' : ''}`}
              >
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary text-primary-foreground">인기</Badge>
                  </div>
                )}

                <CardHeader>
                  <div className="flex items-center gap-2 mb-2">
                    {planIcons[plan.id]}
                    <CardTitle>{plan.name}</CardTitle>
                  </div>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>

                <CardContent>
                  <div className="mb-6">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold">
                        {plan.price_monthly === 0 ? '무료' : `₩${formatPrice(plan.price_monthly)}`}
                      </span>
                      {plan.price_monthly > 0 && (
                        <span className="text-muted-foreground">/월</span>
                      )}
                    </div>
                    {plan.price_yearly > 0 && (
                      <p className="text-sm text-muted-foreground mt-1">
                        연간 결제 시 ₩{formatPrice(Math.round(plan.price_yearly / 12))}/월
                      </p>
                    )}
                  </div>

                  <ul className="space-y-3">
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-green-500" />
                      <span>월 글 생성 {formatLimit(plan.posts_per_month)}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-green-500" />
                      <span>상위노출 분석 {formatLimit(plan.analysis_per_month)}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-green-500" />
                      <span>키워드 연구 {formatLimit(plan.keywords_per_month)}</span>
                    </li>
                    {plan.has_advanced_analytics && (
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>고급 분석 기능</span>
                      </li>
                    )}
                    {plan.has_api_access && (
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>API 액세스</span>
                      </li>
                    )}
                    {plan.has_priority_support && (
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>우선 지원</span>
                      </li>
                    )}
                    {plan.has_team_features && (
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>팀 협업 기능</span>
                      </li>
                    )}
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
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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

        {/* FAQ or Additional Info */}
        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold mb-4">자주 묻는 질문</h2>
          <div className="max-w-2xl mx-auto space-y-4 text-left">
            <div className="bg-card p-4 rounded-lg">
              <h3 className="font-semibold mb-2">언제든지 플랜을 변경할 수 있나요?</h3>
              <p className="text-muted-foreground">
                네, 언제든지 업그레이드하거나 다운그레이드할 수 있습니다.
                업그레이드 시 즉시 적용되며, 다운그레이드는 다음 결제일부터 적용됩니다.
              </p>
            </div>
            <div className="bg-card p-4 rounded-lg">
              <h3 className="font-semibold mb-2">환불 정책은 어떻게 되나요?</h3>
              <p className="text-muted-foreground">
                결제 후 7일 이내 미사용 시 전액 환불이 가능합니다.
                사용량이 있는 경우 남은 기간에 대해 일할 계산하여 환불해 드립니다.
              </p>
            </div>
            <div className="bg-card p-4 rounded-lg">
              <h3 className="font-semibold mb-2">한도를 초과하면 어떻게 되나요?</h3>
              <p className="text-muted-foreground">
                한도 초과 시 추가 크레딧을 구매하거나 상위 플랜으로 업그레이드할 수 있습니다.
                크레딧은 만료되지 않으며 언제든지 사용 가능합니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
