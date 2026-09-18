'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Lightbulb, Check } from 'lucide-react'

interface TitleSelectorProps {
  titles: string[] | null
  currentTitle: string
  onSelect: (title: string) => void
}

export function TitleSelector({ titles, currentTitle, onSelect }: TitleSelectorProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(-1)

  if (!titles || titles.length === 0) {
    return null
  }

  const handleSelect = (title: string, index: number) => {
    setSelectedIndex(index)
    onSelect(title)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
            추천 제목
          </CardTitle>
          <CardDescription className="mt-1">AI가 클릭을 유도하는 제목을 제안했습니다</CardDescription>
        </div>
        <span className="text-xs text-muted-foreground">클릭하여 선택</span>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {titles.map((title, index) => {
            const isSelected = selectedIndex === index || currentTitle === title
            return (
              <button
                key={index}
                type="button"
                onClick={() => handleSelect(title, index)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  isSelected
                    ? 'border-primary bg-accent'
                    : 'hover:bg-muted/40'
                }`}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={`mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border ${
                      isSelected ? 'border-primary bg-primary' : 'border-border'
                    }`}
                  >
                    {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{title}</p>
                    <p className="mt-1 text-xs tabular-nums text-muted-foreground">{title.length}자</p>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
