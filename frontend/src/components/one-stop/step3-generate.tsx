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
import { topPostsAPI, type WritingPackage } from '@/lib/api'
import { Checkbox } from '@/components/ui/checkbox'
import { BrandForm, useBrand } from './brand-form'
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
  // 상위글을 실제로 분석해 키워드별 프롬프트를 만들지 여부
  const [useSpec, setUseSpec] = useState(true)
  const [designing, setDesigning] = useState(false)
  const [packages, setPackages] = useState<WritingPackage[]>([])
  const { brand, setBrand } = useBrand()

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

    // 키워드별 설계서를 먼저 받아온다.
    //  - 지금 그 키워드로 1페이지에 있는 글들을 실제로 읽어서
    //    분량/이미지/소제목 규격과 경쟁글이 빠뜨린 주제를 뽑아낸 프롬프트다.
    //  - 실패하면 기본 템플릿으로 떨어뜨려 생성 자체는 막지 않는다.
    let prompts: Record<string, string> = {}
    if (useSpec) {
      setDesigning(true)
      try {
        const { results } = await topPostsAPI.createWritingSpec({
          keywords: state.approved,
          top_n: 5,
          brand,
        })
        const designed: WritingPackage[] = []
        results.forEach((r) => {
          if (r.prompt) {
            prompts[r.keyword] = r.prompt
            designed.push(r)
          }
        })
        setPackages(designed)
        if (designed.length) {
          toast.success(`${designed.length}개 키워드 설계 완료 (상위글 분석 기반)`)
        }
        if (designed.length < state.approved.length) {
          toast.warning(
            `${state.approved.length - designed.length}개는 설계에 실패해 기본 템플릿으로 씁니다.`,
          )
        }
      } catch (e) {
        toast.warning('설계 서버 응답이 없어 기본 템플릿으로 진행합니다.')
      } finally {
        setDesigning(false)
      }
    }

    const tpl = loadTemplates()[0]
    const items = state.approved.map((keyword, i) => ({
      id: `ws-${Date.now()}-${i}`,
      keyword,
      prompt: prompts[keyword] || renderPrompt(tpl.body, { 키워드: keyword, keyword }),
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

          {/* 상위글 기반 자동 설계 */}
          <div className="rounded-lg border bg-muted/40 p-3 space-y-2">
            <label className="flex items-start gap-2 cursor-pointer">
              <Checkbox
                checked={useSpec}
                onCheckedChange={(v) => setUseSpec(Boolean(v))}
                disabled={running || designing}
                className="mt-0.5"
              />
              <span className="text-sm">
                <b>상위글 기반 자동 설계</b> (권장)
                <span className="block text-muted-foreground text-xs mt-0.5">
                  키워드마다 지금 1페이지에 있는 글들을 실제로 읽어서 분량·이미지·소제목 규격과
                  경쟁글이 빠뜨린 주제를 뽑고, 전환 요소와 의료법 금지어까지 넣은 프롬프트를
                  만들어 씁니다. 끄면 기본 템플릿으로 씁니다.
                </span>
              </span>
            </label>

            {useSpec && (
              <div className="rounded-md border bg-background p-3">
                <BrandForm
                  value={brand}
                  onChange={setBrand}
                  disabled={running || designing}
                />
              </div>
            )}

            {designing && (
              <p className="text-sm text-blue-700">
                상위글을 분석해 키워드별 설계서를 만드는 중입니다… (키워드당 10~30초)
              </p>
            )}

            {packages.length > 0 && (
              <div className="space-y-2 pt-1">
                {packages.map((pkg) => (
                  <details key={pkg.keyword} className="text-xs">
                    <summary className="cursor-pointer font-medium">
                      {pkg.keyword} — 상위글 {pkg.research_summary?.analyzed_count ?? 0}개 분석 ·
                      목표 {pkg.spec?.content.target_length.toLocaleString()}자 ·
                      소제목 {pkg.spec?.content.heading_count}개 ·
                      이미지 {pkg.spec?.media.image_count}장
                    </summary>
                    <div className="mt-1 pl-3 space-y-1 text-muted-foreground">
                      {pkg.differentiation?.primary_pain && (
                        <p className="text-foreground">
                          <b>이 글의 각도:</b> {pkg.differentiation.primary_pain.label}
                          {pkg.differentiation.wedge &&
                            ` · 쐐기 "${pkg.differentiation.wedge.topic}"`}
                        </p>
                      )}
                      {!!pkg.research_summary?.content_gaps?.length && (
                        <p>
                          경쟁글이 빠뜨린 주제:{' '}
                          {pkg.research_summary.content_gaps.join(', ')}
                        </p>
                      )}
                      {!!pkg.research_summary?.questions?.length && (
                        <p>답할 질문: {pkg.research_summary.questions.slice(0, 5).join(', ')}</p>
                      )}
                      <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-background p-2 text-[11px] leading-relaxed">
                        {pkg.prompt}
                      </pre>
                    </div>
                  </details>
                ))}
              </div>
            )}
          </div>

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
            <Button onClick={launch} disabled={designing}>
              {designing ? '설계 중…' : '생성 시작'}
            </Button>
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
