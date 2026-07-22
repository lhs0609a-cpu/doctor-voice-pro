'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  startGeneration,
  cancelGeneration,
  onGenResult,
  renderPrompt,
  loadTemplates,
  DEFAULT_GEN_OPTIONS,
  type GenStatus,
} from '@/lib/keyword-batch'
import type { WizardState } from './use-wizard-state'

interface Props {
  state: WizardState
  onBack: () => void
  onDone: (successCount: number) => void
}

interface Row {
  keyword: string
  status: GenStatus
  chars?: number
  error?: string
}

export function Step3Generate({ state, onBack, onDone }: Props) {
  const [rows, setRows] = useState<Row[]>(
    state.approved.map((k) => ({ keyword: k, status: 'pending' as GenStatus })),
  )
  const [running, setRunning] = useState(false)
  const [finished, setFinished] = useState(false)
  const successRef = useRef(0)

  // 확장이 보내는 건별 결과 구독 (저장은 전역 GenerationSaver가 담당 — 여기선 진행만 추적)
  useEffect(() => {
    const off = onGenResult((r) => {
      if (r.done) {
        setRunning(false)
        setFinished(true)
        return
      }
      if (r.fatal) {
        setRunning(false)
        toast.error(r.error || '생성이 중단되었습니다.')
        return
      }
      setRows((prev) =>
        prev.map((row) =>
          row.keyword === r.keyword
            ? {
                ...row,
                status: r.ok ? 'done' : 'failed',
                chars: r.chars,
                error: r.error,
              }
            : row,
        ),
      )
      if (r.ok) successRef.current += 1
    })
    return off
  }, [])

  const launch = async () => {
    successRef.current = 0
    setFinished(false)
    setRows(state.approved.map((k) => ({ keyword: k, status: 'pending' })))
    const tpl = loadTemplates()[0]
    const items = state.approved.map((keyword, i) => ({
      id: `ws-${Date.now()}-${i}`,
      keyword,
      prompt: renderPrompt(tpl.body, { 키워드: keyword, keyword }),
    }))
    try {
      setRunning(true)
      const res = await startGeneration(items, DEFAULT_GEN_OPTIONS)
      if (!res.success) {
        setRunning(false)
        toast.error(res.error || '생성 시작 실패')
      } else {
        setRows((prev) => prev.map((r) => ({ ...r, status: 'running' })))
        toast.success(`${res.accepted ?? items.length}건 생성을 시작했습니다.`)
      }
    } catch (e) {
      setRunning(false)
      toast.error(e instanceof Error ? e.message : '확장 프로그램 연결 실패')
    }
  }

  const doneCount = rows.filter((r) => r.status === 'done').length
  const failCount = rows.filter((r) => r.status === 'failed').length
  const total = rows.length
  const pct = total ? Math.round(((doneCount + failCount) / total) * 100) : 0

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>3단계 · 글 자동작성 (Gemini 로컬 에이전트)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            선택한 {total}개 키워드로 글을 자동 생성합니다. 브라우저의 Gemini 탭이 자동으로
            열리며, 완료된 글은 <b>저장된 글</b>에 자동 저장됩니다. (창을 닫지 마세요)
          </p>

          {(running || finished) && (
            <div className="space-y-2">
              <Progress value={pct} />
              <p className="text-sm">
                완료 {doneCount} / {total}
                {failCount > 0 && ` · 실패 ${failCount}`}
              </p>
            </div>
          )}

          <div className="grid gap-2 sm:grid-cols-2">
            {rows.map((r) => (
              <div
                key={r.keyword}
                className="flex items-center justify-between rounded border px-3 py-2 text-sm"
              >
                <span className="font-medium">{r.keyword}</span>
                <StatusBadge status={r.status} chars={r.chars} />
              </div>
            ))}
          </div>

          {!running && !finished && (
            <Button onClick={launch}>생성 시작</Button>
          )}
          {running && (
            <Button variant="outline" onClick={() => cancelGeneration()}>
              중단
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack} disabled={running}>
          ← 이전
        </Button>
        <Button
          onClick={() => onDone(successRef.current || doneCount)}
          disabled={running || (!finished && doneCount === 0)}
        >
          다음: 예약발행 →
        </Button>
      </div>
    </div>
  )
}

function StatusBadge({ status, chars }: { status: GenStatus; chars?: number }) {
  if (status === 'done')
    return (
      <Badge className="bg-green-100 text-green-700" variant="secondary">
        완료{chars ? ` · ${chars}자` : ''}
      </Badge>
    )
  if (status === 'failed')
    return (
      <Badge className="bg-red-100 text-red-700" variant="secondary">
        실패
      </Badge>
    )
  if (status === 'running')
    return (
      <Badge className="bg-blue-100 text-blue-700" variant="secondary">
        생성 중…
      </Badge>
    )
  return (
    <Badge variant="secondary" className="bg-muted text-muted-foreground">
      대기
    </Badge>
  )
}
