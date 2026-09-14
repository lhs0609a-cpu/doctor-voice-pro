'use client'

// 원스톱 자동화 — 한 페이지에서 1 → 5 순서대로 끝낸다. 다른 화면으로 보내지 않는다.
// 각 단계의 완료 여부는 실제 상태(실행기 신호·블로그·사진·작업·예약)에서 읽어 저절로 ✓ 가 된다.

import { useCallback, useEffect, useState } from 'react'
import { Check, Loader2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Pill } from '@/components/app-shell/ui-kit'
import { AutopilotPanel } from '@/components/campaign/autopilot-panel'
import { LauncherCard } from '@/components/launcher/launcher-card'
import { useLauncherStatus } from '@/lib/use-launcher-status'
import { campaignAPI, type Campaign, type Client, type PublishJobItem } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'
import { cn } from '@/lib/utils'
import { QuickAutomationSetup } from './quick-automation-setup'
import { BulkPublishPanel } from './bulk-publish-panel'
import { PhotoStep } from './photo-step'
import { BlogStep } from './blog-step'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'
type StepState = 'done' | 'current' | 'next' | 'locked'

const STATE_PILL: Record<StepState, { tone: Tone; label: string } | null> = {
  done: { tone: 'ok', label: '완료' },
  current: { tone: 'accent', label: '지금 할 차례' },
  next: null,
  locked: { tone: 'muted', label: '2번을 먼저 저장하세요' },
}

const JOB_LABEL: Record<string, { label: string; tone: Tone }> = {
  queued: { label: '대기', tone: 'muted' },
  assigned: { label: '준비 중', tone: 'muted' },
  publishing: { label: '네이버에 등록 중', tone: 'accent' },
  submitted: { label: '네이버 예약됨', tone: 'accent' },
  published: { label: '공개 확인', tone: 'ok' },
  failed: { label: '실패', tone: 'danger' },
  uncertain: { label: '확인 필요', tone: 'warn' },
  cancelled: { label: '뺀 글', tone: 'muted' },
}

function StepBlock({ n, title, hint, state, collapsible = false, children }: {
  n: number; title: string; hint: React.ReactNode; state: StepState; collapsible?: boolean; children?: React.ReactNode
}) {
  // 끝난 준비 단계(1~3)는 한 줄로 접는다 — 두 번째 방문부터는 저장된 준비를 건너뛰고 바로 4번(발행)으로 간다.
  // 준비가 풀리면(실행기 꺼짐 등) state 가 done 이 아니게 되어 저절로 다시 펼쳐진다.
  const [open, setOpen] = useState(false)
  const pill = STATE_PILL[state]
  const folded = collapsible && state === 'done'
  if (folded && !open) {
    return <section aria-label={`${n}단계 ${title} (완료)`} className="flex items-center gap-3 rounded-2xl border bg-card px-5 py-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success text-white"><Check className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{n}. {title}</p>
        <div className="truncate text-xs text-muted-foreground">{hint}</div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>바꾸기</Button>
    </section>
  }
  return <section aria-label={`${n}단계 ${title}`} className={cn('rounded-2xl border bg-card p-5 transition-colors',
    state === 'current' && 'border-primary ring-1 ring-primary/30', state === 'locked' && 'opacity-60')}>
    <div className="flex items-start gap-4">
      <span className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-bold tabular-nums',
        state === 'done' ? 'bg-success text-white' : state === 'current' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>
        {state === 'done' ? <Check className="h-5 w-5" /> : n}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">{n}. {title}</h2>
          {pill && <Pill tone={pill.tone}>{pill.label}</Pill>}
          {folded && <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setOpen(false)}>접기</Button>}
        </div>
        <div className="mt-1 text-sm text-muted-foreground">{hint}</div>
        {children && state !== 'locked' && <div className="mt-4">{children}</div>}
      </div>
    </div>
  </section>
}

function shortTime(iso?: string | null) {
  return iso ? iso.replace('T', ' ').slice(5, 16) : ''
}

const CONFIRMED = '원스톱 화면에서 사용자가 네이버 예약 목록에 이 글이 있다고 확인'
const NOT_FOUND = '원스톱 화면에서 사용자가 네이버 예약 목록에 이 글이 없다고 확인'

export function AutomationHome() {
  const launcher = useLauncherStatus()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [selected, setSelected] = useState('')
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [jobs, setJobs] = useState<PublishJobItem[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [readError, setReadError] = useState('')
  const [mode, setMode] = useState<'bulk' | 'recurring'>('bulk')
  const [skipPhotos, setSkipPhotos] = useState(false)
  const [acting, setActing] = useState('')
  const [actionMsg, setActionMsg] = useState('')

  const loadList = useCallback(async () => {
    setError('')
    try {
      const [rows, hospitals] = await Promise.all([campaignAPI.listCampaigns(), campaignAPI.listClients()])
      setCampaigns(rows); setClients(hospitals)
      setSelected(value => rows.some(row => row.id === value) ? value : rows[0]?.id || '')
    } catch (e) { setError(errMsg(e)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void loadList() }, [loadList])
  useEffect(() => {
    if (!selected) return
    let alive = true
    setCampaign(null); setJobs([]); setReadError(''); setActionMsg('')
    const load = async () => {
      try {
        const next = await campaignAPI.getCampaign(selected)
        const [hospital, rows] = await Promise.all([campaignAPI.getClient(next.client_id), campaignAPI.listJobs(selected)])
        if (alive) { setCampaign(next); setClient(hospital); setJobs(rows); setReadError('') }
      } catch (e) { if (alive) setReadError(errMsg(e)) }
    }
    void load()
    const timer = setInterval(load, 10000)
    return () => { alive = false; clearInterval(timer) }
  }, [selected])

  const reloadClient = useCallback(async () => {
    if (!campaign) return
    try { setClient(await campaignAPI.getClient(campaign.client_id)) } catch { /* 다음 주기에 다시 읽는다 */ }
  }, [campaign])

  // 5번의 버튼 — 그 자리에서 처리하고 목록을 다시 읽는다.
  const act = async (key: string, work: () => Promise<string>) => {
    setActing(key); setActionMsg('')
    try {
      setActionMsg(await work())
      if (selected) setJobs(await campaignAPI.listJobs(selected))
    } catch (e) { setActionMsg(errMsg(e)) }
    finally { setActing('') }
  }

  // '사진 없이 진행'은 운영마다 기억한다.
  const skipKey = selected ? `onestop-skip-photos-${selected}` : ''
  useEffect(() => {
    if (!skipKey) return
    try { setSkipPhotos(localStorage.getItem(skipKey) === '1') } catch { /* private mode */ }
  }, [skipKey])
  const chooseNoPhotos = () => {
    setSkipPhotos(true)
    try { localStorage.setItem(skipKey, '1') } catch { /* private mode */ }
  }

  const hasCampaign = campaigns.length > 0 && !creating
  const ready = hasCampaign && !!campaign && !!client
  const blogs = client?.blogs.filter(b => campaign?.blog_ids.includes(b.id)) || []
  const login = blogs.filter(b => ['captcha', 'login_required'].includes(b.status))
  const noCredentials = blogs.some(b => !b.has_password)
  const hasPhotos = !!(campaign?.collection_id || client?.default_collection_id)
  const noImages = skipPhotos && !hasPhotos
  const completed = jobs.filter(j => j.status === 'published').length
  const registered = jobs.filter(j => j.status === 'submitted').length
  const waiting = jobs.filter(j => ['queued', 'assigned', 'publishing'].includes(j.status)).length
  const attention = jobs.filter(j => ['failed', 'uncertain'].includes(j.status))
  const started = jobs.length > 0 || (campaign?.stats?.drafts || 0) > 0

  // 실행기가 켜져 연결만 된 상태(running=false)에서는 아무것도 올라가지 않는다 → '발행 대기 중'이어야 완료.
  const launcherIdle = launcher.online && !launcher.running
  const done = [
    launcher.online && launcher.running,
    ready && blogs.length > 0 && login.length === 0,
    ready && (hasPhotos || skipPhotos),
    ready && started,
    ready && completed + registered > 0,
  ]
  const current = done.findIndex(d => !d)
  const setupDone = done[0] && done[1] && done[2]   // 준비(1~3) 끝 → 접어 두고 발행만 보여 준다
  const stateOf = (index: number): StepState =>
    done[index] ? 'done' : index >= 2 && !ready ? 'locked' : index === current ? 'current' : 'next'
  const doneCount = done.filter(Boolean).length

  const recent = [...jobs].sort((a, b) => (b.scheduled_at || '').localeCompare(a.scheduled_at || '')).slice(0, 10)

  return <div className="mx-auto max-w-3xl space-y-4 pb-10">
    <header className="rounded-2xl border bg-gradient-to-br from-primary/10 via-background to-background p-5">
      <p className="text-xs font-semibold tracking-widest text-primary">원스톱 자동 운영</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{setupDone ? '준비는 끝났습니다. 4번에서 바로 발행하세요' : '1번부터 차례대로 하면 됩니다'}</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {setupDone ? '저장해 둔 준비(1~3번)는 접어 두었습니다. 바꿀 때만 [바꾸기]를 누르세요.'
          : '이 페이지 안에서 모두 끝납니다. 끝난 단계는 저절로 ✓ 로 바뀌고 접힙니다.'}
        {!loading && !error && <> 지금 <b className="text-foreground tabular-nums">{doneCount} / 5</b> 완료
          {current >= 0 && <> · <b className="text-foreground">{current + 1}번</b> 차례</>}</>}
      </p>
    </header>

    {loading ? <div className="flex items-center gap-2 py-10 text-sm" role="status"><Loader2 className="h-4 w-4 animate-spin" />저장된 운영 정보를 불러옵니다</div>
      : error ? <Card className="space-y-3 p-5"><p role="alert">{error}</p><Button onClick={loadList}>다시 불러오기</Button></Card>
      : <>
        {hasCampaign && campaigns.length > 1 && <div><Label htmlFor="operating-campaign">운영할 병원</Label>
          <select id="operating-campaign" className="mt-1 h-11 w-full rounded-lg border bg-background px-3 text-sm" value={selected} onChange={e => setSelected(e.target.value)}>
            {campaigns.map(c => <option key={c.id} value={c.id}>{c.client_name || c.name} · {c.name}</option>)}
          </select></div>}
        {readError && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">현황을 갱신하지 못했습니다. 마지막으로 불러온 정보를 표시합니다. {readError}</p>}

        {/* 1. PC 실행기 */}
        <StepBlock n={1} title="PC 실행기 켜기" state={stateOf(0)} collapsible
          hint={launcherIdle
            ? <>실행기가 연결됐지만 아직 <b className="text-foreground">쉬고 있습니다</b>. 아래처럼 버튼 하나만 누르면 끝입니다.</>
            : launcher.online
              ? <>발행 준비 완료{launcher.version && <> · v{launcher.version}</>}{launcher.note && <> · {launcher.note}</>}. PC와 실행기를 켜 두세요.</>
              : '실행기 열기 → 홈페이지 계정 연결 → 자동 발행 시작. 아래 안내대로 진행하세요.'}>
          {launcherIdle ? <ol className="list-decimal space-y-1 rounded-lg bg-warning-soft p-3 pl-8 text-sm">
            <li>작업 표시줄에서 <b>닥터보이스 자동 발행</b> 창을 엽니다.</li>
            <li><b>자동 발행 시작</b> 버튼을 누릅니다. 로그인을 요청하면 이 홈페이지의 계정을 입력하세요.</li>
            <li>다음부터 자동으로 시작하려면 실행기의 <b>켜지면 바로 발행 시작</b>에 체크하세요. 실행 신호가 도착하면 여기가 ✓ 로 바뀝니다.</li>
          </ol> : !launcher.online && <LauncherCard inline />}
        </StepBlock>

        {/* 2. 병원·블로그 */}
        <StepBlock n={2} title="병원과 네이버 블로그 연결" state={stateOf(1)} collapsible
          hint={!hasCampaign ? '병원 이름, 진료 항목, 네이버 블로그 아이디만 넣고 저장하세요.'
            : !ready ? '불러오는 중…'
              : login.length ? `네이버 로그인이 필요합니다: ${login.map(b => b.label || b.blog_id).join(', ')}`
                : blogs.length ? <>{client?.name} · 블로그 {blogs.length}개 연결됨{noCredentials && <> · 네이버 로그인은 처음 올릴 때 한 번 하면 됩니다(②에 계정을 넣어 두면 자동)</>}</>
                  : '글을 올릴 네이버 블로그를 연결하세요.'}>
          {!hasCampaign ? <QuickAutomationSetup clients={clients} onCancel={campaigns.length ? () => setCreating(false) : undefined} onCreated={async next => {
            setCampaigns(rows => [next, ...rows.filter(row => row.id !== next.id)])
            setSelected(next.id); setCreating(false)
            void loadList()
          }} /> : ready && campaign && client ? <div className="space-y-3">
            <BlogStep campaign={campaign} client={client} setCampaign={setCampaign} onChanged={() => { void reloadClient() }} />
            <Button variant="ghost" size="sm" onClick={() => setCreating(true)}><Plus className="mr-1 h-4 w-4" />다른 병원도 운영하기</Button>
          </div> : null}
        </StepBlock>

        {/* 3. 사진 */}
        <StepBlock n={3} title="글에 넣을 사진 올리기 (선택)" state={stateOf(2)} collapsible
          hint={hasPhotos ? '사진이 준비됐습니다. 더 올려도 됩니다.' : skipPhotos ? '사진 없이 글만 준비합니다.' : '진료실·시술 사진을 올려 두면 글마다 알아서 넣습니다. 없어도 됩니다.'}>
          {ready && campaign && client && <PhotoStep campaign={campaign} client={client} setCampaign={setCampaign}
            skipped={skipPhotos} onSkip={chooseNoPhotos} />}
        </StepBlock>

        {/* 4. 글 쓰기 시작 */}
        <StepBlock n={4} title="글 몇 개 쓸지 정하고 시작" state={stateOf(3)}
          hint={started ? '글 준비를 시작했습니다. 창을 닫아도 서버에서 계속합니다.'
            : <>두 가지 방법 중 하나를 고르세요. 처음이라면 <b className="text-foreground">한 번에 여러 개</b>를 추천합니다.</>}>
          {ready && <div className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="발행 방식">
              <button type="button" aria-pressed={mode === 'bulk'} onClick={() => setMode('bulk')}
                className={cn('rounded-xl border p-3 text-left transition-colors', mode === 'bulk' ? 'border-primary bg-primary/5' : 'hover:bg-muted/40')}>
                <span className="block font-medium">한 번에 여러 개</span>
                <span className="block text-xs text-muted-foreground">지금 10·30·50개를 한꺼번에 써서 날짜별로 예약합니다</span>
              </button>
              <button type="button" aria-pressed={mode === 'recurring'} onClick={() => setMode('recurring')}
                className={cn('rounded-xl border p-3 text-left transition-colors', mode === 'recurring' ? 'border-primary bg-primary/5' : 'hover:bg-muted/40')}>
                <span className="block font-medium">매일 자동으로</span>
                <span className="block text-xs text-muted-foreground">매일 정한 개수씩 알아서 계속 씁니다</span>
              </button>
            </div>
            {mode === 'bulk' ? <BulkPublishPanel key={selected} campaignId={selected} noImages={noImages} onRecurring={() => setMode('recurring')} />
              : <AutopilotPanel key={selected} campaignId={selected} inline noImages={noImages} onComplete={() => { void loadList() }} />}
          </div>}
        </StepBlock>

        {/* 5. 결과 */}
        <StepBlock n={5} title="네이버 예약 결과 확인" state={stateOf(4)}
          hint={!started ? '4번을 시작하면 여기에 결과가 쌓입니다.'
            : completed + registered > 0 ? `네이버 예약 ${registered}건 · 공개 확인 ${completed}건 · 예약 시각이 지나면 공개 여부를 저절로 확인합니다`
              : '원고가 준비되는 대로 실행기가 네이버에 예약합니다. 몇 분에서 몇 시간 걸릴 수 있어요. PC와 실행기를 켜 두세요.'}>
          {ready && jobs.length > 0 && <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {([['공개 확인', completed], ['네이버 예약', registered], ['준비·대기', waiting], ['확인 필요', attention.length]] as const).map(([label, count]) =>
                <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{count}<span className="ml-1 text-xs font-normal">건</span></p></div>)}
            </div>

            {attention.length > 0 && <div className="space-y-3 rounded-lg bg-warning-soft p-3">
              <p className="text-sm font-medium">손봐야 할 글 {attention.length}건 — 버튼 하나만 누르면 됩니다</p>
              {attention.slice(0, 5).map(j => <div key={j.id} className="space-y-2 rounded-lg border bg-card p-3 text-sm">
                <p className="font-medium">{j.title}</p>
                {j.status === 'uncertain' ? <>
                  <p className="text-xs text-muted-foreground">실행기가 올리긴 했는데 네이버에 잡혔는지 확인하지 못했습니다. 네이버 블로그의 <b>예약 글 목록</b>에 이 제목이 있나요?</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={!!acting} onClick={() => act(`ok-${j.id}`, async () => {
                      await campaignAPI.reconcileJob(j.id, 'registered', CONFIRMED)
                      return '예약된 글로 표시했습니다'
                    })}>있어요</Button>
                    <Button size="sm" variant="outline" disabled={!!acting} onClick={() => act(`no-${j.id}`, async () => {
                      await campaignAPI.reconcileJob(j.id, 'not_registered', NOT_FOUND)
                      try { await campaignAPI.retryJob(j.id); return '다시 올리도록 넣었습니다' }
                      catch { return '없는 글로 정리했습니다. 4번에서 다시 쓰면 됩니다' }
                    })}>없어요 · 다시 올리기</Button>
                  </div>
                </> : <>
                  <p className="text-xs text-muted-foreground">{j.error || '네이버에 올리지 못했습니다.'}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={!!acting} onClick={() => act(`retry-${j.id}`, async () => {
                      await campaignAPI.retryJob(j.id)
                      return '다시 올리도록 넣었습니다. 실행기가 다음 차례에 올립니다'
                    })}>다시 시도</Button>
                    <Button size="sm" variant="ghost" disabled={!!acting} onClick={() => act(`cancel-${j.id}`, async () => {
                      await campaignAPI.cancelJob(j.id)
                      return '이 글은 올리지 않도록 뺐습니다'
                    })}>이 글 빼기</Button>
                  </div>
                </>}
              </div>)}
              {actionMsg && <p role="status" className="text-sm">{actionMsg}</p>}
            </div>}

            <div>
              <p className="mb-2 text-sm font-medium">최근 글 {recent.length}건</p>
              <ul className="divide-y rounded-lg border">{recent.map(j => {
                const label = JOB_LABEL[j.status] || { label: j.status, tone: 'muted' as Tone }
                return <li key={j.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                  <span className="w-24 shrink-0 text-xs tabular-nums text-muted-foreground">{shortTime(j.scheduled_at)}</span>
                  <span className="min-w-0 flex-1 truncate">{j.title}</span>
                  <Pill tone={label.tone} className="shrink-0">{label.label}</Pill>
                </li>
              })}</ul>
            </div>
          </div>}
        </StepBlock>
      </>}
  </div>
}
