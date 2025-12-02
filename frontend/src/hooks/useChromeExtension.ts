/**
 * useChromeExtension Hook
 * 크롬 확장 프로그램 통신 관리
 */

import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'

// 크롬 확장 프로그램 ID (환경변수 또는 기본값)
const EXTENSION_ID = process.env.NEXT_PUBLIC_CHROME_EXTENSION_ID || 'bpjddkciomjopkhalbjnblbkedeghpaj'

interface ChromeExtensionMessage {
  type: string
  data: any
}

interface ChromeExtensionResponse {
  success: boolean
  message?: string
  error?: string
  data?: any
}

export const useChromeExtension = () => {
  const [isInstalled, setIsInstalled] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [extensionId, setExtensionId] = useState<string>(EXTENSION_ID)

  /**
   * 크롬 확장 프로그램 설치 여부 확인
   */
  const checkExtension = useCallback(async (): Promise<boolean> => {
    setIsChecking(true)

    try {
      // Chrome API가 없으면 false
      if (!window.chrome?.runtime) {
        setIsInstalled(false)
        setIsChecking(false)
        return false
      }

      // 확장 프로그램에 핑 메시지 전송
      return new Promise<boolean>((resolve) => {
        try {
          window.chrome.runtime.sendMessage(
            extensionId,
            { type: 'PING' },
            (response: any) => {
              // 응답이 있으면 설치됨
              const installed = !!response
              setIsInstalled(installed)
              setIsChecking(false)
              resolve(installed)
            }
          )

          // 타임아웃: 1초 내 응답 없으면 미설치로 간주
          setTimeout(() => {
            if (isChecking) {
              setIsInstalled(false)
              setIsChecking(false)
              resolve(false)
            }
          }, 1000)
        } catch (error) {
          console.error('Extension check error:', error)
          setIsInstalled(false)
          setIsChecking(false)
          resolve(false)
        }
      })
    } catch (error) {
      console.error('Extension check error:', error)
      setIsInstalled(false)
      setIsChecking(false)
      return false
    }
  }, [extensionId, isChecking])

  /**
   * 크롬 확장 프로그램에 메시지 전송
   */
  const sendMessage = useCallback(
    async (type: string, data: any): Promise<ChromeExtensionResponse> => {
      if (!isInstalled) {
        toast.error('크롬 확장 프로그램이 설치되어 있지 않습니다.')
        return {
          success: false,
          error: '크롬 확장 프로그램이 설치되어 있지 않습니다.',
        }
      }

      if (!window.chrome?.runtime) {
        toast.error('크롬 브라우저에서만 사용할 수 있습니다.')
        return {
          success: false,
          error: '크롬 브라우저에서만 사용할 수 있습니다.',
        }
      }

      return new Promise<ChromeExtensionResponse>((resolve) => {
        try {
          const message: ChromeExtensionMessage = { type, data }

          window.chrome.runtime.sendMessage(
            extensionId,
            message,
            (response: ChromeExtensionResponse) => {
              // 에러 체크
              if (window.chrome.runtime.lastError) {
                const error = window.chrome.runtime.lastError.message || '메시지 전송 실패'
                console.error('Chrome runtime error:', error)
                toast.error(error)
                resolve({
                  success: false,
                  error,
                })
                return
              }

              // 응답 처리
              if (response?.success) {
                resolve(response)
              } else {
                const error = response?.error || '알 수 없는 오류'
                toast.error(error)
                resolve({
                  success: false,
                  error,
                })
              }
            }
          )

          // 타임아웃: 30초 내 응답 없으면 실패
          setTimeout(() => {
            resolve({
              success: false,
              error: '요청 시간 초과 (30초)',
            })
          }, 30000)
        } catch (error: any) {
          const errorMsg = error.message || '메시지 전송 중 오류 발생'
          console.error('Send message error:', error)
          toast.error(errorMsg)
          resolve({
            success: false,
            error: errorMsg,
          })
        }
      })
    },
    [isInstalled, extensionId]
  )

  /**
   * 확장 프로그램 설치 페이지 열기
   */
  const openInstallPage = useCallback(() => {
    const installUrl = `https://chrome.google.com/webstore/detail/${extensionId}`
    window.open(installUrl, '_blank')
  }, [extensionId])

  /**
   * 확장 프로그램 ID 변경
   */
  const setCustomExtensionId = useCallback((newId: string) => {
    setExtensionId(newId)
    // ID 변경 후 재확인
    setTimeout(() => {
      checkExtension()
    }, 100)
  }, [checkExtension])

  // 컴포넌트 마운트 시 자동 확인
  useEffect(() => {
    checkExtension()
  }, [checkExtension])

  return {
    isInstalled,
    isChecking,
    extensionId,
    checkExtension,
    sendMessage,
    openInstallPage,
    setCustomExtensionId,
  }
}
