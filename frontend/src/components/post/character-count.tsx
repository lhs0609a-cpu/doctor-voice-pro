'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

  const stats = [
    { icon: Type, label: '전체', value: character_count.total.toLocaleString(), hint: '공백 포함' },
    { icon: Type, label: '순수', value: character_count.no_space.toLocaleString(), hint: '공백 제외' },
    { icon: AlignLeft, label: '문장', value: sentence_count.toLocaleString(), hint: '개' },
    { icon: FileText, label: '단락', value: paragraph_count.toLocaleString(), hint: '개' },
    { icon: Type, label: '줄', value: character_count.lines.toLocaleString(), hint: '개' },
    {
      icon: Type,
      label: '평균',
      value: (sentence_count > 0 ? Math.round(character_count.no_space / sentence_count) : 0).toLocaleString(),
      hint: '자/문장',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          글자수 분석
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {stats.map((s) => {
            const Icon = s.icon
            return (
              <div key={s.label} className="rounded-lg border bg-muted/40 p-3">
                <div className="mb-1 flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground">
                  <Icon className="h-3 w-3" />
                  {s.label}
                </div>
                <p className="text-xl font-semibold tabular-nums">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.hint}</p>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
