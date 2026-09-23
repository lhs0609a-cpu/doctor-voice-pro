'use client'

// 예약 간격 정하기 — 원스톱 화면의 마지막 한 걸음.
//
// 마법사의 5단계(기간 안에 흩뿌리기)는 시작일·기간·하루 건수·블로그를 모두 고르게 한다.
// 여기서는 묻는 것이 둘뿐이다. "언제부터"와 "몇 시간마다". 나머지(블로그·시간대)는 이미
// 등록해 둔 값을 그대로 쓴다. 고르는 즉시 실제 예약 시각을 보여 주고, 한 번 더 누르면 끝난다.
//
// 이미 걸려 있는 예약은 서버가 피해서 잡는다(우리 예약 + 실행기가 읽어 온 네이버 예약).
// 그래서 예약이 있으면 기본값은 '이미 예약된 글 다음부터'다 — 날짜를 세어 보는 일은
// 사람이 아니라 서버가 한다.
//
// 네이버는 '예약 발행'으로만 올린다(실행기가 즉시 발행을 막는다). 그래서 '지금 바로'도
// 실제로는 30분 뒤 예약이다 — 화면에 그 시각을 그대로 적어 헷갈리지 않게 한다.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarClock, Loader2, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { campaignAPI, type BlogReservations, type Campaign, type Client, type SchedulePreview } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'
import { wakeLauncher } from '@/lib/use-launcher-status'
import { cn } from '@/lib/utils'

/** 실행기가 예약을 걸 수 있는 가장 이른 시각(서버도 30분을 요구한다). */
const LEAD_MINUTES = 30

const GAPS = [
  { minutes: 30, label: '30분' },
  { minutes: 60, label: '1시간' },
  { minutes: 120, label: '2시간' },
  { minutes: 180, label: '3시간' },
  { minutes: 360, label: '6시간' },
  { minutes: 1440, label: '하루 1개' },
]

/** 브라우저가 어느 시간대에 있든 한국 시각으로 본다. 서버·네이버가 모두 KST 기준이다. */
function kstNow() {
  const now = new Date()
  return new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000)
}

function pad(n: number) { return String(n).padStart(2, '0') }
function ymd(d: Date) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` }
function hm(d: Date) { return `${pad(d.getHours())}:${pad(d.getMinutes())}` }

/** 10분 단위 올림 — 네이버 예약은 10분 단위만 받는다. */
function ceil10(d: Date) {
  const out = new Date(d)
  out.setSeconds(0, 0)
  const rest = out.getMinutes() % 10
  if (rest) out.setMinutes(out.getMinutes() + (10 - rest))
  return out
}

function soonest() { return ceil10(new Date(kstNow().getTime() + LEAD_MINUTES * 60000)) }

function tomorrowMorning() {
  const d = kstNow()
  d.setDate(d.getDate() + 1)
  d.setHours(9, 0, 0, 0)
  return d
}

/** 9/23(수) 14:40 */
function human(iso?: string | null) {
  if (!iso) return ''
  const [day, clock] = iso.split('T')
  const [, m, d] = day.split('-')
  const week = ['일', '월', '화', '수', '목', '금', '토'][new Date(`${day}T00:00:00`).getDay()]
  return `${Number(m)}/${Number(d)}(${week}) ${clock?.slice(0, 5) || ''}`
}

type When = 'after' | 'now' | 'tomorrow' | 'pick'

export function QuickSchedule({ campaign, client, draftIds, onScheduled, onBack, onUpdated }: {
  campaign: Campaign
  client: Client
  draftIds: string[]
  /** 예약이 걸린 뒤 — 완료 화면으로 넘긴다. */
  onScheduled: () => void
  /** 아무것도 걸지 않고 원고 고르기로 돌아간다. */
  onBack: () => void
  onUpdated: (value: Campaign) => void
}) {
  const [when, setWhen] = useState<When>('now')
  const [date, setDate] = useState(() => ymd(tomorrowMorning()))
  const [clock, setClock] = useState('09:00')
  const [gap, setGap] = useState(120)
  const [preview, setPreview] = useState<SchedulePreview | null>(null)
  const [booked, setBooked] = useState<BlogReservations[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [freeing, setFreeing] = useState('')
  const [rescanning, setRescanning] = useState(false)
  const [rescanMsg, setRescanMsg] = useState('')
  const [error, setError] = useState('')

  // 이미 잡혀 있는 자리를 먼저 읽는다. 있으면 '그 다음부터'가 기본이 된다.
  useEffect(() => {
    let alive = true
    campaignAPI.listReservations(campaign.id)
      .then(rows => {
        if (!alive || !Array.isArray(rows)) return
        setBooked(rows)
        if (rows.some(r => (r.count || 0) > 0)) setWhen('after')
      })
      .catch(() => { /* 못 읽어도 '지금 바로'로 잡으면 된다 */ })
    return () => { alive = false }
  }, [campaign.id])

  const known = booked.reduce((sum, r) => sum + (r.count || 0), 0)
  const lastBooked = booked.map(r => r.last_at || '').filter(Boolean).sort().pop() || ''
  const scannedAt = booked.map(r => r.scanned_at || '').filter(Boolean).sort().pop() || ''
  const stale = booked.some(r => r.stale)

  // 고른 '언제부터'를 한국 시각 문자열로. 지난 시각을 고르면 가장 이른 시각으로 끌어올린다.
  const startAt = useMemo(() => {
    const floor = soonest()
    if (when === 'now' || when === 'after') return `${ymd(floor)}T${hm(floor)}`
    const base = when === 'tomorrow' ? tomorrowMorning() : new Date(`${date}T${clock || '09:00'}:00`)
    const safe = Number.isNaN(base.getTime()) || base < floor ? floor : base
    return `${ymd(safe)}T${hm(safe)}`
  }, [when, date, clock])

  const input = useMemo(() => ({
    start_date: startAt.slice(0, 10),
    days: 60,
    draft_ids: draftIds,
    mode: 'interval' as const,
    start_at: startAt,
    every_minutes: gap,
    start_mode: (when === 'after' ? 'after_last' : 'at') as 'after_last' | 'at',
  }), [startAt, gap, draftIds, when])

  // 고르는 즉시 실제 시각을 보여 준다 — '미리보기' 단추를 따로 누르게 하지 않는다.
  const load = useCallback(async () => {
    if (!draftIds.length) return
    setLoading(true); setError('')
    try {
      const next = await campaignAPI.schedulePreview(campaign.id, input)
      setPreview(next)
      if (next.reservations?.length) setBooked(next.reservations)
    } catch (e) { setPreview(null); setError(errMsg(e)) }
    finally { setLoading(false) }
  }, [campaign.id, input, draftIds.length])

  useEffect(() => {
    const timer = setTimeout(() => { void load() }, 350)
    return () => clearTimeout(timer)
  }, [load])

  const commit = async () => {
    setSaving(true); setError('')
    try {
      await campaignAPI.scheduleCommit(campaign.id, input)
      // 예약을 걸었으면 네이버 등록도 지금 시작해야 한다 — 실행기의 다음 주기를 기다리지 않는다.
      void wakeLauncher()
      try { onUpdated(await campaignAPI.getCampaign(campaign.id)) } catch { /* 현황은 다음 주기에 읽힌다 */ }
      onScheduled()
    } catch (e) { setError(errMsg(e)) }
    finally { setSaving(false) }
  }

  const rescan = async () => {
    setRescanning(true); setRescanMsg('')
    try {
      await campaignAPI.rescanReservations(campaign.id)
      setRescanMsg('실행기가 다음 차례에 네이버 예약 목록을 읽어 옵니다.')
    } catch (e) { setRescanMsg(errMsg(e)) }
    finally { setRescanning(false) }
  }

  /** 네이버에서 직접 지운 예약을 장부에서도 뺀다. 안 그러면 없는 예약을 피해 계속 뒤로 밀린다. */
  const freeSlot = async (blogRefId: string, at: string) => {
    setFreeing(at); setRescanMsg('')
    try {
      setBooked(await campaignAPI.freeReservationSlot(campaign.id, blogRefId, at))
      setRescanMsg('그 시각을 비웠습니다. 다음 글이 그 자리에 들어갑니다.')
      try { onUpdated(await campaignAPI.getCampaign(campaign.id)) } catch { /* 현황은 다음 주기에 읽힌다 */ }
    } catch (e) { setRescanMsg(errMsg(e)) }
    finally { setFreeing('') }
  }

  const blogs = client.blogs.filter(b => campaign.blog_ids.includes(b.id) && b.status === 'active')
  const times = preview?.assigned || []
  const last = times[times.length - 1]
  const anchor = preview?.starts_after || lastBooked

  return (
    <div className="space-y-5">
      {/* 이미 잡혀 있는 자리 — 세어서 말해 준다 */}
      <section aria-label="이미 예약된 글" className="rounded-xl border bg-card p-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p>
            {known > 0
              ? <>이미 예약된 글 <b className="tabular-nums">{known}건</b>{lastBooked && <> · 마지막 <b>{human(lastBooked)}</b></>}</>
              : <>이미 예약된 글이 없습니다.</>}
          </p>
          <Button variant="ghost" size="sm" disabled={rescanning} onClick={rescan}>
            {rescanning ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1 h-4 w-4" />}
            예약 목록 새로 읽기
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {stale
            ? `여기서 잡은 예약끼리는 겹치지 않습니다. 네이버 예약 목록은 ${scannedAt ? `${human(scannedAt)}에 확인했습니다` : '아직 확인하지 못했습니다'} — 손으로 따로 예약한 글이 있다면 새로 읽어 주세요.`
            : `네이버 예약 목록을 ${human(scannedAt)}에 확인했습니다. 그 시간대는 피해서 잡습니다.`}
        </p>
        {/* 자리 하나하나를 보여 주고 손으로 뺄 수 있게 한다. 네이버에서 직접 지운 예약은
            우리에게 알려 오지 않아서, 이 길이 없으면 없는 예약을 피해 계속 뒤로 밀린다. */}
        {booked.flatMap(r => (r.slots || []).map(slot => (
          <div key={`${r.blog_ref_id}-${slot.at}`} className="mt-1 flex items-center gap-2 text-xs">
            <span className="tabular-nums text-muted-foreground">{human(slot.at)}</span>
            <span className="min-w-0 flex-1 truncate">{slot.title || (slot.source === 'naver' ? '네이버에 걸린 예약' : '예약된 글')}</span>
            <button type="button" aria-label={`${human(slot.at)} 예약 빼기`}
              title="네이버에서 직접 취소했다면 눌러 주세요. 이 시각이 다시 비워집니다."
              disabled={freeing === slot.at}
              onClick={() => void freeSlot(r.blog_ref_id, slot.at)}
              className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40">
              {freeing === slot.at ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        )))}
        {rescanMsg && <p role="status" className="mt-1 text-xs text-primary">{rescanMsg}</p>}
        {/* 목록을 못 읽었으면 숨기지 않는다. 조용히 넘어가면 '없는 예약'을 피해 계속 뒤로 밀린다. */}
        {booked.filter(r => r.note).map(r => (
          <p key={`note-${r.blog_ref_id}`} className="mt-1 text-xs text-warning">
            {r.label}: {r.note} — 네이버에서 직접 취소한 글은 위 목록에서 <b>휴지통</b>으로 빼 주시면 그 시각이 비워집니다.
          </p>
        ))}
      </section>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">언제부터 올릴까요?</legend>
        <div className="flex flex-wrap gap-2">
          {([
            ...(known > 0 ? [['after', '이미 예약된 글 다음부터'] as const] : []),
            ['now', `지금 바로 · ${hm(soonest())}`] as const,
            ['tomorrow', '내일 아침 9시'] as const,
            ['pick', '날짜 직접 고르기'] as const,
          ]).map(([key, label]) => (
            <button key={key} type="button" onClick={() => setWhen(key)}
              className={cn('rounded-lg border px-3 py-2 text-sm transition-colors',
                when === key ? 'border-primary bg-primary/10 font-medium' : 'hover:bg-muted/40')}>
              {label}
            </button>
          ))}
        </div>
        {when === 'pick' && (
          <div className="flex flex-wrap gap-2 pt-1">
            <Input aria-label="시작 날짜" type="date" className="w-40" value={date} min={ymd(kstNow())}
              onChange={e => setDate(e.target.value)} />
            <Input aria-label="시작 시각" type="time" step={600} className="w-32" value={clock}
              onChange={e => setClock(e.target.value)} />
          </div>
        )}
        {when === 'after' && (
          <p className="text-xs text-muted-foreground">
            마지막 예약 {human(anchor)} 뒤로 이어 붙입니다.
          </p>
        )}
        {when === 'now' && (
          <p className="text-xs text-muted-foreground">
            네이버는 예약으로만 올립니다. 가장 빠른 예약이 {LEAD_MINUTES}분 뒤라 {hm(soonest())}에 첫 글이 올라갑니다.
            {known > 0 && ' 이미 예약된 시간대는 알아서 건너뜁니다.'}
          </p>
        )}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">글 사이 간격</legend>
        <div className="flex flex-wrap gap-2">
          {GAPS.map(g => (
            <button key={g.minutes} type="button" onClick={() => setGap(g.minutes)}
              className={cn('rounded-lg border px-3 py-2 text-sm tabular-nums transition-colors',
                gap === g.minutes ? 'border-primary bg-primary/10 font-medium' : 'hover:bg-muted/40')}>
              {g.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {blogs.length > 1
            ? `블로그 ${blogs.length}개에 번갈아 올립니다. 발행 시간대 밖으로는 나가지 않습니다.`
            : `발행 시간대(${blogs[0]?.window_start || '09:00'}~${blogs[0]?.window_end || '21:00'}) 밖이면 다음 날 같은 시간대로 넘어갑니다.`}
        </p>
      </fieldset>

      <section aria-label="예약 시각 미리보기" className="rounded-xl border bg-muted/30 p-4">
        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="h-4 w-4 animate-spin" />예약 시각을 계산하는 중…
          </p>
        ) : times.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {error ? '예약할 수 없습니다. 아래 안내를 보세요.' : '올릴 원고를 고르면 예약 시각이 보입니다.'}
          </p>
        ) : (
          <div className="space-y-2">
            <p className="text-sm">
              <b className="tabular-nums">{times.length}건</b>을 <b>{human(times[0].scheduled_at)}</b>부터
              {last && times.length > 1 && <> <b>{human(last.scheduled_at)}</b>까지</>} 올립니다.
            </p>
            <ul className="space-y-1 text-xs tabular-nums text-muted-foreground">
              {times.slice(0, 5).map(a => (
                <li key={`${a.draft_id}-${a.scheduled_at}`} className="flex gap-2">
                  <span className="w-28 shrink-0">{human(a.scheduled_at)}</span>
                  <span className="min-w-0 flex-1 truncate">{a.title}</span>
                  {blogs.length > 1 && <span className="shrink-0">{a.blog_label}</span>}
                </li>
              ))}
              {times.length > 5 && <li>… 외 {times.length - 5}건</li>}
            </ul>
            {preview?.warnings?.map((w, i) => (
              <p key={i} className="rounded-lg bg-warning-soft p-2 text-xs text-warning">{w}</p>
            ))}
          </div>
        )}
      </section>

      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={saving || loading || times.length === 0} onClick={commit}>
          {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <CalendarClock className="mr-1 h-4 w-4" />}
          {saving ? '예약하는 중…' : `${times.length}건 예약하기`}
        </Button>
        <Button variant="ghost" onClick={onBack} disabled={saving}>뒤로</Button>
      </div>
    </div>
  )
}
