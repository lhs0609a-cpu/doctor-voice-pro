'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Button } from '@/components/ui/button'
import { Palette, RotateCcw } from 'lucide-react'

interface WritingStyle {
  formality: number
  friendliness: number
  technical_depth: number
  storytelling: number
  emotion: number
  humor: number
  question_usage: number
  metaphor_usage: number
  sentence_length: number
}

interface WritingStyleConfigProps {
  value: WritingStyle
  onChange: (style: WritingStyle) => void
}

const DEFAULT_STYLE: WritingStyle = {
  formality: 5,
  friendliness: 7,
  technical_depth: 5,
  storytelling: 6,
  emotion: 6,
  humor: 5,
  question_usage: 6,
  metaphor_usage: 5,
  sentence_length: 5,
}

const PRESETS: Record<string, WritingStyle> = {
  professional: {
    formality: 8,
    friendliness: 5,
    technical_depth: 8,
    storytelling: 4,
    emotion: 4,
    humor: 2,
    question_usage: 4,
    metaphor_usage: 3,
    sentence_length: 7,
  },
  friendly: {
    formality: 4,
    friendliness: 9,
    technical_depth: 5,
    storytelling: 7,
    emotion: 7,
    humor: 7,
    question_usage: 8,
    metaphor_usage: 6,
    sentence_length: 4,
  },
  warm: {
    formality: 5,
    friendliness: 8,
    technical_depth: 6,
    storytelling: 8,
    emotion: 9,
    humor: 6,
    question_usage: 7,
    metaphor_usage: 7,
    sentence_length: 5,
  },
  confident: {
    formality: 7,
    friendliness: 6,
    technical_depth: 7,
    storytelling: 6,
    emotion: 5,
    humor: 4,
    question_usage: 5,
    metaphor_usage: 4,
    sentence_length: 6,
  },
}

export function WritingStyleConfig({ value, onChange }: WritingStyleConfigProps) {
  const handleSliderChange = (field: keyof WritingStyle, newValue: number[]) => {
    onChange({
      ...value,
      [field]: newValue[0],
    })
  }

  const handlePreset = (presetName: string) => {
    onChange(PRESETS[presetName])
  }

  const handleReset = () => {
    onChange(DEFAULT_STYLE)
  }

  const styleFields = [
    { key: 'formality', label: '격식체 정도', desc: '낮음: 반말체 / 높음: 격식체' },
    { key: 'friendliness', label: '친근함', desc: '낮음: 딱딱함 / 높음: 편안함' },
    { key: 'technical_depth', label: '전문성', desc: '낮음: 쉬운 설명 / 높음: 전문적' },
    { key: 'storytelling', label: '스토리텔링', desc: '낮음: 사실 전달 / 높음: 이야기' },
    { key: 'emotion', label: '감성적 표현', desc: '낮음: 객관적 / 높음: 감성적' },
    { key: 'humor', label: '유머 사용', desc: '낮음: 진지함 / 높음: 유머러스' },
    { key: 'question_usage', label: '질문형 문장', desc: '낮음: 평서문 / 높음: 질문형' },
    { key: 'metaphor_usage', label: '비유·은유', desc: '낮음: 직접적 / 높음: 비유적' },
    { key: 'sentence_length', label: '문장 길이', desc: '낮음: 짧게 / 높음: 길게' },
  ] as const

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Palette className="h-5 w-5 text-indigo-600" />
            <CardTitle className="text-base">말투 설정</CardTitle>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            className="h-8 gap-1"
          >
            <RotateCcw className="h-3 w-3" />
            초기화
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 프리셋 버튼 */}
        <div>
          <Label className="text-xs text-gray-600 mb-2 block">빠른 프리셋</Label>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePreset('professional')}
              className="h-auto py-2 flex-col items-start"
            >
              <span className="font-semibold">전문적</span>
              <span className="text-xs text-gray-500">격식있고 전문적</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePreset('friendly')}
              className="h-auto py-2 flex-col items-start"
            >
              <span className="font-semibold">친근한</span>
              <span className="text-xs text-gray-500">편안하고 친근함</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePreset('warm')}
              className="h-auto py-2 flex-col items-start"
            >
              <span className="font-semibold">따뜻한</span>
              <span className="text-xs text-gray-500">감성적이고 따뜻함</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePreset('confident')}
              className="h-auto py-2 flex-col items-start"
            >
              <span className="font-semibold">자신감있는</span>
              <span className="text-xs text-gray-500">확신있고 명확함</span>
            </Button>
          </div>
        </div>

        {/* 상세 설정 슬라이더 */}
        <div className="space-y-4">
          <Label className="text-xs text-gray-600">상세 설정</Label>
          {styleFields.map((field) => (
            <div key={field.key} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">{field.label}</Label>
                <span className="text-sm font-bold text-indigo-600">
                  {value[field.key as keyof WritingStyle]}
                </span>
              </div>
              <Slider
                value={[value[field.key as keyof WritingStyle]]}
                onValueChange={(val) => handleSliderChange(field.key as keyof WritingStyle, val)}
                min={1}
                max={10}
                step={1}
                className="w-full"
              />
              <p className="text-xs text-gray-500">{field.desc}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
