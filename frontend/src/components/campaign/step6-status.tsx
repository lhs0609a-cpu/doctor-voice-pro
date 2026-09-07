'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Check, ExternalLink, Loader2, RefreshCw, RotateCcw, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState, StatTile } from '@/components/app-shell/ui-kit'
import { JOB_STATUS_LABEL, campaignAPI, type PublishJobItem } from '@/lib/campaign-api'
import { Pill, StepFooter, TABLE_CLS, errMsg, fmt, fmtDateTime, type StepProps, type Tone } from './common'
import { PublishRunner } from './publish-runner'

const JOB_TONE: Record<string, Tone> = {
  queued: 'muted', assigned: 'info', publishing: 'info', published: 'ok', failed: 'crit', uncertain: 'warn', cancelled: 'muted',
}
const ACTIVE = new Set(['queued', 'assigned', 'publishing'])

export function Step6Status({ campaign, setCampaign, goStep }: StepProps) {
  const [jobs, setJobs] = useState<PublishJobItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async (silent = false) => {
    try {
      const [js, c] = await Promise.all([campaignAPI.listJobs(campaign.id), campaignAPI.getCampaign(campaign.id)])
      setJobs(js)
      setCampaign(c)
    } catch (err: any) {
      if (!silent) toast.error('현황 불러오기 실패', { description: errMsg(err) })
    } finally { setLoading(false) }
  }, [campaign.id, setCampaign])

  useEffect(() => { load() }, [load])

  const anyActive = useMemo(() => jobs.some((j) => ACTIVE.has(j.status)), [jobs])
  useEffect(() => {
    if (!anyActive) return
    const iv = setInterval(() => load(true), 5000)
    return () => clearInterval(iv)
  }, [anyActive, load])

  const counts = useMemo(() => {
    const c = { queued: 0, published: 0, failed: 0, uncertain: 0 }
    for (const j of jobs) {
      if (ACTIVE.has(j.status)) c.queued += 1
      else if (j.status === 'published') c.published += 1
      else if (j.status === 'failed') c.failed += 1
      else if (j.status === 'uncertain') c.uncertain += 1
    }
    return c
  }, [jobs])

  const act = async (id: string, fn: () => Promise<PublishJobItem>, okMsg: string) => {
    setBusy(id)
    try {
      const j = await fn()
      setJobs((prev) => prev.map((x) => (x.id === j.id ? j : x)))
      toast.success(okMsg)
    } catch (err: any) {
      toast.error('실패', { description: errMsg(err) })
    } finally { setBusy(null) }
  }

  const markPublished = (j: PublishJobItem) => {
    const url = window.prompt('발행된 글 주소(URL)를 넣어주세요. 모르면 비워도 됩니다.', j.result_url || '')
    if (url === null) return
    act(j.id, () => campaignAPI.markPublished(j.id, url.trim() || undefined), '발행됨으로 표시했어요')
  }

  const sorted = useMemo(() => [...jobs].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)), [jobs])

  return (
    <div className="space-y-6">
      {/* 요약 타일 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="대기" value={fmt(counts.queued)} />
        <StatTile label="발행됨" value={fmt(counts.published)} tone="ok" />
        <StatTile label="실패" value={fmt(counts.failed)} tone={counts.failed > 0 ? 'danger' : undefined} />
        <StatTile label="확인 필요" value={fmt(counts.uncertain)} tone={counts.uncertain > 0 ? 'warn' : undefined} />
      </div>

      {/* 발행 실행 */}
      <PublishRunner campaign={campaign} onJobsChanged={() => load(true)} />

      {/* 예약 목록 */}
      <Card className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <div>
            <h3 className="section-title">예약 목록 <span className="tabular-nums">{fmt(jobs.length)}</span>건</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">{anyActive ? '진행 중인 건이 있어 5초마다 새로 고칩니다.' : '실패한 건은 다시 시도할 수 있어요.'}</p>
          </div>
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => load()}><RefreshCw /> 새로고침</Button>
        </div>
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...</div>
        ) : jobs.length === 0 ? (
          <EmptyState
            title="아직 예약이 없어요"
            description="5단계에서 준비된 원고를 블로그별로 예약하세요."
            action={<Button variant="outline" size="sm" onClick={() => goStep(5)}>5단계에서 예약 걸기</Button>}
            className="py-8"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table className={TABLE_CLS}>
              <TableHeader>
                <TableRow>
                  <TableHead>예약 시각</TableHead>
                  <TableHead>제목</TableHead>
                  <TableHead>블로그</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead className="text-center">사진</TableHead>
                  <TableHead className="text-right">시도</TableHead>
                  <TableHead>결과</TableHead>
                  <TableHead className="w-[200px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((j) => {
                  const canRetry = ['failed', 'uncertain', 'cancelled'].includes(j.status)
                  const canCancel = ACTIVE.has(j.status)
                  return (
                    <TableRow key={j.id}>
                      <TableCell className="whitespace-nowrap text-xs tabular-nums">{fmtDateTime(j.scheduled_at)}</TableCell>
                      <TableCell className="max-w-[300px]">
                        <div className="truncate font-medium">{j.title}</div>
                        {j.keyword && <div className="text-[11px] text-muted-foreground">{j.keyword}</div>}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs">{j.blog_label}</TableCell>
                      <TableCell><Pill tone={JOB_TONE[j.status] || 'muted'}>{JOB_STATUS_LABEL[j.status] || j.status}</Pill></TableCell>
                      <TableCell className="text-center text-xs tabular-nums">
                        {j.images_ready ? <span className="inline-flex items-center gap-0.5 text-success"><Check className="h-3.5 w-3.5" />{j.image_count}</span> : <span className="text-muted-foreground" title="사진 유니크화 준비 중">{j.image_count}장 준비 중</span>}
                      </TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{j.attempts}</TableCell>
                      <TableCell className="max-w-[260px]">
                        {j.result_url && (
                          <a href={j.result_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                            글 보기 <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                        {j.error && <div className="whitespace-pre-wrap break-words text-[11px] text-danger">{j.error}</div>}
                        {j.published_at && <div className="text-[11px] tabular-nums text-muted-foreground">발행 {fmtDateTime(j.published_at)}</div>}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center justify-end gap-1">
                          {canRetry && (
                            <Button variant="outline" size="sm" disabled={busy === j.id} onClick={() => act(j.id, () => campaignAPI.retryJob(j.id), '다시 대기열에 넣었어요')}>
                              <RotateCcw /> 다시 시도
                            </Button>
                          )}
                          {j.status === 'uncertain' && (
                            <Button variant="outline" size="sm" disabled={busy === j.id} onClick={() => markPublished(j)}>
                              <Check /> 발행됨으로 표시
                            </Button>
                          )}
                          {canCancel && (
                            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-danger" disabled={busy === j.id} onClick={() => act(j.id, () => campaignAPI.cancelJob(j.id), '취소했어요')}>
                              <XCircle /> 취소
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      <StepFooter onBack={() => goStep(5)} />
    </div>
  )
}
