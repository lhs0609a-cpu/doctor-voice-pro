'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Hash, Star } from 'lucide-react'
import { Pill } from '@/components/app-shell/ui-kit'

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

  const medicalCount = keywords.filter((k) => k.is_medical).length

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Hash className="h-4 w-4 text-muted-foreground" />
          키워드 분석
        </CardTitle>
        <Pill tone="muted">{keywords.length}개</Pill>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword, index) => (
            <span
              key={index}
              className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${
                keyword.is_medical
                  ? 'border-primary/20 bg-accent text-accent-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {keyword.is_medical && <Star className="h-3 w-3 fill-current text-primary" />}
              <span className="font-medium">{keyword.word}</span>
              <span className="text-xs tabular-nums opacity-70">×{keyword.count}</span>
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2 border-t pt-3 text-xs text-muted-foreground">
          <Star className="h-3 w-3 fill-current text-primary" />
          <span>의료 전문 키워드</span>
          <span className="ml-auto tabular-nums">
            {medicalCount}개 / {keywords.length}개
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
