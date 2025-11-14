/**
 * 백엔드 연결 상태 관리 Hook
 * 백엔드 헬스체크 및 자동 재연결 기능 제공
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

interface ConnectionConfig {
  backend: {
    host: string
    port: number
    protocol: string
  }
  connection: {
    health_check_interval: number
    reconnect_interval: number
    max_reconnect_attempts: number
    timeout: number
  }
}

interface ConnectionStatus {
  isConnected: boolean
  isChecking: boolean
  reconnectAttempts: number
  backendUrl: string
  error: string | null
  lastCheckTime: Date | null
}

const DEFAULT_CONFIG: ConnectionConfig = {
  backend: {
    host: 'localhost',
    port: 8010,
    protocol: 'http'
  },
  connection: {
    health_check_interval: 5,
    reconnect_interval: 3,
    max_reconnect_attempts: 100,
    timeout: 5
  }
}

export function useBackendConnection() {
  const [status, setStatus] = useState<ConnectionStatus>({
    isConnected: false,
    isChecking: true,
    reconnectAttempts: 0,
    backendUrl: '',
    error: null,
    lastCheckTime: null
  })

  const [config, setConfig] = useState<ConnectionConfig>(DEFAULT_CONFIG)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)
  const healthCheckTimerRef = useRef<NodeJS.Timeout | null>(null)
  const isMonitoringRef = useRef<boolean>(false)

  /**
   * 설정 파일 로드
   */
  const loadConfig = useCallback(async () => {
    try {
      const response = await fetch('/connection_config.json')
      if (response.ok) {
        const data = await response.json()
        setConfig(data)
        console.log('✅ 연결 설정 로드 완료:', data)
        return data
      }
    } catch (error) {
      console.warn('⚠️  설정 파일 로드 실패, 기본 설정 사용')
    }
    return DEFAULT_CONFIG
  }, [])

  /**
   * 백엔드 URL 생성
   */
  const getBackendUrl = useCallback((cfg: ConnectionConfig) => {
    // 기본 포트(http: 80, https: 443)는 URL에 포함하지 않음
    const isDefaultPort =
      (cfg.backend.protocol === 'http' && cfg.backend.port === 80) ||
      (cfg.backend.protocol === 'https' && cfg.backend.port === 443)

    if (isDefaultPort) {
      return `${cfg.backend.protocol}://${cfg.backend.host}`
    }
    return `${cfg.backend.protocol}://${cfg.backend.host}:${cfg.backend.port}`
  }, [])

  /**
   * 백엔드 헬스체크
   */
  const checkBackendHealth = useCallback(async (cfg: ConnectionConfig): Promise<boolean> => {
    const backendUrl = getBackendUrl(cfg)

    try {
      const response = await axios.get(`${backendUrl}/health`, {
        timeout: cfg.connection.timeout * 1000
      })

      if (response.status === 200) {
        return true
      }
      return false
    } catch (error) {
      return false
    }
  }, [getBackendUrl])

  /**
   * 재연결 시도
   */
  const attemptReconnect = useCallback(async (cfg: ConnectionConfig) => {
    const maxAttempts = cfg.connection.max_reconnect_attempts
    const interval = cfg.connection.reconnect_interval

    let attempts = 0

    const tryConnect = async (): Promise<boolean> => {
      attempts++

      setStatus(prev => ({
        ...prev,
        isChecking: true,
        reconnectAttempts: attempts,
        error: `재연결 시도 중... (${attempts}${maxAttempts > 0 ? `/${maxAttempts}` : ''})`
      }))

      const connected = await checkBackendHealth(cfg)

      if (connected) {
        setStatus(prev => ({
          ...prev,
          isConnected: true,
          isChecking: false,
          reconnectAttempts: 0,
          error: null,
          lastCheckTime: new Date()
        }))
        return true
      }

      // 최대 재시도 횟수 체크 (0은 무한)
      if (maxAttempts > 0 && attempts >= maxAttempts) {
        setStatus(prev => ({
          ...prev,
          isConnected: false,
          isChecking: false,
          error: `최대 재시도 횟수(${maxAttempts}회)에 도달했습니다.`
        }))
        return false
      }

      // 다음 시도 예약
      reconnectTimerRef.current = setTimeout(() => {
        tryConnect()
      }, interval * 1000)

      return false
    }

    return tryConnect()
  }, [checkBackendHealth])

  /**
   * 연결 상태 모니터링 시작
   */
  const startMonitoring = useCallback(async (cfg: ConnectionConfig) => {
    if (isMonitoringRef.current) return

    isMonitoringRef.current = true
    const backendUrl = getBackendUrl(cfg)

    setStatus(prev => ({
      ...prev,
      backendUrl,
      isChecking: true
    }))

    console.log('🔌 백엔드 연결 모니터링 시작:', backendUrl)

    const performHealthCheck = async () => {
      const connected = await checkBackendHealth(cfg)

      setStatus(prev => {
        // 연결 상태가 변경된 경우에만 처리
        if (prev.isConnected !== connected) {
          if (connected) {
            console.log('🟢 백엔드 연결됨:', backendUrl)
          } else {
            console.log('🔴 백엔드 연결 끊김:', backendUrl)

            // 재연결 시도
            if (reconnectTimerRef.current) {
              clearTimeout(reconnectTimerRef.current)
            }
            attemptReconnect(cfg)
          }
        }

        return {
          ...prev,
          isConnected: connected,
          isChecking: false,
          lastCheckTime: new Date(),
          error: connected ? null : '백엔드와 연결할 수 없습니다.'
        }
      })

      // 다음 헬스체크 예약
      if (isMonitoringRef.current) {
        healthCheckTimerRef.current = setTimeout(
          performHealthCheck,
          cfg.connection.health_check_interval * 1000
        )
      }
    }

    // 초기 헬스체크
    await performHealthCheck()
  }, [getBackendUrl, checkBackendHealth, attemptReconnect])

  /**
   * 모니터링 중지
   */
  const stopMonitoring = useCallback(() => {
    isMonitoringRef.current = false

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }

    if (healthCheckTimerRef.current) {
      clearTimeout(healthCheckTimerRef.current)
      healthCheckTimerRef.current = null
    }

    console.log('✅ 백엔드 모니터링 중지')
  }, [])

  /**
   * 초기화 및 모니터링 시작
   */
  useEffect(() => {
    let mounted = true

    const initialize = async () => {
      const cfg = await loadConfig()
      if (mounted) {
        startMonitoring(cfg)
      }
    }

    initialize()

    // 클린업
    return () => {
      mounted = false
      stopMonitoring()
    }
  }, [loadConfig, startMonitoring, stopMonitoring])

  /**
   * 수동 재연결 시도
   */
  const manualReconnect = useCallback(async () => {
    setStatus(prev => ({
      ...prev,
      reconnectAttempts: 0,
      error: null
    }))

    await attemptReconnect(config)
  }, [config, attemptReconnect])

  return {
    ...status,
    manualReconnect
  }
}
