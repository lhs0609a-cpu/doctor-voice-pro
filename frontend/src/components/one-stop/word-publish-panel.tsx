'use client'

// Word 원고 올리기 → 예약. 원스톱의 마지막 칸.
//
// 묻는 것은 둘뿐이다. 어떤 원고를 올릴지, 언제·몇 시간 간격으로 올릴지.
// 강조 서식은 한 번 정해 두면 그대로 쓰이므로 접어 둔다(바꾸고 싶을 때만 편다).
//
// 파일은 **끌어다 놓는 것이 기본**이다. 원고 열 개를 하나씩 고르게 하지 않는다.
// 한 건씩 따로 올리는 이유는 하나다 — 서버는 한 파일이라도 읽다 실패하면 그 요청 전체를
// 물린다. 스무 개를 한 번에 보내면 깨진 파일 하나 때문에 열아홉 개가 같이 사라진다.

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Loader2, Trash2, Upload, X } from 'lucide-react'
import { campaignAPI, type Campaign, type Client, type Draft } from '@/lib/campaign-api'
import { PointFormattingPanel } from '@/components/campaign/point-formatting'
import { Button } from '@/components/ui/button'
import { errMsg } from '@/components/campaign/common'
import { cn } from '@/lib/utils'
import { QuickSchedule } from './quick-schedule'

/** 동시에 보내는 개수. 서버가 사진까지 풀에 저장하므로 너무 많이 밀면 느려진다. */
const AT_ONCE = 2

type Job = { name: string; state: 'wait' | 'up' | 'done' | 'review' | 'fail'; note?: string }

const STATE: Record<Job['state'], { label: string; tone: string }> = {
  wait: { label: '차례 기다리는 중', tone: 'text-muted-foreground' },
  up: { label: '올리는 중…', tone: 'text-primary' },
  done: { label: '완료', tone: 'text-success' },
  review: { label: '원고 검토 필요', tone: 'text-warning' },
  fail: { label: '실패', tone: 'text-destructive' },
}

function isWord(file: File) {
  return file.name.toLowerCase().endsWith('.docx')
}

/** 9/24(목) 09:00 */
function whenLabel(iso?: string | null) {
  if (!iso) return ''
  const [day, clock] = iso.split('T')
  const [, m, d] = day.split('-')
  const week = ['일', '월', '화', '수', '목', '금', '토'][new Date(`${day}T00:00:00`).getDay()]
  return `${Number(m)}/${Number(d)}(${week}) ${clock?.slice(0, 5) || ''}`
}

type Flag = { text?: string; category?: string; suggestion?: string }
type Fix = { from?: string; to?: string; category?: string }

/** 올릴 때 서버가 알아서 고친 의료광고 표현. 막지 않고 고치므로 '무엇을 고쳤는지'만 알리면 된다. */
function fixesOf(draft: Draft): Fix[] {
  const checks = (draft.checks || {}) as Record<string, unknown>
  return Array.isArray(checks.auto_fixed) ? (checks.auto_fixed as Fix[]) : []
}

/** '원고 검토 필요'의 실제 이유. 서버가 글자 패턴으로 잡은 것들이다. */
function flagsOf(draft: Draft): Flag[] {
  const checks = (draft.checks || {}) as Record<string, unknown>
  const law = Array.isArray(checks.medical_law) ? (checks.medical_law as Flag[]) : []
  const words = Array.isArray(checks.forbidden) ? (checks.forbidden as string[]) : []
  return [...law, ...words.map(w => ({ text: w, category: '병원 금칙어' }))]
}

export function WordPublishPanel({ campaign, client, onUpdated }: {
  campaign: Campaign; client: Client; onUpdated: (value: Campaign) => void
}) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [saved, setSaved] = useState(false)
  const [jobs, setJobs] = useState<Job[]>([])
  const [uploading, setUploading] = useState(false)
  const [dropping, setDropping] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState('')        // 검수 이유를 펴 둔 원고
  const [busy, setBusy] = useState('')        // 확인/지우기 중인 원고
  const [step, setStep] = useState<'upload' | 'schedule' | 'done'>('upload')
  const depth = useRef(0)          // dragenter/leave 는 자식 위를 지날 때도 울린다 — 세어야 한다

  useEffect(() => {
    campaignAPI.listDrafts(campaign.id)
      .then(rows => {
        const mine = rows.filter(d => d.source === 'upload')
        setDrafts(mine)
        const pickable = new Set(mine.filter(d => d.status === 'ready' && !d.booked_at).map(d => d.id))
        setSelected(previous => previous.filter(id => pickable.has(id)))
      })
      .catch(e => setError(errMsg(e)))
  }, [campaign.id])

  // 칸 밖에 떨어뜨리면 브라우저가 그 파일을 열어 버린다(화면이 통째로 바뀐다).
  // 이 칸이 떠 있는 동안에는 창 전체에서 기본 동작을 막아 둔다.
  useEffect(() => {
    const stop = (e: DragEvent) => { if (e.dataTransfer?.types?.includes('Files')) e.preventDefault() }
    window.addEventListener('dragover', stop)
    window.addEventListener('drop', stop)
    return () => { window.removeEventListener('dragover', stop); window.removeEventListener('drop', stop) }
  }, [])

  const take = useCallback(async (picked: File[]) => {
    const words = picked.filter(isWord)
    const others = picked.filter(f => !isWord(f))
    setError(others.length
      ? `워드(.docx) 파일만 올릴 수 있습니다. ${others.map(f => f.name).join(', ')} 은(는) 건너뛰었습니다.`
      : '')
    if (!words.length) return

    const base = jobs.length
    setJobs(previous => [...previous, ...words.map(f => ({ name: f.name, state: 'wait' as const }))])
    setUploading(true)
    const mark = (i: number, patch: Partial<Job>) =>
      setJobs(previous => previous.map((j, n) => (n === base + i ? { ...j, ...patch } : j)))

    // 한 건씩(동시에 몇 개만) 보낸다. 하나가 실패해도 나머지는 그대로 올라간다.
    let cursor = 0
    const worker = async () => {
      for (let i = cursor++; i < words.length; i = cursor++) {
        mark(i, { state: 'up' })
        try {
          const rows = await campaignAPI.uploadDrafts(campaign.id, [words[i]])
          setDrafts(previous => [...previous, ...rows])
          setSelected(previous => [...previous, ...rows.filter(d => d.status === 'ready' && !d.booked_at).map(d => d.id)])
          const needsReview = rows.some(d => d.status !== 'ready')
          mark(i, { state: needsReview ? 'review' : 'done' })
        } catch (err) {
          mark(i, { state: 'fail', note: errMsg(err) })
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(AT_ONCE, words.length) }, worker))
    setUploading(false)
  }, [campaign.id, jobs.length])

  // 검수는 글자 패턴이라 오탐이 많다. 올린 사람이 보고 판단하면 그대로 쓴다.
  const approve = async (d: Draft) => {
    setBusy(d.id); setError('')
    try {
      const next = await campaignAPI.approveDraft(d.id)
      setDrafts(previous => previous.map(x => (x.id === d.id ? next : x)))
      setSelected(previous => (previous.includes(d.id) ? previous : [...previous, d.id]))
      setOpen('')
    } catch (e) { setError(errMsg(e)) } finally { setBusy('') }
  }

  // 예약 취소 — 아직 네이버에 올리지 않았으면 자리까지 비워 준다.
  const unbook = async (d: Draft) => {
    if (!d.booked_job_id) return
    setBusy(d.id); setError('')
    try {
      await campaignAPI.cancelJob(d.booked_job_id)
      const rows = await campaignAPI.listDrafts(campaign.id)
      setDrafts(rows.filter(x => x.source === 'upload'))
    } catch (e) { setError(errMsg(e)) } finally { setBusy('') }
  }

  const remove = async (d: Draft) => {
    setBusy(d.id); setError('')
    try {
      await campaignAPI.deleteDraft(d.id)
      setDrafts(previous => previous.filter(x => x.id !== d.id))
      setSelected(previous => previous.filter(id => id !== d.id))
    } catch (e) { setError(errMsg(e)) } finally { setBusy('') }
  }

  if (step === 'done') return (
    <div className="space-y-3">
      <p role="status">예약을 걸었습니다. PC 실행기가 네이버 예약 등록을 진행합니다. 아래 발행 현황에서 결과를 확인하세요.</p>
      <Button variant="outline" onClick={() => { setSelected([]); setJobs([]); setStep('upload') }}>다른 Word 원고 올리기</Button>
    </div>
  )

  if (step === 'schedule') return (
    <QuickSchedule campaign={campaign} client={client} draftIds={selected}
      onUpdated={onUpdated} onScheduled={() => setStep('done')} onBack={() => setStep('upload')} />
  )

  const waiting = jobs.filter(j => j.state === 'wait' || j.state === 'up').length
  const failed = jobs.filter(j => j.state === 'fail').length

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Word 파일을 올리면 글·표·사진이 그대로 저장됩니다. 그다음 언제부터 몇 시간 간격으로 올릴지만 고르면 끝입니다.
      </p>

      {/* 끌어다 놓는 칸. 눌러서 고르는 길도 그대로 둔다. */}
      <label
        onDragEnter={e => { e.preventDefault(); depth.current += 1; setDropping(true) }}
        onDragOver={e => e.preventDefault()}
        onDragLeave={e => { e.preventDefault(); depth.current -= 1; if (depth.current <= 0) setDropping(false) }}
        onDrop={async e => {
          e.preventDefault()
          depth.current = 0
          setDropping(false)
          const files = Array.from(e.dataTransfer?.files || [])
          if (files.length) await take(files)
        }}
        className={cn('flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center text-sm transition-colors',
          dropping ? 'border-primary bg-primary/10' : 'hover:bg-muted/30')}
      >
        <Upload className={cn('h-6 w-6', dropping ? 'text-primary' : 'text-muted-foreground')} />
        <span className="font-medium">
          {dropping ? '여기에 놓으면 한꺼번에 올라갑니다' : 'Word 파일을 여기로 끌어다 놓으세요'}
        </span>
        <span className="text-xs text-muted-foreground">여러 개를 한 번에 놓아도 됩니다 · 눌러서 고를 수도 있습니다 (.docx)</span>
        <input aria-label="예약할 Word 파일" className="sr-only" type="file" accept=".docx" multiple disabled={uploading}
          onChange={async e => {
            const input = e.currentTarget
            const files = Array.from(input.files || [])
            if (files.length) await take(files)
            input.value = ''
          }} />
      </label>

      {/* 올리는 중인 파일들 — 한 건씩 상태를 보여 준다. 실패한 것만 다시 올리면 된다. */}
      {jobs.length > 0 && (
        <div className="space-y-2 rounded-lg border p-3">
          <div className="flex items-center justify-between gap-2 text-sm">
            <p className="font-medium">
              올린 파일 {jobs.length}개
              {waiting > 0 && <span className="ml-2 font-normal text-muted-foreground">{waiting}개 남음</span>}
              {failed > 0 && <span className="ml-2 font-normal text-destructive">{failed}개 실패</span>}
            </p>
            {!uploading && (
              <Button variant="ghost" size="sm" onClick={() => setJobs([])}>목록 지우기</Button>
            )}
          </div>
          <ul className="space-y-1 text-sm">
            {jobs.map((j, i) => (
              <li key={`${j.name}-${i}`} className="flex items-center gap-2">
                {j.state === 'up' ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                  : j.state === 'done' ? <Check className="h-4 w-4 shrink-0 text-success" />
                  : j.state === 'fail' ? <X className="h-4 w-4 shrink-0 text-destructive" />
                  : j.state === 'review' ? <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
                  : <span className="h-4 w-4 shrink-0" />}
                <span className="min-w-0 flex-1 truncate">{j.name}</span>
                <span className={cn('shrink-0 text-xs', STATE[j.state].tone)}>{STATE[j.state].label}</span>
              </li>
            ))}
          </ul>
          {jobs.filter(j => j.note).slice(0, 3).map((j, i) => (
            <p key={i} className="text-xs text-destructive">{j.name}: {j.note}</p>
          ))}
        </div>
      )}

      {drafts.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {drafts.map(d => {
            const flags = flagsOf(d)
            const fixes = fixesOf(d)
            const review = d.status !== 'ready'
            const booked = !!d.booked_at          // 이미 예약이 걸린 원고는 다시 걸 수 없다
            return (
              <li key={d.id} className="px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <input type="checkbox" id={`pick-${d.id}`} checked={selected.includes(d.id)} disabled={review || booked}
                    onChange={e => setSelected(value => e.target.checked ? [...value, d.id] : value.filter(id => id !== d.id))} />
                  <label htmlFor={`pick-${d.id}`} className={cn('min-w-0 flex-1 truncate', (review || booked) ? 'text-muted-foreground' : 'cursor-pointer')}>
                    {d.title}
                  </label>
                  {booked && (
                    <>
                      <span className="shrink-0 text-xs text-success">예약됨 · {whenLabel(d.booked_at)}</span>
                      {d.booked_status === 'queued' ? (
                        <button type="button" disabled={!!busy} onClick={() => void unbook(d)}
                          className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-destructive hover:underline disabled:opacity-40">
                          {busy === d.id ? '취소하는 중…' : '예약 취소'}
                        </button>
                      ) : (
                        <span className="shrink-0 text-xs text-muted-foreground">네이버에 등록됨</span>
                      )}
                    </>
                  )}
                  {booked ? null : review ? (
                    <button type="button" onClick={() => setOpen(open === d.id ? '' : d.id)}
                      className="shrink-0 text-xs text-warning underline-offset-2 hover:underline">
                      검토 필요 {flags.length > 0 && `· ${flags.length}곳`}
                    </button>
                  ) : fixes.length > 0 && (
                    <button type="button" onClick={() => setOpen(open === d.id ? '' : d.id)}
                      className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:underline">
                      표현 {fixes.length}곳 고침
                    </button>
                  )}
                  <button type="button" aria-label={`${d.title} 빼기`}
                    title={booked ? '예약을 먼저 취소하세요' : '이 원고 빼기'}
                    disabled={!!busy || booked} onClick={() => void remove(d)}
                    className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40">
                    {busy === d.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  </button>
                </div>

                {!review && open === d.id && fixes.length > 0 && (
                  <div className="mt-2 space-y-2 rounded-lg bg-muted/50 p-3">
                    <p className="text-xs">
                      의료광고법에 걸릴 수 있는 표현을 <b>올릴 때 자동으로 고쳤습니다.</b>
                      바꿔 쓸 말이 없는 가격·할인 문장은 그 문장을 덜어냈습니다.
                    </p>
                    <ul className="space-y-1 text-xs">
                      {fixes.slice(0, 8).map((f, i) => (
                        <li key={i} className="flex flex-wrap items-center gap-1.5">
                          <s className="text-muted-foreground">{f.from}</s>
                          <span>→</span>
                          <b className="rounded bg-card px-1.5 py-0.5">{f.to || '(문장 삭제)'}</b>
                          <span className="text-muted-foreground">{f.category}</span>
                        </li>
                      ))}
                      {fixes.length > 8 && <li className="text-muted-foreground">… 외 {fixes.length - 8}곳</li>}
                    </ul>
                  </div>
                )}

                {review && open === d.id && (
                  <div className="mt-2 space-y-2 rounded-lg bg-warning-soft p-3">
                    <p className="text-xs">
                      <b>병원에 등록해 둔 금칙어</b>가 들어 있어 세워 둔 원고입니다.
                      (의료광고 표현은 올릴 때 자동으로 고치므로 여기서 막지 않습니다.)
                    </p>
                    {flags.length > 0 ? (
                      <ul className="space-y-1 text-xs">
                        {flags.slice(0, 8).map((f, i) => (
                          <li key={i} className="flex flex-wrap items-center gap-1.5">
                            <b className="rounded bg-card px-1.5 py-0.5">{f.text || '(표현)'}</b>
                            <span className="text-muted-foreground">{f.category}</span>
                            {f.suggestion && <span className="text-muted-foreground">→ {f.suggestion}</span>}
                          </li>
                        ))}
                        {flags.length > 8 && <li className="text-muted-foreground">… 외 {flags.length - 8}곳</li>}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground">걸린 표현을 따로 적어 두지 않았습니다. 원고를 한 번 훑어보세요.</p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" disabled={busy === d.id} onClick={() => void approve(d)}>
                        {busy === d.id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
                        확인했습니다 · 이대로 올리기
                      </Button>
                      <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => void remove(d)}>
                        이 원고 빼기
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {drafts.some(d => d.status !== 'ready') && (
        <p className="text-xs text-muted-foreground">
          검토가 필요한 원고는 <b>확인 전까지 예약되지 않습니다</b>. 줄 오른쪽의 &lsquo;검토 필요&rsquo;를 눌러 이유를 보세요.
        </p>
      )}
      {drafts.length > 0 && drafts.every(d => d.booked_at) && (
        <p className="text-sm text-muted-foreground">
          올린 원고가 모두 예약되어 있습니다. 더 올리려면 <b>새 Word 파일</b>을 놓으시고,
          시간을 바꾸려면 줄 오른쪽의 <b>[예약 취소]</b>를 누른 뒤 다시 잡으세요.
        </p>
      )}
      {drafts.some(d => d.status === 'ready' && fixesOf(d).length > 0) && (
        <p className="text-xs text-muted-foreground">
          의료광고법에 걸릴 수 있는 표현은 <b>올릴 때 자동으로 고쳤습니다</b>. 줄 오른쪽의 &lsquo;표현 N곳 고침&rsquo;에서 확인하세요.
        </p>
      )}

      <details className="rounded-lg border px-3 py-2">
        <summary className="cursor-pointer text-sm text-muted-foreground">글자 강조 설정 바꾸기</summary>
        <div className="mt-3">
          <PointFormattingPanel campaignId={campaign.id} drafts={drafts} onSavedState={setSaved} />
        </div>
      </details>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      <div className="space-y-2">
        <Button disabled={!saved || uploading || selected.length === 0} onClick={() => setStep('schedule')}>
          선택한 {selected.length}개 원고 예약하기
        </Button>
        {/* 강조 설정은 접혀 있어 저장이 막히면 이유가 보이지 않는다 — 여기서 알려 준다. */}
        {!saved && selected.length > 0 && (
          <p className="text-xs text-muted-foreground">강조 설정을 저장하는 중입니다. 잠시 뒤 눌러 주세요(멈춰 있으면 위 설정을 펴서 확인하세요).</p>
        )}
      </div>
    </div>
  )
}
