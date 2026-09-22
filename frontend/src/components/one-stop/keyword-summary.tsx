'use client'

// 찾은 키워드 — 준비를 접어 둔 뒤에도 '무엇을 쓸지'는 늘 보여야 한다.
//
// 3번 칸(키워드 찾기)은 준비가 끝나면 한 줄로 접히는데, 그러면 어렵게 찾은 키워드가
// 화면에서 통째로 사라진다. 원고는 이 키워드로 쓰는 것이므로 목록은 항상 남겨 둔다.

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Check, Copy, FileSpreadsheet, FileText, Loader2, Search, Sparkles, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pill } from '@/components/app-shell/ui-kit'
import { campaignAPI, type Keyword } from '@/lib/campaign-api'
import { cn } from '@/lib/utils'

const MINE: Record<string, { label: string; tone: 'ok' | 'warn' | 'muted' | 'accent' }> = {
  likely: { label: '가능', tone: 'ok' },
  contested: { label: '해볼 만함', tone: 'warn' },
  already_ranked: { label: '이미 노출 중', tone: 'accent' },
  unlikely: { label: '어려움', tone: 'muted' },
  unknown: { label: '판정 불가', tone: 'muted' },
}

/** 간절함 점수 → 사람 말. 숫자보다 이 말이 먼저 읽힌다. */
function urgency(score?: number): { label: string; tone: 'ok' | 'warn' | 'muted' } {
  const value = score || 0
  if (value >= 75) return { label: '지금 찾는 중', tone: 'ok' }
  if (value >= 50) return { label: '알아보는 중', tone: 'warn' }
  return { label: '정보만 보는 중', tone: 'muted' }
}

const SPOT: Record<string, string> = {
  possible: '자리 있음',
  contested: '경쟁 중',
  avoid: '자리 없음',
  unknown: '미확인',
}

const PAGE = 20

/** 엑셀이 한글을 깨뜨리지 않도록 BOM 을 붙이고, 쉼표·따옴표·줄바꿈이 든 칸은 감싼다. */
function csv(rows: (string | number)[][]) {
  const cell = (value: string | number) => {
    const text = String(value ?? '')
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  return '﻿' + rows.map(row => row.map(cell).join(',')).join('\r\n')
}

function save(name: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function today() {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
}

export function KeywordSummary({ keywords, campaignId, onChanged, huntHref }: {
  keywords: Keyword[]
  /** 주면 키워드를 지울 수 있다(쓸모없는 후보를 걸러 내는 일이 목록의 절반이다). */
  campaignId?: string
  /** 지운 뒤 목록을 다시 읽게 한다. */
  onChanged?: () => void
  /** 주면 '더 찾기' 단추가 붙는다(키워드 찾기 탭으로 보낸다). 찾기 화면 자신에서는 주지 않는다. */
  huntHref?: string
}) {
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [copied, setCopied] = useState(false)
  const [gone, setGone] = useState<string[]>([])      // 지운 직후 화면에서 바로 뺀다(다시 읽기 전까지)
  const [busy, setBusy] = useState('')
  const [askBulk, setAskBulk] = useState(false)
  const [askAll, setAskAll] = useState(false)
  const [error, setError] = useState('')

  // 쓸 키워드(판정 통과)를 먼저, 그 다음 나머지 후보.
  // 각각 **간절한 순** — 검색량이 큰 글이 아니라 환자가 될 사람이 보는 글부터 쓴다.
  const rows = useMemo(() => {
    const by = (a: Keyword, b: Keyword) =>
      (b.intent_score || 0) - (a.intent_score || 0) ||
      (b.my_probability || 0) - (a.my_probability || 0) || (b.monthly_mobile || 0) - (a.monthly_mobile || 0)
    const live = keywords.filter(k => !gone.includes(k.id))
    const picked = live.filter(k => k.selected).sort(by)
    const rest = live.filter(k => !k.selected).sort(by)
    return { picked, rest, all: [...picked, ...rest] }
  }, [keywords, gone])

  const found = query.trim()
    ? rows.all.filter(k => k.keyword.replace(/\s/g, '').includes(query.trim().replace(/\s/g, '')))
    : rows.all
  const list = found.slice(0, shown)

  // 내려받기는 화면에 보이는 것과 같은 순서로(쓸 키워드 먼저). 검색 중이면 걸러진 것만.
  const downloadExcel = () => {
    const head = ['키워드', '글 성격', '간절함(100점)', '왜 간절한가', '월 검색량(모바일)', '월 검색량(PC)',
                  '통합검색 자리', '우리 블로그 판정', '가능성(%)', '쓸 키워드']
    const body = found.map(k => [
      k.keyword,
      k.category || '',
      k.intent_score || 0,
      k.intent_reason || '',
      k.monthly_mobile || 0,
      k.monthly_pc || 0,
      SPOT[k.verdict] || SPOT.unknown,
      (MINE[k.my_verdict || 'unknown'] || MINE.unknown).label,
      typeof k.my_probability === 'number' ? Math.round(k.my_probability * 100) : '',
      k.selected ? 'O' : '',
    ])
    save(`키워드_${today()}.csv`, csv([head, ...body]), 'text/csv')
  }

  const downloadText = () => {
    save(`키워드_${today()}.txt`, found.map(k => k.keyword).join('\r\n'), 'text/plain')
  }

  const copyAll = async () => {
    const text = (rows.picked.length ? rows.picked : rows.all).map(k => k.keyword).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* 클립보드를 막아 둔 브라우저 — 목록은 화면에 그대로 있다 */ }
  }

  // 지우기 — 목록에서 바로 빼고, 서버가 실패하면 되돌린다.
  const remove = async (ids: string[]) => {
    if (!campaignId || !ids.length) return
    setBusy(ids.length === 1 ? ids[0] : 'bulk'); setError(''); setAskBulk(false)
    setGone(previous => [...previous, ...ids])
    const failed: string[] = []
    for (const id of ids) {
      try { await campaignAPI.deleteKeyword(campaignId, id) } catch { failed.push(id) }
    }
    if (failed.length) {
      setGone(previous => previous.filter(id => !failed.includes(id)))
      setError(`${failed.length}개를 지우지 못했습니다. 잠시 뒤 다시 해 보세요.`)
    }
    setBusy('')
    onChanged?.()
  }

  // 전부 지우기 — 새로 찾기 전에 판을 비운다. 지난 판정은 블로그 지수·경쟁이 바뀌면 맞지 않는다.
  const removeAll = async () => {
    if (!campaignId) return
    setBusy('all'); setError(''); setAskAll(false)
    try {
      await campaignAPI.clearKeywords(campaignId)
      setGone(keywords.map(k => k.id))
      onChanged?.()
    } catch {
      setError('키워드를 비우지 못했습니다. 잠시 뒤 다시 해 보세요.')
    } finally { setBusy('') }
  }

  if (!keywords.length) return null

  return (
    <section aria-label="찾은 키워드" className="space-y-3 rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">
            쓸 키워드 <span className="tabular-nums text-success">{rows.picked.length}</span>개
            <span className="ml-2 text-xs font-normal text-muted-foreground">후보 {keywords.length}개</span>
          </h2>
          <p className="text-xs text-muted-foreground">
            위에서부터 쓰세요 — 검색량이 아니라 <b>얼마나 간절한 검색인지</b> 순서입니다.
            {query.trim() && <> · 내려받기는 지금 검색된 {found.length}개만 담깁니다.</>}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1">
          <Button variant="outline" size="sm" onClick={downloadExcel}>
            <FileSpreadsheet className="mr-1 h-4 w-4" />엑셀
          </Button>
          <Button variant="outline" size="sm" onClick={downloadText}>
            <FileText className="mr-1 h-4 w-4" />텍스트
          </Button>
          <Button variant="outline" size="sm" onClick={copyAll}>
            {copied ? <Check className="mr-1 h-4 w-4 text-success" /> : <Copy className="mr-1 h-4 w-4" />}
            {copied ? '복사됨' : '전체 복사'}
          </Button>
          {campaignId && !query.trim() && rows.all.length > 0 && (
            askAll ? (
              <>
                <Button variant="destructive" size="sm" disabled={busy === 'all'} onClick={() => void removeAll()}>
                  {busy === 'all' ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1 h-4 w-4" />}
                  정말 {rows.all.length}개 전부 지우기
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setAskAll(false)}>취소</Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setAskAll(true)}>
                <Trash2 className="mr-1 h-4 w-4" />전부 지우기
              </Button>
            )
          )}
          {campaignId && query.trim() && found.length > 0 && (
            askBulk ? (
              <>
                <Button variant="destructive" size="sm" disabled={busy === 'bulk'} onClick={() => void remove(found.map(k => k.id))}>
                  {busy === 'bulk' ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1 h-4 w-4" />}
                  정말 {found.length}개 지우기
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setAskBulk(false)}>취소</Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setAskBulk(true)}>
                <Trash2 className="mr-1 h-4 w-4" />검색된 {found.length}개 지우기
              </Button>
            )
          )}
          {huntHref && (
            <Button asChild variant="ghost" size="sm">
              <Link href={huntHref}><Sparkles className="mr-1 h-4 w-4" />더 찾기</Link>
            </Button>
          )}
        </div>
      </div>

      {keywords.length > PAGE && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input aria-label="키워드 검색" className="pl-9" placeholder="키워드 검색"
            value={query} onChange={e => { setQuery(e.target.value); setShown(PAGE) }} />
        </div>
      )}

      {list.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">찾는 키워드가 없습니다.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {list.map(k => {
            const mine = MINE[k.my_verdict || 'unknown'] || MINE.unknown
            return (
              <li key={k.id} className={cn('flex items-center gap-2 px-3 py-2', !k.selected && 'opacity-60')}>
                <span className="min-w-0 flex-1 truncate text-sm">{k.keyword}</span>
                {k.category && (
                  <span className="hidden shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground sm:inline">
                    {k.category}
                  </span>
                )}
                <span className="hidden shrink-0 text-xs text-muted-foreground md:inline">
                  {k.intent_reason || ''}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  월 {(k.monthly_mobile || 0).toLocaleString()}
                </span>
                <Pill tone={urgency(k.intent_score).tone} className="shrink-0">
                  {urgency(k.intent_score).label}
                </Pill>
                <Pill tone={mine.tone} className="shrink-0">{mine.label}</Pill>
                {campaignId && (
                  <button type="button" aria-label={`${k.keyword} 지우기`} title="이 키워드 지우기"
                    disabled={!!busy} onClick={() => void remove([k.id])}
                    className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40">
                    {busy === k.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {found.length > list.length && (
        <Button variant="outline" size="sm" className="w-full" onClick={() => setShown(n => n + PAGE * 2)}>
          {found.length - list.length}개 더 보기
        </Button>
      )}
    </section>
  )
}
