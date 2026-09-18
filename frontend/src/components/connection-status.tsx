'use client'

/**
 * 백엔드 연결 상태 표시 컴포넌트
 * 화면 우측 하단에 연결 상태를 실시간으로 표시합니다.
 */

import { useBackendConnection } from '@/hooks/useBackendConnection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Pill } from '@/components/app-shell/ui-kit'
import { Wifi, WifiOff, RefreshCw, CheckCircle2, XCircle, Loader2, X } from 'lucide-react'
import { useState } from 'react'

type Tone = 'ok' | 'warn' | 'danger'

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

  // 연결 상태 아이콘 및 의미색
  const getStatusInfo = (): { icon: React.ReactNode; dot: string; text: string; tone: Tone } => {
    if (isChecking && reconnectAttempts > 0) {
      return {
        icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
        dot: 'bg-warning',
        text: '재연결 중',
        tone: 'warn'
      }
    }

    if (isConnected) {
      return {
        icon: <Wifi className="h-3.5 w-3.5" />,
        dot: 'bg-success',
        text: '연결됨',
        tone: 'ok'
      }
    }

    return {
      icon: <WifiOff className="h-3.5 w-3.5" />,
      dot: 'bg-danger',
      text: '연결 끊김',
      tone: 'danger'
    }
  }

  const statusInfo = getStatusInfo()

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* 축소된 상태 - 작은 알약 */}
      {!isExpanded && (
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className="rounded-full shadow-card transition-transform hover:scale-105"
          aria-label="백엔드 연결 상태 열기"
        >
          <Pill tone={statusInfo.tone} className="px-3 py-1.5">
            {statusInfo.icon}
            {statusInfo.text}
          </Pill>
        </button>
      )}

      {/* 확장된 상태 - 상세 정보 카드 */}
      {isExpanded && (
        <Card className="w-80 shadow-pop">
          <CardContent className="p-4">
            {/* 헤더 */}
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`h-2.5 w-2.5 animate-pulse rounded-full ${statusInfo.dot}`} />
                <h3 className="text-sm font-semibold">백엔드 연결 상태</h3>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsExpanded(false)}
                className="h-7 w-7"
                aria-label="닫기"
              >
                <X />
              </Button>
            </div>

            {/* 연결 상태 */}
            <div className="space-y-3">
              {/* 상태 표시 */}
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-muted-foreground">상태</span>
                <Pill tone={statusInfo.tone}>
                  {statusInfo.icon}
                  {statusInfo.text}
                </Pill>
              </div>

              {/* 백엔드 URL */}
              <div className="flex items-center justify-between gap-3">
                <span className="text-[13px] font-medium text-muted-foreground">백엔드</span>
                <span className="truncate font-mono text-xs">{backendUrl || 'N/A'}</span>
              </div>

              {/* 재연결 시도 횟수 */}
              {reconnectAttempts > 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-medium text-muted-foreground">재시도</span>
                  <Pill tone="muted">{reconnectAttempts}회</Pill>
                </div>
              )}

              {/* 마지막 체크 시간 */}
              {lastCheckTime && (
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-medium text-muted-foreground">마지막 확인</span>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {lastCheckTime.toLocaleTimeString('ko-KR')}
                  </span>
                </div>
              )}

              {/* 에러 메시지 */}
              {error && (
                <div className="rounded-lg bg-danger-soft p-2.5">
                  <div className="flex items-start gap-2">
                    <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-danger" />
                    <p className="text-xs text-danger">{error}</p>
                  </div>
                </div>
              )}

              {/* 성공 메시지 */}
              {isConnected && !error && (
                <div className="rounded-lg bg-success-soft p-2.5">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    <p className="text-xs text-success">
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
                  className="mt-2 w-full"
                  size="sm"
                  variant="outline"
                >
                  <RefreshCw className={isChecking ? 'animate-spin' : ''} />
                  {isChecking ? '재연결 중...' : '다시 연결하기'}
                </Button>
              )}
            </div>

            {/* 도움말 */}
            <div className="mt-4 border-t pt-3">
              <p className="text-xs text-muted-foreground">
                백엔드 서버가 실행 중인지 확인하세요.
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
