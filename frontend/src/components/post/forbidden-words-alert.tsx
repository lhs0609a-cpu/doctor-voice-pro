'use client'

import { Card, CardContent } from '@/components/ui/card'
import { AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react'
import { Pill } from '@/components/app-shell/ui-kit'

interface ForbiddenWordsAlertProps {
  forbiddenCheck: {
    content_replacements: Array<{
      original: string
      replaced: string
      count: number
    }>
    title_replacements: Array<{
      original: string
      replaced: string
      count: number
    }>
  } | null
}

function ReplacementRow({ original, replaced, count }: { original: string; replaced: string; count: number }) {
  return (
    <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs">
      <span className="text-danger line-through">{original}</span>
      <ArrowRight className="h-3 w-3 text-muted-foreground" />
      <span className="font-medium text-success">{replaced}</span>
      <span className="ml-auto tabular-nums text-muted-foreground">×{count}</span>
    </div>
  )
}

export function ForbiddenWordsAlert({ forbiddenCheck }: ForbiddenWordsAlertProps) {
  if (!forbiddenCheck) {
    return null
  }

  const totalReplacements =
    (forbiddenCheck.content_replacements?.length || 0) +
    (forbiddenCheck.title_replacements?.length || 0)

  if (totalReplacements === 0) {
    return (
      <Card>
        <CardContent className="p-5">
          <div className="flex items-center gap-2 text-success">
            <CheckCircle2 className="h-4 w-4" />
            <h3 className="text-sm font-semibold">금칙어 검사 완료</h3>
          </div>
          <p className="mt-1.5 text-sm text-muted-foreground">
            네이버 블로그 금칙어가 발견되지 않았습니다.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="rounded-xl border border-warning/20 bg-warning-soft p-5">
      <div className="mb-2 flex items-center gap-2">
        <AlertCircle className="h-4 w-4 text-warning" />
        <h3 className="text-sm font-semibold text-warning">금칙어 자동 수정</h3>
        <Pill tone="warn" className="ml-auto">
          {totalReplacements}건 수정됨
        </Pill>
      </div>

      <p className="mb-3 text-sm text-muted-foreground">
        네이버 블로그 정책에 위배될 수 있는 표현을 자동으로 수정했습니다.
      </p>

      <div className="space-y-3">
        {forbiddenCheck.title_replacements && forbiddenCheck.title_replacements.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[13px] font-medium text-muted-foreground">제목</p>
            {forbiddenCheck.title_replacements.map((item, index) => (
              <ReplacementRow key={index} original={item.original} replaced={item.replaced} count={item.count} />
            ))}
          </div>
        )}

        {forbiddenCheck.content_replacements && forbiddenCheck.content_replacements.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[13px] font-medium text-muted-foreground">본문</p>
            {forbiddenCheck.content_replacements.slice(0, 5).map((item, index) => (
              <ReplacementRow key={index} original={item.original} replaced={item.replaced} count={item.count} />
            ))}
            {forbiddenCheck.content_replacements.length > 5 && (
              <p className="text-xs text-muted-foreground">
                외 {forbiddenCheck.content_replacements.length - 5}건 더
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
