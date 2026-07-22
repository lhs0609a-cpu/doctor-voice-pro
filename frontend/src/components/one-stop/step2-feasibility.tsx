'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { topPostsAPI, type FeasibilityDTO } from '@/lib/api'
import type { WizardState } from './use-wizard-state'

const VERDICT_STYLE: Record<string, string> = {
  유망: 'bg-green-100 text-green-700',
  보통: 'bg-yellow-100 text-yellow-700',
  레드오션: 'bg-red-100 text-red-700',
}

interface Props {
  state: WizardState
  onFeasibility: (f: FeasibilityDTO[]) => void
  onBack: () => void
  onNext: (approved: string[]) => void
}

export function Step2Feasibility({ state, onFeasibility, onBack, onNext }: Props) {
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState<Record<string, boolean>>({})

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

  const preselect = (list: FeasibilityDTO[]) => {
    const pre: Record<string, boolean> = {}
    // 레드오션이 아닌 것 기본 승인
    list.forEach((f) => (pre[f.keyword] = f.verdict !== '레드오션'))
    setChecked((prev) => ({ ...pre, ...prev }))
  }

  const items = state.selected
    .map((k) => state.feasibility[k])
    .filter(Boolean)
    .sort((a, b) => a.difficulty_score - b.difficulty_score)

  const approved = items.filter((f) => checked[f.keyword]).map((f) => f.keyword)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>2단계 · 상위노출 가능성 (실측 신호 기반)</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && (
            <p className="text-sm text-muted-foreground">
              상위 블로그 글을 실시간 분석 중입니다… (키워드당 수 초 소요)
            </p>
          )}
          {!loading && items.length === 0 && (
            <p className="text-sm text-muted-foreground">분석 결과가 없습니다.</p>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {items.map((f) => (
              <div
                key={f.keyword}
                className="rounded-lg border p-4 flex flex-col gap-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      checked={!!checked[f.keyword]}
                      onCheckedChange={(v) =>
                        setChecked((prev) => ({ ...prev, [f.keyword]: !!v }))
                      }
                    />
                    <span className="font-semibold">{f.keyword}</span>
                  </div>
                  <Badge className={VERDICT_STYLE[f.verdict] ?? ''} variant="secondary">
                    {f.verdict}
                  </Badge>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-muted-foreground">난이도</span>
                  <div className="flex-1 h-2 bg-muted rounded overflow-hidden">
                    <div
                      className={
                        f.difficulty_score < 40
                          ? 'h-full bg-green-500'
                          : f.difficulty_score < 70
                          ? 'h-full bg-yellow-500'
                          : 'h-full bg-red-500'
                      }
                      style={{ width: `${f.difficulty_score}%` }}
                    />
                  </div>
                  <span className="font-medium">{f.difficulty_score}</span>
                </div>
                <p className="text-xs text-muted-foreground">{f.reason}</p>
                <div className="text-xs text-muted-foreground border-t pt-2">
                  목표: 본문 {f.target.content_length.toLocaleString()}자 · 이미지{' '}
                  {f.target.image_count}장 · 소제목 {f.target.heading_count}개
                  {f.search_volume > 0 && ` · 월 검색량 ${f.search_volume.toLocaleString()}`}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          ← 이전
        </Button>
        <Button
          onClick={() => {
            if (!approved.length) {
              toast.error('작성할 키워드를 하나 이상 선택하세요.')
              return
            }
            onNext(approved)
          }}
          disabled={loading}
        >
          다음: 글 자동작성 ({approved.length}개) →
        </Button>
      </div>
    </div>
  )
}
