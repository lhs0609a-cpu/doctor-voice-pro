'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Download,
  Settings,
  Globe,
  Upload,
  MousePointer,
  Copy,
  ExternalLink,
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
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg max-h-[90vh] overflow-hidden bg-white shadow-2xl">
        {/* 헤더 */}
        <div className="bg-gradient-to-r from-green-500 to-emerald-600 p-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <Play className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-bold text-lg">블로그 발행 가이드</h2>
                <p className="text-sm text-white/80">단계별로 따라하세요</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="text-white hover:bg-white/20"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* 진행률 바 */}
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-1">
              <span>진행률</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-2 bg-white/30" />
          </div>
        </div>

        {/* 단계 목록 */}
        <CardContent className="p-0 max-h-[60vh] overflow-y-auto">
          <div className="divide-y">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className={`p-4 transition-all duration-300 ${
                  step.current
                    ? 'bg-green-50 border-l-4 border-green-500'
                    : step.completed
                    ? 'bg-gray-50'
                    : 'bg-white opacity-60'
                } ${isAnimating && step.current ? 'animate-pulse' : ''}`}
              >
                <div className="flex items-start gap-4">
                  {/* 단계 번호/체크 */}
                  <div
                    className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all ${
                      step.completed
                        ? 'bg-green-500 text-white'
                        : step.current
                        ? 'bg-green-100 text-green-700 ring-2 ring-green-500 ring-offset-2'
                        : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {step.completed ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : (
                      step.id
                    )}
                  </div>

                  {/* 내용 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`${step.current || step.completed ? 'text-gray-900' : 'text-gray-500'}`}>
                        {step.icon}
                      </span>
                      <h3
                        className={`font-semibold ${
                          step.current ? 'text-green-700' : step.completed ? 'text-gray-700' : 'text-gray-500'
                        }`}
                      >
                        {step.title}
                      </h3>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">{step.description}</p>

                    {/* 현재 단계 액션 버튼 */}
                    {step.current && !step.completed && (
                      <div className="mt-3">
                        {step.actionType === 'auto' ? (
                          <div className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg inline-flex items-center gap-2">
                            <Circle className="h-3 w-3 animate-pulse" />
                            {step.action}
                          </div>
                        ) : (
                          <Button
                            size="sm"
                            className="bg-green-600 hover:bg-green-700 gap-2"
                            onClick={() => handleStepAction(step)}
                          >
                            {step.action}
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    )}

                    {/* 완료 표시 */}
                    {step.completed && (
                      <div className="mt-2 text-sm text-green-600 flex items-center gap-1">
                        <CheckCircle2 className="h-4 w-4" />
                        완료됨
                      </div>
                    )}
                  </div>
                </div>

                {/* 연결선 (마지막 제외) */}
                {index < steps.length - 1 && (
                  <div className="ml-5 mt-2 mb-2 pl-4 border-l-2 border-dashed border-gray-200 h-2" />
                )}
              </div>
            ))}
          </div>
        </CardContent>

        {/* 푸터 */}
        <div className="p-4 bg-gray-50 border-t flex items-center justify-between">
          <Button variant="outline" size="sm" onClick={resetGuide} className="gap-2">
            <RotateCcw className="h-4 w-4" />
            처음부터
          </Button>

          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{completedSteps.size}</span>
            <span>/</span>
            <span>{steps.length} 완료</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
