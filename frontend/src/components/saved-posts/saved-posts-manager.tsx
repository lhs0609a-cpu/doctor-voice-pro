'use client'

/**
 * SavedPostsManager - Refactored Version
 * 통합 글 관리 시스템: 원클릭 네이버 발행
 */

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from 'sonner'
import {
  FileText,
  Trash2,
  Calendar,
  Edit3,
  Eye,
  Send,
  CheckCircle,
  AlertCircle,
  Settings,
  Loader2,
} from 'lucide-react'
import { PostEditor, type SavedPost } from './post-editor'
import { ImageManager } from './image-manager'
import type { ImageRecord } from '@/lib/indexeddb'
import { deleteImagesByPostId } from '@/lib/indexeddb'
import { useNaverAuth } from '@/hooks/useNaverAuth'
import { useChromeExtension } from '@/hooks/useChromeExtension'
import { blobToBase64, calculateImagePositions } from '@/lib/image-utils'

// 샘플 글 (항상 유지)
const SAMPLE_POST: SavedPost = {
  id: 'sample-post-001',
  savedAt: '2025-01-01T00:00:00.000Z',
  suggested_titles: ['정기 검진을 받지 않으면 놓치는 위험은?'],
  title: '정기 검진을 받지 않으면 놓치는 위험은?',
  generated_content: `안녕하세요, 여러분의 건강을 책임지는 닥터보이스입니다.

오늘은 정기 검진의 중요성에 대해 이야기해 볼까 합니다. 많은 분들이 "나는 건강하니까 괜찮아"라고 생각하시지만, 사실 대부분의 질병은 초기에 증상이 없는 경우가 많습니다.

특히 고혈압, 당뇨, 암 같은 질환들은 초기에 발견하면 치료가 훨씬 쉽고, 완치율도 높아집니다. 하지만 증상이 나타난 후에 병원을 찾으시면 이미 병이 상당히 진행된 경우가 많죠.

정기 검진을 통해 확인할 수 있는 주요 항목들:
- 혈압 및 혈당 수치
- 콜레스테롤 수치
- 간 기능 검사
- 신장 기능 검사
- 암 표지자 검사

40대 이상이시라면 최소 1년에 한 번, 50대 이상이시라면 6개월에 한 번은 검진을 받으시는 것을 권장드립니다.

건강은 잃고 나서야 그 소중함을 알게 됩니다. 지금 바로 가까운 병원에서 검진 예약을 해보시는 건 어떨까요?

여러분의 건강한 내일을 응원합니다!`,
  seo_keywords: ['정기검진', '건강검진', '예방의학', '건강관리', '암검진'],
  original_content: '',
}

export function SavedPostsManager() {
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([])
  const [selectedPost, setSelectedPost] = useState<SavedPost | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [images, setImages] = useState<ImageRecord[]>([])
  const [positionStrategy, setPositionStrategy] = useState<'between' | 'even'>('between')
  const [isPublishing, setIsPublishing] = useState(false)

  // 네이버 로그인 설정
  const [showSettings, setShowSettings] = useState(false)
  const [tempUsername, setTempUsername] = useState('')
  const [tempPassword, setTempPassword] = useState('')
  const [saveCredentials, setSaveCredentials] = useState(true)

  // 훅
  const { credentials, isLoading: authLoading, saveCredentials: saveToServer, deleteCredentials } = useNaverAuth()
  const { isInstalled, isChecking, sendMessage, openInstallPage } = useChromeExtension()

  /**
   * 로컬 스토리지에서 저장된 글 로드
   */
  useEffect(() => {
    const loadSavedPosts = () => {
      try {
        const saved = localStorage.getItem('saved-posts')
        let posts: SavedPost[] = saved ? JSON.parse(saved) : []

        const hasSamplePost = posts.some((p) => p.id === SAMPLE_POST.id)
        if (!hasSamplePost) {
          posts = [...posts, SAMPLE_POST]
          localStorage.setItem('saved-posts', JSON.stringify(posts))
        }

        setSavedPosts(posts)
      } catch (error) {
        console.error('저장된 글 로드 실패:', error)
        setSavedPosts([SAMPLE_POST])
        localStorage.setItem('saved-posts', JSON.stringify([SAMPLE_POST]))
      }
    }

    loadSavedPosts()
    window.addEventListener('storage', loadSavedPosts)
    return () => window.removeEventListener('storage', loadSavedPosts)
  }, [])

  useEffect(() => {
    if (selectedPost) {
      setIsEditing(false)
    }
  }, [selectedPost])

  /**
   * 네이버 로그인 정보 저장
   */
  const handleSaveCredentials = async () => {
    if (!tempUsername.trim() || !tempPassword.trim()) {
      toast.error('아이디와 비밀번호를 입력해주세요')
      return
    }

    const success = await saveToServer(tempUsername, tempPassword)
    if (success) {
      setShowSettings(false)
      setTempUsername('')
      setTempPassword('')
      toast.success('네이버 로그인 정보가 저장되었습니다')
    }
  }

  /**
   * 네이버 로그인 정보 삭제
   */
  const handleDeleteCredentials = async () => {
    if (!confirm('저장된 로그인 정보를 삭제하시겠습니까?')) return

    const success = await deleteCredentials()
    if (success) {
      toast.success('로그인 정보가 삭제되었습니다')
    }
  }

  /**
   * 원클릭 네이버 발행
   */
  const handleOneClickPublish = async () => {
    if (!selectedPost) {
      toast.error('글을 선택해주세요')
      return
    }

    // 1. 크롬 확장 확인
    if (!isInstalled) {
      toast.error('크롬 확장 프로그램을 먼저 설치해주세요')
      openInstallPage()
      return
    }

    // 2. 로그인 정보 확인
    if (!credentials) {
      toast.error('네이버 로그인 정보를 먼저 설정해주세요')
      setShowSettings(true)
      return
    }

    // 3. 제목/본문 확인
    if (!selectedPost.title?.trim() && !selectedPost.generated_content?.trim()) {
      toast.error('제목 또는 본문이 비어있습니다')
      return
    }

    setIsPublishing(true)

    try {
      // 이미지 Base64 변환
      const base64Images: string[] = []

      if (images.length > 0) {
        toast.info(`${images.length}개의 이미지를 처리 중...`)

        for (const image of images) {
          const base64 = await blobToBase64(image.file)
          base64Images.push(base64)
        }
      }

      // 이미지 위치 계산
      const paragraphs = (selectedPost.generated_content || '').split('\n\n').filter((p) => p.trim())
      const imagePositions = calculateImagePositions(
        paragraphs.length,
        base64Images.length,
        positionStrategy
      )

      // 크롬 확장으로 메시지 전송
      toast.loading('네이버 블로그에 발행 중...')

      const response = await sendMessage('ONE_CLICK_PUBLISH', {
        title: selectedPost.title || selectedPost.suggested_titles?.[0] || '제목 없음',
        content: selectedPost.generated_content || '',
        images: base64Images,
        imagePositions,
        credentials: {
          id: credentials.username,
          pw: credentials.password,
        },
      })

      if (response.success) {
        toast.success('네이버 블로그에 발행되었습니다! 🎉')
      } else {
        throw new Error(response.error || '발행 실패')
      }
    } catch (error: any) {
      console.error('Publish error:', error)
      toast.error(error.message || '발행 중 오류가 발생했습니다')
    } finally {
      setIsPublishing(false)
    }
  }

  /**
   * 글 저장 (편집 후)
   */
  const handleSavePost = (title: string, content: string) => {
    if (!selectedPost) return

    const updatedPost: SavedPost = {
      ...selectedPost,
      title,
      generated_content: content,
      updated_at: new Date().toISOString(),
    }

    const updatedPosts = savedPosts.map((p) =>
      p.id === selectedPost.id ? updatedPost : p
    )

    setSavedPosts(updatedPosts)
    localStorage.setItem('saved-posts', JSON.stringify(updatedPosts))
    setSelectedPost(updatedPost)
    setIsEditing(false)

    toast.success('글이 저장되었습니다.')
  }

  /**
   * 글 삭제
   */
  const handleDeletePost = async (id: string) => {
    if (id === SAMPLE_POST.id) {
      toast.error('샘플 글은 삭제할 수 없습니다')
      return
    }

    if (!confirm('이 글을 삭제하시겠습니까?')) return

    try {
      await deleteImagesByPostId(id)
      const updated = savedPosts.filter((p) => p.id !== id)
      setSavedPosts(updated)
      localStorage.setItem('saved-posts', JSON.stringify(updated))

      if (selectedPost?.id === id) {
        setSelectedPost(null)
      }

      toast.success('글이 삭제되었습니다')
    } catch (error) {
      console.error('Delete error:', error)
      toast.error('글 삭제에 실패했습니다')
    }
  }

  const handleImagesChange = (newImages: ImageRecord[]) => {
    setImages(newImages)
  }

  // 로그인 정보 상태
  const hasLoginInfo = !!credentials
  const isReady = isInstalled && hasLoginInfo

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-3xl font-bold">저장된 글 관리</h1>
        <p className="text-gray-600 mt-2">
          원클릭으로 네이버 블로그에 자동 발행하세요
        </p>
      </div>

      {/* 네이버 로그인 설정 카드 */}
      <Card className="border-2 border-blue-200">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-blue-600" />
              <span>네이버 로그인 설정</span>
              {hasLoginInfo && (
                <span className="text-sm font-normal text-green-600 flex items-center gap-1">
                  <CheckCircle className="h-4 w-4" />
                  저장됨
                </span>
              )}
            </div>
            {!showSettings && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSettings(!showSettings)}
              >
                {hasLoginInfo ? '수정' : '설정'}
              </Button>
            )}
          </CardTitle>
        </CardHeader>

        {showSettings ? (
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="naver-id">네이버 아이디</Label>
              <Input
                id="naver-id"
                value={tempUsername}
                onChange={(e) => setTempUsername(e.target.value)}
                placeholder="네이버 아이디"
                autoComplete="username"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="naver-pw">비밀번호</Label>
              <Input
                id="naver-pw"
                type="password"
                value={tempPassword}
                onChange={(e) => setTempPassword(e.target.value)}
                placeholder="비밀번호"
                autoComplete="current-password"
              />
            </div>

            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-xs">
                로그인 정보는 AES 암호화되어 서버에 저장됩니다. 네이버 블로그 자동 발행에만 사용됩니다.
              </AlertDescription>
            </Alert>

            <div className="flex gap-2">
              <Button onClick={handleSaveCredentials} disabled={authLoading}>
                저장
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowSettings(false)
                  setTempUsername('')
                  setTempPassword('')
                }}
              >
                취소
              </Button>
              {hasLoginInfo && (
                <Button variant="destructive" onClick={handleDeleteCredentials}>
                  삭제
                </Button>
              )}
            </div>
          </CardContent>
        ) : hasLoginInfo ? (
          <CardContent>
            <Alert>
              <CheckCircle className="h-4 w-4" />
              <AlertTitle>설정 완료</AlertTitle>
              <AlertDescription>
                네이버 아이디: <strong>{credentials.username}</strong> (저장됨)
                <br />
                이제 글을 선택하고 "원클릭 발행" 버튼만 클릭하세요!
              </AlertDescription>
            </Alert>
          </CardContent>
        ) : (
          <CardContent>
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>설정 필요</AlertTitle>
              <AlertDescription>
                네이버 로그인 정보를 먼저 설정해주세요. 한 번만 설정하면 됩니다.
              </AlertDescription>
            </Alert>
          </CardContent>
        )}
      </Card>

      {/* 크롬 확장 프로그램 상태 */}
      {!isChecking && !isInstalled && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>크롬 확장 프로그램 미설치</AlertTitle>
          <AlertDescription>
            자동 발행을 위해 크롬 확장 프로그램을 설치해주세요.
            <Button
              onClick={openInstallPage}
              variant="outline"
              size="sm"
              className="mt-2"
            >
              확장 프로그램 설치하기
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* 메인 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 왼쪽: 글 목록 */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>저장된 글 ({savedPosts.length})</CardTitle>
            <CardDescription>클릭해서 선택하세요</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[700px] overflow-y-auto">
            {savedPosts.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>저장된 글이 없습니다</p>
              </div>
            ) : (
              savedPosts.map((post) => (
                <div
                  key={post.id}
                  onClick={() => setSelectedPost(post)}
                  className={`p-4 border rounded-lg cursor-pointer transition-all ${
                    selectedPost?.id === post.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <h3 className="font-semibold text-sm line-clamp-2">
                    {post.title || post.suggested_titles?.[0] || '제목 없음'}
                  </h3>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                    <Calendar className="w-3 h-3" />
                    {new Date(post.savedAt || post.created_at || Date.now()).toLocaleDateString(
                      'ko-KR'
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2 mt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedPost(post)
                        setIsEditing(false)
                      }}
                    >
                      <Eye className="w-3 h-3 mr-1" />
                      보기
                    </Button>
                    <Button
                      size="sm"
                      variant="default"
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedPost(post)
                        setIsEditing(true)
                      }}
                    >
                      <Edit3 className="w-3 h-3 mr-1" />
                      편집
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeletePost(post.id)
                      }}
                      disabled={post.id === SAMPLE_POST.id}
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* 오른쪽: 편집 + 이미지 + 발행 */}
        <div className="lg:col-span-2 space-y-6">
          {!selectedPost ? (
            <Card>
              <CardContent className="pt-12 pb-12">
                <div className="text-center text-gray-500">
                  <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">왼쪽에서 글을 선택하세요</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* 편집 영역 또는 미리보기 */}
              {isEditing ? (
                <PostEditor
                  post={selectedPost}
                  onSave={handleSavePost}
                  onCancel={() => setIsEditing(false)}
                />
              ) : (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span>글 미리보기</span>
                      <Button onClick={() => setIsEditing(true)} size="sm" className="gap-2">
                        <Edit3 className="h-4 w-4" />
                        편집
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <h3 className="text-xl font-bold mb-4">
                        {selectedPost.title || selectedPost.suggested_titles?.[0] || '제목 없음'}
                      </h3>
                      <div className="prose prose-sm max-w-none bg-gray-50 p-4 rounded-lg max-h-[400px] overflow-y-auto whitespace-pre-wrap">
                        {selectedPost.generated_content || selectedPost.content || '본문 없음'}
                      </div>
                    </div>

                    {selectedPost.seo_keywords && selectedPost.seo_keywords.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        <span className="text-sm text-gray-600 font-medium">키워드:</span>
                        {selectedPost.seo_keywords.map((keyword: string, i: number) => (
                          <span
                            key={i}
                            className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* 이미지 관리 */}
              <ImageManager postId={selectedPost.id} onImagesChange={handleImagesChange} />

              {/* 원클릭 발행 */}
              <Card className="border-2 border-green-200">
                <CardHeader>
                  <CardTitle className="text-green-700">🚀 원클릭 네이버 발행</CardTitle>
                  <CardDescription>
                    버튼 한 번 클릭으로 자동 발행됩니다
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isReady ? (
                    <Alert className="bg-green-50 border-green-200">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      <AlertTitle className="text-green-800">발행 준비 완료!</AlertTitle>
                      <AlertDescription className="text-green-700">
                        • 네이버 로그인: ✓ 저장됨
                        <br />
                        • 크롬 확장: ✓ 설치됨
                        <br />• 이미지: {images.length}개
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>발행 준비 미완료</AlertTitle>
                      <AlertDescription>
                        {!hasLoginInfo && '• 네이버 로그인 정보 설정 필요'}
                        <br />
                        {!isInstalled && '• 크롬 확장 프로그램 설치 필요'}
                      </AlertDescription>
                    </Alert>
                  )}

                  <Button
                    onClick={handleOneClickPublish}
                    disabled={isPublishing || !isReady}
                    size="lg"
                    className="w-full bg-green-600 hover:bg-green-700 text-white gap-2"
                  >
                    {isPublishing ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        발행 중...
                      </>
                    ) : (
                      <>
                        <Send className="h-5 w-5" />
                        원클릭 발행 (이미지 {images.length}개 포함)
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * 글 저장 훅 (다른 컴포넌트에서 사용)
 */
export function useSavePost() {
  const savePost = (post: Record<string, any>) => {
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
