'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect, useCallback, useRef } from 'react'

// 확장 프로그램 실시간 연동 상태 훅
// - content-website.js 가 localStorage['doctorvoice-extension-id'] 에 실제 확장 ID 를 심는다.
// - 그 ID 로 PING 을 주기적으로 보내 연결/버전/업데이트 상태를 실시간 파악한다.
//   PING 응답: { success, version, updateAvailable, latest, downloadUrl, notes }

export type ExtLight = 'connected' | 'update' | 'disconnected' | 'checking'

export interface ExtensionStatus {
  light: ExtLight
  connected: boolean
  version: string | null
  latest: string | null
  updateAvailable: boolean
  downloadUrl: string | null
  notes: string | null
  extensionId: string | null
  lastCheckedAt: number | null
  refresh: () => void
}

const EXT_ID_KEY = 'doctorvoice-extension-id'
const POLL_MS = 5000
const PING_TIMEOUT = 1500

function sendPing(extId: string): Promise<any> {
  return new Promise((resolve) => {
    if (typeof chrome === 'undefined' || !chrome?.runtime?.sendMessage) {
      resolve(null)
      return
    }
    let settled = false
    const timer = setTimeout(() => {
      if (!settled) { settled = true; resolve(null) }
    }, PING_TIMEOUT)
    try {
      chrome.runtime.sendMessage(extId, { action: 'PING' }, (res: any) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        if (chrome.runtime?.lastError) resolve(null)
        else resolve(res || null)
      })
    } catch {
      if (!settled) { settled = true; clearTimeout(timer); resolve(null) }
    }
  })
}

export function useExtensionStatus(pollMs: number = POLL_MS): ExtensionStatus {
  const [state, setState] = useState<Omit<ExtensionStatus, 'refresh'>>({
    light: 'checking',
    connected: false,
    version: null,
    latest: null,
    updateAvailable: false,
    downloadUrl: null,
    notes: null,
    extensionId: null,
    lastCheckedAt: null,
  })
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const check = useCallback(async () => {
    let extId: string | null = null
    try { extId = localStorage.getItem(EXT_ID_KEY) } catch { /* private mode */ }

    if (!extId) {
      setState((s) => ({
        ...s, light: 'disconnected', connected: false, extensionId: null,
        lastCheckedAt: Date.now(),
      }))
      return
    }

    const res = await sendPing(extId)
    if (res?.success) {
      const updateAvailable = !!res.updateAvailable
      setState({
        light: updateAvailable ? 'update' : 'connected',
        connected: true,
        version: res.version || null,
        latest: res.latest || res.version || null,
        updateAvailable,
        downloadUrl: res.downloadUrl || null,
        notes: res.notes || null,
        extensionId: extId,
        lastCheckedAt: Date.now(),
      })
    } else {
      // ID 는 있으나 응답 없음 → 확장이 꺼졌거나 제거됨
      setState((s) => ({
        ...s, light: 'disconnected', connected: false, lastCheckedAt: Date.now(),
      }))
    }
  }, [])

  useEffect(() => {
    check()
    timerRef.current = setInterval(check, pollMs)

    // content-website.js 가 준비되면 즉시 재확인
    const onReady = () => check()
    window.addEventListener('doctorvoice-extension-ready', onReady)
    window.addEventListener('focus', onReady)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      window.removeEventListener('doctorvoice-extension-ready', onReady)
      window.removeEventListener('focus', onReady)
    }
  }, [check, pollMs])

  return { ...state, refresh: check }
}
