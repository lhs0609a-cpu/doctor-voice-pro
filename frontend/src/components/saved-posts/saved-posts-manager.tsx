'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import {
  FileText,
  Download,
  Trash2,
  Image,
  Upload,
  Sparkles,
  Eye,
  Calendar,
} from 'lucide-react'
import type { Post } from '@/types'

interface SavedPost extends Post {
  savedAt: string
  id: string
}

export function SavedPostsManager() {
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([])
  const [selectedPost, setSelectedPost] = useState<SavedPost | null>(null)
  const [uploadedImages, setUploadedImages] = useState<File[]>([])
  const [imagePreview, setImagePreview] = useState<string[]>([])
  const [distributionStrategy, setDistributionStrategy] = useState<'even' | 'paragraphs'>('paragraphs')

  // 로컬 스토리지에서 저장된 글 로드
  useEffect(() => {
    const loadSavedPosts = () => {
      try {
        const saved = localStorage.getItem('saved-posts')
        if (saved) {
          const posts = JSON.parse(saved)
          setSavedPosts(posts)
        }
      } catch (error) {
        console.error('저장된 글 로드 실패:', error)
      }
    }

    loadSavedPosts()

    // 다른 탭에서 저장한 경우를 위한 이벤트 리스너
    window.addEventListener('storage', loadSavedPosts)
    return () => window.removeEventListener('storage', loadSavedPosts)
  }, [])

  // 글 저장 함수 (create page에서 호출)
  const savePost = (post: Post) => {
    const savedPost: SavedPost = {
      ...post,
      id: `post-${Date.now()}`,
      savedAt: new Date().toISOString(),
    }

    const updated = [savedPost, ...savedPosts]
    setSavedPosts(updated)
    localStorage.setItem('saved-posts', JSON.stringify(updated))

    toast.success('글이 저장되었습니다', {
      description: '저장된 글 탭에서 확인하세요',
    })
  }

  // 글 삭제
  const deletePost = (id: string) => {
    const updated = savedPosts.filter((p) => p.id !== id)
    setSavedPosts(updated)
    localStorage.setItem('saved-posts', JSON.stringify(updated))

    if (selectedPost?.id === id) {
      setSelectedPost(null)
    }

    toast.success('글이 삭제되었습니다')
  }

  // 이미지 폴더 선택
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const imageFiles = files.filter((file) =>
      /\.(jpg|jpeg|png|gif|webp)$/i.test(file.name)
    )

    if (imageFiles.length === 0) {
      toast.error('이미지 파일만 업로드 가능합니다', {
        description: 'JPG, PNG, GIF, WEBP 형식만 지원됩니다',
      })
      return
    }

    setUploadedImages(imageFiles)

    // 미리보기 생성
    const previews = imageFiles.map((file) => URL.createObjectURL(file))
    setImagePreview(previews)

    toast.success(`${imageFiles.length}개의 이미지가 업로드되었습니다`)
  }

  // 이미지와 함께 워드 다운로드
  const exportWithImages = async () => {
    if (!selectedPost) {
      toast.error('글을 선택해주세요')
      return
    }

    if (uploadedImages.length === 0) {
      toast.error('이미지를 먼저 업로드해주세요')
      return
    }

    try {
      const formData = new FormData()
      formData.append('content', selectedPost.generated_content || '')
      formData.append('title', selectedPost.suggested_titles?.[0] || '')
      formData.append('keywords', JSON.stringify(selectedPost.seo_keywords || []))
      formData.append('emphasis_phrases', JSON.stringify([]))
      formData.append('distribution_strategy', distributionStrategy)

      // 이미지 추가
      uploadedImages.forEach((file) => {
        formData.append('images', file)
      })

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/with-images`,
        {
          method: 'POST',
          body: formData,
        }
      )

      if (!response.ok) {
        throw new Error('워드 문서 생성 실패')
      }

      // 파일 다운로드
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedPost.suggested_titles?.[0] || 'blog'}_with_images.docx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast.success('네이버 블로그용 워드 문서 다운로드 완료!', {
        description: '워드를 열어서 전체 선택 후 블로그에 붙여넣기 하세요',
      })
    } catch (error) {
      console.error('Export error:', error)
      toast.error('워드 문서 생성 실패')
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">저장된 글 관리</h1>
          <p className="text-gray-600 mt-2">
            AI가 생성한 글을 저장하고 이미지와 함께 네이버 블로그용으로 내보내세요
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 왼쪽: 저장된 글 목록 */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>저장된 글 ({savedPosts.length})</CardTitle>
            <CardDescription>클릭해서 선택하세요</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[600px] overflow-y-auto">
            {savedPosts.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>저장된 글이 없습니다</p>
                <p className="text-sm mt-1">글 생성 페이지에서 저장하세요</p>
              </div>
            ) : (
              savedPosts.map((post) => (
                <div
                  key={post.id}
                  onClick={() => setSelectedPost(post)}
                  className={`p-4 border rounded-lg cursor-pointer transition-all ${
                    selectedPost?.id === post.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <h3 className="font-semibold text-sm line-clamp-2">
                    {post.suggested_titles?.[0] || '제목 없음'}
                  </h3>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                    <Calendar className="w-3 h-3" />
                    {new Date(post.savedAt).toLocaleDateString('ko-KR')}
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedPost(post)
                      }}
                    >
                      <Eye className="w-3 h-3 mr-1" />
                      보기
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={(e) => {
                        e.stopPropagation()
                        deletePost(post.id)
                      }}
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* 오른쪽: 선택된 글 + 이미지 업로드 */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>블로그 포스팅 준비</CardTitle>
            <CardDescription>
              이미지를 업로드하면 자동으로 콘텐츠에 배치됩니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!selectedPost ? (
              <div className="text-center py-12 text-gray-500">
                <Sparkles className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-lg">왼쪽에서 글을 선택하세요</p>
              </div>
            ) : (
              <Tabs defaultValue="content">
                <TabsList className="w-full">
                  <TabsTrigger value="content" className="flex-1">
                    <FileText className="w-4 h-4 mr-2" />
                    콘텐츠
                  </TabsTrigger>
                  <TabsTrigger value="images" className="flex-1">
                    <Image className="w-4 h-4 mr-2" />
                    이미지 ({uploadedImages.length})
                  </TabsTrigger>
                  <TabsTrigger value="export" className="flex-1">
                    <Download className="w-4 h-4 mr-2" />
                    다운로드
                  </TabsTrigger>
                </TabsList>

                {/* 콘텐츠 탭 */}
                <TabsContent value="content" className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-lg mb-2">
                      {selectedPost.suggested_titles?.[0]}
                    </h3>
                    <div className="prose prose-sm max-w-none bg-gray-50 p-4 rounded-lg max-h-[400px] overflow-y-auto">
                      {(selectedPost.generated_content || '').split('\n').map((para, i) => (
                        <p key={i}>{para}</p>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <div className="text-sm text-gray-600">
                      키워드: {selectedPost.seo_keywords?.join(', ') || '없음'}
                    </div>
                  </div>
                </TabsContent>

                {/* 이미지 탭 */}
                <TabsContent value="images" className="space-y-4">
                  <div>
                    <Label>이미지 업로드 (여러 파일 선택 가능)</Label>
                    <Input
                      type="file"
                      multiple
                      accept=".jpg,.jpeg,.png,.gif,.webp"
                      onChange={handleImageUpload}
                      className="mt-2"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      JPG, PNG, GIF, WEBP 형식만 지원됩니다. Ctrl+클릭으로 여러 파일을 선택하세요.
                    </p>
                  </div>

                  {uploadedImages.length > 0 && (
                    <div>
                      <Label>업로드된 이미지 ({uploadedImages.length}개)</Label>
                      <div className="grid grid-cols-3 gap-3 mt-2">
                        {imagePreview.map((preview, i) => (
                          <div key={i} className="relative">
                            <img
                              src={preview}
                              alt={uploadedImages[i].name}
                              className="w-full h-32 object-cover rounded-lg"
                            />
                            <p className="text-xs mt-1 truncate">
                              {uploadedImages[i].name}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <Label>이미지 배치 전략</Label>
                    <div className="flex gap-3 mt-2">
                      <Button
                        variant={distributionStrategy === 'paragraphs' ? 'default' : 'outline'}
                        onClick={() => setDistributionStrategy('paragraphs')}
                      >
                        문단 사이 (추천)
                      </Button>
                      <Button
                        variant={distributionStrategy === 'even' ? 'default' : 'outline'}
                        onClick={() => setDistributionStrategy('even')}
                      >
                        균등 분포
                      </Button>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      {distributionStrategy === 'paragraphs'
                        ? '2-3 문단마다 이미지를 자동으로 배치합니다'
                        : '전체 글에 이미지를 균등하게 분포시킵니다'}
                    </p>
                  </div>
                </TabsContent>

                {/* 다운로드 탭 */}
                <TabsContent value="export" className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 className="font-semibold text-blue-900 mb-2">
                      📋 네이버 블로그 복붙 가이드
                    </h3>
                    <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
                      <li>아래 버튼으로 워드 문서 다운로드</li>
                      <li>다운로드된 .docx 파일 열기</li>
                      <li>전체 선택 (Ctrl+A 또는 Cmd+A)</li>
                      <li>복사 (Ctrl+C 또는 Cmd+C)</li>
                      <li>네이버 블로그 에디터에서 붙여넣기 (Ctrl+V)</li>
                    </ol>
                    <p className="text-xs text-blue-700 mt-3">
                      ✨ 형광펜, 볼드, 인용구, 이미지 모두 완벽하게 유지됩니다!
                    </p>
                  </div>

                  <Button
                    onClick={exportWithImages}
                    disabled={uploadedImages.length === 0}
                    className="w-full"
                    size="lg"
                  >
                    <Download className="w-5 h-5 mr-2" />
                    네이버 블로그용 워드 다운로드
                  </Button>

                  {uploadedImages.length === 0 && (
                    <p className="text-sm text-center text-gray-500">
                      이미지를 먼저 업로드해주세요
                    </p>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// 전역 함수로 내보내기 (다른 컴포넌트에서 사용)
export function useSavePost() {
  const savePost = (post: Post) => {
    const savedPost: SavedPost = {
      ...post,
      id: `post-${Date.now()}`,
      savedAt: new Date().toISOString(),
    }

    try {
      const existing = localStorage.getItem('saved-posts')
      const posts = existing ? JSON.parse(existing) : []
      const updated = [savedPost, ...posts]
      localStorage.setItem('saved-posts', JSON.stringify(updated))

      toast.success('글이 저장되었습니다', {
        description: '저장된 글 탭에서 확인하세요',
      })

      return true
    } catch (error) {
      console.error('저장 실패:', error)
      toast.error('글 저장에 실패했습니다')
      return false
    }
  }

  return { savePost }
}
