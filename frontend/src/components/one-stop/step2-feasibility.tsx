'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2, Target } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Pill } from '@/components/app-shell/ui-kit'
import { TaskProgress } from '@/components/campaign/common'
import { BlogPicker, readRememberedBlogId } from '@/components/blog-index/blog-picker'
import { BlogIndexPanel, type IndexSeed } from '@/components/blog-index/blog-index-card'
import { VerdictTable, type VerdictRow } from '@/components/blog-index/verdict-table'
import { cn } from '@/lib/utils'
import { topPostsAPI, type FeasibilityDTO } from '@/lib/api'
import { blogIndexAPI, type VerdictBatchResult } from '@/lib/blog-index-api'
import type { Task } from '@/lib/campaign-api'
import type { WizardState } from './use-wizard-state'

const VERDICT_TONE: Record<string, 'ok' | 'warn' | 'danger'> = {
  유망: 'ok',
  보통: 'warn',
  레드오션: 'danger',
}

/** 판정 표에서 기본으로 체크해 둘 종류 */
const PRESELECT = new Set(['already_ranked', 'likely', 'contested'])

interface Props {
  state: WizardState
  onFeasibility: (f: FeasibilityDTO[]) => void
  onBack: () => void
  onNext: (approved: string[]) => void
}

export function Step2Feasibility({ state, onFeasibility, onBack, onNext }: Props) {
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  // 내 블로그 기준 판정
  const [blogId, setBlogId] = useState('')
  const [verdictTaskId, setVerdictTaskId] = useState<string | null>(null)
  const [verdictStarting, setVerdictStarting] = useState(false)
  const [verdict, setVerdict] = useState<{ blogId: string; items: VerdictRow[]; my?: IndexSeed | null; disclaimer?: string | null } | null>(null)
  const [verdictSelected, setVerdictSelected] = useState<string[]>([])
  const [restoring, setRestoring] = useState(false)

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      // 이미 판정된 게 있으면 재요청하지 않음
      const need = state.selected.filter((k) => !state.feasibility[k])
      if (!need.length) {
        preselect(Object.values(state.feasibility))
        return
      }
      setLoading(true)
      try {
        const { results } = await topPostsAPI.getFeasibility(state.selected)
        if (cancelled) return
        onFeasibility(results)
        preselect(results)
      } catch (e) {
        if (!cancelled) toast.error(e instanceof Error ? e.message : '가능성 분석 실패')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 기억해 둔 블로그가 있으면 최근 판정 결과를 되살린다
  useEffect(() => {
    const remembered = readRememberedBlogId()
    if (!remembered || !state.selected.length) return
    setBlogId(remembered)
    let cancelled = false
    setRestoring(true)
    blogIndexAPI.verdictLatest(remembered, state.selected)
      .then((r) => {
        if (cancelled || !r.items?.length) return
        applyVerdict(remembered, r.items, null, null)
      })
      .catch(() => { /* 최근 결과가 없으면 조용히 넘어간다 */ })
      .finally(() => { if (!cancelled) setRestoring(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const preselect = (list: FeasibilityDTO[]) => {
    const pre: Record<string, boolean> = {}
    // 레드오션이 아닌 것 기본 승인
    list.forEach((f) => (pre[f.keyword] = f.verdict !== '레드오션'))
    setChecked((prev) => ({ ...pre, ...prev }))
  }

  const applyVerdict = (id: string, items: VerdictRow[], my: IndexSeed | null | undefined, disclaimer: string | null | undefined) => {
    // 서버는 요청한 키워드만 돌려준다. 공백·대소문자 차이로 빠지지 않게 정규화해 대조하고,
    // 대조가 실패하면 결과를 버리지 말고 전부 보여준다(결과가 사라지는 것이 더 나쁘다).
    const norm = (k: string) => (k || '').replace(/\s+/g, '').toLowerCase()
    const inScope = new Set(state.selected.map(norm))
    const filtered = items.filter((i) => inScope.has(norm(i.keyword)))
    const rows = filtered.length ? filtered : items
    setVerdict({ blogId: id, items: rows, my, disclaimer })
    setVerdictSelected(rows.filter((i) => PRESELECT.has(i.verdict)).map((i) => i.keyword))
  }

  const runVerdict = async () => {
    if (!blogId) { toast.error('먼저 내 블로그 ID 를 넣어 주세요.'); return }
    if (!state.selected.length) { toast.error('판정할 키워드가 없습니다.'); return }
    setVerdictStarting(true)
    try {
      const t = await blogIndexAPI.verdictBatch(blogId, state.selected)
      setVerdictTaskId(t.id)
    } catch (e) {
      toast.error('판정 시작 실패', { description: e instanceof Error ? e.message : undefined })
    } finally {
      setVerdictStarting(false)
    }
  }

  const onVerdictDone = (t: Task) => {
    setVerdictTaskId(null)
    if (t.status !== 'done') {
      toast.error(t.status === 'cancelled' ? '판정을 취소했습니다' : `판정 실패: ${t.error || '알 수 없는 오류'}`)
      return
    }
    const r = t.result as unknown as VerdictBatchResult | null
    if (!r?.items) { toast.error('판정 결과가 비어 있습니다'); return }
    // 입력값(로그인 ID 등)과 서버가 교정한 실제 블로그 주소가 달라도 결과가 사라지지 않게 입력값 기준으로 묶는다
    applyVerdict(blogId, r.items, r.my, r.disclaimer)
    toast.success(`${r.items.length}개 키워드를 내 블로그 기준으로 판정했습니다`)
  }

  const items = state.selected
    .map((k) => state.feasibility[k])
    .filter(Boolean)
    .sort((a, b) => a.difficulty_score - b.difficulty_score)

  const checkedKeywords = items.filter((f) => checked[f.keyword]).map((f) => f.keyword)
  // 판정을 돌렸으면 판정 표에서 체크한 키워드, 아니면 기존 난이도 카드 선택
  const useVerdictSelection = !!verdict && verdict.blogId === blogId && verdict.items.length > 0
  const approved = useVerdictSelection ? verdictSelected : checkedKeywords

  const verdictCounts = useMemo(() => {
    const c: Record<string, number> = {}
    verdict?.items.forEach((i) => { c[i.verdict] = (c[i.verdict] || 0) + 1 })
    return c
  }, [verdict])

  const verdictBusy = !!verdictTaskId || verdictStarting

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>2단계 · 상위노출 가능성</CardTitle>
          <CardDescription>내 블로그 지수와 1페이지 경쟁 블로그를 비교해 키워드별 진입 확률을 매깁니다. 글을 쓸 키워드만 체크하세요.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 내 블로그로 판정 */}
          <section className="space-y-3 rounded-xl border bg-muted/20 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="section-title">내 블로그로 판정</h3>
                <p className="mt-0.5 text-[13px] text-muted-foreground">내 블로그 ID 를 넣고 판정을 누르면, 선택한 {state.selected.length.toLocaleString('ko-KR')}개 키워드마다 진입 확률이 나옵니다.</p>
              </div>
              {restoring && <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" /> 최근 결과 확인 중</span>}
            </div>
            <BlogPicker value={blogId} onChange={setBlogId} disabled={verdictBusy} />
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={runVerdict} disabled={verdictBusy || !blogId || !state.selected.length}>
                {verdictStarting ? <Loader2 className="animate-spin" /> : <Target />}
                내 블로그 기준으로 판정
              </Button>
              {useVerdictSelection && (
                <span className="text-xs tabular-nums text-muted-foreground">
                  이미 노출 {(verdictCounts.already_ranked || 0).toLocaleString('ko-KR')} · 가능성 높음 {(verdictCounts.likely || 0).toLocaleString('ko-KR')} · 경합 {(verdictCounts.contested || 0).toLocaleString('ko-KR')} · 낮음 {(verdictCounts.unlikely || 0).toLocaleString('ko-KR')}
                </span>
              )}
            </div>
            <TaskProgress
              taskId={verdictTaskId}
              onDone={onVerdictDone}
              onTick={(t) => {
                // 키워드 하나가 끝날 때마다 서버가 부분 결과를 흘려준다 → 완료를 기다리지 않고 바로 그린다
                const r = t.result as unknown as VerdictBatchResult | null
                if (t.status === 'running' && r?.partial && r.items?.length) applyVerdict(blogId, r.items, r.my, r.disclaimer)
              }}
            />

            {useVerdictSelection && (
              <div className="grid gap-4 2xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
                <BlogIndexPanel blogId={verdict!.blogId} seed={verdict!.my} />
                <div className="min-w-0 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[13px] font-medium text-muted-foreground">키워드별 판정 · 글을 쓸 키워드를 체크하세요</div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setVerdictSelected(verdict!.items.filter((i) => PRESELECT.has(i.verdict)).map((i) => i.keyword))}>가능성 높음·경합만</Button>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setVerdictSelected(verdict!.items.map((i) => i.keyword))}>전체</Button>
                    </div>
                  </div>
                  <VerdictTable items={verdict!.items} selectable selected={verdictSelected} onSelectionChange={setVerdictSelected} disclaimer={verdict!.disclaimer} />
                </div>
              </div>
            )}
          </section>

          {/* 키워드 난이도(블로그 무관) */}
          <section className="space-y-3">
            <div>
              <h3 className="section-title">키워드 난이도(블로그 무관)</h3>
              <p className="mt-0.5 text-[13px] text-muted-foreground">상위 블로그 글만 보고 매긴 난이도입니다. 어떤 블로그로 써도 같은 값입니다.</p>
            </div>
            {loading && (
              <p className="text-sm text-muted-foreground">
                상위 블로그 글을 실시간 분석 중입니다… (키워드당 수 초 소요)
              </p>
            )}
            {!loading && items.length === 0 && (
              <p className="text-sm text-muted-foreground">분석 결과가 없습니다.</p>
            )}
            {items.length > 0 && (
              <div className={cn('grid gap-4 md:grid-cols-2', useVerdictSelection && 'opacity-80')}>
                {items.map((f) => (
                  <div key={f.keyword} className="flex flex-col gap-2 rounded-lg border p-4">
                    <div className="flex items-center justify-between gap-2">
                      <label className="flex min-w-0 cursor-pointer items-center gap-2">
                        <Checkbox
                          checked={!!checked[f.keyword]}
                          disabled={useVerdictSelection}
                          onCheckedChange={(v) =>
                            setChecked((prev) => ({ ...prev, [f.keyword]: !!v }))
                          }
                        />
                        <span className="truncate font-semibold">{f.keyword}</span>
                      </label>
                      <Pill tone={VERDICT_TONE[f.verdict] ?? 'muted'}>{f.verdict}</Pill>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-[13px] text-muted-foreground">난이도</span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            f.difficulty_score < 40 ? 'bg-success' : f.difficulty_score < 70 ? 'bg-warning' : 'bg-danger',
                          )}
                          style={{ width: `${f.difficulty_score}%` }}
                        />
                      </div>
                      <span className="w-6 text-right font-medium tabular-nums">{f.difficulty_score}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{f.reason}</p>
                    <div className="border-t pt-2 text-xs text-muted-foreground tabular-nums">
                      목표: 본문 {f.target.content_length.toLocaleString('ko-KR')}자 · 이미지{' '}
                      {f.target.image_count}장 · 소제목 {f.target.heading_count}개
                      {f.search_volume > 0 && ` · 월 검색량 ${f.search_volume.toLocaleString('ko-KR')}`}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {useVerdictSelection && (
              <p className="text-xs text-muted-foreground">내 블로그 판정을 돌렸으므로 위 판정 표에서 체크한 키워드로 넘어갑니다.</p>
            )}
          </section>

          <div className="flex justify-between border-t pt-4">
            <Button variant="outline" onClick={onBack}>
              이전
            </Button>
            <Button
              onClick={() => {
                if (!approved.length) {
                  toast.error('작성할 키워드를 하나 이상 선택하세요.')
                  return
                }
                onNext(approved)
              }}
              disabled={loading || verdictBusy}
            >
              다음: 글 자동작성 (<span className="tabular-nums">{approved.length}</span>개)
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
