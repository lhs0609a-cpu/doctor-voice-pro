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

const tutorialSteps: TutorialStep[] = [
  {
    id: 1,
    title: '글 생성하기',
    description: 'AI가 전문적인 블로그 글을 자동으로 작성합니다.',
    icon: <FileText className="h-12 w-12 text-blue-500" />,
    tips: [
      '대시보드에서 "새 글 작성" 버튼을 클릭하세요',
      '주제와 키워드를 입력하면 AI가 글을 생성합니다',
      '생성된 글은 수정하거나 바로 발행할 수 있습니다'
    ]
  },
  {
    id: 2,
    title: '상위노출 분석',
    description: '경쟁 키워드를 분석하고 상위 노출 전략을 세우세요.',
    icon: <Search className="h-12 w-12 text-green-500" />,
    tips: [
      '분석하고 싶은 키워드를 입력하세요',
      '상위 10개 블로그의 패턴을 분석합니다',
      '최적의 제목, 내용 구조를 제안받으세요'
    ]
  },
  {
    id: 3,
    title: '자동 발행',
    description: '네이버 블로그에 원클릭으로 자동 발행합니다.',
    icon: <Zap className="h-12 w-12 text-yellow-500" />,
    tips: [
      'SNS 연동에서 네이버 계정을 연결하세요',
      '글 작성 후 "발행" 버튼만 누르면 끝!',
      '예약 발행도 가능합니다'
    ]
  },
  {
    id: 4,
    title: '성과 분석',
    description: '블로그 성과를 한눈에 확인하세요.',
    icon: <BarChart3 className="h-12 w-12 text-purple-500" />,
    tips: [
      '발행한 글의 조회수, 댓글을 추적합니다',
      '키워드별 순위 변동을 확인하세요',
      '리포트로 성과를 정리할 수 있습니다'
    ]
  },
  {
    id: 5,
    title: '구독 플랜',
    description: '나에게 맞는 플랜을 선택하세요.',
    icon: <CreditCard className="h-12 w-12 text-pink-500" />,
    tips: [
      'Free: 월 3건 글 생성 (무료)',
      'Starter: 월 30건 + 상위노출 분석',
      'Pro: 무제한 생성 + 모든 기능',
      'Business: 팀 기능 + API 접근'
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl bg-white dark:bg-gray-900 shadow-2xl">
        <CardContent className="p-0">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-muted-foreground">
                튜토리얼 {currentStep + 1} / {tutorialSteps.length}
              </span>
            </div>
            <Button variant="ghost" size="icon" onClick={handleSkip}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Progress */}
          <div className="px-4 pt-4">
            <Progress value={progress} className="h-2" />
          </div>

          {/* Content */}
          <div className="p-8">
            <div className="flex flex-col items-center text-center mb-8">
              <div className="p-4 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-2xl mb-4">
                {step.icon}
              </div>
              <h2 className="text-2xl font-bold mb-2">{step.title}</h2>
              <p className="text-muted-foreground">{step.description}</p>
            </div>

            {/* Tips */}
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4 space-y-3">
              {step.tips.map((tip, index) => (
                <div key={index} className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
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
                onClick={() => setCurrentStep(index)}
                className={`w-2 h-2 rounded-full transition-all ${
                  index === currentStep
                    ? 'w-6 bg-primary'
                    : completedSteps.includes(index)
                    ? 'bg-primary/50'
                    : 'bg-gray-300 dark:bg-gray-600'
                }`}
              />
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-4 border-t bg-gray-50 dark:bg-gray-800/50">
            <Button
              variant="ghost"
              onClick={handlePrev}
              disabled={currentStep === 0}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
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
                  <ChevronRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
