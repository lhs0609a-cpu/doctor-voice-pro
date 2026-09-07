'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Pill } from '@/components/app-shell/ui-kit'
import { keywordBatchAPI, type KeywordVolumeDTO } from '@/lib/api'
import type { WizardState } from './use-wizard-state'

const COMP_LABEL: Record<string, { text: string; tone: 'ok' | 'warn' | 'danger' }> = {
  low: { text: '낮음', tone: 'ok' },
  mid: { text: '중간', tone: 'warn' },
  high: { text: '높음', tone: 'danger' },
}

interface Props {
  state: WizardState
  onCandidates: (c: KeywordVolumeDTO[]) => void
  onNext: (selected: string[]) => void
}

export function Step1Keywords({ state, onCandidates, onNext }: Props) {
  const [raw, setRaw] = useState('')
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [apiConfigured, setApiConfigured] = useState<boolean | null>(null)
  const [includeRelated, setIncludeRelated] = useState(true)
  // 연관검색어 일괄 선택 기준(월 모바일 검색량). 마케팅팀 기준: 지역 20 / 전국 100, 인근 지역 탐색은 50.
  const [bulkMin, setBulkMin] = useState(50)
  const [relatedFilter, setRelatedFilter] = useState('')

  useEffect(() => {
    keywordBatchAPI
      .getVolumeStatus()
      .then((s) => setApiConfigured(s.configured))
      .catch(() => setApiConfigured(null))
  }, [])

  const lookup = async () => {
    const keywords = Array.from(
      new Set(
        raw
          .split(/[\n,]/)
          .map((k) => k.trim())
          .filter(Boolean),
      ),
    ).slice(0, 100)
    if (!keywords.length) {
      toast.error('키워드를 한 줄에 하나씩 입력하세요.')
      return
    }
    setLoading(true)
    try {
      const rows = await keywordBatchAPI.getVolumes(keywords, { includeRelated, relatedLimit: 100 })
      // 입력 키워드는 검색량 내림차순, 연관어는 서버가 모바일 검색량 순으로 준다
      const own = rows.filter((r) => !r.is_related).sort((a, b) => b.total_volume - a.total_volume)
      const rel = rows.filter((r) => r.is_related)
      onCandidates([...own, ...rel])
      // 입력 키워드 중 검색량 있는 것만 기본 선택. 연관어는 사용자가 고른다.
      const pre: Record<string, boolean> = {}
      own.forEach((r) => (pre[r.keyword] = r.total_volume > 0))
      setChecked(pre)
      if (includeRelated && rel.length === 0 && apiConfigured) {
        toast.message('연관검색어가 없습니다.', { description: '검색광고 API 가 이 키워드의 연관어를 주지 않았습니다.' })
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '검색량 조회 실패')
    } finally {
      setLoading(false)
    }
  }

  const candidates = state.candidates
  const own = useMemo(() => candidates.filter((c) => !c.is_related), [candidates])
  const related = useMemo(() => candidates.filter((c) => c.is_related), [candidates])
  const relatedShown = useMemo(() => {
    const q = relatedFilter.replace(/\s/g, '')
    return q ? related.filter((r) => r.keyword.replace(/\s/g, '').includes(q)) : related
  }, [related, relatedFilter])
  const selectedKeywords = candidates.filter((c) => checked[c.keyword]).map((c) => c.keyword)
  const selectedRelated = related.filter((c) => checked[c.keyword]).length

  const toggle = (kw: string, v: boolean) => setChecked((prev) => ({ ...prev, [kw]: v }))
  const bulkSelectRelated = (on: boolean) => {
    setChecked((prev) => {
      const next = { ...prev }
      relatedShown.forEach((r) => {
        if (r.monthly_mobile >= bulkMin) next[r.keyword] = on
      })
      return next
    })
  }

  const renderRow = (c: KeywordVolumeDTO) => {
    const comp = COMP_LABEL[c.competition] ?? COMP_LABEL.mid
    return (
      <tr key={c.keyword} className="border-b last:border-0 hover:bg-muted/40">
        <td className="py-2.5 pl-1">
          <Checkbox checked={!!checked[c.keyword]} onCheckedChange={(v) => toggle(c.keyword, !!v)} />
        </td>
        <td className="py-2.5 font-medium">
          {c.keyword}
          {c.is_related && c.related_of && (
            <span className="ml-2 text-xs text-muted-foreground">← {c.related_of}</span>
          )}
        </td>
        <td className="py-2.5 text-right font-semibold tabular-nums">{c.total_volume.toLocaleString()}</td>
        <td className="py-2.5 text-right text-muted-foreground tabular-nums">{c.monthly_pc.toLocaleString()}</td>
        <td className="py-2.5 text-right text-muted-foreground tabular-nums">{c.monthly_mobile.toLocaleString()}</td>
        <td className="py-2.5 text-center">
          <Pill tone={comp.tone}>{comp.text}</Pill>
        </td>
      </tr>
    )
  }

  const tableHead = (
    <thead>
      <tr className="border-b text-left text-[12px] font-medium uppercase tracking-wide text-muted-foreground">
        <th className="w-10 py-2.5 pl-1 font-medium"></th>
        <th className="py-2.5 font-medium">키워드</th>
        <th className="py-2.5 text-right font-medium">월 검색량</th>
        <th className="py-2.5 text-right font-medium">PC</th>
        <th className="py-2.5 text-right font-medium">모바일</th>
        <th className="py-2.5 text-center font-medium">경쟁도</th>
      </tr>
    </thead>
  )

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>1단계 · 키워드 검색량 확인</CardTitle>
          <CardDescription>키워드를 한 줄에 하나씩 넣고 실제 월 검색량을 조회합니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {apiConfigured === false && (
            <div className="rounded-lg border bg-warning-soft p-3 text-sm text-warning">
              네이버 검색광고 API 자격증명이 설정되지 않아 검색량이 0으로 표시되고 연관검색어도 나오지 않습니다.
              서버 <code>.env</code>에 <code>NAVER_AD_CUSTOMER_ID / NAVER_AD_API_KEY / NAVER_AD_SECRET_KEY</code>를 설정하세요.
            </div>
          )}
          <Textarea
            placeholder={'키워드를 한 줄에 하나씩 입력하세요.\n예)\n임플란트\n강남 임플란트\n임플란트 가격'}
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={6}
          />
          <div className="flex flex-wrap items-center justify-between gap-4">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={includeRelated} onCheckedChange={(v) => setIncludeRelated(!!v)} />
              연관검색어도 함께 조회 (예: 임플란트 → 임플란트가격, 강남임플란트 …)
            </label>
            <Button onClick={lookup} disabled={loading} variant={candidates.length > 0 ? 'outline' : 'default'}>
              {loading ? '조회 중…' : '검색량 조회'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {candidates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>유망 키워드 선택</CardTitle>
            <CardDescription>
              글을 쓸 키워드를 고르세요. 현재 <span className="font-medium tabular-nums text-foreground">{selectedKeywords.length}개</span> 선택
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                {tableHead}
                <tbody>{own.map(renderRow)}</tbody>
              </table>
            </div>

            {related.length > 0 && (
              <div className="space-y-3 border-t pt-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="section-title">
                      연관검색어 <span className="tabular-nums">{related.length}</span>개
                      {selectedRelated > 0 && (
                        <span className="ml-2 text-[13px] font-normal text-muted-foreground tabular-nums">{selectedRelated}개 선택</span>
                      )}
                    </div>
                    <div className="text-[13px] text-muted-foreground">
                      네이버 검색광고가 함께 알려준 키워드입니다. 모바일 검색량 순입니다.
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Input
                      className="h-8 w-40"
                      placeholder="키워드 검색(예: 강남)"
                      value={relatedFilter}
                      onChange={(e) => setRelatedFilter(e.target.value)}
                    />
                    <span className="text-[13px] text-muted-foreground">모바일</span>
                    <Input
                      type="number"
                      className="h-8 w-20 tabular-nums"
                      value={bulkMin}
                      min={0}
                      onChange={(e) => setBulkMin(Math.max(0, Number(e.target.value) || 0))}
                    />
                    <span className="text-[13px] text-muted-foreground">이상</span>
                    <Button size="sm" variant="outline" onClick={() => bulkSelectRelated(true)}>
                      전부 선택
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => bulkSelectRelated(false)}>
                      선택 해제
                    </Button>
                  </div>
                </div>
                <div className="max-h-[480px] overflow-x-auto overflow-y-auto">
                  <table className="w-full text-sm">
                    {tableHead}
                    <tbody>{relatedShown.map(renderRow)}</tbody>
                  </table>
                  {relatedShown.length === 0 && (
                    <div className="py-6 text-center text-sm text-muted-foreground">검색 조건에 맞는 연관검색어가 없습니다.</div>
                  )}
                </div>
              </div>
            )}

            <div className="flex justify-end border-t pt-4">
              <Button
                onClick={() => {
                  if (!selectedKeywords.length) {
                    toast.error('키워드를 하나 이상 선택하세요.')
                    return
                  }
                  onNext(selectedKeywords)
                }}
              >
                다음: 상위노출 가능성 분석 (<span className="tabular-nums">{selectedKeywords.length}</span>개)
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
