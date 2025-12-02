/**
 * NaverPublishButton Component
 * 네이버 블로그 통합 발행 버튼
 */

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { toast } from 'sonner'
import { Send, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { useNaverAuth } from '@/hooks/useNaverAuth'
import { useChromeExtension } from '@/hooks/useChromeExtension'
import { blobToBase64, calculateImagePositions } from '@/lib/image-utils'
import type { ImageRecord } from '@/lib/indexeddb'
import type { SavedPost } from './post-editor'

interface NaverPublishButtonProps {
  post: SavedPost
  images: ImageRecord[]
  positionStrategy?: 'between' | 'even'
  disabled?: boolean
}

export const NaverPublishButton: React.FC<NaverPublishButtonProps> = ({
  post,
  images,
  positionStrategy = 'between',
  disabled = false,
}) => {
  const { credentials, loadCredentials, saveCredentials, hasCredentials } = useNaverAuth()
  const { isInstalled, isChecking, sendMessage, openInstallPage } = useChromeExtension()

  const [isPublishing, setIsPublishing] = useState(false)
  const [showLoginDialog, setShowLoginDialog] = useState(false)
  const [showExtensionDialog, setShowExtensionDialog] = useState(false)

  // 로그인 폼 상태
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [shouldSave, setShouldSave] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  /**
   * 발행 전 체크
   */
  const checkBeforePublish = (): boolean => {
    // 제목 또는 본문 확인
    if (!post.title?.trim() && !post.generated_content?.trim()) {
      toast.error('제목 또는 본문이 비어있습니다.')
      return false
    }

    // 크롬 확장 확인
    if (!isInstalled) {
      setShowExtensionDialog(true)
      return false
    }

    // 로그인 정보 확인
    if (!hasCredentials()) {
      setShowLoginDialog(true)
      return false
    }

    return true
  }

  /**
   * 네이버 블로그 발행
   */
  const handlePublish = async () => {
    if (!checkBeforePublish()) {
      return
    }

    setIsPublishing(true)

    try {
      // 1. 이미지 Base64 변환
      const base64Images: string[] = []

      if (images.length > 0) {
        toast.info(`${images.length}개의 이미지를 처리 중...`)

        for (let i = 0; i < images.length; i++) {
          const image = images[i]
          const base64 = await blobToBase64(image.file)
          base64Images.push(base64)
        }
      }

      // 2. 이미지 위치 계산
      const paragraphs = (post.generated_content || '').split('\n\n').filter((p) => p.trim())
      const imagePositions = calculateImagePositions(
        paragraphs.length,
        base64Images.length,
        positionStrategy
      )

      // 3. 크롬 확장으로 메시지 전송
      toast.info('네이버 블로그에 발행 중...')

      const response = await sendMessage('ONE_CLICK_PUBLISH', {
        title: post.title || '제목 없음',
        content: post.generated_content || '',
        images: base64Images,
        imagePositions,
        credentials: credentials
          ? {
              id: credentials.username,
              pw: credentials.password,
            }
          : undefined,
      })

      if (response.success) {
        toast.success('네이버 블로그에 발행되었습니다!')
      } else {
        throw new Error(response.error || '발행 실패')
      }
    } catch (error: any) {
      console.error('Publish error:', error)
      const errorMsg = error.message || '발행 중 오류가 발생했습니다.'
      toast.error(errorMsg)
    } finally {
      setIsPublishing(false)
    }
  }

  /**
   * 로그인 정보 저장
   */
  const handleSaveLogin = async () => {
    if (!username.trim() || !password.trim()) {
      toast.error('아이디와 비밀번호를 입력해주세요.')
      return
    }

    setIsSaving(true)

    try {
      if (shouldSave) {
        // 서버에 저장
        const success = await saveCredentials(username, password)
        if (!success) {
          throw new Error('저장 실패')
        }
      }

      // 다이얼로그 닫기
      setShowLoginDialog(false)

      // 발행 진행
      setTimeout(() => {
        handlePublish()
      }, 500)
    } catch (error: any) {
      console.error('Save login error:', error)
      toast.error('로그인 정보 저장에 실패했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  // 발행 버튼 비활성화 조건
  const isDisabled =
    disabled ||
    isPublishing ||
    isChecking ||
    !post.title?.trim() ||
    !post.generated_content?.trim()

  return (
    <>
      {/* 발행 버튼 */}
      <Button
        onClick={handlePublish}
        disabled={isDisabled}
        size="lg"
        className="w-full gap-2"
      >
        {isPublishing ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            발행 중...
          </>
        ) : (
          <>
            <Send className="h-5 w-5" />
            네이버 블로그 발행
          </>
        )}
      </Button>

      {/* 상태 안내 */}
      {!isInstalled && !isChecking && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>크롬 확장 프로그램 미설치</AlertTitle>
          <AlertDescription>
            네이버 블로그 자동 포스팅을 위해 크롬 확장 프로그램을 설치해주세요.
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

      {isInstalled && hasCredentials() && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertTitle>발행 준비 완료</AlertTitle>
          <AlertDescription>
            네이버 로그인 정보가 저장되어 있습니다. 발행 버튼을 눌러주세요.
          </AlertDescription>
        </Alert>
      )}

      {/* 로그인 다이얼로그 */}
      <Dialog open={showLoginDialog} onOpenChange={setShowLoginDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>네이버 로그인 정보 입력</DialogTitle>
            <DialogDescription>
              네이버 블로그 자동 발행을 위해 로그인 정보를 입력해주세요.
              <br />
              정보는 안전하게 암호화되어 서버에 저장됩니다.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="naver-id">네이버 아이디</Label>
              <Input
                id="naver-id"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="네이버 아이디"
                autoComplete="username"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="naver-pw">비밀번호</Label>
              <Input
                id="naver-pw"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호"
                autoComplete="current-password"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="save-credentials"
                checked={shouldSave}
                onCheckedChange={(checked) => setShouldSave(checked === true)}
              />
              <Label
                htmlFor="save-credentials"
                className="text-sm font-normal cursor-pointer"
              >
                로그인 정보 저장 (다음에 자동 입력)
              </Label>
            </div>

            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-xs">
                로그인 정보는 AES 암호화되어 서버에 저장됩니다. 네이버 API가 아닌 크롬
                확장 프로그램을 통한 자동 포스팅에만 사용됩니다.
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowLoginDialog(false)}
              disabled={isSaving}
            >
              취소
            </Button>
            <Button onClick={handleSaveLogin} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  저장 중...
                </>
              ) : (
                '저장하고 발행'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 확장 프로그램 미설치 다이얼로그 */}
      <Dialog open={showExtensionDialog} onOpenChange={setShowExtensionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>크롬 확장 프로그램 설치 필요</DialogTitle>
            <DialogDescription>
              네이버 블로그 자동 포스팅을 위해서는 크롬 확장 프로그램이 필요합니다.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>설치 방법</AlertTitle>
              <AlertDescription>
                <ol className="list-decimal list-inside space-y-2 mt-2 text-sm">
                  <li>아래 버튼을 클릭하여 Chrome 웹 스토어로 이동</li>
                  <li>"Chrome에 추가" 버튼 클릭</li>
                  <li>확장 프로그램 설치 완료 후 페이지 새로고침</li>
                </ol>
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExtensionDialog(false)}>
              닫기
            </Button>
            <Button onClick={openInstallPage}>확장 프로그램 설치하기</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
