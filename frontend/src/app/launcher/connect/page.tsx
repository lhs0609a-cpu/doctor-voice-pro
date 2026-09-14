'use client'

// 실행기가 열어 준 승인 화면.
//
// PC 실행기를 켜면 브라우저가 이 주소로 열린다. 여기에 로그인돼 있으면 사용자는 아무것도 입력하지 않는다 —
// 이 페이지가 서버에 "이 PC를 내 계정에 연결한다"고 알려 주면 실행기가 그 답을 받아 간다.
//
// 왜 이 길이 필요한가: 반대 방향(홈페이지 → 이 PC의 127.0.0.1 창구)은 브라우저가 로컬 접근을 막으면 끊긴다.
// 이 길은 브라우저가 평소처럼 우리 서버에 요청하는 것뿐이라 막히지 않는다.
//
// 안전장치: 이 PC에서 실행기가 같은 요청을 들고 있는 것이 확인되면 바로 승인한다.
// 확인되지 않으면(다른 PC일 수 있다) PC 이름을 보여 주고 한 번 누르게 한다 — 남이 보낸 링크로 몰래 연결되지 않게.

import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { CheckCircle2, Laptop, Loader2, ShieldQuestion } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Logo } from '@/components/app-shell/logo'
import { campaignAPI, type AgentPairRequestInfo } from '@/lib/campaign-api'
import { useAuthStore } from '@/store/auth'

const LOCAL_PORTS = [47815, 47816, 47817]

/** 이 PC의 실행기가 정말 이 요청을 들고 있는지 확인한다. 못 물어보면 null(모름). */
async function deviceHere(deviceId: string): Promise<boolean | null> {
  let reachable = false
  for (const port of LOCAL_PORTS) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/status`, { signal: AbortSignal.timeout(800), cache: 'no-store' })
      if (!res.ok) continue
      const body = await res.json()
      if (body?.app !== 'doctorvoice-launcher') continue
      reachable = true
      if (body?.device_id === deviceId) return true
    } catch {
      // 실행기가 없거나 브라우저가 로컬 접근을 막았다 — 다음 포트
    }
  }
  return reachable ? false : null
}

type Phase = 'loading' | 'confirm' | 'approving' | 'done' | 'error'

function ConnectBody() {
  const router = useRouter()
  const params = useSearchParams()
  const requestId = params.get('r') || ''
  const { user, hydrated, hydrate } = useAuthStore()

  const [phase, setPhase] = useState<Phase>('loading')
  const [info, setInfo] = useState<AgentPairRequestInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => { if (!hydrated) hydrate() }, [hydrated, hydrate])

  const approve = useCallback(async () => {
    setPhase('approving')
    try {
      await campaignAPI.agentPairApprove(requestId)
      setPhase('done')
    } catch (e: any) {
      setError(e?.response?.data?.detail || '연결하지 못했습니다. 실행기에서 [지금 연결하기]를 다시 눌러 주세요')
      setPhase('error')
    }
  }, [requestId])

  useEffect(() => {
    if (!hydrated || started.current) return
    if (!requestId) {
      setError('연결 주소가 올바르지 않습니다. 실행기에서 [지금 연결하기]를 다시 눌러 주세요')
      setPhase('error')
      return
    }
    if (!user) {
      // 로그인만 하면 이 화면으로 돌아와 그대로 연결된다.
      router.replace(`/login?next=${encodeURIComponent(`/launcher/connect?r=${requestId}`)}`)
      return
    }
    started.current = true
    void (async () => {
      let found: AgentPairRequestInfo
      try {
        found = await campaignAPI.agentPairRequestInfo(requestId)
      } catch (e: any) {
        setError(e?.response?.data?.detail || '연결 요청을 찾을 수 없습니다. 실행기에서 [지금 연결하기]를 다시 눌러 주세요')
        setPhase('error')
        return
      }
      setInfo(found)
      const here = await deviceHere(found.device_id)
      if (here === false) {
        // 이 PC에 실행기는 있는데 다른 요청을 들고 있다 — 남의 PC를 연결하려는 링크일 수 있다.
        setPhase('confirm')
        return
      }
      await approve()      // 같은 PC이거나(true) 확인할 수 없는 경우(null) — 아래 확인 버튼 없이 바로 연결
    })()
  }, [hydrated, user, requestId, router, approve])

  const pc = info?.label || info?.device_id?.slice(0, 8) || '이 PC'

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex justify-center"><Logo href="/" /></div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {phase === 'done' ? <CheckCircle2 className="h-5 w-5 text-success" />
                : phase === 'confirm' ? <ShieldQuestion className="h-5 w-5 text-warning" />
                : <Laptop className="h-5 w-5" />}
              PC 실행기 연결
            </CardTitle>
            <CardDescription>
              {phase === 'done' ? '이 PC가 내 계정에 연결되었습니다'
                : phase === 'error' ? '연결하지 못했습니다'
                : '실행기를 내 계정에 연결하는 중입니다'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(phase === 'loading' || phase === 'approving') && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> 잠시만 기다려 주세요…
              </p>
            )}

            {phase === 'confirm' && (
              <>
                <p className="text-sm">
                  <b>{pc}</b> 를 <b>{user?.email}</b> 계정에 연결할까요?
                </p>
                <p className="text-sm text-muted-foreground">
                  이 PC에서 켜 둔 실행기와는 다른 요청입니다. 내가 켠 실행기가 맞을 때만 연결하세요.
                </p>
                <Button onClick={() => void approve()} className="w-full">연결하기</Button>
              </>
            )}

            {phase === 'done' && (
              <>
                <p className="text-sm">
                  <b>{pc}</b> 가 <b>{user?.email}</b> 계정에 연결되었습니다.
                  실행기 창이 곧 <b>연결됨</b> 으로 바뀌고 자동 발행이 시작됩니다.
                </p>
                <p className="text-sm text-muted-foreground">
                  다음부터는 실행기를 켜기만 하면 됩니다. 이 창은 닫아도 됩니다.
                </p>
                <Button variant="outline" className="w-full" onClick={() => router.push('/dashboard/one-stop')}>
                  원스톱 자동화로 가기
                </Button>
              </>
            )}

            {phase === 'error' && (
              <>
                <p className="text-sm text-danger">{error}</p>
                <p className="text-sm text-muted-foreground">
                  연결 요청은 10분 동안만 유효합니다. 실행기 창에서 [지금 연결하기]를 누르면 새 창이 열립니다.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function LauncherConnectPage() {
  return (
    <Suspense fallback={null}>
      <ConnectBody />
    </Suspense>
  )
}
