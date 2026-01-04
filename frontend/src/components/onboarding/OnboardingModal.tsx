'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Sparkles,
  Check,
  Crown,
  Rocket,
  Gift,
  ArrowRight,
  X
} from 'lucide-react'

interface PricingPlan {
  id: string
  name: string
  price: number
  period: string
  description: string
  features: string[]
  popular?: boolean
  badge?: string
}

const plans: PricingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    period: '영구 무료',
    description: '서비스를 체험해보세요',
    features: [
      '월 3건 글 생성',
      '월 10건 상위노출 분석',
      '기본 템플릿',
      '커뮤니티 지원'
    ],
    badge: '시작하기'
  },
  {
    id: 'starter',
    name: 'Starter',
    price: 29000,
    period: '월',
    description: '본격적인 블로그 운영',
    features: [
      '월 30건 글 생성',
      '월 100건 상위노출 분석',
      '모든 템플릿',
      '네이버 자동 발행',
      '이메일 지원'
    ]
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 79000,
    period: '월',
    description: '전문 마케터를 위한 플랜',
    features: [
      '무제한 글 생성',
      '무제한 상위노출 분석',
      'AI 이미지 생성',
      '고급 분석 리포트',
      '예약 발행',
      '우선 지원'
    ],
    popular: true,
    badge: '가장 인기'
  },
  {
    id: 'business',
    name: 'Business',
    price: 199000,
    period: '월',
    description: '팀과 기업을 위한 플랜',
    features: [
      'Pro의 모든 기능',
      '팀 멤버 5명',
      'API 접근',
      '전담 매니저',
      '커스텀 템플릿',
      'SLA 보장'
    ],
    badge: '기업용'
  }
]

interface OnboardingModalProps {
  userName?: string
  onComplete: () => void
  onClose: () => void
}

export default function OnboardingModal({ userName, onComplete, onClose }: OnboardingModalProps) {
  const router = useRouter()
  const [step, setStep] = useState<'welcome' | 'pricing'>('welcome')

  const handleStartFree = () => {
    localStorage.setItem('onboarding_completed', 'true')
    onComplete()
  }

  const handleSelectPlan = (planId: string) => {
    localStorage.setItem('onboarding_completed', 'true')
    if (planId === 'free') {
      onComplete()
    } else {
      router.push(`/pricing?plan=${planId}`)
      onClose()
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ko-KR').format(price)
  }

  if (step === 'welcome') {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-lg bg-white dark:bg-gray-900 shadow-2xl overflow-hidden">
          <CardContent className="p-0">
            {/* Header with gradient */}
            <div className="relative bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500 p-8 text-white">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 text-white/70 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>

              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-white/20 rounded-xl">
                  <Sparkles className="h-8 w-8" />
                </div>
              </div>

              <h1 className="text-3xl font-bold mb-2">
                {userName ? `${userName}님, 환영합니다!` : '환영합니다!'}
              </h1>
              <p className="text-white/90">
                닥터보이스 프로와 함께 블로그 자동화를 시작하세요
              </p>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              {/* Benefits */}
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="p-2 bg-blue-100 dark:bg-blue-800 rounded-lg">
                    <Rocket className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="font-medium">AI 글 자동 생성</p>
                    <p className="text-sm text-muted-foreground">전문적인 블로그 글을 AI가 작성</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                  <div className="p-2 bg-purple-100 dark:bg-purple-800 rounded-lg">
                    <Crown className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="font-medium">상위노출 분석</p>
                    <p className="text-sm text-muted-foreground">경쟁 키워드 분석으로 상위 노출</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <div className="p-2 bg-green-100 dark:bg-green-800 rounded-lg">
                    <Gift className="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p className="font-medium">무료로 시작하기</p>
                    <p className="text-sm text-muted-foreground">월 3건 글 생성 무료 제공</p>
                  </div>
                </div>
              </div>

              {/* CTA Buttons */}
              <div className="space-y-3 pt-4">
                <Button
                  className="w-full h-12 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                  onClick={() => setStep('pricing')}
                >
                  구독 플랜 보기
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>

                <Button
                  variant="outline"
                  className="w-full h-12"
                  onClick={handleStartFree}
                >
                  무료로 시작하기
                </Button>
              </div>

              <p className="text-center text-xs text-muted-foreground">
                언제든지 플랜을 변경하거나 취소할 수 있습니다
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Pricing Step
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
      <Card className="w-full max-w-5xl bg-white dark:bg-gray-900 shadow-2xl my-8">
        <CardContent className="p-0">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <div>
              <h2 className="text-2xl font-bold">구독 플랜 선택</h2>
              <p className="text-muted-foreground">나에게 맞는 플랜을 선택하세요</p>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Plans Grid */}
          <div className="p-6">
            <div className="grid md:grid-cols-4 gap-4">
              {plans.map((plan) => (
                <div
                  key={plan.id}
                  className={`relative rounded-xl border-2 p-5 transition-all hover:shadow-lg ${
                    plan.popular
                      ? 'border-purple-500 bg-purple-50/50 dark:bg-purple-900/10'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  {plan.badge && (
                    <Badge
                      className={`absolute -top-3 left-4 ${
                        plan.popular
                          ? 'bg-purple-500'
                          : 'bg-gray-500'
                      }`}
                    >
                      {plan.badge}
                    </Badge>
                  )}

                  <div className="mb-4">
                    <h3 className="text-lg font-bold">{plan.name}</h3>
                    <p className="text-sm text-muted-foreground">{plan.description}</p>
                  </div>

                  <div className="mb-4">
                    <span className="text-3xl font-bold">
                      {plan.price === 0 ? '무료' : `₩${formatPrice(plan.price)}`}
                    </span>
                    {plan.price > 0 && (
                      <span className="text-muted-foreground">/{plan.period}</span>
                    )}
                  </div>

                  <ul className="space-y-2 mb-6">
                    {plan.features.map((feature, index) => (
                      <li key={index} className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    className={`w-full ${
                      plan.popular
                        ? 'bg-purple-600 hover:bg-purple-700'
                        : ''
                    }`}
                    variant={plan.popular ? 'default' : 'outline'}
                    onClick={() => handleSelectPlan(plan.id)}
                  >
                    {plan.price === 0 ? '무료로 시작' : '선택하기'}
                  </Button>
                </div>
              ))}
            </div>

            {/* Back button */}
            <div className="mt-6 text-center">
              <Button variant="ghost" onClick={() => setStep('welcome')}>
                뒤로 가기
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
