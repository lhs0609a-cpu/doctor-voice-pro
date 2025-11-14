'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Loader2, Wifi, WifiOff, Sparkles } from 'lucide-react'
import axios from 'axios'

interface AIStatus {
  connected: boolean
  model?: string | null
}

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
        <div className="flex flex-col gap-1 px-4 py-3 rounded-lg bg-blue-50 border border-blue-300 shadow-lg max-w-xs">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
            <span className="text-sm font-medium text-blue-700">서버 연결 중...</span>
          </div>
          <span className="text-xs text-blue-600 ml-6">
            최초 연결 시 10-30초 소요될 수 있습니다
          </span>
        </div>
      </div>
    )
  }

  if (backendStatus === 'connected') {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-green-50 border border-green-300 shadow-lg">
            <div className="relative">
              <Wifi className="h-4 w-4 text-green-600" />
              <div className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
            </div>
            <span className="text-sm font-medium text-green-700">서버 연결됨</span>
            {lastCheck && (
              <span className="text-xs text-green-600">
                {lastCheck.toLocaleTimeString()}
              </span>
            )}
          </div>

          {/* AI 연동 상태 */}
          {aiStatus && (
            <div className={`flex items-center gap-2 px-4 py-2 rounded-full shadow-lg ${
              aiStatus.connected
                ? 'bg-purple-50 border border-purple-300'
                : 'bg-gray-50 border border-gray-300'
            }`}>
              <Sparkles className={`h-4 w-4 ${
                aiStatus.connected ? 'text-purple-600' : 'text-gray-400'
              }`} />
              <span className={`text-sm font-medium ${
                aiStatus.connected ? 'text-purple-700' : 'text-gray-500'
              }`}>
                {aiStatus.connected ? 'Claude AI 연동됨' : 'Claude AI 미연동'}
              </span>
              {aiStatus.connected && aiStatus.model && (
                <span className="text-xs text-purple-600 bg-purple-100 px-2 py-0.5 rounded">
                  Sonnet 4.5
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-50 border border-red-300 shadow-lg">
        <WifiOff className="h-4 w-4 text-red-600" />
        <span className="text-sm font-medium text-red-700">서버 연결 끊김</span>
        <button
          onClick={() => checkBackendConnection()}
          className="text-xs text-red-600 hover:text-red-800 underline"
        >
          재연결
        </button>
      </div>
    </div>
  )
}
