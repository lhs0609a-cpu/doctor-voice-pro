'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import type { CafeReviewStyle } from '@/types'
import { Smile, Heart, Sparkles, MessageCircle, Laugh, FileText, AlertCircle } from 'lucide-react'

interface ReviewStyleConfigProps {
  value: CafeReviewStyle
  onChange: (style: CafeReviewStyle) => void
}

export function ReviewStyleConfig({ value, onChange }: ReviewStyleConfigProps) {
  const updateStyle = (key: keyof CafeReviewStyle, val: number) => {
    onChange({ ...value, [key]: val })
  }

  const styleOptions = [
    {
      key: 'friendliness' as keyof CafeReviewStyle,
      label: '친근함',
      icon: Smile,
      description: '격식있게 ↔ 친구처럼',
      min: '격식있게',
      max: '친구처럼',
    },
    {
      key: 'emotion' as keyof CafeReviewStyle,
      label: '감정 표현',
      icon: Heart,
      description: '담담하게 ↔ 감정 풍부',
      min: '담담하게',
      max: '감정 풍부',
    },
    {
      key: 'humor' as keyof CafeReviewStyle,
      label: '유머',
      icon: Laugh,
      description: '진지하게 ↔ 재치있게',
      min: '진지하게',
      max: '재치있게',
    },
    {
      key: 'colloquial' as keyof CafeReviewStyle,
      label: '구어체',
      icon: MessageCircle,
      description: '문어체 ↔ 말하듯',
      min: '문어체',
      max: '말하듯',
    },
    {
      key: 'emoji_usage' as keyof CafeReviewStyle,
      label: '이모티콘',
      icon: Sparkles,
      description: '없음 ↔ 많이',
      min: '없음',
      max: '많이',
    },
    {
      key: 'detail_level' as keyof CafeReviewStyle,
      label: '디테일',
      icon: FileText,
      description: '간략히 ↔ 구체적으로',
      min: '간략히',
      max: '구체적으로',
    },
    {
      key: 'honesty' as keyof CafeReviewStyle,
      label: '솔직함',
      icon: AlertCircle,
      description: '긍정만 ↔ 단점도 언급',
      min: '긍정만',
      max: '단점도',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          후기 작성 스타일
        </CardTitle>
        <CardDescription>
          슬라이더를 움직여 원하는 말투로 맞추세요
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {styleOptions.map((option) => {
          const Icon = option.icon
          return (
            <div key={option.key} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <Label className="text-sm font-medium">{option.label}</Label>
                </div>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {value[option.key]}
                </span>
              </div>
              <Slider
                value={[value[option.key]]}
                onValueChange={(vals) => updateStyle(option.key, vals[0])}
                min={1}
                max={10}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{option.min}</span>
                <span className="text-center text-xs italic">{option.description}</span>
                <span>{option.max}</span>
              </div>
            </div>
          )
        })}

        <div className="rounded-lg border bg-muted/40 p-3">
          <p className="mb-2 text-[13px] font-medium">자연스러운 후기 팁</p>
          <ul className="space-y-1 pl-4 text-xs text-muted-foreground">
            <li>• 친근함 7-9: 실제 지인에게 추천하는 느낌</li>
            <li>• 감정 6-8: 솔직한 느낌을 담되 과하지 않게</li>
            <li>• 솔직함 6-7: 작은 단점도 언급하면 신뢰도가 올라갑니다</li>
            <li>• 디테일 7-8: 구체적인 경험일수록 진짜처럼</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}
