'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  ChevronLeft,
  ChevronRight,
  X,
  FileText,
  Search,
  Zap,
  BarChart3,
  Settings,
  CreditCard,
  CheckCircle2
} from 'lucide-react'

interface TutorialStep {
  id: number
  title: string
  description: string
  icon: React.ReactNode
  tips: string[]
}

// P2 Fix: 5단계 → 3단계로 간소화 (핵심 기능에 집중)
const tutorialSteps: TutorialStep[] = [
  {
    id: 1,
    title: 'AI 글 생성',
    description: '의료법을 지키는 전문적인 블로그 글을 AI가 자동으로 작성합니다.',
    icon: <FileText className="h-7 w-7" />,
    tips: [
      '"새 글 작성" 버튼 → 주제 입력 → AI가 글 생성',
      '의료법 위반 표현을 자동으로 검사하고 고쳐 드려요',
      '생성된 글은 에디터에서 자유롭게 수정할 수 있어요'
    ]
  },
  {
    id: 2,
    title: '상위노출 분석',
    description: '네이버 검색 상위 블로그를 분석해 최적의 글쓰기 전략을 제안합니다.',
    icon: <Search className="h-7 w-7" />,
    tips: [
      '원하는 키워드 입력 → 상위 10개 블로그 자동 분석',
      '제목, 본문 길이, 키워드 배치 패턴을 알려 드려요',
      '분석 결과를 바탕으로 AI가 최적화된 글을 생성해요'
    ]
  },
  {
    id: 3,
    title: '발행 & 성과 추적',
    description: '네이버 블로그에 바로 발행하고, 성과를 한눈에 확인하세요.',
    icon: <Zap className="h-7 w-7" />,
    tips: [
      '크롬 확장 프로그램으로 원클릭 발행',
      '조회수, 댓글, 검색 순위를 자동으로 추적',
      '예약 발행으로 최적의 시간에 글을 올릴 수 있어요'
    ]
  }
]

interface TutorialGuideProps {
  onComplete?: () => void
  onClose?: () => void
}

export default function TutorialGuide({ onComplete, onClose }: TutorialGuideProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])

  const progress = ((currentStep + 1) / tutorialSteps.length) * 100

  const handleNext = () => {
    if (!completedSteps.includes(currentStep)) {
      setCompletedSteps([...completedSteps, currentStep])
    }
    if (currentStep < tutorialSteps.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      // 튜토리얼 완료
      localStorage.setItem('tutorial_completed', 'true')
      onComplete?.()
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSkip = () => {
    localStorage.setItem('tutorial_completed', 'true')
    onClose?.()
  }

  const step = tutorialSteps[currentStep]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm">
      <Card className="w-full max-w-2xl shadow-pop">
        <CardContent className="p-0">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-5 py-3">
            <span className="text-[13px] font-medium text-muted-foreground tabular-nums">
              튜토리얼 {currentStep + 1} / {tutorialSteps.length}
            </span>
            <Button variant="ghost" size="icon" onClick={handleSkip} aria-label="닫기">
              <X />
            </Button>
          </div>

          {/* Progress */}
          <div className="px-5 pt-4">
            <Progress value={progress} className="h-1.5" />
          </div>

          {/* Content */}
          <div className="p-8">
            <div className="mb-8 flex flex-col items-center text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-accent text-primary">
                {step.icon}
              </div>
              <h2 className="text-xl font-semibold leading-7 tracking-tight">{step.title}</h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">{step.description}</p>
            </div>

            {/* Tips */}
            <div className="space-y-3 rounded-lg bg-muted/40 p-4">
              {step.tips.map((tip, index) => (
                <div key={index} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" />
                  <span className="text-sm">{tip}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Step Indicators */}
          <div className="flex justify-center gap-2 pb-4">
            {tutorialSteps.map((_, index) => (
              <button
                key={index}
                type="button"
                onClick={() => setCurrentStep(index)}
                aria-label={`${index + 1}단계`}
                className={`h-2 rounded-full transition-all ${
                  index === currentStep
                    ? 'w-6 bg-primary'
                    : completedSteps.includes(index)
                    ? 'w-2 bg-primary/50'
                    : 'w-2 bg-border'
                }`}
              />
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t bg-muted/40 px-5 py-3">
            <Button
              variant="ghost"
              onClick={handlePrev}
              disabled={currentStep === 0}
            >
              <ChevronLeft />
              이전
            </Button>

            <Button variant="ghost" onClick={handleSkip} className="text-muted-foreground">
              건너뛰기
            </Button>

            <Button onClick={handleNext}>
              {currentStep === tutorialSteps.length - 1 ? (
                '완료'
              ) : (
                <>
                  다음
                  <ChevronRight />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
