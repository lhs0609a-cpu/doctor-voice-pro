'use client'

/**
 * 백엔드 연결 상태 표시 컴포넌트
 * 화면 우측 하단에 연결 상태를 실시간으로 표시합니다.
 */

import { useBackendConnection } from '@/hooks/useBackendConnection'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Wifi, WifiOff, RefreshCw, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'

export function ConnectionStatus() {
  const {
    isConnected,
    isChecking,
    reconnectAttempts,
    backendUrl,
    error,
    lastCheckTime,
    manualReconnect
  } = useBackendConnection()

  const [isExpanded, setIsExpanded] = useState(false)

  // 연결 상태 아이콘 및 색상
  const getStatusInfo = () => {
    if (isChecking && reconnectAttempts > 0) {
      return {
        icon: <Loader2 className="h-4 w-4 animate-spin" />,
        color: 'bg-yellow-500',
        text: '재연결 중',
        variant: 'secondary' as const
      }
    }

    if (isConnected) {
      return {
        icon: <Wifi className="h-4 w-4" />,
        color: 'bg-green-500',
        text: '연결됨',
        variant: 'default' as const
      }
    }

    return {
      icon: <WifiOff className="h-4 w-4" />,
      color: 'bg-red-500',
      text: '연결 끊김',
      variant: 'destructive' as const
    }
  }

  const statusInfo = getStatusInfo()

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* 축소된 상태 - 작은 배지 */}
      {!isExpanded && (
        <Badge
          variant={statusInfo.variant}
          className="cursor-pointer hover:scale-105 transition-transform flex items-center gap-2 px-3 py-2"
          onClick={() => setIsExpanded(true)}
        >
          {statusInfo.icon}
          <span className="text-xs font-medium">{statusInfo.text}</span>
        </Badge>
      )}

      {/* 확장된 상태 - 상세 정보 카드 */}
      {isExpanded && (
        <Card className="w-80 shadow-lg">
          <CardContent className="pt-4">
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${statusInfo.color} animate-pulse`} />
                <h3 className="font-semibold">백엔드 연결 상태</h3>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(false)}
                className="h-6 w-6 p-0"
              >
                ×
              </Button>
            </div>

            {/* 연결 상태 */}
            <div className="space-y-3">
              {/* 상태 표시 */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">상태</span>
                <div className="flex items-center gap-2">
                  {statusInfo.icon}
                  <span className="text-sm font-medium">{statusInfo.text}</span>
                </div>
              </div>

              {/* 백엔드 URL */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">백엔드</span>
                <span className="text-sm font-mono">{backendUrl || 'N/A'}</span>
              </div>

              {/* 재연결 시도 횟수 */}
              {reconnectAttempts > 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">재시도</span>
                  <Badge variant="outline" className="text-xs">
                    {reconnectAttempts}회
                  </Badge>
                </div>
              )}

              {/* 마지막 체크 시간 */}
              {lastCheckTime && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">마지막 체크</span>
                  <span className="text-xs text-muted-foreground">
                    {lastCheckTime.toLocaleTimeString('ko-KR')}
                  </span>
                </div>
              )}

              {/* 에러 메시지 */}
              {error && (
                <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded p-2">
                  <div className="flex items-start gap-2">
                    <XCircle className="h-4 w-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
                  </div>
                </div>
              )}

              {/* 성공 메시지 */}
              {isConnected && !error && (
                <div className="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded p-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                    <p className="text-xs text-green-600 dark:text-green-400">
                      백엔드가 정상적으로 작동 중입니다
                    </p>
                  </div>
                </div>
              )}

              {/* 수동 재연결 버튼 */}
              {!isConnected && (
                <Button
                  onClick={manualReconnect}
                  disabled={isChecking}
                  className="w-full mt-2"
                  size="sm"
                  variant="outline"
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${isChecking ? 'animate-spin' : ''}`} />
                  {isChecking ? '재연결 중...' : '수동 재연결'}
                </Button>
              )}
            </div>

            {/* 도움말 */}
            <div className="mt-4 pt-3 border-t">
              <p className="text-xs text-muted-foreground">
                💡 백엔드 서버가 실행 중인지 확인하세요.
                <br />
                포트: {backendUrl ? new URL(backendUrl).port : '8010'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
