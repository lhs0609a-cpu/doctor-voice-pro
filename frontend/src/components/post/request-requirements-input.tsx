'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileEdit, Save, Trash2, Plus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface RequestRequirements {
  common: string[]
  individual: string
}

interface RequestRequirementsInputProps {
  value: RequestRequirements
  onChange: (requirements: RequestRequirements) => void
}

export function RequestRequirementsInput({ value, onChange }: RequestRequirementsInputProps) {
  const [newCommon, setNewCommon] = useState('')
  const [savedCommon, setSavedCommon] = useState<string[]>([])

  // Load saved common requirements from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('common_requirements')
    if (saved) {
      try {
        setSavedCommon(JSON.parse(saved))
      } catch (e) {
        console.error('Failed to load common requirements:', e)
      }
    }
  }, [])

  const handleSaveCommon = () => {
    if (!newCommon.trim()) return

    const updated = [...savedCommon, newCommon.trim()]
    setSavedCommon(updated)
    localStorage.setItem('common_requirements', JSON.stringify(updated))

    // Add to current common requirements
    onChange({
      ...value,
      common: [...value.common, newCommon.trim()],
    })

    setNewCommon('')
  }

  const handleDeleteCommon = (index: number) => {
    const updated = savedCommon.filter((_, i) => i !== index)
    setSavedCommon(updated)
    localStorage.setItem('common_requirements', JSON.stringify(updated))
  }

  const handleToggleCommon = (requirement: string) => {
    if (value.common.includes(requirement)) {
      onChange({
        ...value,
        common: value.common.filter((r) => r !== requirement),
      })
    } else {
      onChange({
        ...value,
        common: [...value.common, requirement],
      })
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileEdit className="h-5 w-5 text-blue-600" />
          <CardTitle className="text-base">요청사항</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="common" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="common">
              공통 반영사항
              {value.common.length > 0 && (
                <Badge variant="secondary" className="ml-2">
                  {value.common.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="individual">개별 반영사항</TabsTrigger>
          </TabsList>

          <TabsContent value="common" className="space-y-3">
            <p className="text-xs text-gray-600">
              모든 글에 공통으로 반영할 요청사항을 저장하고 재사용하세요
            </p>

            {/* 새 공통 요청사항 추가 */}
            <div className="space-y-2">
              <Label className="text-sm">새 공통 요청사항 추가</Label>
              <div className="flex gap-2">
                <Textarea
                  value={newCommon}
                  onChange={(e) => setNewCommon(e.target.value)}
                  placeholder="예: 병원 위치를 자연스럽게 언급해주세요"
                  className="min-h-[60px]"
                />
                <Button
                  onClick={handleSaveCommon}
                  disabled={!newCommon.trim()}
                  size="sm"
                  className="flex-shrink-0"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* 저장된 공통 요청사항 목록 */}
            {savedCommon.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm">저장된 공통 요청사항</Label>
                <div className="space-y-2">
                  {savedCommon.map((requirement, index) => (
                    <div
                      key={index}
                      className={`flex items-start gap-2 p-3 rounded-lg border-2 transition-all cursor-pointer ${
                        value.common.includes(requirement)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => handleToggleCommon(requirement)}
                    >
                      <div className="flex-1">
                        <p className="text-sm">{requirement}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteCommon(index)
                        }}
                        className="flex-shrink-0 h-6 w-6 p-0"
                      >
                        <Trash2 className="h-3 w-3 text-red-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {savedCommon.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                저장된 공통 요청사항이 없습니다
              </p>
            )}
          </TabsContent>

          <TabsContent value="individual" className="space-y-3">
            <p className="text-xs text-gray-600">
              이 글에만 적용할 특별한 요청사항을 입력하세요
            </p>

            <div className="space-y-2">
              <Label className="text-sm">개별 요청사항</Label>
              <Textarea
                value={value.individual}
                onChange={(e) =>
                  onChange({
                    ...value,
                    individual: e.target.value,
                  })
                }
                placeholder="예: 겨울철 관리 팁을 특별히 강조해주세요"
                className="min-h-[120px]"
              />
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
