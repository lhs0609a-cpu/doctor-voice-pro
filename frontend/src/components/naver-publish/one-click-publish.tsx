'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { Send, Upload, Image as ImageIcon, X, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import type { Post } from '@/types'

// 확장 프로그램 ID (manifest.json의 key로 고정됨)
// 실제 배포 시 확장 프로그램 ID로 교체 필요
const EXTENSION_IDS = [
  'YOUR_EXTENSION_ID_HERE', // 실제 확장 프로그램 ID
  // 개발 환경에서는 chrome://extensions에서 확인
]

interface OneClickPublishProps {
  post: Post
}

export function OneClickPublish({ post }: OneClickPublishProps) {
  const [open, setOpen] = useState(false)
  const [naverId, setNaverId] = useState('')
  const [naverPw, setNaverPw] = useState('')
  const [saveLogin, setSaveLogin] = useState(true)
  const [images, setImages] = useState<{ file: File; preview: string }[]>([])
  const [publishing, setPublishing] = useState(false)
  const [extensionInstalled, setExtensionInstalled] = useState<boolean | null>(null)
  const [extensionId, setExtensionId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 저장된 로그인 정보 불러오기
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

  // 확장 프로그램 설치 확인
  const checkExtension = async () => {
    // localStorage에서 저장된 확장 프로그램 ID 확인
    const savedExtensionId = localStorage.getItem('doctorvoice-extension-id')
    if (savedExtensionId) {
      try {
        const response = await sendMessageToExtension(savedExtensionId, { action: 'PING' })
        if (response?.success) {
          setExtensionInstalled(true)
          setExtensionId(savedExtensionId)
          return
        }
      } catch (e) {
        // 저장된 ID가 더 이상 유효하지 않음
        localStorage.removeItem('doctorvoice-extension-id')
      }
    }

    // 알려진 확장 프로그램 ID들 시도
    for (const id of EXTENSION_IDS) {
      if (id === 'YOUR_EXTENSION_ID_HERE') continue
      try {
        const response = await sendMessageToExtension(id, { action: 'PING' })
        if (response?.success) {
          setExtensionInstalled(true)
          setExtensionId(id)
          localStorage.setItem('doctorvoice-extension-id', id)
          return
        }
      } catch (e) {
        continue
      }
    }

    setExtensionInstalled(false)
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

  // 모달 열기
  const handleOpen = () => {
    loadSavedCredentials()
    checkExtension()
    setOpen(true)
  }

  // 이미지 업로드
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const imageFiles = files.filter(f => f.type.startsWith('image/'))

    const newImages = imageFiles.map(file => ({
      file,
      preview: URL.createObjectURL(file),
    }))

    setImages(prev => [...prev, ...newImages])
  }

  // 이미지 제거
  const removeImage = (index: number) => {
    setImages(prev => {
      const newImages = [...prev]
      URL.revokeObjectURL(newImages[index].preview)
      newImages.splice(index, 1)
      return newImages
    })
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

  // 원클릭 발행 - 버튼 하나로 전체 자동화
  const handleOneClickPublish = async () => {
    if (!naverId || !naverPw) {
      toast.error('네이버 아이디와 비밀번호를 입력하세요')
      return
    }

    setPublishing(true)
    const loadingToast = toast.loading('발행 준비 중...')

    try {
      // 1. 로그인 정보 저장
      if (saveLogin) {
        localStorage.setItem('naver-credentials', JSON.stringify({ id: naverId, pw: naverPw }))
      }

      // 2. 이미지 Base64 변환
      toast.loading('이미지 변환 중...', { id: loadingToast })
      const imageBase64List: string[] = []
      for (const img of images) {
        const base64 = await imageToBase64(img.file)
        imageBase64List.push(base64)
      }

      // 3. 포스트 데이터 준비
      const postData = {
        title: post.title || post.suggested_titles?.[0] || '',
        content: post.generated_content || '',
        images: imageBase64List,
        keywords: post.seo_keywords || [],
        hashtags: post.hashtags || [],
      }

      // 4. 확장 프로그램으로 데이터 전송 및 발행 시작
      toast.loading('네이버 블로그 발행 시작...', { id: loadingToast })

      if (extensionId) {
        // 확장 프로그램이 설치된 경우 - 직접 통신
        const response = await sendMessageToExtension(extensionId, {
          action: 'ONE_CLICK_PUBLISH',
          postData,
          credentials: { id: naverId, pw: naverPw },
          options: {
            useQuote: true,
            useHighlight: true,
            useImages: true,
          }
        })

        if (response?.success) {
          toast.success('발행 시작됨!', {
            id: loadingToast,
            description: '새 탭에서 네이버 로그인 후 자동으로 글이 작성됩니다',
          })
          setOpen(false)
        } else {
          throw new Error(response?.error || '발행 시작 실패')
        }
      } else {
        // 확장 프로그램이 없는 경우 - localStorage 방식 (팝업 필요)
        const existingPosts = JSON.parse(localStorage.getItem('saved-posts') || '[]')
        const postToSave = {
          id: post.id || `post-${Date.now()}`,
          title: postData.title,
          content: postData.content,
          generated_content: postData.content,
          images: imageBase64List,
          savedAt: Date.now(),
          pendingPublish: true,
        }

        const postIndex = existingPosts.findIndex((p: any) => p.id === postToSave.id)
        if (postIndex >= 0) {
          existingPosts[postIndex] = postToSave
        } else {
          existingPosts.unshift(postToSave)
        }
        localStorage.setItem('saved-posts', JSON.stringify(existingPosts))

        toast.success('발행 준비 완료!', {
          id: loadingToast,
          description: '확장 프로그램 아이콘을 클릭하여 발행하세요',
        })
        setOpen(false)
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
          setExtensionInstalled(true)
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

  return (
    <>
      <Button
        className="w-full bg-green-600 hover:bg-green-700 gap-2"
        size="lg"
        onClick={handleOpen}
      >
        <Send className="h-4 w-4" />
        네이버 블로그 발행
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-5 w-5 text-green-600" />
              네이버 블로그 원클릭 발행
            </DialogTitle>
            <DialogDescription>
              이미지 추가 후 발행 버튼 하나로 자동으로 글이 작성됩니다
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* 확장 프로그램 상태 */}
            {extensionInstalled === false && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <p className="font-medium text-amber-800">확장 프로그램 연결 필요</p>
                    <p className="text-amber-600 mt-1">
                      자동 발행을 위해 확장 프로그램을 설치하고 ID를 연결하세요
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

            {extensionInstalled === true && (
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
                  id="saveLogin"
                  checked={saveLogin}
                  onChange={(e) => setSaveLogin(e.target.checked)}
                  className="rounded"
                />
                <Label htmlFor="saveLogin" className="text-sm cursor-pointer">
                  로그인 정보 저장
                </Label>
              </div>
            </div>

            {/* 이미지 업로드 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4" />
                이미지 추가 (선택)
              </Label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4 mr-2" />
                이미지 업로드
              </Button>

              {images.length > 0 && (
                <div className="grid grid-cols-4 gap-2 mt-2">
                  {images.map((img, index) => (
                    <div key={index} className="relative group">
                      <img
                        src={img.preview}
                        alt=""
                        className="w-full h-16 object-cover rounded border"
                      />
                      <button
                        onClick={() => removeImage(index)}
                        className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 발행할 글 미리보기 */}
            <div className="p-3 bg-gray-50 rounded-lg space-y-1">
              <p className="text-sm font-medium truncate">
                {post.title || post.suggested_titles?.[0] || '제목 없음'}
              </p>
              <p className="text-xs text-gray-500">
                {(post.generated_content || '').slice(0, 100)}...
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
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
    </>
  )
}
