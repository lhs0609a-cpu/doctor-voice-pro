'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Sparkles,
  Check,
  Crown,
  Rocket,
  Gift,
  ArrowRight,
  X,
  Wand2,
  Loader2,
  ChevronRight,
  AlertTriangle,
  Shield,
} from 'lucide-react'

// API URL 설정
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
      '월 10건 글 생성',
      '월 30건 상위노출 분석',
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
    description: '대행사 & 다점포 의료기관용',
    features: [
      'Pro의 모든 기능',
      '팀 멤버 5명 + 역할 관리',
      'REST API 접근',
      '전담 매니저 + 월 1회 컨설팅',
      '경쟁 병원 분석 리포트',
      '병원별 AI 스타일 학습',
      '화이트라벨 리포트'
    ],
    badge: '대행사용'
  }
]

interface OnboardingModalProps {
  userName?: string
  onComplete: () => void
  onClose: () => void
}

// 샘플 원문 및 AI 변환 결과 (데모용)
const SAMPLE_ORIGINAL = `우리 병원에서는 최첨단 레이저 장비로 피부 치료를 합니다. 다른 병원보다 훨씬 좋은 결과를 보장합니다. 시술 후 100% 만족하실 겁니다.`

const SAMPLE_TRANSFORMED = `피부과 전문의로서 10년간 수천 건의 시술 경험을 바탕으로 말씀드립니다.

최근 도입한 프락셀 레이저는 표피 손상을 최소화하면서 진피층까지 열에너지를 전달하는 방식입니다. 개인차가 있지만, 많은 분들이 3-5회 시술 후 눈에 띄는 개선을 경험하고 계십니다.

시술 전 충분한 상담을 통해 피부 상태를 정확히 파악하고, 현실적인 기대 효과를 안내해 드립니다. 모든 시술에는 개인차가 있으며, 저희는 정직한 상담을 약속드립니다.`

const SAMPLE_LAW_CHECK = {
  violations: [
    { text: '다른 병원보다 훨씬 좋은', suggestion: '많은 분들이 만족하시는' },
    { text: '100% 만족', suggestion: '높은 만족도' },
    { text: '보장합니다', suggestion: '기대하실 수 있습니다' },
  ]
}

// 실제 API 응답 타입
interface DemoApiResponse {
  original_text: string
  transformed_text: string
  medical_law_check: {
    is_compliant: boolean
    violations: Array<{
      text: string
      suggestion: string
      category: string
    }>
  }
  violations_fixed: Array<{
    original: string
    replaced: string
    category: string
  }>
  stats: {
    persuasion_score: number
    compliance_score: number
    estimated_time_saved_minutes: number
  }
}

export default function OnboardingModal({ userName, onComplete, onClose }: OnboardingModalProps) {
  const router = useRouter()
  const [step, setStep] = useState<'welcome' | 'demo' | 'demo-result' | 'pricing'>('welcome')
  const [isTransforming, setIsTransforming] = useState(false)
  const [showResult, setShowResult] = useState(false)

  // P0 버그 수정: 실제 API 응답 저장
  const [apiResult, setApiResult] = useState<DemoApiResponse | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  const handleStartDemo = () => {
    setStep('demo')
  }

  const handleTransform = async () => {
    setIsTransforming(true)
    setApiError(null)

    try {
      // P0 버그 수정: 실제 API 호출
      const response = await fetch(`${API_URL}/api/v1/demo/transform`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: SAMPLE_ORIGINAL }),
      })

      if (response.ok) {
        const data: DemoApiResponse = await response.json()
        setApiResult(data)
      } else {
        // API 실패 시 fallback (하드코딩된 결과 사용)
        console.warn('Demo API failed, using fallback data')
        setApiResult(null)
      }
    } catch (error) {
      // 네트워크 오류 등의 경우 fallback 사용
      console.warn('Demo API error, using fallback data:', error)
      setApiResult(null)
    }

    setIsTransforming(false)
    setStep('demo-result')
    setShowResult(true)
  }

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
                    <p className="text-sm text-muted-foreground">월 10건 글 생성 무료 제공</p>
                  </div>
                </div>
              </div>

              {/* CTA Buttons */}
              <div className="space-y-3 pt-4">
                <Button
                  className="w-full h-12 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                  onClick={handleStartDemo}
                >
                  <Wand2 className="mr-2 h-5 w-5" />
                  30초 체험하기
                </Button>

                <Button
                  variant="outline"
                  className="w-full h-12"
                  onClick={handleStartFree}
                >
                  바로 시작하기
                </Button>
              </div>

              <p className="text-center text-xs text-muted-foreground">
                체험 후 무료로 시작할 수 있습니다
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Demo Step - AI 변환 체험
  if (step === 'demo') {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-2xl bg-white dark:bg-gray-900 shadow-2xl overflow-hidden">
          <CardContent className="p-0">
            {/* Header */}
            <div className="relative bg-gradient-to-br from-purple-600 via-blue-600 to-cyan-500 p-6 text-white">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 text-white/70 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>

              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-white/20 rounded-xl">
                  <Wand2 className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold">AI 변환 체험</h2>
              </div>
              <p className="text-white/90 text-sm">
                아래 샘플 원문이 어떻게 변환되는지 확인해보세요
              </p>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              {/* 원문 */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  📝 원본 글 (의료법 위반 표현 포함)
                </label>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-gray-800 text-sm leading-relaxed">
                    {SAMPLE_ORIGINAL}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {SAMPLE_LAW_CHECK.violations.map((v, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full">
                        <AlertTriangle className="h-3 w-3" />
                        {v.text}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* 변환 버튼 */}
              <div className="text-center py-2">
                <Button
                  size="lg"
                  onClick={handleTransform}
                  disabled={isTransforming}
                  className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                >
                  {isTransforming ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      AI가 변환 중...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-5 w-5" />
                      AI로 변환하기
                    </>
                  )}
                </Button>
              </div>

              {/* 안내 */}
              <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg">
                <Shield className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-blue-800">
                  AI가 의료법 위반 표현을 자동으로 감지하고, 전문적이고 설득력 있는 문장으로 변환합니다.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Demo Result Step - 변환 결과
  // P0 버그 수정: API 결과 또는 fallback 데이터 사용
  const displayResult = {
    originalText: apiResult?.original_text || SAMPLE_ORIGINAL,
    transformedText: apiResult?.transformed_text || SAMPLE_TRANSFORMED,
    violations: apiResult?.violations_fixed?.map(v => ({
      text: v.original,
      suggestion: v.replaced
    })) || SAMPLE_LAW_CHECK.violations,
    persuasionScore: apiResult?.stats?.persuasion_score || 87,
    isCompliant: apiResult?.medical_law_check?.is_compliant ?? true,
    timeSaved: apiResult?.stats?.estimated_time_saved_minutes || 5,
    isRealApi: !!apiResult  // 실제 API 결과인지 표시
  }

  if (step === 'demo-result') {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
        <Card className="w-full max-w-2xl bg-white dark:bg-gray-900 shadow-2xl my-8">
          <CardContent className="p-0">
            {/* Header */}
            <div className="relative bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-500 p-6 text-white">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 text-white/70 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>

              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-white/20 rounded-xl">
                  <Check className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold">변환 완료!</h2>
                {/* P0: 실제 API 사용 여부 표시 */}
                {displayResult.isRealApi && (
                  <Badge className="bg-white/20 text-white text-xs">
                    실제 AI 검증
                  </Badge>
                )}
              </div>
              <p className="text-white/90 text-sm">
                의료법을 준수하면서 설득력 있는 글로 변환되었습니다
              </p>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              {/* 변환 전 */}
              <div>
                <label className="text-sm font-medium text-red-600 mb-2 block flex items-center gap-1">
                  <X className="h-4 w-4" /> 변환 전 (의료법 위반 위험)
                </label>
                <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                  <p className="text-gray-600 text-sm line-through">
                    {displayResult.originalText}
                  </p>
                </div>
              </div>

              {/* 변환 후 */}
              <div>
                <label className="text-sm font-medium text-emerald-600 mb-2 block flex items-center gap-1">
                  <Check className="h-4 w-4" /> 변환 후 (의료법 준수 + 설득력 강화)
                </label>
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                  <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-line">
                    {displayResult.transformedText}
                  </p>
                </div>
              </div>

              {/* 수정된 표현 */}
              {displayResult.violations.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-amber-800 mb-2">🔧 자동 수정된 표현</p>
                  <div className="space-y-2">
                    {displayResult.violations.map((v, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="text-red-600 line-through">{v.text}</span>
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                        <span className="text-emerald-600 font-medium">{v.suggestion}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 점수 */}
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-3 bg-purple-50 rounded-lg">
                  <p className="text-2xl font-bold text-purple-600">{displayResult.persuasionScore}점</p>
                  <p className="text-xs text-gray-600">설득력 점수</p>
                </div>
                <div className="text-center p-3 bg-emerald-50 rounded-lg">
                  <p className="text-2xl font-bold text-emerald-600">
                    {displayResult.isCompliant ? '통과' : '수정됨'}
                  </p>
                  <p className="text-xs text-gray-600">의료법 검증</p>
                </div>
                <div className="text-center p-3 bg-blue-50 rounded-lg">
                  <p className="text-2xl font-bold text-blue-600">{displayResult.timeSaved}분</p>
                  <p className="text-xs text-gray-600">작성 시간</p>
                </div>
              </div>

              {/* CTA */}
              <div className="space-y-3 pt-2">
                <Button
                  className="w-full h-12 text-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
                  onClick={() => setStep('pricing')}
                >
                  이런 글을 직접 만들어보기
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleStartFree}
                >
                  무료 10건으로 시작하기
                </Button>
              </div>
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
