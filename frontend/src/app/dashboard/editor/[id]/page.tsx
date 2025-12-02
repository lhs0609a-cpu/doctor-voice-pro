'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { BlogEditor } from '@/components/blog-editor/blog-editor'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

interface SavedPost {
  id: string
  savedAt: string
  suggested_titles?: string[]
  generated_content?: string
  seo_keywords?: string[]
  original_content?: string
  title?: string
  hashtags?: string[]
}

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
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!post) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-gray-500">글을 찾을 수 없습니다</p>
        <Button onClick={() => router.push('/dashboard/saved')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          돌아가기
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <BlogEditor post={post} onSave={handleSave} />
    </div>
  )
}
