'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Hash, Star } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface Keyword {
  word: string
  count: number
  is_medical: boolean
  importance: string
}

interface KeywordTagsProps {
  keywords: Keyword[] | null
}

export function KeywordTags({ keywords }: KeywordTagsProps) {
  if (!keywords || keywords.length === 0) {
    return null
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Hash className="h-4 w-4 text-green-600" />
          <h3 className="font-semibold text-sm">키워드 분석</h3>
          <Badge variant="outline" className="ml-auto">
            {keywords.length}개
          </Badge>
        </div>

        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword, index) => (
            <div
              key={index}
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm ${
                keyword.is_medical
                  ? 'bg-green-100 text-green-800 border border-green-300'
                  : 'bg-gray-100 text-gray-700 border border-gray-300'
              }`}
            >
              {keyword.is_medical && (
                <Star className="h-3 w-3 fill-current" />
              )}
              <span className="font-medium">{keyword.word}</span>
              <span className="text-xs opacity-70">×{keyword.count}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 pt-3 border-t text-xs text-gray-500 flex items-center gap-2">
          <Star className="h-3 w-3 text-green-600 fill-current" />
          <span>의료 전문 키워드</span>
          <span className="ml-auto">
            {keywords.filter(k => k.is_medical).length}개 /  {keywords.length}개
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
