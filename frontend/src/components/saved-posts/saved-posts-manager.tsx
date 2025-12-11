'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

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
  Globe,
  ExternalLink,
  Send,
  Edit3,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
// 저장된 글 타입 (간단한 버전)
interface SavedPost {
  id: string
  savedAt: string
  suggested_titles?: string[]
  generated_content?: string
  seo_keywords?: string[]
  original_content?: string
  title?: string
  content?: string
  // DB에서 온 글 식별용
  sourcePostId?: string
  sourceType?: 'database' | 'local'
}

// 샘플 글 (항상 유지)
const SAMPLE_POST: SavedPost = {
  id: 'sample-post-001',
  savedAt: '2025-01-01T00:00:00.000Z',
  suggested_titles: ['정기 검진을 받지 않으면 놓치는 위험은?'],
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
  const router = useRouter()
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([])
  const [selectedPost, setSelectedPost] = useState<SavedPost | null>(null)
  const [uploadedImages, setUploadedImages] = useState<File[]>([])
  const [imagePreview, setImagePreview] = useState<string[]>([])
  const [distributionStrategy, setDistributionStrategy] = useState<'even' | 'paragraphs'>('paragraphs')
  const [extensionInstalled, setExtensionInstalled] = useState(false)

  // 원클릭 발행 관련 상태
  const [publishDialogOpen, setPublishDialogOpen] = useState(false)
  const [naverId, setNaverId] = useState('')
  const [naverPw, setNaverPw] = useState('')
  const [saveLogin, setSaveLogin] = useState(true)
  const [publishing, setPublishing] = useState(false)
  const [extensionId, setExtensionId] = useState<string | null>(null)
  const [extensionConnected, setExtensionConnected] = useState<boolean | null>(null)

  // 크롬 확장 프로그램 설치 여부 확인
  useEffect(() => {
    // 확장 프로그램이 설치되면 window에 메시지를 보낼 수 있음
    const checkExtension = () => {
      if (typeof window !== 'undefined' && (window as any).doctorvoiceExtension) {
        setExtensionInstalled(true)
      }
    }
    checkExtension()
    window.addEventListener('message', (e) => {
      if (e.data?.type === 'DOCTORVOICE_EXTENSION_READY') {
        setExtensionInstalled(true)
      }
    })
  }, [])

  // 로컬 스토리지에서 저장된 글 로드 (샘플 글 항상 포함)
  useEffect(() => {
    const loadSavedPosts = () => {
      try {
        const saved = localStorage.getItem('saved-posts')
        let posts: SavedPost[] = saved ? JSON.parse(saved) : []

        // 샘플 글이 없으면 추가
        const hasSamplePost = posts.some(p => p.id === SAMPLE_POST.id)
        if (!hasSamplePost) {
          posts = [...posts, SAMPLE_POST]
          localStorage.setItem('saved-posts', JSON.stringify(posts))
        }

        setSavedPosts(posts)

        // 자동 선택할 글이 있는지 확인
        const selectId = localStorage.getItem('saved-posts-select')
        if (selectId) {
          const postToSelect = posts.find(p => p.id === selectId)
          if (postToSelect) {
            setSelectedPost(postToSelect)
            // 사용 후 제거
            localStorage.removeItem('saved-posts-select')
          }
        }
      } catch (error) {
        console.error('저장된 글 로드 실패:', error)
        // 오류 시 샘플 글만이라도 표시
        setSavedPosts([SAMPLE_POST])
        localStorage.setItem('saved-posts', JSON.stringify([SAMPLE_POST]))
      }
    }

    loadSavedPosts()

    // 다른 탭에서 저장한 경우를 위한 이벤트 리스너
    window.addEventListener('storage', loadSavedPosts)
    return () => window.removeEventListener('storage', loadSavedPosts)
  }, [])

  // 글 저장 함수 (create page에서 호출)
  const savePost = (post: Partial<SavedPost>) => {
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

  // 글 삭제 (샘플 글은 삭제 불가)
  const deletePost = (id: string) => {
    // 샘플 글은 삭제 불가
    if (id === SAMPLE_POST.id) {
      toast.error('샘플 글은 삭제할 수 없습니다')
      return
    }

    const updated = savedPosts.filter((p) => p.id !== id)
    setSavedPosts(updated)
    localStorage.setItem('saved-posts', JSON.stringify(updated))

    if (selectedPost?.id === id) {
      setSelectedPost(null)
    }

    toast.success('글이 삭제되었습니다')
  }

  // 이미지 폴더 선택
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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

    toast.success(`${imageFiles.length}개의 이미지가 업로드되었습니다`, {
      description: '자동으로 워드 문서를 생성하고 있습니다...'
    })

    // 자동으로 워드 다운로드 실행
    if (selectedPost) {
      // 짧은 딜레이 후 자동 다운로드 (UI 업데이트 대기)
      setTimeout(() => {
        exportWithImagesAuto(imageFiles)
      }, 500)
    }
  }

  // 블로그 자동 포스팅용 데이터 전송
  const sendToExtension = (post: SavedPost) => {
    const postData = {
      title: post.suggested_titles?.[0] || '',
      content: post.generated_content || '',
      keywords: post.seo_keywords || [],
      images: imagePreview || [],
    }

    // localStorage에 저장 (확장 프로그램에서 읽음)
    localStorage.setItem('doctorvoice-pending-post', JSON.stringify(postData))

    // 확장 프로그램에 메시지 전송 시도
    try {
      window.postMessage({
        type: 'DOCTORVOICE_POST_DATA',
        data: postData
      }, '*')
    } catch (e) {
      console.log('Extension message failed, using localStorage fallback')
    }

    toast.success('포스팅 데이터가 준비되었습니다!', {
      description: '크롬 확장 프로그램 아이콘을 클릭하여 포스팅을 시작하세요'
    })
  }

  // 확장 프로그램 다운로드
  const downloadExtension = () => {
    const link = document.createElement('a')
    link.href = '/doctorvoice-chrome-extension.zip'
    link.download = 'doctorvoice-chrome-extension.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast.success('확장 프로그램 다운로드 시작', {
      description: 'ZIP 파일을 압축 해제 후 크롬에 설치하세요'
    })
  }

  // ============================================
  // 원클릭 발행 관련 함수들
  // ============================================

  // 저장된 로그인 정보 로드
  const loadSavedCredentials = () => {
    try {
      const saved = localStorage.getItem('naver-credentials')
      if (saved) {
        const { id, pw } = JSON.parse(saved)
        setNaverId(id || '')
        setNaverPw(pw || '')
      }
    } catch (e) {
      console.error('로그인 정보 로드 실패:', e)
    }
  }

  // 확장 프로그램 연결 확인
  const checkExtensionConnection = async () => {
    const savedExtensionId = localStorage.getItem('doctorvoice-extension-id')
    if (savedExtensionId) {
      try {
        const response = await sendMessageToExtension(savedExtensionId, { action: 'PING' })
        if (response?.success) {
          setExtensionConnected(true)
          setExtensionId(savedExtensionId)
          return
        }
      } catch (e) {
        localStorage.removeItem('doctorvoice-extension-id')
      }
    }
    setExtensionConnected(false)
  }

  // 확장 프로그램에 메시지 보내기
  const sendMessageToExtension = (extId: string, message: any): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
        reject(new Error('Chrome API not available'))
        return
      }
      try {
        chrome.runtime.sendMessage(extId, message, (response: any) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError)
          } else {
            resolve(response)
          }
        })
      } catch (e) {
        reject(e)
      }
    })
  }

  // 발행 다이얼로그 열기
  const openPublishDialog = (post: SavedPost) => {
    setSelectedPost(post)
    loadSavedCredentials()
    checkExtensionConnection()
    setPublishDialogOpen(true)
  }

  // 이미지를 Base64로 변환 (압축 포함)
  const imageToBase64 = (file: File, maxWidth = 1200, quality = 0.8): Promise<string> => {
    return new Promise((resolve, reject) => {
      // 이미지가 1MB 이하면 압축 없이 변환
      if (file.size < 1024 * 1024) {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = reject
        reader.readAsDataURL(file)
        return
      }

      // 큰 이미지는 압축
      const img = new window.Image()
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')

      img.onload = () => {
        let width = img.width
        let height = img.height

        // 최대 너비 제한
        if (width > maxWidth) {
          height = (height * maxWidth) / width
          width = maxWidth
        }

        canvas.width = width
        canvas.height = height
        ctx?.drawImage(img, 0, 0, width, height)

        const compressedBase64 = canvas.toDataURL('image/jpeg', quality)
        resolve(compressedBase64)
      }

      img.onerror = reject
      img.src = URL.createObjectURL(file)
    })
  }

  // 원클릭 발행 실행
  const handleOneClickPublish = async () => {
    if (!selectedPost) return
    if (!naverId || !naverPw) {
      toast.error('네이버 아이디와 비밀번호를 입력하세요')
      return
    }

    setPublishing(true)
    const loadingToast = toast.loading('발행 준비 중...')

    try {
      // 로그인 정보 저장
      if (saveLogin) {
        localStorage.setItem('naver-credentials', JSON.stringify({ id: naverId, pw: naverPw }))
      }

      // 이미지 Base64 변환
      toast.loading('이미지 변환 중...', { id: loadingToast })
      const imageBase64List: string[] = []
      for (const file of uploadedImages) {
        const base64 = await imageToBase64(file)
        imageBase64List.push(base64)
      }

      // 포스트 데이터 준비
      const postData = {
        title: selectedPost.suggested_titles?.[0] || selectedPost.title || '',
        content: selectedPost.generated_content || selectedPost.content || '',
        images: imageBase64List,
        keywords: selectedPost.seo_keywords || [],
      }

      toast.loading('네이버 블로그 발행 시작...', { id: loadingToast })

      if (extensionId) {
        // 확장 프로그램으로 직접 발행
        const response = await sendMessageToExtension(extensionId, {
          action: 'ONE_CLICK_PUBLISH',
          postData,
          credentials: { id: naverId, pw: naverPw },
          options: { useQuote: true, useHighlight: true, useImages: true }
        })

        if (response?.success) {
          toast.success('발행 시작됨!', {
            id: loadingToast,
            description: '새 탭에서 네이버 로그인 후 자동으로 글이 작성됩니다',
          })
          setPublishDialogOpen(false)
        } else {
          throw new Error(response?.error || '발행 시작 실패')
        }
      } else {
        // 확장 프로그램 없음 - localStorage 방식
        const existingPosts = JSON.parse(localStorage.getItem('saved-posts') || '[]')
        const postToSave = {
          ...selectedPost,
          images: imageBase64List,
          pendingPublish: true,
        }
        const postIndex = existingPosts.findIndex((p: any) => p.id === selectedPost.id)
        if (postIndex >= 0) {
          existingPosts[postIndex] = postToSave
        }
        localStorage.setItem('saved-posts', JSON.stringify(existingPosts))

        toast.success('발행 준비 완료!', {
          id: loadingToast,
          description: '확장 프로그램 아이콘을 클릭하여 발행하세요',
        })
        setPublishDialogOpen(false)
      }

    } catch (error: any) {
      console.error('발행 실패:', error)
      toast.error('발행 실패', {
        id: loadingToast,
        description: error.message || '다시 시도해주세요',
      })
    } finally {
      setPublishing(false)
    }
  }

  // 확장 프로그램 ID 직접 입력
  const handleSetExtensionId = async () => {
    const id = prompt('확장 프로그램 ID를 입력하세요 (chrome://extensions에서 확인)')
    if (id) {
      try {
        const response = await sendMessageToExtension(id, { action: 'PING' })
        if (response?.success) {
          setExtensionConnected(true)
          setExtensionId(id)
          localStorage.setItem('doctorvoice-extension-id', id)
          toast.success('확장 프로그램 연결 성공!')
        } else {
          toast.error('확장 프로그램을 찾을 수 없습니다')
        }
      } catch (e) {
        toast.error('확장 프로그램 연결 실패')
      }
    }
  }

  // 자동 다운로드용 함수 (이미지 파일 직접 전달)
  const exportWithImagesAuto = async (images: File[]) => {
    if (!selectedPost) return

    const loadingToast = toast.loading('이미지와 함께 워드 문서를 생성하고 있습니다...')

    try {
      const formData = new FormData()
      formData.append('content', selectedPost.generated_content || '')
      formData.append('title', selectedPost.suggested_titles?.[0] || '')
      formData.append('keywords', JSON.stringify(selectedPost.seo_keywords || []))
      formData.append('emphasis_phrases', JSON.stringify([]))
      formData.append('distribution_strategy', distributionStrategy)

      // 이미지 추가
      images.forEach((file) => {
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

      toast.success('워드 문서 다운로드 완료!', {
        id: loadingToast,
        description: '이미지가 포함된 워드 파일이 저장되었습니다'
      })
    } catch (error) {
      console.error('Export error:', error)
      toast.error('워드 문서 생성 실패', {
        id: loadingToast,
      })
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
        <Button
          variant="outline"
          onClick={downloadExtension}
          className="gap-2"
        >
          <Globe className="w-4 h-4" />
          확장 프로그램 다운로드
        </Button>
      </div>

      {/* 확장 프로그램 안내 카드 */}
      <Card className="border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <Globe className="w-8 h-8 text-purple-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-bold text-lg text-purple-900">네이버 블로그 자동 포스팅</h3>
              <p className="text-sm text-purple-700 mt-1">
                크롬 확장 프로그램을 설치하면 클릭 한 번으로 네이버 블로그에 자동 포스팅할 수 있습니다.
                인용구, 배경색, 이미지가 자동으로 적용됩니다.
              </p>
              <div className="flex gap-3 mt-3">
                <Button size="sm" onClick={downloadExtension} className="gap-2 bg-purple-600 hover:bg-purple-700">
                  <Download className="w-4 h-4" />
                  다운로드 (.zip)
                </Button>
                <Button size="sm" variant="outline" onClick={() => window.open('chrome://extensions', '_blank')} className="gap-2">
                  <ExternalLink className="w-4 h-4" />
                  설치 방법 보기
                </Button>
              </div>
              <div className="mt-4 p-3 bg-white/60 rounded-lg">
                <p className="text-xs font-medium text-purple-900 mb-2">설치 방법 (간단 3단계)</p>
                <ol className="text-xs text-purple-800 space-y-1 list-decimal list-inside">
                  <li>ZIP 파일 다운로드 후 압축 해제</li>
                  <li>크롬 주소창에 <code className="bg-purple-100 px-1 rounded">chrome://extensions</code> 입력</li>
                  <li>"개발자 모드" 켜고 → "압축해제된 확장 프로그램 로드" → 폴더 선택</li>
                </ol>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

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
                      : post.sourceType === 'database'
                      ? 'border-green-200 hover:border-green-300 bg-green-50/30'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-sm line-clamp-2 flex-1">
                      {post.suggested_titles?.[0] || post.title || '제목 없음'}
                    </h3>
                    {post.sourceType === 'database' && (
                      <span className="flex-shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-medium rounded">
                        <Database className="w-2.5 h-2.5" />
                        DB
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                    <Calendar className="w-3 h-3" />
                    {new Date(post.savedAt).toLocaleDateString('ko-KR')}
                  </div>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <Button
                      size="sm"
                      variant="default"
                      className="bg-blue-600 hover:bg-blue-700"
                      onClick={(e) => {
                        e.stopPropagation()
                        router.push(`/dashboard/editor/${post.id}`)
                      }}
                    >
                      <Edit3 className="w-3 h-3 mr-1" />
                      에디터
                    </Button>
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
                    이미지 업로드 ({uploadedImages.length})
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
                    <Label>이미지 폴더 업로드 (폴더 전체 선택 가능)</Label>
                    <input
                      type="file"
                      multiple
                      {...({webkitdirectory: "", directory: ""} as any)}
                      accept="image/*,.jpg,.jpeg,.png,.gif,.webp"
                      onChange={handleImageUpload}
                      className="mt-2 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      JPG, PNG, GIF, WEBP 형식 지원. 폴더를 선택하면 안에 있는 모든 이미지가 자동으로 업로드됩니다.
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
                        size="sm"
                      >
                        문단 사이 (추천)
                      </Button>
                      <Button
                        variant={distributionStrategy === 'even' ? 'default' : 'outline'}
                        onClick={() => setDistributionStrategy('even')}
                        size="sm"
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

                  {/* 자동 다운로드 안내 */}
                  {uploadedImages.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <h4 className="font-semibold text-green-900 mb-2">
                        ✅ 이미지 {uploadedImages.length}개가 업로드되었습니다!
                      </h4>
                      <p className="text-sm text-green-800 mb-2">
                        워드 문서가 자동으로 생성 중입니다. 잠시만 기다려주세요...
                      </p>
                      <div className="mt-3 pt-3 border-t border-green-300">
                        <p className="text-xs text-green-900 font-semibold mb-1">📋 네이버 블로그 복붙 방법:</p>
                        <ol className="text-xs text-green-800 space-y-1 list-decimal list-inside">
                          <li>다운로드된 .docx 파일 열기</li>
                          <li>전체 선택 (Ctrl+A)</li>
                          <li>복사 (Ctrl+C)</li>
                          <li>네이버 블로그에 붙여넣기 (Ctrl+V)</li>
                        </ol>
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 원클릭 발행 다이얼로그 */}
      <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-5 w-5 text-green-600" />
              네이버 블로그 원클릭 발행
            </DialogTitle>
            <DialogDescription>
              선택한 글을 네이버 블로그에 자동으로 발행합니다
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* 확장 프로그램 상태 */}
            {extensionConnected === false && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <p className="font-medium text-amber-800">확장 프로그램 연결 필요</p>
                    <p className="text-amber-600 mt-1">
                      자동 발행을 위해 확장 프로그램 ID를 연결하세요
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={handleSetExtensionId}
                    >
                      확장 프로그램 ID 입력
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {extensionConnected === true && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="text-sm font-medium">확장 프로그램 연결됨</span>
                </div>
              </div>
            )}

            {/* 네이버 로그인 정보 */}
            <div className="space-y-3">
              <div className="space-y-2">
                <Label>네이버 아이디</Label>
                <Input
                  placeholder="네이버 아이디"
                  value={naverId}
                  onChange={(e) => setNaverId(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>비밀번호</Label>
                <Input
                  type="password"
                  placeholder="비밀번호"
                  value={naverPw}
                  onChange={(e) => setNaverPw(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="saveLoginDialog"
                  checked={saveLogin}
                  onChange={(e) => setSaveLogin(e.target.checked)}
                  className="rounded"
                />
                <Label htmlFor="saveLoginDialog" className="text-sm cursor-pointer">
                  로그인 정보 저장
                </Label>
              </div>
            </div>

            {/* 이미지 업로드 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Image className="h-4 w-4" />
                이미지 추가 (선택)
              </Label>
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={handleImageUpload}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
              {uploadedImages.length > 0 && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    {uploadedImages.length}개의 이미지가 함께 발행됩니다
                  </p>
                  <div className="grid grid-cols-4 gap-2 mt-2">
                    {imagePreview.slice(0, 4).map((preview, i) => (
                      <img
                        key={i}
                        src={preview}
                        alt=""
                        className="w-full h-12 object-cover rounded"
                      />
                    ))}
                    {uploadedImages.length > 4 && (
                      <div className="w-full h-12 bg-gray-200 rounded flex items-center justify-center text-xs text-gray-600">
                        +{uploadedImages.length - 4}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* 발행할 글 미리보기 */}
            {selectedPost && (
              <div className="p-3 bg-gray-50 rounded-lg space-y-1">
                <p className="text-sm font-medium truncate">
                  {selectedPost.suggested_titles?.[0] || selectedPost.title || '제목 없음'}
                </p>
                <p className="text-xs text-gray-500">
                  {(selectedPost.generated_content || selectedPost.content || '').slice(0, 100)}...
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setPublishDialogOpen(false)}>
              취소
            </Button>
            <Button
              className="bg-green-600 hover:bg-green-700 gap-2"
              onClick={handleOneClickPublish}
              disabled={publishing || !naverId || !naverPw}
            >
              {publishing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  발행 중...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  원클릭 발행
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// 전역 함수로 내보내기 (다른 컴포넌트에서 사용)
export function useSavePost() {
  const savePost = (post: Record<string, any>) => {
    const savedPost = {
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
