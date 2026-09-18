'use client'

import { useEffect, useState } from 'react'
import { Loader2, Wifi, WifiOff, Sparkles } from 'lucide-react'
import axios from 'axios'

interface AIStatus {
  connected: boolean
  model?: string | null
}

/** 우측 하단 상태 알약 공통 껍데기 */
const chipBase = 'flex items-center gap-2 rounded-full border bg-card px-3.5 py-1.5 text-[13px] font-medium shadow-card'

export function ServerStatus() {
  const [backendStatus, setBackendStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking')
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null)
  const [lastCheck, setLastCheck] = useState<Date | null>(null)

  const checkBackendConnection = async (retries = 2) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await axios.get(`${apiUrl}/health`, { timeout: 30000 })
      if (response.status === 200) {
        setBackendStatus('connected')
        setLastCheck(new Date())
        // AI 상태 정보 저장
        if (response.data.ai) {
          setAiStatus(response.data.ai)
        }
      } else {
        setBackendStatus('disconnected')
      }
    } catch (error) {
      // Retry on first attempt
      if (retries > 0) {
        console.log(`Connection failed, retrying... (${retries} attempts left)`)
        await new Promise(resolve => setTimeout(resolve, 5000)) // Wait 5 seconds
        return checkBackendConnection(retries - 1)
      }
      setBackendStatus('disconnected')
      setLastCheck(new Date())
      setAiStatus(null)
    }
  }

  useEffect(() => {
    // 초기 체크
    checkBackendConnection()

    // 10초마다 체크
    const interval = setInterval(checkBackendConnection, 10000)

    return () => clearInterval(interval)
  }, [])

  if (backendStatus === 'checking') {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <div className="surface flex max-w-xs flex-col gap-1 px-4 py-3">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="text-[13px] font-medium">서버 연결 중...</span>
          </div>
          <span className="ml-6 text-xs text-muted-foreground">
            처음 연결할 때는 10~30초 걸릴 수 있어요
          </span>
        </div>
      </div>
    )
  }

  if (backendStatus === 'connected') {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <div className="flex flex-col items-end gap-2">
          <div className={chipBase}>
            <div className="relative">
              <Wifi className="h-4 w-4 text-success" />
              <div className="absolute -right-1 -top-1 h-2 w-2 animate-pulse rounded-full bg-success" />
            </div>
            <span className="text-success">서버 연결됨</span>
            {lastCheck && (
              <span className="text-xs text-muted-foreground tabular-nums">
                {lastCheck.toLocaleTimeString()}
              </span>
            )}
          </div>

          {/* AI 연동 상태 */}
          {aiStatus && (
            <div className={chipBase}>
              <Sparkles className={`h-4 w-4 ${aiStatus.connected ? 'text-primary' : 'text-muted-foreground'}`} />
              <span className={aiStatus.connected ? 'text-foreground' : 'text-muted-foreground'}>
                {aiStatus.connected ? 'Claude AI 연동됨' : 'Claude AI 미연동'}
              </span>
              {aiStatus.connected && aiStatus.model && (
                <span className="pill pill-accent">Sonnet 4.5</span>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className={chipBase}>
        <WifiOff className="h-4 w-4 text-danger" />
        <span className="text-danger">서버 연결 끊김</span>
        <button
          type="button"
          onClick={() => checkBackendConnection()}
          className="text-xs text-primary underline-offset-4 hover:underline"
        >
          다시 연결
        </button>
      </div>
    </div>
  )
}
