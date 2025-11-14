'use client'

import { Card, CardContent } from '@/components/ui/card'
import { FileText, AlignLeft, Type } from 'lucide-react'

interface CharacterCountProps {
  analysis: {
    character_count: {
      total: number
      no_space: number
      no_markdown: number
      spaces: number
      lines: number
    }
    sentence_count: number
    paragraph_count: number
  } | null
}

export function CharacterCount({ analysis }: CharacterCountProps) {
  if (!analysis) {
    return null
  }

  const { character_count, sentence_count, paragraph_count } = analysis

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="h-4 w-4 text-blue-600" />
          <h3 className="font-semibold text-sm">글자수 분석</h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="p-3 bg-blue-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <Type className="h-3 w-3 text-blue-600" />
              <p className="text-xs text-gray-600">전체</p>
            </div>
            <p className="text-lg font-bold text-blue-600">
              {character_count.total.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500">공백 포함</p>
          </div>

          <div className="p-3 bg-green-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <Type className="h-3 w-3 text-green-600" />
              <p className="text-xs text-gray-600">순수</p>
            </div>
            <p className="text-lg font-bold text-green-600">
              {character_count.no_space.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500">공백 제외</p>
          </div>

          <div className="p-3 bg-purple-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <AlignLeft className="h-3 w-3 text-purple-600" />
              <p className="text-xs text-gray-600">문장</p>
            </div>
            <p className="text-lg font-bold text-purple-600">
              {sentence_count}
            </p>
            <p className="text-xs text-gray-500">개</p>
          </div>

          <div className="p-3 bg-orange-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="h-3 w-3 text-orange-600" />
              <p className="text-xs text-gray-600">단락</p>
            </div>
            <p className="text-lg font-bold text-orange-600">
              {paragraph_count}
            </p>
            <p className="text-xs text-gray-500">개</p>
          </div>

          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <Type className="h-3 w-3 text-gray-600" />
              <p className="text-xs text-gray-600">줄</p>
            </div>
            <p className="text-lg font-bold text-gray-600">
              {character_count.lines}
            </p>
            <p className="text-xs text-gray-500">개</p>
          </div>

          <div className="p-3 bg-indigo-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <Type className="h-3 w-3 text-indigo-600" />
              <p className="text-xs text-gray-600">평균</p>
            </div>
            <p className="text-lg font-bold text-indigo-600">
              {sentence_count > 0
                ? Math.round(character_count.no_space / sentence_count)
                : 0}
            </p>
            <p className="text-xs text-gray-500">자/문장</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
