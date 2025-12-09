'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Loader2, Wifi, WifiOff } from 'lucide-react'
import axios from 'axios'

export function ServerStatus() {
  const [backendStatus, setBackendStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking')
  const [lastCheck, setLastCheck] = useState<Date | null>(null)

  const checkBackendConnection = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await axios.get(`${apiUrl}/health`, { timeout: 3000 })
      if (response.status === 200) {
        setBackendStatus('connected')
        setLastCheck(new Date())
      } else {
        setBackendStatus('disconnected')
      }
    } catch (error) {
      setBackendStatus('disconnected')
      setLastCheck(new Date())
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
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 border border-gray-300 shadow-lg">
          <Loader2 className="h-4 w-4 animate-spin text-gray-600" />
          <span className="text-sm text-gray-700">서버 확인 중...</span>
        </div>
      </div>
    )
  }

  if (backendStatus === 'connected') {
    return (
      <div className="fixed bottom-4 right-4 z-50">
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
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-50 border border-red-300 shadow-lg">
        <WifiOff className="h-4 w-4 text-red-600" />
        <span className="text-sm font-medium text-red-700">서버 연결 끊김</span>
        <button
          onClick={checkBackendConnection}
          className="text-xs text-red-600 hover:text-red-800 underline"
        >
          재연결
        </button>
      </div>
    </div>
  )
}
