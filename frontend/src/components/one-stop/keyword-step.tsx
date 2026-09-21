'use client'

// 3단계 키워드 — 무엇을 쓸지 서버가 찾아 준다.
//
// 세 번 거른다. 사용자에게는 한 줄씩만 보여 준다.
//   ① 진료 항목에서 후보를 넓게 모은다(검색량 포함)
//   ② 통합검색에 병원 블로그가 들어갈 자리가 있는지 본다 → '자리 없음'은 버린다
//   ③ 남은 것만 우리 블로그 지수로 뚫리는지 판정한다 → 여기가 비싸서 개수를 제한한다
// 판정 결과는 서버의 키워드 행에 남으므로 창을 닫아도 이어진다.

import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Pill } from '@/components/app-shell/ui-kit'
import { campaignAPI, type Keyword, type Task } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'
import { cn } from '@/lib/utils'

const PRESETS = [100, 200, 300]

/** 내 블로그 판정 → 화면 라벨. 통검 판정(verdict)과 다른 값이므로 섞지 않는다. */
const MINE: Record<string, { label: string; tone: 'ok' | 'warn' | 'muted' | 'accent' }> = {
  likely: { label: '가능', tone: 'ok' },
  contested: { label: '해볼 만함', tone: 'warn' },
  already_ranked: { label: '이미 노출 중', tone: 'accent' },
  unlikely: { label: '어려움', tone: 'muted' },
  unknown: { label: '판정 불가', tone: 'muted' },
}

const SPOT: Record<string, string> = {
  possible: '자리 있음',
  contested: '경쟁 중',
  avoid: '자리 없음',
  unknown: '미확인',
}

function pct(p?: number | null) {
  return typeof p === 'number' ? `${Math.round(p * 100)}%` : '—'
}

export function KeywordStep({ campaignId, keywords, onChanged }: {
  campaignId: string
  keywords: Keyword[]
  onChanged: () => void
}) {
  const [target, setTarget] = useState(100)
  const [task, setTask] = useState<Task | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const running = task?.status === 'pending' || task?.status === 'running'
  const changed = useRef(onChanged)
  changed.current = onChanged

  // 새로고침해도 돌던 발굴을 다시 붙잡는다.
  useEffect(() => {
    let alive = true
    campaignAPI.listTasks({ campaign_id: campaignId, limit: 20 })
      .then(rows => { if (alive) { setTask(rows.find(t => t.type === 'keyword_hunt') || null); setLoaded(true) } })
      .catch(e => { if (alive) { setError(errMsg(e)); setLoaded(true) } })
    return () => { alive = false }
  }, [campaignId])

  // 도는 동안에는 작업과 키워드 표를 같이 갱신한다 — 판정이 끝난 줄부터 바로 채워진다.
  useEffect(() => {
    if (!task || !running) return
    let alive = true
    const timer = setInterval(async () => {
      try {
        const next = await campaignAPI.getTask(task.id)
        if (!alive) return
        setTask(next)
        changed.current()
      } catch (e) { if (alive) setError(errMsg(e)) }
    }, 4000)
    return () => { alive = false; clearInterval(timer) }
  }, [task?.id, running])

  const start = useCallback(async () => {
    if (busy || running) return
    setBusy(true); setError('')
    try { setTask(await campaignAPI.huntKeywords(campaignId, { target })) }
    catch (e) { setError(errMsg(e)) }
    finally { setBusy(false) }
  }, [busy, running, campaignId, target])

  const stop = async () => {
    if (!task) return
    setBusy(true)
    try { await campaignAPI.cancelTask(task.id); setTask({ ...task, status: 'cancelled' }) }
    catch (e) { setError(errMsg(e)) }
    finally { setBusy(false) }
  }

  const judged = keywords.filter(k => k.my_verdict)
  const picked = keywords.filter(k => k.selected)
  const spots = keywords.filter(k => k.verdict === 'possible' || k.verdict === 'contested')
  const top = [...picked].sort((a, b) => (b.my_probability || 0) - (a.my_probability || 0)).slice(0, 8)
  const percent = task?.total ? Math.min(100, Math.round((task.progress / task.total) * 100)) : 0

  return <div className="space-y-4">
    {running ? (
      <div className="space-y-3" role="status">
        <p className="font-medium">키워드를 찾고 판정하는 중입니다</p>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
        </div>
        <p className="text-sm">{task?.message || '진료 항목에서 후보를 모으고 있습니다.'}</p>
        <p className="text-xs text-muted-foreground">
          통합검색을 키워드마다 한 번씩 읽고, 살아남은 것만 우리 블로그로 뚫리는지 봅니다.
          300개 기준 30분~1시간이 걸립니다. 창을 닫아도 서버에서 계속합니다.
        </p>
        <Button variant="outline" disabled={busy} onClick={stop}>발굴 중단</Button>
      </div>
    ) : (
      <>
        <div>
          <Label htmlFor="hunt-target">몇 개나 찾을까요?</Label>
          <div className="my-2 flex flex-wrap gap-2">
            {PRESETS.map(n => (
              <Button key={n} variant={target === n ? 'default' : 'outline'} aria-pressed={target === n}
                disabled={busy} onClick={() => setTarget(n)}>{n}개</Button>
            ))}
          </div>
          <Input id="hunt-target" type="number" min={10} max={300} value={target} disabled={busy}
            onChange={e => setTarget(Number(e.target.value))} />
          <p className="mt-1 text-xs text-muted-foreground">
            찾은 키워드는 쌓입니다. 글은 여기서 쓰지 않고, 아래 단계에서 필요한 만큼 꺼내 씁니다.
          </p>
        </div>
        <Button className="h-12 w-full text-base"
          disabled={busy || !loaded || !Number.isInteger(target) || target < 10 || target > 300}
          onClick={start}>
          {busy ? '시작하는 중…' : picked.length ? `키워드 ${target}개 더 찾기` : `키워드 ${target}개 찾기`}
        </Button>
      </>
    )}

    {task && !running && task.status === 'failed' && (
      <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{task.error}</p>
    )}
    {task && !running && task.status === 'cancelled' && (
      <p role="status" className="rounded-lg bg-muted/50 p-3 text-sm">발굴을 중단했습니다. 지금까지 판정한 키워드는 그대로 남아 있습니다.</p>
    )}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

    {keywords.length > 0 && (
      <div className="space-y-3 rounded-xl border p-3">
        <div className="grid grid-cols-3 gap-2">
          {([['모은 후보', keywords.length, ''],
             ['통검 자리 있음', spots.length, ''],
             ['우리 블로그로 가능', picked.length, picked.length ? 'text-success' : '']] as const).map(([label, count, tone]) => (
            <div key={label} className="rounded-lg border p-2 text-center">
              <p className={cn('text-xl font-semibold tabular-nums', tone)}>{count}</p>
              <p className="text-[11px] text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
        {judged.length > 0 && top.length > 0 && (
          <details open>
            <summary className="cursor-pointer text-sm text-muted-foreground">
              쓸 키워드 {picked.length}개 중 위에서 {top.length}개 보기
            </summary>
            <ul className="mt-2 divide-y rounded-lg border">
              {top.map(k => {
                const mine = MINE[k.my_verdict || 'unknown'] || MINE.unknown
                return (
                  <li key={k.id} className="flex items-center gap-2 px-3 py-2">
                    <span className="min-w-0 flex-1 truncate text-sm">{k.keyword}</span>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      월 {(k.monthly_mobile || 0).toLocaleString()}
                    </span>
                    <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
                      {SPOT[k.verdict] || SPOT.unknown}
                    </span>
                    <Pill tone={mine.tone} className="shrink-0">{mine.label} {pct(k.my_probability)}</Pill>
                  </li>
                )
              })}
            </ul>
          </details>
        )}
        <p className="text-xs text-muted-foreground">
          &lsquo;가능&rsquo;은 우리 블로그 점수가 그 키워드 1페이지 컷라인을 넘는다는 추정입니다.
          실제 순위는 발행 뒤에 확인해야 합니다.
        </p>
      </div>
    )}
  </div>
}
