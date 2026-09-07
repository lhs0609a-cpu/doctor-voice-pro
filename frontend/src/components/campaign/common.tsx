'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Loader2, X, ArrowLeft, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Pill as KitPill } from '@/components/app-shell/ui-kit'
import { cn } from '@/lib/utils'
import { campaignAPI, pollTask, type Campaign, type Client, type Task } from '@/lib/campaign-api'

// ───────────────────────── 공용 타입 ─────────────────────────
export interface StepProps {
  campaign: Campaign
  client: Client
  setCampaign: (c: Campaign) => void
  goStep: (n: number) => void
}

export const STEP_LABELS: { n: number; label: string }[] = [
  { n: 1, label: '병원·블로그' },
  { n: 2, label: '키워드' },
  { n: 3, label: '원고' },
  { n: 4, label: '사진' },
  { n: 5, label: '예약' },
  { n: 6, label: '현황' },
]

/** 표 공통 스타일(헤더 12px 대문자, 행 py-2.5, hover). `<Table className={TABLE_CLS}>` */
export const TABLE_CLS =
  'text-sm [&_th]:h-9 [&_th]:px-3 [&_th]:text-[12px] [&_th]:font-medium [&_th]:uppercase [&_th]:tracking-wide [&_th]:text-muted-foreground [&_td]:px-3 [&_td]:py-2.5 [&_tbody_tr]:hover:bg-muted/40 [&_tbody_tr:last-child]:border-0'

// ───────────────────────── 헬퍼 ─────────────────────────
/** 오류 메시지: FastAPI detail 우선, 없으면 message */
export function errMsg(err: any): string {
  const d = err?.response?.data?.detail
  if (typeof d === 'string' && d) return d
  if (d && typeof d === 'object') {
    try { return JSON.stringify(d) } catch { /* noop */ }
  }
  return err?.message || '알 수 없는 오류'
}

export const fmt = (n?: number | null): string => (n ?? 0).toLocaleString('ko-KR')

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd} ${hh}:${mi}`
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

export function todayPlus(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

// ───────────────────────── Pill ─────────────────────────
/** 캠페인 도메인 톤. crit → danger, info → accent 로 디자인 시스템 Pill 에 매핑한다. */
export type Tone = 'ok' | 'warn' | 'crit' | 'muted' | 'info'

export const CAMPAIGN_STATUS_LABEL: Record<string, { label: string; tone: Tone }> = {
  draft: { label: '준비 중', tone: 'muted' },
  scheduled: { label: '예약됨', tone: 'info' },
  running: { label: '발행 중', tone: 'warn' },
  done: { label: '완료', tone: 'ok' },
  cancelled: { label: '취소', tone: 'crit' },
}

const KIT_TONE: Record<Tone, 'ok' | 'warn' | 'danger' | 'accent' | 'muted'> = {
  ok: 'ok', warn: 'warn', crit: 'danger', muted: 'muted', info: 'accent',
}

/** 시맨틱 톤 → 디자인 시스템 Pill 로 변환 */
export const kitTone = (t?: Tone | null) => KIT_TONE[t || 'muted']

export function Pill({ tone = 'muted', children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <KitPill tone={KIT_TONE[tone]} className={className}>
      {title ? <span title={title} className="inline-flex items-center gap-1">{children}</span> : children}
    </KitPill>
  )
}

// ───────────────────────── Chips 입력 ─────────────────────────
export function ChipsInput({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [text, setText] = useState('')
  const commit = () => {
    const parts = text.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)
    if (parts.length) onChange(Array.from(new Set([...value, ...parts])))
    setText('')
  }
  return (
    <div className="flex min-h-[38px] flex-wrap items-center gap-1.5 rounded-lg border border-input bg-card px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1">
      {value.map((v) => (
        <span key={v} className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs">
          {v}
          <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => onChange(value.filter((x) => x !== v))} aria-label="삭제">
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        className="min-w-[80px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        value={text}
        placeholder={placeholder || '입력 후 Enter'}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); commit() } }}
        onBlur={commit}
      />
    </div>
  )
}

// ───────────────────────── 작업 진행률 ─────────────────────────
export function TaskProgress({ taskId, onDone, onTick, className }: {
  taskId: string | null
  onDone?: (t: Task) => void
  onTick?: (t: Task) => void
  className?: string
}) {
  const [task, setTask] = useState<Task | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const onDoneRef = useRef(onDone)
  const onTickRef = useRef(onTick)
  onDoneRef.current = onDone
  onTickRef.current = onTick

  useEffect(() => {
    if (!taskId) { setTask(null); return }
    let alive = true
    setTask(null)
    pollTask(taskId, (t) => { if (alive) { setTask(t); onTickRef.current?.(t) } })
      .then((t) => { if (alive) onDoneRef.current?.(t) })
      .catch((err) => {
        if (!alive) return
        const t: Task = { id: taskId, type: '', status: 'failed', progress: 0, total: 0, error: errMsg(err) }
        setTask(t)
        onDoneRef.current?.(t)
      })
    return () => { alive = false }
  }, [taskId])

  if (!taskId) return null
  const pct = task && task.total > 0 ? Math.min(100, Math.round((task.progress / task.total) * 100)) : 0
  const active = !task || task.status === 'pending' || task.status === 'running'

  const cancel = async () => {
    setCancelling(true)
    try { await campaignAPI.cancelTask(taskId) } catch { /* noop */ } finally { setCancelling(false) }
  }

  return (
    <div className={cn('space-y-2 rounded-lg bg-muted/60 p-3', className)}>
      <div className="flex items-center gap-2 text-sm">
        {active ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
        <span className="flex-1 truncate">
          {task?.message || (active ? '작업을 시작하는 중...' : '')}
          {task?.status === 'failed' && <span className="text-danger"> 실패: {task.error || '알 수 없는 오류'}</span>}
          {task?.status === 'cancelled' && <span className="text-muted-foreground"> 취소됨</span>}
          {task?.status === 'done' && !task?.message && <span className="text-success">완료</span>}
        </span>
        {task && task.total > 0 && (
          <span className="text-xs tabular-nums text-muted-foreground">{fmt(task.progress)}/{fmt(task.total)}</span>
        )}
        {active && (
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={cancel} disabled={cancelling}>
            취소
          </Button>
        )}
      </div>
      {active && <Progress value={task && task.total > 0 ? pct : undefined} className="h-1.5" />}
    </div>
  )
}

/** 작업 결과 토스트용 요약 (done/failed/cancelled) */
export function taskOutcome(t: Task): { ok: boolean; text: string } {
  if (t.status === 'done') return { ok: true, text: t.message || '완료' }
  if (t.status === 'cancelled') return { ok: false, text: '취소됨' }
  return { ok: false, text: t.error || t.message || '실패' }
}

// ───────────────────────── 단계 이동 푸터 ─────────────────────────
export function StepFooter({ onBack, onNext, nextLabel, nextDisabled, children }: {
  onBack?: () => void
  onNext?: () => void
  nextLabel?: string
  nextDisabled?: boolean
  children?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t pt-4">
      <div>
        {onBack && (
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft /> 이전
          </Button>
        )}
      </div>
      <div className="flex items-center gap-3">
        {children}
        {onNext && (
          <Button variant="outline" onClick={onNext} disabled={nextDisabled}>
            {nextLabel || '다음'} <ArrowRight />
          </Button>
        )}
      </div>
    </div>
  )
}

// ───────────────────────── 빈 상태 ─────────────────────────
export function EmptyNote({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('rounded-xl border border-dashed px-6 py-10 text-center text-sm text-muted-foreground', className)}>{children}</div>
}
