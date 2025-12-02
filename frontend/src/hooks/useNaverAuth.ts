/**
 * useNaverAuth Hook
 * 네이버 로그인 정보 관리 (서버 기반)
 */

import { useState, useEffect } from 'react'
import { naverAPI } from '@/lib/api'
import { toast } from 'sonner'

interface NaverCredentials {
  username: string
  password: string
}

export const useNaverAuth = () => {
  const [credentials, setCredentials] = useState<NaverCredentials | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /**
   * 서버에서 네이버 로그인 정보 불러오기
   */
  const loadCredentials = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await naverAPI.getCredentials()
      setCredentials(data)
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || '로그인 정보를 불러오는데 실패했습니다.'
      setError(errorMsg)
      console.error('Load credentials error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * 네이버 로그인 정보 저장
   */
  const saveCredentials = async (username: string, password: string) => {
    setIsLoading(true)
    setError(null)

    try {
      await naverAPI.saveCredentials(username, password)
      setCredentials({ username, password })
      toast.success('네이버 로그인 정보가 안전하게 저장되었습니다.')
      return true
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || '로그인 정보 저장에 실패했습니다.'
      setError(errorMsg)
      toast.error(errorMsg)
      console.error('Save credentials error:', err)
      return false
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * 네이버 로그인 정보 삭제
   */
  const deleteCredentials = async () => {
    setIsLoading(true)
    setError(null)

    try {
      await naverAPI.deleteCredentials()
      setCredentials(null)
      toast.success('네이버 로그인 정보가 삭제되었습니다.')
      return true
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || '로그인 정보 삭제에 실패했습니다.'
      setError(errorMsg)
      toast.error(errorMsg)
      console.error('Delete credentials error:', err)
      return false
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * 로그인 정보 존재 여부 확인
   */
  const hasCredentials = (): boolean => {
    return credentials !== null
  }

  // 컴포넌트 마운트 시 자동 로드
  useEffect(() => {
    loadCredentials()
  }, [])

  return {
    credentials,
    isLoading,
    error,
    loadCredentials,
    saveCredentials,
    deleteCredentials,
    hasCredentials,
  }
}
