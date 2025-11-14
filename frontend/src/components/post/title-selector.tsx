'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="h-4 w-4 text-yellow-600" />
          <h3 className="font-semibold text-sm">추천 제목</h3>
          <span className="text-xs text-gray-500 ml-auto">클릭하여 선택</span>
        </div>

        <div className="space-y-2">
          {titles.map((title, index) => (
            <button
              key={index}
              onClick={() => handleSelect(title, index)}
              className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                selectedIndex === index || currentTitle === title
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-start gap-2">
                <div className={`mt-0.5 h-5 w-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  selectedIndex === index || currentTitle === title
                    ? 'border-blue-500 bg-blue-500'
                    : 'border-gray-300'
                }`}>
                  {(selectedIndex === index || currentTitle === title) && (
                    <Check className="h-3 w-3 text-white" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {title.length}자
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>

        <p className="text-xs text-gray-500 mt-3">
          💡 AI가 클릭을 유도하는 매력적인 제목을 생성했습니다
        </p>
      </CardContent>
    </Card>
  )
}
