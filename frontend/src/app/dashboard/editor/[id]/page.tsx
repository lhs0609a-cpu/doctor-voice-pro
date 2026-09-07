'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { BlogEditor } from '@/components/blog-editor/blog-editor'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/app-shell/ui-kit'
import { ArrowLeft, FileText } from 'lucide-react'
import { toast } from 'sonner'
import type { SavedPost } from '@/types'

export default function EditorPage() {
  const params = useParams()
  const router = useRouter()
  const [post, setPost] = useState<SavedPost | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadPost = () => {
      try {
        const saved = localStorage.getItem('saved-posts')
        if (saved) {
          const posts: SavedPost[] = JSON.parse(saved)
          const found = posts.find(p => p.id === params.id)
          if (found) {
            setPost(found)
          } else {
            toast.error('글을 찾을 수 없습니다')
            router.push('/dashboard/saved')
          }
        }
      } catch (error) {
        console.error('글 로드 실패:', error)
        toast.error('글 로드 실패')
      } finally {
        setLoading(false)
      }
    }

    if (params.id) {
      loadPost()
    }
  }, [params.id, router])

  const handleSave = (updatedPost: SavedPost) => {
    try {
      const saved = localStorage.getItem('saved-posts')
      const posts: SavedPost[] = saved ? JSON.parse(saved) : []
      const index = posts.findIndex(p => p.id === updatedPost.id)

      if (index !== -1) {
        posts[index] = updatedPost
        localStorage.setItem('saved-posts', JSON.stringify(posts))
        setPost(updatedPost)
        toast.success('저장되었습니다')
      }
    } catch (error) {
      console.error('저장 실패:', error)
      toast.error('저장 실패')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  if (!post) {
    return (
      <EmptyState
        icon={<FileText className="h-8 w-8" />}
        title="글을 찾을 수 없습니다"
        description="저장된 글 목록에서 다시 선택해 주세요."
        action={
          <Button onClick={() => router.push('/dashboard/saved')}>
            <ArrowLeft />
            저장된 글로 돌아가기
          </Button>
        }
      />
    )
  }

  return <BlogEditor post={post} onSave={handleSave} />
}
