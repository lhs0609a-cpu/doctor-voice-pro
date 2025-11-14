'use client'

import { Card, CardContent } from '@/components/ui/card'
import { List } from 'lucide-react'

interface SubtitlePreviewProps {
  subtitles: string[] | null
}

export function SubtitlePreview({ subtitles }: SubtitlePreviewProps) {
  if (!subtitles || subtitles.length === 0) {
    return null
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <List className="h-4 w-4 text-purple-600" />
          <h3 className="font-semibold text-sm">추천 소제목</h3>
        </div>

        <div className="space-y-3">
          {subtitles.map((subtitle, index) => (
            <div
              key={index}
              className="flex items-start gap-3 p-3 bg-gradient-to-r from-purple-50 to-transparent rounded-lg border border-purple-100"
            >
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs font-bold">
                {index + 1}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{subtitle}</p>
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-500 mt-3">
          📝 본문의 흐름에 맞는 매력적인 소제목입니다
        </p>
      </CardContent>
    </Card>
  )
}
