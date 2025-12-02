/**
 * PostEditor Component
 * 저장된 글의 간단한 인라인 편집 (제목, 본문)
 */

import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Save, X } from 'lucide-react'

export interface SavedPost {
  id: string
  title?: string
  generated_content?: string
  created_at?: string
  updated_at?: string
  [key: string]: any
}

interface PostEditorProps {
  post: SavedPost
  onSave: (title: string, content: string) => void
  onCancel: () => void
}

export const PostEditor: React.FC<PostEditorProps> = ({ post, onSave, onCancel }) => {
  const [title, setTitle] = useState(post.title || '')
  const [content, setContent] = useState(post.generated_content || '')
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    // 제목과 본문이 모두 비어있으면 경고
    if (!title.trim() && !content.trim()) {
      alert('제목 또는 본문을 입력해주세요.')
      return
    }

    setIsSaving(true)

    try {
      await onSave(title.trim(), content.trim())
    } catch (error) {
      console.error('Save error:', error)
    } finally {
      setIsSaving(false)
    }
  }

  // 변경 여부 확인
  const hasChanges =
    title.trim() !== (post.title || '').trim() ||
    content.trim() !== (post.generated_content || '').trim()

  // Ctrl/Cmd + S로 저장
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      if (hasChanges) {
        handleSave()
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>글 편집</span>
          <div className="flex gap-2">
            <Button
              onClick={handleSave}
              disabled={isSaving || !hasChanges}
              size="sm"
              className="gap-2"
            >
              <Save className="h-4 w-4" />
              {isSaving ? '저장 중...' : '저장'}
            </Button>
            <Button onClick={onCancel} variant="outline" size="sm" className="gap-2">
              <X className="h-4 w-4" />
              취소
            </Button>
          </div>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 제목 입력 */}
        <div className="space-y-2">
          <Label htmlFor="post-title">제목</Label>
          <Input
            id="post-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="글 제목을 입력하세요"
            className="text-lg font-semibold"
            onKeyDown={handleKeyDown}
          />
          <p className="text-xs text-muted-foreground">{title.length} / 100자</p>
        </div>

        {/* 본문 입력 */}
        <div className="space-y-2">
          <Label htmlFor="post-content">본문</Label>
          <Textarea
            id="post-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="글 본문을 입력하세요"
            rows={20}
            className="font-mono text-sm leading-relaxed"
            onKeyDown={handleKeyDown}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{content.length.toLocaleString()}자</span>
            <span>
              {content.split('\n\n').filter((p) => p.trim()).length}개 문단
            </span>
          </div>
        </div>

        {/* 단축키 안내 */}
        <div className="pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            💡 <strong>Ctrl/Cmd + S</strong>를 눌러 빠르게 저장할 수 있습니다.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
