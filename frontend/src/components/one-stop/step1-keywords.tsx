'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { keywordBatchAPI, type KeywordVolumeDTO } from '@/lib/api'
import type { WizardState } from './use-wizard-state'

const COMP_LABEL: Record<string, { text: string; cls: string }> = {
  low: { text: '낮음', cls: 'bg-green-100 text-green-700' },
  mid: { text: '중간', cls: 'bg-yellow-100 text-yellow-700' },
  high: { text: '높음', cls: 'bg-red-100 text-red-700' },
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
      const rows = await keywordBatchAPI.getVolumes(keywords)
      // 검색량 내림차순
      rows.sort((a, b) => b.total_volume - a.total_volume)
      onCandidates(rows)
      // 검색량 있는 키워드를 기본 선택
      const pre: Record<string, boolean> = {}
      rows.forEach((r) => (pre[r.keyword] = r.total_volume > 0))
      setChecked(pre)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '검색량 조회 실패')
    } finally {
      setLoading(false)
    }
  }

  const candidates = state.candidates
  const selectedKeywords = candidates.filter((c) => checked[c.keyword]).map((c) => c.keyword)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>1단계 · 키워드 실검색량 분석</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {apiConfigured === false && (
            <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
              네이버 검색광고 API 자격증명이 설정되지 않아 검색량이 0으로 표시됩니다.
              서버 <code>.env</code>에 <code>NAVER_AD_CUSTOMER_ID / NAVER_AD_API_KEY / NAVER_AD_SECRET_KEY</code>를 설정하세요.
            </div>
          )}
          <Textarea
            placeholder={'키워드를 한 줄에 하나씩 입력하세요.\n예)\n임플란트\n강남 임플란트\n임플란트 가격'}
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={6}
          />
          <Button onClick={lookup} disabled={loading}>
            {loading ? '조회 중…' : '실검색량 조회'}
          </Button>
        </CardContent>
      </Card>

      {candidates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>검색량 결과 · 유망 키워드 선택 ({selectedKeywords.length}개)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="py-2 w-10"></th>
                    <th className="py-2">키워드</th>
                    <th className="py-2 text-right">월 검색량</th>
                    <th className="py-2 text-right">PC</th>
                    <th className="py-2 text-right">모바일</th>
                    <th className="py-2 text-center">경쟁도</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => {
                    const comp = COMP_LABEL[c.competition] ?? COMP_LABEL.mid
                    return (
                      <tr key={c.keyword} className="border-b last:border-0">
                        <td className="py-2">
                          <Checkbox
                            checked={!!checked[c.keyword]}
                            onCheckedChange={(v) =>
                              setChecked((prev) => ({ ...prev, [c.keyword]: !!v }))
                            }
                          />
                        </td>
                        <td className="py-2 font-medium">{c.keyword}</td>
                        <td className="py-2 text-right font-semibold">
                          {c.total_volume.toLocaleString()}
                        </td>
                        <td className="py-2 text-right text-muted-foreground">
                          {c.monthly_pc.toLocaleString()}
                        </td>
                        <td className="py-2 text-right text-muted-foreground">
                          {c.monthly_mobile.toLocaleString()}
                        </td>
                        <td className="py-2 text-center">
                          <Badge className={comp.cls} variant="secondary">
                            {comp.text}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex justify-end">
              <Button
                onClick={() => {
                  if (!selectedKeywords.length) {
                    toast.error('키워드를 하나 이상 선택하세요.')
                    return
                  }
                  onNext(selectedKeywords)
                }}
              >
                다음: 상위노출 가능성 분석 →
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
