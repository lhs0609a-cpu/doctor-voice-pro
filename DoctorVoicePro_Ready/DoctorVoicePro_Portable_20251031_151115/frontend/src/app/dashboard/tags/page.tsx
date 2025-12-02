'use client'

import { useState, useEffect } from 'react'
import { tagsAPI } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
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
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">태그 관리</h1>
          <p className="text-muted-foreground">
            포스팅을 분류하고 관리하기 위한 태그를 생성하세요
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreateDialog} className="gap-2">
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
                <div className="grid grid-cols-4 gap-2 mt-2">
                  {COLOR_OPTIONS.map((color) => (
                    <button
                      key={color.value}
                      type="button"
                      onClick={() => setFormData({ ...formData, color: color.value })}
                      className={`h-12 rounded-md border-2 transition-all ${
                        formData.color === color.value
                          ? 'border-primary scale-105'
                          : 'border-transparent hover:border-gray-300'
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
      </div>

      {tags.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-6">
            <div className="text-center py-12 text-muted-foreground">
              <Hash className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>아직 생성된 태그가 없습니다</p>
              <p className="text-sm mt-2">새 태그를 만들어 포스팅을 분류해보세요</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tags.map((tag) => (
            <Card key={tag.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge style={{ backgroundColor: tag.color, color: 'white' }}>
                    {tag.name}
                  </Badge>
                  <div className="flex items-center gap-1">
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
                      <Trash2 className="h-4 w-4 text-red-600" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {tag.post_count}개의 포스팅
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
