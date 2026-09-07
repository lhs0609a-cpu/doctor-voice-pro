'use client'

/**
 * 내 블로그 기준 상위노출 판정 표. VerdictSummary(+detail) 목록을 보여준다.
 * 체크박스로 고른 키워드를 onSelectionChange 로 돌려준다(가능성 높음·경합만 남기기 등).
 */
import { Fragment, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Pill } from '@/components/app-shell/ui-kit'
import { cn } from '@/lib/utils'
import { VERDICT_LABEL, VERDICT_TONE, type VerdictDetail, type VerdictSummary } from '@/lib/blog-index-api'

export type VerdictRow = VerdictSummary & { detail?: VerdictDetail }

const CONF_LABEL: Record<string, string> = { high: '높음', medium: '보통', mid: '보통', low: '낮음' }
const num = (v?: number | null, digits = 0) => (v == null || Number.isNaN(v) ? '측정 불가' : v.toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits }))

const BAR_COLOR: Record<string, string> = {
  accent: 'bg-primary', ok: 'bg-success', warn: 'bg-warning', danger: 'bg-danger', muted: 'bg-muted-foreground/40',
}

/** 진입 확률 막대 + 숫자. null 이면 "측정 불가" */
export function ProbabilityBar({ percent, verdict, className }: { percent?: number | null; verdict?: string; className?: string }) {
  const tone = VERDICT_TONE[verdict || 'unknown'] || 'muted'
  if (percent == null) return <span className={cn('text-xs text-muted-foreground', className)}>측정 불가</span>
  const p = Math.max(0, Math.min(100, Math.round(percent)))
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full', BAR_COLOR[tone])} style={{ width: `${p}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-medium tabular-nums">{p}%</span>
    </div>
  )
}

/** VerdictSummary 하나를 알약으로 */
export function VerdictPill({ verdict, className }: { verdict?: string | null; className?: string }) {
  const k = verdict || 'unknown'
  return <Pill tone={VERDICT_TONE[k] || 'muted'} className={className}>{VERDICT_LABEL[k] || k}</Pill>
}

interface Props {
  items: VerdictRow[]
  selectable?: boolean
  selected?: string[]
  onSelectionChange?: (keywords: string[]) => void
  /** 표 아래 한 번만 보여줄 안내문. 없으면 detail.disclaimer 를 쓴다 */
  disclaimer?: string | null
  className?: string
}

export function VerdictTable({ items, selectable, selected = [], onSelectionChange, disclaimer, className }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const sel = new Set(selected)
  const allSelected = items.length > 0 && items.every((i) => sel.has(i.keyword))

  const toggle = (kw: string, on: boolean) => {
    if (!onSelectionChange) return
    const next = new Set(sel)
    if (on) next.add(kw); else next.delete(kw)
    onSelectionChange(items.filter((i) => next.has(i.keyword)).map((i) => i.keyword))
  }
  const toggleAll = (on: boolean) => onSelectionChange?.(on ? items.map((i) => i.keyword) : [])

  const note = disclaimer ?? items.find((i) => i.detail?.disclaimer)?.detail?.disclaimer ?? null

  if (items.length === 0) {
    return <div className={cn('rounded-xl border border-dashed px-6 py-8 text-center text-sm text-muted-foreground', className)}>판정 결과가 없습니다.</div>
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="overflow-x-auto">
        <Table className="min-w-[760px] text-sm [&_th]:whitespace-nowrap [&_td]:align-middle [&_th]:h-9 [&_th]:px-3 [&_th]:text-[12px] [&_th]:font-medium [&_th]:uppercase [&_th]:tracking-wide [&_th]:text-muted-foreground [&_td]:px-3 [&_td]:py-2.5 [&_tbody_tr:last-child]:border-0">
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-10">
                  <Checkbox checked={allSelected} onCheckedChange={(v) => toggleAll(v === true)} aria-label="전체 선택" />
                </TableHead>
              )}
              <TableHead>키워드</TableHead>
              <TableHead className="text-right">검색량</TableHead>
              <TableHead>판정</TableHead>
              <TableHead>진입 확률</TableHead>
              <TableHead className="text-right">내 점수 / 컷</TableHead>
              <TableHead>신뢰도</TableHead>
              <TableHead>근거</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((it) => {
              const open = expanded === it.keyword
              const reasons = it.reasons || []
              const comps = it.detail?.competitors || []
              const hasMore = reasons.length > 1 || comps.length > 0
              const cols = selectable ? 8 : 7
              return (
                <Fragment key={it.keyword}>
                  <TableRow className={cn(open && 'bg-muted/30', 'hover:bg-muted/40')}>
                    {selectable && (
                      <TableCell>
                        <Checkbox checked={sel.has(it.keyword)} onCheckedChange={(v) => toggle(it.keyword, v === true)} aria-label={`${it.keyword} 선택`} />
                      </TableCell>
                    )}
                    <TableCell className="whitespace-nowrap font-medium">
                      {it.keyword}
                      {it.my_rank != null && <span className="ml-1.5 text-[11px] font-normal tabular-nums text-muted-foreground">현재 {it.my_rank}위</span>}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-right tabular-nums">{num(it.volume)}</TableCell>
                    <TableCell><VerdictPill verdict={it.verdict} /></TableCell>
                    <TableCell><ProbabilityBar percent={it.percent} verdict={it.verdict} /></TableCell>
                    <TableCell className="whitespace-nowrap text-right tabular-nums">
                      {it.my_score == null && it.cut_line == null ? (
                        <span className="text-xs text-muted-foreground">측정 불가</span>
                      ) : (
                        <>
                          <span className="font-medium">{num(it.my_score, 1)}</span>
                          <span className="text-muted-foreground"> / 컷 {num(it.cut_line, 1)}</span>
                        </>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{it.confidence ? (CONF_LABEL[it.confidence] || it.confidence) : '-'}</TableCell>
                    <TableCell className="max-w-[22rem]">
                      <div className="flex items-start gap-1.5">
                        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={reasons[0] || undefined}>
                          {reasons[0] || (it.ok ? '-' : '판정하지 못했습니다')}
                        </span>
                        {hasMore && (
                          <button
                            type="button"
                            onClick={() => setExpanded(open ? null : it.keyword)}
                            className="inline-flex shrink-0 items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                            aria-expanded={open}
                          >
                            {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            {open ? '접기' : `더보기${reasons.length > 1 ? ` ${reasons.length}` : ''}`}
                          </button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                  {open && (
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableCell colSpan={cols} className="!py-3">
                        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
                          <div>
                            <div className="mb-1 text-[12px] font-medium text-muted-foreground">판정 근거</div>
                            <ul className="list-disc space-y-0.5 pl-4 text-xs">
                              {reasons.map((r, i) => <li key={i}>{r}</li>)}
                            </ul>
                            <div className="mt-2 text-[11px] tabular-nums text-muted-foreground">
                              중앙값 {num(it.median_score, 1)} · 채점된 경쟁자 {num(it.scored_competitors)} · 빈자리 {num(it.vacancy_count)}
                              {it.at && ` · ${it.at.slice(0, 16).replace('T', ' ')}`}
                            </div>
                          </div>
                          {comps.length > 0 && (
                            <div>
                              <div className="mb-1 text-[12px] font-medium text-muted-foreground">1페이지 경쟁 블로그</div>
                              <div className="overflow-x-auto rounded-lg border bg-card">
                                <table className="w-full text-xs">
                                  <thead>
                                    <tr className="border-b text-[11px] text-muted-foreground">
                                      <th className="px-2 py-1.5 text-left">순위</th>
                                      <th className="px-2 py-1.5 text-left">블로그</th>
                                      <th className="px-2 py-1.5 text-right">점수</th>
                                      <th className="px-2 py-1.5 text-left">등급</th>
                                      <th className="px-2 py-1.5 text-right">최근 글</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {comps.map((c) => (
                                      <tr key={`${c.rank}-${c.blog_id}`} className="border-b last:border-0">
                                        <td className="px-2 py-1.5 tabular-nums">{c.rank}</td>
                                        <td className="max-w-[14rem] truncate px-2 py-1.5" title={c.post_title || undefined}>
                                          {c.blog_name || c.blog_id}
                                          <span className="ml-1 font-mono text-[10px] text-muted-foreground">{c.blog_id}</span>
                                        </td>
                                        <td className="px-2 py-1.5 text-right tabular-nums">{c.measured === false ? <span className="text-muted-foreground">측정 불가</span> : num(c.score, 1)}</td>
                                        <td className="px-2 py-1.5">{c.grade || '-'}</td>
                                        <td className="px-2 py-1.5 text-right tabular-nums">{c.recent_activity_days == null ? '-' : `${num(c.recent_activity_days)}일 전`}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {note && <p className="text-xs leading-5 text-muted-foreground">{note}</p>}
    </div>
  )
}
