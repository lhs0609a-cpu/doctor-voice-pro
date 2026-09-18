'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Pill } from '@/components/app-shell/ui-kit'
import { LogoMark } from '@/components/app-shell/logo'
// P2 Fix: Textarea import 제거 (사용 안 함)
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

// P2 Fix: pricing 단계 제거로 PricingPlan 인터페이스와 plans 배열 삭제
// 요금제 정보는 /pricing 페이지에서 확인 가능

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

/** 모달 공통 껍데기: 어두운 배경 + 카드 */
function ModalShell({ children, wide = false, scroll = false }: { children: React.ReactNode; wide?: boolean; scroll?: boolean }) {
  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm ${scroll ? 'overflow-y-auto' : ''}`}>
      <Card className={`w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} ${scroll ? 'my-8' : ''} overflow-hidden shadow-pop`}>
        <CardContent className="p-0">{children}</CardContent>
      </Card>
    </div>
  )
}

/** 모달 머리: 아이콘 + 제목 + 설명 + 닫기 */
function ModalHead({ icon, title, description, onClose, badge }: { icon: React.ReactNode; title: string; description: string; onClose: () => void; badge?: React.ReactNode }) {
  return (
    <div className="relative border-b px-6 py-5">
      <button
        type="button"
        onClick={onClose}
        aria-label="닫기"
        className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">{icon}</div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold leading-6">{title}</h2>
            {badge}
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
    </div>
  )
}

// P2 Fix: 4단계 → 3단계로 간소화 (pricing 단계 제거 - 대시보드에서 접근 가능)
export default function OnboardingModal({ userName, onComplete, onClose }: OnboardingModalProps) {
  const router = useRouter()
  const [step, setStep] = useState<'welcome' | 'demo' | 'demo-result'>('welcome')
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

  // P2 Fix: handleSelectPlan, formatPrice 제거됨 (pricing 단계 삭제)

  if (step === 'welcome') {
    const benefits = [
      { icon: Rocket, title: 'AI 글 자동 생성', desc: '전문적인 블로그 글을 AI가 작성해요' },
      { icon: Crown, title: '상위노출 분석', desc: '경쟁 키워드를 분석해 상위 노출을 노려요' },
      { icon: Gift, title: '무료로 시작하기', desc: '매월 글 10건을 무료로 생성할 수 있어요' },
    ]
    return (
      <ModalShell>
        <div className="relative border-b px-6 py-6">
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
          <LogoMark className="mb-4 h-9 w-9" />
          <h1 className="text-[22px] font-semibold leading-7 tracking-tight">
            {userName ? `${userName}님, 환영합니다` : '환영합니다'}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            닥터보이스 프로와 함께 블로그 자동화를 시작해 보세요.
          </p>
        </div>

        {/* Content */}
        <div className="space-y-4 p-6">
          {/* Benefits */}
          <div className="divide-y rounded-lg border">
            {benefits.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-center gap-3 px-4 py-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-[13px] text-muted-foreground">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* CTA Buttons */}
          <div className="space-y-2 pt-2">
            <Button className="w-full" size="lg" onClick={handleStartDemo}>
              <Wand2 />
              30초 체험하기
            </Button>

            <Button variant="outline" className="w-full" size="lg" onClick={handleStartFree}>
              바로 시작하기
            </Button>
          </div>

          <p className="text-center text-xs text-muted-foreground">
            체험 후에도 무료로 시작할 수 있어요
          </p>
        </div>
      </ModalShell>
    )
  }

  // Demo Step - AI 변환 체험
  if (step === 'demo') {
    return (
      <ModalShell wide>
        <ModalHead
          icon={<Wand2 className="h-5 w-5" />}
          title="AI 변환 체험"
          description="아래 샘플 원문이 어떻게 바뀌는지 확인해 보세요."
          onClose={onClose}
        />

        {/* Content */}
        <div className="space-y-4 p-6">
          {/* 원문 */}
          <div>
            <label className="mb-2 block text-[13px] font-medium text-muted-foreground">
              원본 글 (의료법 위반 표현 포함)
            </label>
            <div className="rounded-lg border border-danger/20 bg-danger-soft p-4">
              <p className="text-sm leading-relaxed text-foreground">
                {SAMPLE_ORIGINAL}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {SAMPLE_LAW_CHECK.violations.map((v, i) => (
                  <Pill key={i} tone="danger">
                    <AlertTriangle className="h-3 w-3" />
                    {v.text}
                  </Pill>
                ))}
              </div>
            </div>
          </div>

          {/* 변환 버튼 */}
          <div className="py-2 text-center">
            <Button size="lg" onClick={handleTransform} disabled={isTransforming}>
              {isTransforming ? (
                <>
                  <Loader2 className="animate-spin" />
                  AI가 변환 중...
                </>
              ) : (
                <>
                  <Sparkles />
                  AI로 변환하기
                </>
              )}
            </Button>
          </div>

          {/* 안내 */}
          <div className="flex items-start gap-2 rounded-lg bg-muted/40 p-3">
            <Shield className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
            <p className="text-xs text-muted-foreground">
              AI가 의료법 위반 표현을 자동으로 찾아내고, 전문적이고 설득력 있는 문장으로 바꿔 줍니다.
            </p>
          </div>
        </div>
      </ModalShell>
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
      <ModalShell wide scroll>
        <ModalHead
          icon={<Check className="h-5 w-5" />}
          title="변환 완료"
          description="의료법을 지키면서 설득력 있는 글로 바뀌었습니다."
          onClose={onClose}
          badge={displayResult.isRealApi ? <Pill tone="ok">실제 AI 검증</Pill> : undefined}
        />

        {/* Content */}
        <div className="space-y-4 p-6">
          {/* 변환 전 */}
          <div>
            <label className="mb-2 flex items-center gap-1 text-[13px] font-medium text-danger">
              <X className="h-4 w-4" /> 변환 전 (의료법 위반 위험)
            </label>
            <div className="rounded-lg border border-danger/20 bg-danger-soft p-3">
              <p className="text-sm text-muted-foreground line-through">
                {displayResult.originalText}
              </p>
            </div>
          </div>

          {/* 변환 후 */}
          <div>
            <label className="mb-2 flex items-center gap-1 text-[13px] font-medium text-success">
              <Check className="h-4 w-4" /> 변환 후 (의료법 준수 + 설득력 강화)
            </label>
            <div className="rounded-lg border border-success/20 bg-success-soft p-4">
              <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                {displayResult.transformedText}
              </p>
            </div>
          </div>

          {/* 수정된 표현 */}
          {displayResult.violations.length > 0 && (
            <div className="rounded-lg border border-warning/20 bg-warning-soft p-4">
              <p className="mb-2 text-[13px] font-medium text-warning">자동으로 고친 표현</p>
              <div className="space-y-2">
                {displayResult.violations.map((v, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="text-danger line-through">{v.text}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium text-success">{v.suggestion}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 점수 */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-muted/40 p-3 text-center">
              <p className="kpi text-primary">{displayResult.persuasionScore}점</p>
              <p className="text-xs text-muted-foreground">설득력 점수</p>
            </div>
            <div className="rounded-lg bg-muted/40 p-3 text-center">
              <p className="kpi text-success">
                {displayResult.isCompliant ? '통과' : '수정됨'}
              </p>
              <p className="text-xs text-muted-foreground">의료법 검증</p>
            </div>
            <div className="rounded-lg bg-muted/40 p-3 text-center">
              <p className="kpi">{displayResult.timeSaved}분</p>
              <p className="text-xs text-muted-foreground">아낀 작성 시간</p>
            </div>
          </div>

          {/* P2 Fix: CTA 간소화 - pricing 단계 제거, 바로 시작 유도 */}
          <div className="space-y-2 pt-2">
            <Button className="w-full" size="lg" onClick={handleStartFree}>
              무료로 시작하기
              <ArrowRight />
            </Button>
            <Button
              variant="ghost"
              className="w-full text-muted-foreground"
              onClick={() => {
                localStorage.setItem('onboarding_completed', 'true')
                router.push('/pricing')
                onClose()
              }}
            >
              요금제 먼저 살펴보기
            </Button>
          </div>
        </div>
      </ModalShell>
    )
  }

  // P2 Fix: pricing 단계 제거됨 - 대시보드에서 /pricing 페이지로 접근 가능
  // demo-result가 마지막 단계
  return null
}
