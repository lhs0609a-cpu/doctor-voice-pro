'use client'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
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
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <List className="h-4 w-4 text-muted-foreground" />
          추천 소제목
        </CardTitle>
        <CardDescription>본문 흐름에 맞춰 AI가 제안한 소제목입니다</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="divide-y rounded-lg border">
          {subtitles.map((subtitle, index) => (
            <div key={index} className="flex items-start gap-3 px-4 py-3 text-sm">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold tabular-nums text-primary">
                {index + 1}
              </div>
              <p className="flex-1 font-medium">{subtitle}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
