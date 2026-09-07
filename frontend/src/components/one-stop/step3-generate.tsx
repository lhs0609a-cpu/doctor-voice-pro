'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { toastExtensionMissing } from '@/lib/extension-toast'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { Download, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Pill } from '@/components/app-shell/ui-kit'
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
  const ext = useExtensionStatus()
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
    if (!ext.connected) {
      toastExtensionMissing()
      return
    }
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
      const msg = e instanceof Error ? e.message : '확장 프로그램 연결 실패'
      if (msg.includes('확장')) toastExtensionMissing(msg)
      else toast.error(msg)
    }
  }

  const doneCount = rows.filter((r) => r.status === 'done').length
  const failCount = rows.filter((r) => r.status === 'failed').length
  const total = rows.length
  const pct = total ? Math.round(((doneCount + failCount) / total) * 100) : 0

  return (
    <div className="space-y-6">
      {!ext.connected && ext.light !== 'checking' && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">확장 프로그램이 연결되지 않았습니다</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              글 자동작성은 크롬 확장 프로그램이 Gemini 탭을 열어 진행합니다. 먼저 설치해주세요.
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={ext.refresh}>
            <RefreshCw />
            다시 확인
          </Button>
          <Link href="/dashboard/extension">
            <Button size="sm">
              <Download />
              설치하기
            </Button>
          </Link>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>3단계 · 글 자동작성</CardTitle>
          <CardDescription>
            선택한 <span className="tabular-nums">{total}</span>개 키워드로 글을 자동 생성합니다. 브라우저의 Gemini 탭이
            자동으로 열리며, 완료된 글은 <b className="font-medium text-foreground">저장된 글</b>에 자동 저장됩니다. 창을 닫지 마세요.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(running || finished) && (
            <div className="space-y-2">
              <Progress value={pct} />
              <p className="text-[13px] text-muted-foreground tabular-nums">
                완료 {doneCount} / {total}
                {failCount > 0 && ` · 실패 ${failCount}`}
              </p>
            </div>
          )}

          <div className="rounded-lg border">
            {rows.map((r) => (
              <div
                key={r.keyword}
                className="flex items-center justify-between gap-3 border-b px-4 py-2.5 text-sm last:border-b-0"
              >
                <span className="truncate font-medium">{r.keyword}</span>
                <StatusBadge status={r.status} chars={r.chars} />
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between border-t pt-4">
            <Button variant="outline" onClick={onBack} disabled={running}>
              이전
            </Button>
            <div className="flex items-center gap-2">
              {!running && !finished && (
                <Button onClick={launch} disabled={!ext.connected} title={!ext.connected ? '확장 프로그램을 먼저 설치하세요' : undefined}>
                  생성 시작
                </Button>
              )}
              {running && (
                <Button variant="outline" onClick={() => cancelGeneration()}>
                  중단
                </Button>
              )}
              <Button
                variant={finished ? 'default' : 'outline'}
                onClick={() => onDone(successRef.current || doneCount)}
                disabled={running || (!finished && doneCount === 0)}
              >
                다음: 예약발행
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatusBadge({ status, chars }: { status: GenStatus; chars?: number }) {
  if (status === 'done')
    return (
      <Pill tone="ok" className="tabular-nums">
        완료{chars ? ` · ${chars.toLocaleString()}자` : ''}
      </Pill>
    )
  if (status === 'failed') return <Pill tone="danger">실패</Pill>
  if (status === 'running') return <Pill tone="accent">생성 중…</Pill>
  return <Pill tone="muted">대기</Pill>
}
