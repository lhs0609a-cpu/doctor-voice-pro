'use client'

import { useState, useEffect } from 'react'
import { tagsAPI } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/app-shell/page-header'
import { EmptyState } from '@/components/app-shell/ui-kit'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Hash } from 'lucide-react'

interface Tag {
  id: string
  name: string
  color: string
  post_count: number
}

const COLOR_OPTIONS = [
  { name: '파랑', value: '#3B82F6' },
  { name: '초록', value: '#10B981' },
  { name: '빨강', value: '#EF4444' },
  { name: '노랑', value: '#F59E0B' },
  { name: '보라', value: '#8B5CF6' },
  { name: '분홍', value: '#EC4899' },
  { name: '청록', value: '#14B8A6' },
  { name: '주황', value: '#F97316' },
]

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [formData, setFormData] = useState({ name: '', color: '#3B82F6' })

  useEffect(() => {
    loadTags()
  }, [])

  const loadTags = async () => {
    try {
      setLoading(true)
      const data = await tagsAPI.getAll()
      setTags(data)
    } catch (error) {
      toast.error('태그 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      toast.error('태그 이름을 입력하세요')
      return
    }

    try {
      if (editingTag) {
        await tagsAPI.update(editingTag.id, formData)
        toast.success('태그가 수정되었습니다')
      } else {
        await tagsAPI.create(formData)
        toast.success('태그가 생성되었습니다')
      }
      setDialogOpen(false)
      setEditingTag(null)
      setFormData({ name: '', color: '#3B82F6' })
      loadTags()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '오류가 발생했습니다')
    }
  }

  const handleEdit = (tag: Tag) => {
    setEditingTag(tag)
    setFormData({ name: tag.name, color: tag.color })
    setDialogOpen(true)
  }

  const handleDelete = async (tagId: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      await tagsAPI.delete(tagId)
      toast.success('태그가 삭제되었습니다')
      loadTags()
    } catch (error) {
      toast.error('삭제 실패')
    }
  }

  const openCreateDialog = () => {
    setEditingTag(null)
    setFormData({ name: '', color: '#3B82F6' })
    setDialogOpen(true)
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="태그 관리"
        description="태그를 만들어 포스팅을 분류하고 관리하세요"
        actions={
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreateDialog}>
                <Plus className="h-4 w-4" />
                새 태그
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingTag ? '태그 수정' : '새 태그 만들기'}</DialogTitle>
                <DialogDescription>
                  태그 이름과 색상을 선택하세요
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="name">태그 이름</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="예: 진료 안내"
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label>색상 선택</Label>
                  <div className="mt-2 grid grid-cols-4 gap-2">
                    {COLOR_OPTIONS.map((color) => (
                      <button
                        key={color.value}
                        type="button"
                        onClick={() => setFormData({ ...formData, color: color.value })}
                        className={`h-12 rounded-md border-2 transition-all ${
                          formData.color === color.value
                            ? 'scale-105 border-primary'
                            : 'border-transparent hover:border-border'
                        }`}
                        style={{ backgroundColor: color.value }}
                        title={color.name}
                      />
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">미리보기:</span>
                  <Badge style={{ backgroundColor: formData.color, color: 'white' }}>
                    {formData.name || '태그 이름'}
                  </Badge>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setDialogOpen(false)}
                  >
                    취소
                  </Button>
                  <Button type="submit">
                    {editingTag ? '수정' : '생성'}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {tags.length === 0 ? (
        <EmptyState
          icon={<Hash className="h-8 w-8" />}
          title="아직 생성된 태그가 없습니다"
          description="새 태그를 만들어 포스팅을 분류해보세요"
          action={
            <Button variant="outline" onClick={openCreateDialog}>
              <Plus className="h-4 w-4" />
              새 태그 만들기
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {tags.map((tag) => (
            <div key={tag.id} className="surface flex items-center justify-between gap-3 p-4">
              <div className="min-w-0 space-y-1">
                <Badge style={{ backgroundColor: tag.color, color: 'white' }}>
                  {tag.name}
                </Badge>
                <p className="text-sm tabular-nums text-muted-foreground">
                  {tag.post_count}개의 포스팅
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEdit(tag)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(tag.id)}
                >
                  <Trash2 className="h-4 w-4 text-danger" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
