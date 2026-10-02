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
  /** 이 PC가 맡고 있는 계정 전체. 새 실행기만 알려 준다(옛 실행기는 undefined). */
  accounts?: string[]
  slot?: string
  /** 계정별 창을 띄울 수 있는 실행기인가(accounts 를 알려 주면 그렇다). */
  multiAccount: boolean
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
  /** 켜져 있다는 신호는 오는데 정작 글을 가져가지 않을 때의 안내(없으면 null) */
  stalled: string | null
  devices: AgentDevice[]
  lastSeenAt: string | null
  local: LocalLauncher | null      // 이 PC에서 찾은 실행기(없으면 null)
  pairing: boolean
  pairError: string | null
  refresh: () => void
  pairNow: () => void              // 다른 계정에 연결돼 있을 때 등, 사용자가 직접 누르는 연결
}

const MANIFEST_URL = '/downloads/launcher-version.json'
// 계정마다 실행기 창이 하나씩 뜨고 창마다 포트 하나를 잡는다(실행기의 local_bridge.PORTS 와 같다).
// 셋만 보면 네 번째 계정부터는 찾지 못해 '다른 계정'으로만 보인다.
const LOCAL_PORTS = Array.from({ length: 16 }, (_, i) => 47815 + i)
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

/** 포트 하나를 들여다본다. 실행기가 없거나 브라우저가 막으면 null. */
async function probePort(port: number): Promise<LocalLauncher | null> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 800)
  try {
    const res = await fetch(`http://127.0.0.1:${port}/status`, { signal: ctrl.signal, cache: 'no-store' })
    if (!res.ok) return null
    const body = await res.json()
    if (body?.app !== 'doctorvoice-launcher') return null
    const accounts = Array.isArray(body.accounts)
      ? body.accounts.filter((a: unknown): a is string => typeof a === 'string' && !!a)
      : undefined
    return {
      port, version: body.version, paired: !!body.paired, email: body.email ?? null,
      connected: !!body.connected, running: !!body.running,
      accounts, slot: typeof body.slot === 'string' ? body.slot : undefined,
      multiAccount: accounts !== undefined,
    }
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

/** 이 PC에 떠 있는 실행기 창 전부. 계정마다 창이 하나씩이라 여러 개가 나온다. */
export async function probeLocalAll(): Promise<LocalLauncher[]> {
  const found = await Promise.all(LOCAL_PORTS.map(probePort))
  return found.filter((l): l is LocalLauncher => !!l)
}

/** 지금 로그인한 계정을 맡은 창을 고른다.
 *  ① 내 계정 창 → ② 아직 계정이 안 붙은 창 → ③ 남의 계정 창(그 창이 내 계정 창을 띄워 준다). */
export function pickLocal(all: LocalLauncher[], myEmail?: string | null): LocalLauncher | null {
  return all.find((l) => sameAccount(l.email, myEmail))
    || all.find((l) => !l.paired || !l.email)
    || all[0]
    || null
}

/** 한 포트만 보고 멈추던 옛 호출을 위해 남겨 둔다. */
async function probeLocal(myEmail?: string | null): Promise<LocalLauncher | null> {
  return pickLocal(await probeLocalAll(), myEmail)
}

/** 로그인된 이 페이지가 1회용 코드를 받아 실행기에 건넨다.
 *
 *  계정(email)을 함께 보내는 것이 핵심이다. 실행기는 그 계정이 자기 자리가 아니면 코드를
 *  쓰지 않고 **그 계정 전용 창을 새로 띄워** 넘긴다(spawned). 계정을 알려 주지 않으면
 *  실행기가 코드를 먼저 써 버리고, 새 창은 쓸 코드가 없어 사람이 브라우저에서 승인해야 한다. */
function pairWith(local: LocalLauncher, myEmail?: string | null): Promise<{ ok: boolean; spawned?: boolean; error?: string }> {
  if (pairInFlight) return pairInFlight
  lastPairAt = Date.now()
  pairInFlight = (async () => {
    try {
      const { code } = await campaignAPI.agentPair()
      const res = await fetch(`http://127.0.0.1:${local.port}/pair`, {
        signal: AbortSignal.timeout(25000),
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, email: myEmail || undefined }),
      })
      const body = await res.json().catch(() => ({}))
      if (res.ok && body?.ok) return { ok: true }
      // 내 계정 전용 창을 띄웠다 — 실패가 아니다. 그 창이 잠시 뒤 스스로 연결한다.
      if (body?.spawned) return { ok: true, spawned: true }
      return { ok: false, error: body?.message || body?.error || '실행기가 연결을 받지 못했습니다' }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : '연결하지 못했습니다' }
    } finally {
      pairInFlight = null
    }
  })()
  return pairInFlight
}

/** 예약을 걸자마자 이 PC의 실행기에게 '지금 가져가라'고 알린다.
 *  실행기가 없거나 브라우저가 로컬 접근을 막으면 조용히 넘어간다 — 그래도 다음 주기에 가져간다. */
export async function wakeLauncher(myEmail?: string | null): Promise<boolean> {
  // 계정마다 창이 따로다 — 아무 창이나 깨우면 남의 계정 창이 헛걸음한다.
  const mine = pickLocal(await probeLocalAll(), myEmail)
  const ports = mine ? [mine.port] : LOCAL_PORTS
  for (const port of ports) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/wake`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        signal: AbortSignal.timeout(1500),
      })
      if (res.ok) return true
    } catch { /* 이 포트에는 실행기가 없다 */ }
  }
  return false
}

function sameAccount(a?: string | null, b?: string | null): boolean {
  return !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase()
}

export function useLauncherStatus(pollMs: number = POLL_MS): LauncherStatus {
  const myEmail = useAuthStore((s) => s.user?.email) || null
  const [state, setState] = useState<Omit<LauncherStatus, 'refresh' | 'pairNow'>>({
    light: 'checking', label: LIGHT_LABEL.checking, online: false, running: false,
    version: null, latest: null, updateAvailable: false, note: null, stalled: null, devices: [], lastSeenAt: null,
    local: null, pairing: false, pairError: null,
  })
  const latestRef = useRef<string | null>(null)
  const checkRef = useRef<() => Promise<void>>(async () => {})
  const myEmailRef = useRef<string | null>(myEmail)
  useEffect(() => { myEmailRef.current = myEmail }, [myEmail])

  const runPair = useCallback(async (local: LocalLauncher) => {
    setState((s) => ({ ...s, pairing: true, pairError: null, light: 'connecting', label: LIGHT_LABEL.connecting }))
    const result = await pairWith(local, myEmailRef.current)
    setState((s) => ({ ...s, pairing: false, pairError: result.ok ? null : (result.error || '연결하지 못했습니다') }))
    // 실행기가 서버에 첫 신호를 보낼 시간을 준 뒤 다시 본다.
    // 새 창을 띄운 경우(spawned)는 창이 뜨고 스스로 연결할 시간이 더 걸린다.
    setTimeout(() => { void checkRef.current() }, result.spawned ? 6000 : result.ok ? 1500 : 0)
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
      setState((s) => ({ ...s, light: 'error', label: LIGHT_LABEL.error, online: false, running: false, stalled: null,
        note: '서버에서 연결 상태를 확인하지 못했습니다. 인터넷 연결을 확인하고 다시 확인해 주세요. 실행기가 꺼졌다는 뜻은 아닙니다.' }))
      return
    }

    // 서버가 '켜짐'이면 로컬을 찾을 필요가 없다(브라우저의 로컬 접근 확인도 띄우지 않는다).
    const all = status.online ? [] : await probeLocalAll()
    const local = pickLocal(all, myEmail)
    // 내 계정을 맡은 창이 이 PC에 없다. 남의 계정 창만 떠 있는 상태다.
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
      stalled: status.stalled ? (status.stalled_hint || '실행기가 켜져 있지만 글을 가져가지 않습니다') : null,
      devices: status.devices, lastSeenAt: status.devices[0]?.last_seen_at || null, local,
      pairError: status.online ? null : s.pairError,
    }))

    // 자동 연결.
    //  · 내 계정 창이거나 아직 주인이 없는 창이면 그대로 연결한다.
    //  · 남의 계정 창만 있으면 **그 창에 내 계정을 알려 준다** — 창이 계정을 갈아타는 게 아니라
    //    내 계정 전용 창을 하나 더 띄운다(계정마다 크롬 로그인 세션이 따로여야 한다).
    //    계정별 창을 띄울 수 있는 실행기(accounts 를 알려 주는 새 버전)에만 맡긴다. 옛 버전은
    //    코드를 먼저 써 버려 사람이 브라우저에서 승인해야 하므로 [지금 연결하기] 단추로 남긴다.
    const canAsk = !!local && (!other || local.multiAccount)
    const needPair = !!local && (other || !local.paired || !local.connected)
    if (myEmail && canAsk && needPair && Date.now() - lastPairAt > PAIR_COOLDOWN_MS) {
      void runPair(local as LocalLauncher)
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
      const local = state.local || await probeLocal(myEmailRef.current)
      if (!local) {
        setState((s) => ({ ...s, pairError: '홈페이지에서 연결 가능한 실행기를 찾지 못했습니다. 다운로드 폴더의 옛 ZIP 실행기를 닫고 Windows 시작 메뉴의 [닥터보이스 프로 자동 발행]을 여세요. 설치본의 [지금 연결하기]를 누르면 연결을 시작합니다.' }))
        return
      }
      await runPair(local)
    })()
  }, [state.local, runPair])

  return { ...state, refresh: () => { void check() }, pairNow }
}
