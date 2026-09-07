'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Pill } from '@/components/app-shell/ui-kit'
import {
  CheckCircle2,
  Check,
  Circle,
  Download,
  Settings,
  Globe,
  Upload,
  MousePointer,
  Sparkles,
  X,
  ChevronRight,
  Play,
  RotateCcw,
} from 'lucide-react'

interface PublishGuideProps {
  isOpen: boolean
  onClose: () => void
  onDownloadExtension: () => void
  hasExtension: boolean
  hasSelectedPost: boolean
  hasImages: boolean
  onStartPublish: () => void
}

interface Step {
  id: number
  title: string
  description: string
  action?: string
  actionType?: 'button' | 'link' | 'auto'
  icon: React.ReactNode
  completed: boolean
  current: boolean
}

export function PublishGuide({
  isOpen,
  onClose,
  onDownloadExtension,
  hasExtension,
  hasSelectedPost,
  hasImages,
  onStartPublish,
}: PublishGuideProps) {
  const [currentStep, setCurrentStep] = useState(1)
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set())
  const [isAnimating, setIsAnimating] = useState(false)

  // 단계 정의
  const steps: Step[] = [
    {
      id: 1,
      title: '확장 프로그램 다운로드',
      description: 'ZIP 파일을 다운로드하세요',
      action: '다운로드',
      actionType: 'button',
      icon: <Download className="h-5 w-5" />,
      completed: completedSteps.has(1),
      current: currentStep === 1,
    },
    {
      id: 2,
      title: '크롬에서 확장프로그램 페이지 열기',
      description: 'chrome://extensions 입력',
      action: '복사하기',
      actionType: 'button',
      icon: <Globe className="h-5 w-5" />,
      completed: completedSteps.has(2),
      current: currentStep === 2,
    },
    {
      id: 3,
      title: '개발자 모드 켜기',
      description: '오른쪽 상단 토글 스위치를 켜세요',
      action: '완료',
      actionType: 'button',
      icon: <Settings className="h-5 w-5" />,
      completed: completedSteps.has(3),
      current: currentStep === 3,
    },
    {
      id: 4,
      title: '압축해제된 확장 프로그램 로드',
      description: '다운로드한 ZIP 압축 해제 후 폴더 선택',
      action: '완료',
      actionType: 'button',
      icon: <Upload className="h-5 w-5" />,
      completed: completedSteps.has(4),
      current: currentStep === 4,
    },
    {
      id: 5,
      title: '발행할 글 선택',
      description: '왼쪽 목록에서 글을 클릭하세요',
      action: hasSelectedPost ? '완료됨' : '글 선택 필요',
      actionType: 'auto',
      icon: <MousePointer className="h-5 w-5" />,
      completed: completedSteps.has(5) || hasSelectedPost,
      current: currentStep === 5,
    },
    {
      id: 6,
      title: '이미지 업로드 (선택)',
      description: '이미지 탭에서 사진을 업로드하세요',
      action: hasImages ? '완료됨' : '건너뛰기',
      actionType: 'button',
      icon: <Upload className="h-5 w-5" />,
      completed: completedSteps.has(6) || hasImages,
      current: currentStep === 6,
    },
    {
      id: 7,
      title: '네이버 블로그에 발행하기',
      description: '버튼을 클릭하면 자동으로 진행됩니다',
      action: '발행 시작',
      actionType: 'button',
      icon: <Sparkles className="h-5 w-5" />,
      completed: completedSteps.has(7),
      current: currentStep === 7,
    },
  ]

  // 자동 완료 체크
  useEffect(() => {
    if (hasSelectedPost && currentStep === 5) {
      completeStep(5)
    }
    if (hasImages && currentStep === 6) {
      completeStep(6)
    }
  }, [hasSelectedPost, hasImages, currentStep])

  const completeStep = (stepId: number) => {
    setIsAnimating(true)
    setCompletedSteps(prev => new Set([...prev, stepId]))

    setTimeout(() => {
      if (stepId < 7) {
        setCurrentStep(stepId + 1)
      }
      setIsAnimating(false)
    }, 500)
  }

  const handleStepAction = (step: Step) => {
    switch (step.id) {
      case 1:
        onDownloadExtension()
        completeStep(1)
        break
      case 2:
        navigator.clipboard.writeText('chrome://extensions')
        completeStep(2)
        break
      case 3:
      case 4:
        completeStep(step.id)
        break
      case 5:
        if (hasSelectedPost) completeStep(5)
        break
      case 6:
        completeStep(6)
        break
      case 7:
        onStartPublish()
        completeStep(7)
        onClose()
        break
    }
  }

  const resetGuide = () => {
    setCurrentStep(1)
    setCompletedSteps(new Set())
  }

  const progress = (completedSteps.size / steps.length) * 100

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4">
      <Card className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden shadow-pop">
        {/* 헤더 */}
        <div className="border-b p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <Play className="h-4 w-4" />
              </div>
              <div>
                <h2 className="section-title">블로그 발행 가이드</h2>
                <p className="text-[13px] text-muted-foreground">단계별로 따라하세요</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="닫기">
              <X />
            </Button>
          </div>

          {/* 진행률 바 */}
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-[13px] text-muted-foreground">
              <span>진행률</span>
              <span className="tabular-nums">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-1.5" />
          </div>
        </div>

        {/* 단계 목록 */}
        <CardContent className="max-h-[60vh] overflow-y-auto p-0">
          <div className="divide-y">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`p-4 transition-colors ${
                  step.current ? 'bg-accent/60' : step.completed ? '' : 'opacity-60'
                } ${isAnimating && step.current ? 'animate-pulse' : ''}`}
              >
                <div className="flex items-start gap-4">
                  {/* 단계 번호/체크 */}
                  <div
                    className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums ${
                      step.completed
                        ? 'bg-success-soft text-success'
                        : step.current
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {step.completed ? <Check className="h-4 w-4" /> : step.id}
                  </div>

                  {/* 내용 */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={step.current || step.completed ? 'text-foreground' : 'text-muted-foreground'}>
                        {step.icon}
                      </span>
                      <h3 className={`text-sm font-semibold ${step.current ? 'text-accent-foreground' : step.completed ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {step.title}
                      </h3>
                    </div>
                    <p className="mt-1 text-[13px] text-muted-foreground">{step.description}</p>

                    {/* 현재 단계 액션 버튼 */}
                    {step.current && !step.completed && (
                      <div className="mt-3">
                        {step.actionType === 'auto' ? (
                          <Pill tone="warn">
                            <Circle className="h-3 w-3 animate-pulse" />
                            {step.action}
                          </Pill>
                        ) : (
                          <Button size="sm" onClick={() => handleStepAction(step)}>
                            {step.action}
                            <ChevronRight />
                          </Button>
                        )}
                      </div>
                    )}

                    {/* 완료 표시 */}
                    {step.completed && (
                      <div className="mt-2 flex items-center gap-1 text-[13px] text-success">
                        <CheckCircle2 className="h-4 w-4" />
                        완료됨
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>

        {/* 푸터 */}
        <div className="flex items-center justify-between border-t bg-muted/30 p-4">
          <Button variant="outline" size="sm" onClick={resetGuide}>
            <RotateCcw />
            처음부터
          </Button>

          <div className="text-[13px] tabular-nums text-muted-foreground">
            {completedSteps.size} / {steps.length} 완료
          </div>
        </div>
      </Card>
    </div>
  )
}
