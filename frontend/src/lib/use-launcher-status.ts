'use client'

// PC 실행기 신호등 + 홈페이지 자동 연결.
//
// 신호등: 실행기가 서버에 남긴 하트비트를 읽는다(서버가 기준).
// 자동 연결: 서버가 '꺼짐'이라고 하면 이 PC 안(127.0.0.1)에 실행기가 떠 있는지 찾아본다.
//   있으면 로그인된 이 페이지가 서버에서 1회용 코드를 받아 실행기에 건넨다 → 실행기가 이 계정으로 연결된다.
//   사용자는 아무것도 입력하지 않는다. 비밀번호는 오가지 않는다.
// 최신 버전: 배포된 /downloads/launcher-version.json 과 대조한다(실행기가 쓰는 파일과 같다).

import { useCallback, useEffect, useRef, useState } from 'react'

import { campaignAPI, type AgentDevice } from '@/lib/campaign-api'
import { useAuthStore } from '@/store/auth'

export type LauncherLight = 'running' | 'idle' | 'update' | 'connecting' | 'other' | 'offline' | 'checking' | 'error'

export interface LocalLauncher {
  port: number
  version?: string
  paired: boolean
  email?: string | null
  connected: boolean
  running?: boolean
}

export interface LauncherStatus {
  light: LauncherLight
  label: string
  online: boolean
  running: boolean
  version: string | null
  latest: string | null
  updateAvailable: boolean
  note: string | null
  devices: AgentDevice[]
  lastSeenAt: string | null
  local: LocalLauncher | null      // 이 PC에서 찾은 실행기(없으면 null)
  pairing: boolean
  pairError: string | null
  refresh: () => void
  pairNow: () => void              // 다른 계정에 연결돼 있을 때 등, 사용자가 직접 누르는 연결
}

const MANIFEST_URL = '/downloads/launcher-version.json'
const LOCAL_PORTS = [47815, 47816, 47817]
const POLL_MS = 15000
const PAIR_COOLDOWN_MS = 30000

export const LIGHT_LABEL: Record<LauncherLight, string> = {
  running: '자동 발행 실행 중',
  idle: '켜짐 · 시작 전',   // 연결만 되고 발행은 멈춘 상태 — 실행기에서 '자동 발행 시작'을 눌러야 한다
  update: '업데이트 필요',
  connecting: '연결 중',
  other: '다른 계정',
  offline: '실행기 연결 필요',
  error: '연결 확인 실패',
  checking: '확인 중',
}

// 한 페이지에 신호등이 여러 개(상단 바·카드) 있어도 연결 시도는 한 번만 한다.
let pairInFlight: Promise<{ ok: boolean; error?: string }> | null = null
let lastPairAt = 0

function parts(version: string): number[] {
  return version.trim().split('.').map((n) => parseInt(n, 10) || 0)
}

/** a 가 b 보다 높은 버전인가. 자릿수가 달라도 숫자로 비교한다(1.10.0 > 1.9.0). */
export function isNewer(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false
  const [x, y] = [parts(a), parts(b)]
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    const [p, q] = [x[i] || 0, y[i] || 0]
    if (p !== q) return p > q
  }
  return false
}

/** 이 PC에서 실행기를 찾는다. 없거나 브라우저가 막으면 null. */
async function probeLocal(): Promise<LocalLauncher | null> {
  for (const port of LOCAL_PORTS) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 800)
    try {
      const res = await fetch(`http://127.0.0.1:${port}/status`, { signal: ctrl.signal, cache: 'no-store' })
      if (!res.ok) continue
      const body = await res.json()
      if (body?.app !== 'doctorvoice-launcher') continue
      return {
        port, version: body.version, paired: !!body.paired, email: body.email ?? null,
        connected: !!body.connected, running: !!body.running,
      }
    } catch {
      // 실행기가 없거나 브라우저가 로컬 접근을 막았다 — 다음 포트
    } finally {
      clearTimeout(timer)
    }
  }
  return null
}

/** 로그인된 이 페이지가 1회용 코드를 받아 실행기에 건넨다. */
function pairWith(local: LocalLauncher): Promise<{ ok: boolean; error?: string }> {
  if (pairInFlight) return pairInFlight
  lastPairAt = Date.now()
  pairInFlight = (async () => {
    try {
      const { code } = await campaignAPI.agentPair()
      const res = await fetch(`http://127.0.0.1:${local.port}/pair`, {
        signal: AbortSignal.timeout(25000),
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }),
      })
      const body = await res.json().catch(() => ({}))
      if (res.ok && body?.ok) return { ok: true }
      return { ok: false, error: body?.message || body?.error || '실행기가 연결을 받지 못했습니다' }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : '연결하지 못했습니다' }
    } finally {
      pairInFlight = null
    }
  })()
  return pairInFlight
}

function sameAccount(a?: string | null, b?: string | null): boolean {
  return !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase()
}

export function useLauncherStatus(pollMs: number = POLL_MS): LauncherStatus {
  const myEmail = useAuthStore((s) => s.user?.email) || null
  const [state, setState] = useState<Omit<LauncherStatus, 'refresh' | 'pairNow'>>({
    light: 'checking', label: LIGHT_LABEL.checking, online: false, running: false,
    version: null, latest: null, updateAvailable: false, note: null, devices: [], lastSeenAt: null,
    local: null, pairing: false, pairError: null,
  })
  const latestRef = useRef<string | null>(null)
  const checkRef = useRef<() => Promise<void>>(async () => {})

  const runPair = useCallback(async (local: LocalLauncher) => {
    setState((s) => ({ ...s, pairing: true, pairError: null, light: 'connecting', label: LIGHT_LABEL.connecting }))
    const result = await pairWith(local)
    setState((s) => ({ ...s, pairing: false, pairError: result.ok ? null : (result.error || '연결하지 못했습니다') }))
    // 실행기가 서버에 첫 신호를 보낼 시간을 준 뒤 다시 본다.
    setTimeout(() => { void checkRef.current() }, result.ok ? 1500 : 0)
  }, [])

  const check = useCallback(async () => {
    // 최신 버전 파일은 자주 바뀌지 않는다 → 한 번만 읽어 기억한다.
    if (latestRef.current === null) {
      try {
        const res = await fetch(MANIFEST_URL, { cache: 'no-store' })
        const body = res.ok ? await res.json() : null
        latestRef.current = typeof body?.version === 'string' ? body.version : ''
      } catch {
        latestRef.current = ''
      }
    }
    const latest = latestRef.current || null

    let status
    try {
      status = await campaignAPI.agentStatus()
    } catch {
      // 서버를 못 읽는 것과 실행기가 꺼진 것은 다르다 — 마지막으로 알던 값을 유지한다.
      setState((s) => ({ ...s, light: 'error', label: LIGHT_LABEL.error, online: false, running: false,
        note: '서버에서 연결 상태를 확인하지 못했습니다. 인터넷 연결을 확인하고 다시 확인해 주세요. 실행기가 꺼졌다는 뜻은 아닙니다.' }))
      return
    }

    // 서버가 '켜짐'이면 로컬을 찾을 필요가 없다(브라우저의 로컬 접근 확인도 띄우지 않는다).
    const local = status.online ? null : await probeLocal()
    const other = !!local && local.paired && !!local.email && !!myEmail && !sameAccount(local.email, myEmail)

    const live = status.devices.filter((d) => d.seconds_ago <= 150)
    const note = live.find((d) => d.note)?.note || null
    const updateAvailable = isNewer(latest, status.version || local?.version)
    const light: LauncherLight = status.online
      ? (updateAvailable ? 'update' : status.running ? 'running' : 'idle')
      : local ? (other ? 'other' : 'connecting') : 'offline'
    setState((s) => ({
      ...s, light, label: LIGHT_LABEL[light], online: status.online, running: status.running,
      version: status.version || local?.version || null, latest, updateAvailable, note,
      devices: status.devices, lastSeenAt: status.devices[0]?.last_seen_at || null, local,
      pairError: status.online ? null : s.pairError,
    }))

    // 자동 연결: 실행기가 아직 연결 전이거나 연결이 끊긴 경우. 다른 계정에 붙어 있으면 몰래 바꾸지 않는다.
    if (myEmail && local && !other && (!local.paired || !local.connected) && Date.now() - lastPairAt > PAIR_COOLDOWN_MS) {
      void runPair(local)
    }
  }, [myEmail, runPair])

  useEffect(() => { checkRef.current = check }, [check])

  useEffect(() => {
    void check()
    const timer = setInterval(() => { void check() }, pollMs)
    const onFocus = () => { void check() }
    window.addEventListener('focus', onFocus)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [check, pollMs])

  const pairNow = useCallback(() => {
    void (async () => {
      const local = state.local || await probeLocal()
      if (!local) {
        setState((s) => ({ ...s, pairError: '이 PC에서 실행기를 찾지 못했습니다. 실행기를 켠 뒤 다시 눌러 주세요' }))
        return
      }
      await runPair(local)
    })()
  }, [state.local, runPair])

  return { ...state, refresh: () => { void check() }, pairNow }
}
