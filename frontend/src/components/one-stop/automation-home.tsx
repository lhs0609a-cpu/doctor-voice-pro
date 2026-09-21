'use client'

// 원스톱 자동화 — 한 번에 한 가지만 보여 준다.
//
// 지키는 규칙 넷.
// 1) 펼쳐지는 칸은 언제나 하나다. 지금 할 일 말고는 전부 한 줄로 접는다.
// 2) 펼쳐진 칸에는 누를 것이 하나뿐이고, 그 자리를 ▶ 로 가리킨다.
// 3) 준비(1~3번)는 한 번 끝내면 다음부터 뜨지 않는다 — '준비 완료' 한 줄로 바뀐다.
// 4) 끝난 칸도 눌러서 언제든 다시 연다(준비 다시 하기).
//
// 완료 여부는 설명이 아니라 실제 상태(실행기 신호·블로그·사진·작업)에서 읽는다.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, ChevronDown, Loader2, Lock, Plus, Settings2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Pill } from '@/components/app-shell/ui-kit'
import { AutopilotPanel } from '@/components/campaign/autopilot-panel'
import { LauncherCard } from '@/components/launcher/launcher-card'
import { useLauncherStatus } from '@/lib/use-launcher-status'
import { campaignAPI, type Campaign, type Client, type Keyword, type PublishJobItem } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'
import { cn } from '@/lib/utils'
import { QuickAutomationSetup } from './quick-automation-setup'
import { BulkPublishPanel } from './bulk-publish-panel'
import { PhotoStep } from './photo-step'
import { BlogStep } from './blog-step'
import { KeywordStep } from './keyword-step'
import { WordPublishPanel } from './word-publish-panel'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const JOB_LABEL: Record<string, { label: string; tone: Tone }> = {
  queued: { label: '대기', tone: 'muted' },
  assigned: { label: '준비 중', tone: 'muted' },
  publishing: { label: '올리는 중', tone: 'accent' },
  submitted: { label: '네이버 예약됨', tone: 'accent' },
  published: { label: '공개 확인', tone: 'ok' },
  failed: { label: '실패', tone: 'danger' },
  uncertain: { label: '확인 필요', tone: 'warn' },
  cancelled: { label: '뺀 글', tone: 'muted' },
}

const TITLES = ['PC 실행기 켜기', '블로그 연결', '키워드 찾기', '사진 올리기', '글 쓰기 시작']
const LAST = TITLES.length   // 글 쓰기 칸 번호. 준비(1~4)가 끝나면 이 칸만 남는다

/** 누를 곳을 가리키는 표시. 펼쳐진 칸에 하나만 쓴다. */
function Here({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-xl bg-primary/5 p-3 ring-1 ring-primary/30">
      <span aria-hidden className="shrink-0 font-bold text-primary motion-safe:animate-bounce">▶</span>
      <div className="min-w-0 flex-1 text-sm">{children}</div>
    </div>
  )
}

/** 접힌 단계 한 줄. 눌러서 펼친다. */
function Row({ n, title, note, tone, onOpen, disabled }: {
  n: number; title: string; note: string; tone: 'done' | 'todo' | 'locked'; onOpen: () => void; disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={disabled}
      className={cn('flex w-full items-center gap-3 rounded-xl border bg-card px-4 py-3 text-left transition-colors',
        disabled ? 'opacity-55' : 'hover:bg-muted/40')}
    >
      <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold tabular-nums',
        tone === 'done' ? 'bg-success text-white' : 'bg-muted text-muted-foreground')}>
        {tone === 'done' ? <Check className="h-4 w-4" /> : tone === 'locked' ? <Lock className="h-3.5 w-3.5" /> : n}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{n}. {title}</span>
        <span className="block truncate text-xs text-muted-foreground">{note}</span>
      </span>
      {!disabled && <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />}
    </button>
  )
}

/** 펼쳐진 단계. 화면에 하나만 나온다. */
function Panel({ n, title, note, children }: { n: number; title: string; note: string; children: React.ReactNode }) {
  return (
    <section aria-label={`${n}단계 ${title}`} className="rounded-2xl border border-primary bg-card p-5 ring-1 ring-primary/25">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-bold tabular-nums text-primary-foreground">{n}</span>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold leading-tight">{title}</h2>
          <p className="text-xs text-muted-foreground">{note}</p>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
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
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [readError, setReadError] = useState('')
  const [mode, setMode] = useState<'bulk' | 'recurring'>('bulk')
  const [skipPhotos, setSkipPhotos] = useState(false)
  const [acting, setActing] = useState('')
  const [actionMsg, setActionMsg] = useState('')
  const [opened, setOpened] = useState<number | null>(null)   // 사용자가 직접 연 칸(없으면 지금 할 차례가 열린다)
  const [showSetup, setShowSetup] = useState(false)           // 준비가 끝난 뒤 [준비 다시 하기]

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
    setCampaign(null); setJobs([]); setKeywords([]); setReadError(''); setActionMsg('')
    const load = async () => {
      try {
        const next = await campaignAPI.getCampaign(selected)
        const [hospital, rows, found] = await Promise.all([
          campaignAPI.getClient(next.client_id), campaignAPI.listJobs(selected), campaignAPI.listKeywords(selected),
        ])
        if (alive) { setCampaign(next); setClient(hospital); setJobs(rows); setKeywords(found); setReadError('') }
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

  const reloadKeywords = useCallback(async () => {
    if (!selected) return
    try { setKeywords(await campaignAPI.listKeywords(selected)) } catch { /* 다음 주기에 다시 읽는다 */ }
  }, [selected])

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
  const blogs = useMemo(() => client?.blogs.filter(b => campaign?.blog_ids.includes(b.id)) || [], [client, campaign])
  const login = blogs.filter(b => ['captcha', 'login_required'].includes(b.status))
  const hasPhotos = !!(campaign?.collection_id || client?.default_collection_id)
  const noImages = skipPhotos && !hasPhotos
  const completed = jobs.filter(j => j.status === 'published').length
  const registered = jobs.filter(j => j.status === 'submitted').length
  const waiting = jobs.filter(j => ['queued', 'assigned', 'publishing'].includes(j.status)).length
  const attention = jobs.filter(j => ['failed', 'uncertain'].includes(j.status))
  const started = jobs.length > 0 || (campaign?.stats?.drafts || 0) > 0

  // 실행기가 켜져 연결만 된 상태(running=false)에서는 아무것도 올라가지 않는다 → '발행 대기 중'이어야 완료.
  const launcherIdle = launcher.online && !launcher.running
  const picked = keywords.filter(k => k.selected)
  const done = [
    launcher.online && launcher.running,
    ready && blogs.length > 0 && login.length === 0,
    ready && picked.length > 0,
    ready && (hasPhotos || skipPhotos),
    ready && started,
  ]
  const current = done.findIndex(d => !d)                     // -1 이면 전부 끝
  const setupDone = done.slice(0, LAST - 1).every(Boolean)
  // 지금 펼쳐진 칸. 준비를 접어 둔 동안에는 준비 줄 자체가 없으므로 마지막 칸만 열린다
  // — 안 그러면 사용자가 아까 열어 둔 2번을 따라가다 아무 칸도 안 펼쳐진 빈 화면이 된다.
  const open = setupDone && !showSetup ? LAST : (opened ?? (current === -1 ? LAST : current + 1))
  const locked = (n: number) => n >= 3 && !ready              // 병원을 만들기 전에는 3번 뒤를 못 연다

  // 접혔을 때 이 한 줄만 읽으면 되게 쓴다.
  const notes = [
    launcher.online
      ? (launcher.running ? `발행 대기 중${launcher.version ? ` · v${launcher.version}` : ''}` : '켜졌지만 쉬는 중 — 시작을 눌러야 합니다')
      : '실행기가 꺼져 있습니다',
    !hasCampaign ? '병원과 블로그를 등록하세요'
      : !ready ? '불러오는 중…'
        : login.length ? `네이버 로그인 필요: ${login.map(b => b.label || b.blog_id).join(', ')}`
          : blogs.length ? `${client?.name} · 블로그 ${blogs.length}개` : '올릴 블로그를 고르세요',
    !ready ? '블로그를 먼저 연결하세요'
      : picked.length ? `쓸 키워드 ${picked.length}개 · 후보 ${keywords.length}개`
        : '우리 블로그로 뚫리는 키워드를 찾습니다',
    hasPhotos ? '사진 준비됨' : skipPhotos ? '사진 없이 진행' : '안 올려도 됩니다',
    started ? `글 ${jobs.length}건 진행 중` : '몇 개 쓸지 정하면 시작합니다',
  ]

  const recent = [...jobs].sort((a, b) => (b.scheduled_at || '').localeCompare(a.scheduled_at || '')).slice(0, 10)
  const step = (n: number) => ({ n, title: TITLES[n - 1], note: notes[n - 1] })

  /** 열려 있으면 펼친 칸, 아니면 한 줄. */
  const slot = (n: number, body: React.ReactNode) => open === n && !locked(n)
    ? <Panel key={n} {...step(n)}>{body}</Panel>
    : <Row key={n} {...step(n)} tone={done[n - 1] ? 'done' : locked(n) ? 'locked' : 'todo'}
        disabled={locked(n)} onOpen={() => setOpened(n)} />

  // 연결은 됐는데 발행이 멈춰 있는 상태. 여기서 바로 시작시킨다.
  // 실행기는 '홈페이지가 연결을 걸어 오면' 그것을 이 계정으로 발행하라는 뜻으로 보고 발행을 시작한다
  // (실행기의 bridge_pair → autostart). 그래서 다시 연결을 거는 것이 곧 시작 버튼이 된다.
  const step1 = launcherIdle
    ? <Here>
        <p className="font-medium">연결은 됐는데 아직 발행이 멈춰 있습니다.</p>
        <Button size="sm" className="mt-2" disabled={launcher.pairing} onClick={launcher.pairNow}>
          {launcher.pairing ? '시작하는 중…' : '이 PC에서 발행 시작하기'}
        </Button>
        {launcher.pairError && <p className="mt-2 text-xs text-danger">{launcher.pairError}</p>}
        <p className="mt-2 text-xs text-muted-foreground">
          눌리지 않으면 실행기 창에서 <b>[자동 발행 시작]</b>을 눌러도 됩니다.
        </p>
      </Here>
    : launcher.online
      ? <p className="text-sm text-muted-foreground">PC와 실행기를 켜 두세요. 창을 닫아도 서버는 계속 글을 준비합니다.</p>
      : <LauncherCard inline />

  const step2 = !hasCampaign
    ? <QuickAutomationSetup
        clients={clients}
        onCancel={campaigns.length ? () => setCreating(false) : undefined}
        onCreated={async next => {
          setCampaigns(rows => [next, ...rows.filter(row => row.id !== next.id)])
          setSelected(next.id); setCreating(false); setOpened(null)
          void loadList()
        }}
      />
    : ready && campaign && client
      ? <div className="space-y-3">
          <BlogStep campaign={campaign} client={client} setCampaign={setCampaign} onChanged={() => { void reloadClient() }} />
          <Button variant="ghost" size="sm" onClick={() => { setCreating(true); setOpened(2) }}>
            <Plus className="mr-1 h-4 w-4" />다른 병원 추가
          </Button>
        </div>
      : null

  const step3 = ready
    ? <KeywordStep key={selected} campaignId={selected} keywords={keywords} onChanged={() => { void reloadKeywords() }} />
    : null

  const step4 = ready && campaign && client
    ? <PhotoStep campaign={campaign} client={client} setCampaign={setCampaign} skipped={skipPhotos} onSkip={chooseNoPhotos} />
    : null

  const step5 = ready ? (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="발행 방식">
        <button type="button" aria-pressed={mode === 'bulk'} onClick={() => setMode('bulk')}
          className={cn('rounded-xl border p-3 text-left transition-colors', mode === 'bulk' ? 'border-primary bg-primary/5' : 'hover:bg-muted/40')}>
          <span className="block text-sm font-medium">한 번에 여러 개</span>
          <span className="block text-xs text-muted-foreground">지금 30개를 써서 날짜별로 예약</span>
        </button>
        <button type="button" aria-pressed={mode === 'recurring'} onClick={() => setMode('recurring')}
          className={cn('rounded-xl border p-3 text-left transition-colors', mode === 'recurring' ? 'border-primary bg-primary/5' : 'hover:bg-muted/40')}>
          <span className="block text-sm font-medium">매일 자동으로</span>
          <span className="block text-xs text-muted-foreground">매일 정한 개수씩 계속</span>
        </button>
      </div>
      {!started && <Here>개수를 정하고 <b>시작</b>을 누르면 끝입니다. 창을 닫아도 서버가 계속 씁니다.</Here>}
      {mode === 'bulk'
        ? <BulkPublishPanel key={selected} campaignId={selected} noImages={noImages} huntedCount={picked.length}
            onRecurring={() => setMode('recurring')} onStarted={() => { void reloadKeywords() }} />
        : <AutopilotPanel key={selected} campaignId={selected} inline noImages={noImages} onComplete={() => { void loadList() }} />}
    </div>
  ) : null

  return (
    <div className="mx-auto max-w-2xl space-y-3 pb-10">
      {/* 한눈에 — 지금 어디까지 왔는지 막대 네 개로 */}
      <header className="rounded-2xl border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-base font-semibold">{current === -1 ? '자동 운영 중입니다' : `${current + 1}번을 하면 됩니다`}</h1>
          <span className="text-xs tabular-nums text-muted-foreground">{done.filter(Boolean).length} / 4</span>
        </div>
        <ol className="mt-3 flex gap-1.5" aria-label="진행 상황">
          {TITLES.map((title, i) => (
            <li key={title} className="flex-1">
              <span className={cn('block h-1.5 rounded-full', done[i] ? 'bg-success' : i === current ? 'bg-primary' : 'bg-muted')} />
              <span className={cn('mt-1.5 block text-[11px] leading-tight', done[i] || i === current ? 'text-foreground' : 'text-muted-foreground')}>{title}</span>
            </li>
          ))}
        </ol>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 py-10 text-sm" role="status"><Loader2 className="h-4 w-4 animate-spin" />불러오는 중…</div>
      ) : error ? (
        <Card className="space-y-3 p-5"><p role="alert">{error}</p><Button onClick={loadList}>다시 불러오기</Button></Card>
      ) : (
        <>
          {hasCampaign && campaigns.length > 1 && (
            <select aria-label="운영할 병원" className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
              value={selected} onChange={e => { setSelected(e.target.value); setOpened(null); setShowSetup(false) }}>
              {campaigns.map(c => <option key={c.id} value={c.id}>{c.client_name || c.name} · {c.name}</option>)}
            </select>
          )}
          {readError && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">현황을 갱신하지 못했습니다. {readError}</p>}

          {/* 준비(1~3)는 끝나면 한 줄로 사라진다. 바꿀 때만 다시 연다. */}
          {setupDone && !showSetup ? (
            <div className="flex items-center gap-3 rounded-xl border bg-success-soft px-4 py-3">
              <Check className="h-5 w-5 shrink-0 text-success" />
              <p className="min-w-0 flex-1 truncate text-sm">준비 완료 · {notes[1]}</p>
              <Button variant="ghost" size="sm" className="shrink-0" onClick={() => { setShowSetup(true); setOpened(1) }}>
                <Settings2 className="mr-1 h-4 w-4" />준비 다시 하기
              </Button>
            </div>
          ) : (
            <>
              {slot(1, step1)}
              {slot(2, step2)}
              {slot(3, step3)}
              {slot(4, step4)}
              {showSetup && (
                <Button variant="outline" size="sm" className="w-full" onClick={() => { setShowSetup(false); setOpened(null) }}>
                  준비 접기
                </Button>
              )}
            </>
          )}

          {slot(LAST, step5)}

          {ready && campaign && client && <details className="rounded-2xl border bg-card p-5">
            <summary className="cursor-pointer font-semibold">Word 원고로 예약 발행</summary>
            <div className="mt-4"><WordPublishPanel key={campaign.id} campaign={campaign} client={client} onUpdated={setCampaign} /></div>
          </details>}

          {/* 현황 — 단계가 아니라 결과다. 시작한 뒤에만 보인다. */}
          {ready && jobs.length > 0 && (
            <section aria-label="발행 현황" className="space-y-3 rounded-2xl border bg-card p-4">
              <div className="grid grid-cols-4 gap-2">
                {([['공개', completed, 'text-success'], ['예약됨', registered, 'text-primary'], ['대기', waiting, ''],
                   ['확인 필요', attention.length, attention.length ? 'text-warning' : '']] as const).map(([label, count, tone]) => (
                  <div key={label} className="rounded-lg border p-2 text-center">
                    <p className={cn('text-xl font-semibold tabular-nums', tone)}>{count}</p>
                    <p className="text-[11px] text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>

              {attention.length > 0 && (
                <div className="space-y-2 rounded-lg bg-warning-soft p-3">
                  <p className="text-sm font-medium">손봐야 할 글 {attention.length}건</p>
                  {attention.slice(0, 5).map(j => (
                    <div key={j.id} className="space-y-2 rounded-lg border bg-card p-3 text-sm">
                      <p className="truncate font-medium">{j.title}</p>
                      {j.status === 'uncertain' ? (
                        <>
                          <p className="text-xs text-muted-foreground">네이버 <b>예약 글 목록</b>에 이 제목이 있나요?</p>
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" disabled={!!acting} onClick={() => act(`ok-${j.id}`, async () => {
                              await campaignAPI.reconcileJob(j.id, 'registered', CONFIRMED)
                              return '예약된 글로 표시했습니다'
                            })}>있어요</Button>
                            <Button size="sm" variant="outline" disabled={!!acting} onClick={() => act(`no-${j.id}`, async () => {
                              await campaignAPI.reconcileJob(j.id, 'not_registered', NOT_FOUND)
                              try { await campaignAPI.retryJob(j.id); return '다시 올리도록 넣었습니다' }
                              catch { return '없는 글로 정리했습니다' }
                            })}>없어요 · 다시 올리기</Button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p className="text-xs text-muted-foreground">{j.error || '네이버에 올리지 못했습니다.'}</p>
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" disabled={!!acting} onClick={() => act(`retry-${j.id}`, async () => {
                              await campaignAPI.retryJob(j.id)
                              return '다시 올리도록 넣었습니다'
                            })}>다시 시도</Button>
                            <Button size="sm" variant="ghost" disabled={!!acting} onClick={() => act(`cancel-${j.id}`, async () => {
                              await campaignAPI.cancelJob(j.id)
                              return '이 글은 빼 두었습니다'
                            })}>이 글 빼기</Button>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                  {actionMsg && <p role="status" className="text-sm">{actionMsg}</p>}
                </div>
              )}

              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">최근 글 {recent.length}건 보기</summary>
                <ul className="mt-2 divide-y rounded-lg border">
                  {recent.map(j => {
                    const label = JOB_LABEL[j.status] || { label: j.status, tone: 'muted' as Tone }
                    return (
                      <li key={j.id} className="flex items-center gap-3 px-3 py-2">
                        <span className="w-24 shrink-0 text-xs tabular-nums text-muted-foreground">{shortTime(j.scheduled_at)}</span>
                        <span className="min-w-0 flex-1 truncate text-sm">{j.title}</span>
                        <Pill tone={label.tone} className="shrink-0">{label.label}</Pill>
                      </li>
                    )
                  })}
                </ul>
              </details>
            </section>
          )}
        </>
      )}
    </div>
  )
}
