'use client'

import { Card, CardContent } from '@/components/ui/card'
import { AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

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
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            <h3 className="font-semibold text-sm">금칙어 검사 완료</h3>
          </div>
          <p className="text-sm text-gray-600 mt-2">
            네이버 블로그 금칙어가 발견되지 않았습니다.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-yellow-200 bg-yellow-50">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle className="h-5 w-5 text-yellow-600" />
          <h3 className="font-semibold text-sm text-yellow-900">금칙어 자동 수정</h3>
          <Badge variant="outline" className="ml-auto bg-white">
            {totalReplacements}건 수정됨
          </Badge>
        </div>

        <p className="text-sm text-yellow-800 mb-3">
          네이버 블로그 정책에 위배될 수 있는 표현을 자동으로 수정했습니다.
        </p>

        <div className="space-y-2">
          {forbiddenCheck.title_replacements && forbiddenCheck.title_replacements.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-yellow-900 mb-1">제목</p>
              {forbiddenCheck.title_replacements.map((item, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 p-2 bg-white rounded text-xs"
                >
                  <span className="text-red-600 line-through">{item.original}</span>
                  <ArrowRight className="h-3 w-3 text-gray-400" />
                  <span className="text-green-600 font-medium">{item.replaced}</span>
                  <Badge variant="secondary" className="ml-auto">
                    ×{item.count}
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {forbiddenCheck.content_replacements && forbiddenCheck.content_replacements.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-yellow-900 mb-1">본문</p>
              {forbiddenCheck.content_replacements.slice(0, 5).map((item, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 p-2 bg-white rounded text-xs"
                >
                  <span className="text-red-600 line-through">{item.original}</span>
                  <ArrowRight className="h-3 w-3 text-gray-400" />
                  <span className="text-green-600 font-medium">{item.replaced}</span>
                  <Badge variant="secondary" className="ml-auto">
                    ×{item.count}
                  </Badge>
                </div>
              ))}
              {forbiddenCheck.content_replacements.length > 5 && (
                <p className="text-xs text-gray-500 mt-1">
                  외 {forbiddenCheck.content_replacements.length - 5}건 더...
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
