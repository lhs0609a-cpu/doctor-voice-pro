'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, CalendarClock, Loader2, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { campaignAPI, type ScheduleInput, type SchedulePreview } from '@/lib/campaign-api'
import { EmptyNote, Pill, StepFooter, TABLE_CLS, errMsg, fmt, fmtDateTime, todayPlus, type StepProps } from './common'

export function Step5Schedule({ campaign, client, setCampaign, goStep }: StepProps) {
  const candidateBlogs = useMemo(() => {
    const active = (client.blogs || []).filter((b) => b.status === 'active')
    const inCampaign = active.filter((b) => campaign.blog_ids?.includes(b.id))
    return inCampaign.length ? inCampaign : active
  }, [client.blogs, campaign.blog_ids])

  const [startDate, setStartDate] = useState(todayPlus(1))
  const [days, setDays] = useState('14')
  const [perDay, setPerDay] = useState('')
  const [blogIds, setBlogIds] = useState<string[]>(candidateBlogs.map((b) => b.id))
  const [includeNeedsReview, setIncludeNeedsReview] = useState(false)
  const [preview, setPreview] = useState<SchedulePreview | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  const buildInput = (): ScheduleInput => ({
    start_date: startDate,
    days: Math.max(1, Number(days) || 1),
    blog_ids: blogIds,
    per_day: perDay.trim() ? Number(perDay) : null,
    include_needs_review: includeNeedsReview,
  })

  const validate = () => {
    if (!startDate) { toast.error('시작일을 넣어주세요'); return false }
    if (blogIds.length === 0) { toast.error('블로그를 하나 이상 고르세요'); return false }
    return true
  }

  const doPreview = async () => {
    if (!validate()) return
    setPreviewing(true)
    try { setPreview(await campaignAPI.schedulePreview(campaign.id, buildInput())) }
    catch (err: any) { toast.error('미리보기 실패', { description: errMsg(err) }) }
    finally { setPreviewing(false) }
  }

  const doCommit = async () => {
    setConfirmOpen(false)
    setCommitting(true)
    try {
      const r = await campaignAPI.scheduleCommit(campaign.id, buildInput())
      toast.success(`${fmt(r.assigned.length)}건 예약을 걸었어요`, { description: '사진 유니크화가 백그라운드에서 준비됩니다.' })
      try { setCampaign(await campaignAPI.getCampaign(campaign.id)) } catch { /* noop */ }
      goStep(6)
    } catch (err: any) {
      toast.error('예약 실패', { description: errMsg(err) })
    } finally { setCommitting(false) }
  }

  const doCancel = async () => {
    setCancelOpen(false)
    setCancelling(true)
    try {
      const r = await campaignAPI.scheduleCancel(campaign.id)
      toast.success(`${fmt(r.cancelled)}건 예약을 취소했어요`)
      try { setCampaign(await campaignAPI.getCampaign(campaign.id)) } catch { /* noop */ }
      setPreview(null)
    } catch (err: any) {
      toast.error('취소 실패', { description: errMsg(err) })
    } finally { setCancelling(false) }
  }

  const blogLabel = (id: string) => client.blogs?.find((b) => b.id === id)?.label || client.blogs?.find((b) => b.id === id)?.blog_id || id
  const alreadyScheduled = campaign.status === 'scheduled' || campaign.status === 'running'

  return (
    <div className="space-y-6">
      {alreadyScheduled && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
          <CalendarClock className="h-4 w-4" />
          <span className="flex-1 tabular-nums">이미 예약이 걸려 있습니다. 대기 {fmt(campaign.stats?.queued)} · 발행됨 {fmt(campaign.stats?.published)} · 실패 {fmt(campaign.stats?.failed)}</span>
          <Button variant="outline" size="sm" onClick={() => goStep(6)}>현황 보기</Button>
          <Button variant="destructive" size="sm" onClick={() => setCancelOpen(true)} disabled={cancelling}>
            {cancelling && <Loader2 className="animate-spin" />} 예약 전체 취소
          </Button>
        </div>
      )}

      <Card className="space-y-4 p-5">
        <div>
          <h3 className="section-title">예약 계획</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">준비된 원고를 블로그별 하루 발행 한도·시간대에 맞춰 자동으로 나눠 배정합니다.</p>
        </div>
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5"><Label>시작일</Label><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>기간 (일)</Label><Input type="number" min={1} max={90} value={days} onChange={(e) => setDays(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>하루 발행 수 (블로그당)</Label><Input type="number" min={1} max={20} value={perDay} onChange={(e) => setPerDay(e.target.value)} placeholder="비우면 블로그 설정값" /></div>
          </div>
          <div className="space-y-1.5">
            <Label>블로그</Label>
            {candidateBlogs.length === 0 ? (
              <div className="text-sm text-warning">정상 상태의 블로그가 없습니다. 1단계에서 블로그를 확인하세요.</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {candidateBlogs.map((b) => {
                  const on = blogIds.includes(b.id)
                  return (
                    <label key={b.id} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${on ? 'border-primary/40 bg-accent' : 'hover:bg-muted/40'}`}>
                      <Checkbox checked={on} onCheckedChange={(v) => setBlogIds((prev) => (v === true ? [...prev, b.id] : prev.filter((x) => x !== b.id)))} />
                      <span>{b.label || b.blog_id}</span>
                      <span className="text-xs text-muted-foreground">하루 {b.daily_limit}건</span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox checked={includeNeedsReview} onCheckedChange={(v) => setIncludeNeedsReview(v === true)} />
            &lsquo;확인 필요&rsquo; 원고도 포함 (검수 통과가 아닌 원고까지 예약)
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={doPreview} disabled={previewing || candidateBlogs.length === 0}>
              {previewing ? <Loader2 className="animate-spin" /> : <Eye />} 미리보기
            </Button>
            <Button onClick={() => { if (validate()) setConfirmOpen(true) }} disabled={committing || candidateBlogs.length === 0 || !preview} title={!preview ? '먼저 미리보기를 눌러 확인하세요' : undefined}>
              {committing ? <Loader2 className="animate-spin" /> : <CalendarClock />} 예약 걸기
            </Button>
            {!preview && <span className="text-xs text-muted-foreground">미리보기로 배정 결과를 확인한 뒤 예약을 걸 수 있어요.</span>}
          </div>
        </div>
      </Card>

      {preview && (
        <Card className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="section-title">배정 미리보기</h3>
            <Pill tone="info">총 {fmt(preview.total)}건</Pill>
            <Pill tone="ok">배정 {fmt(preview.assigned.length)}건</Pill>
            {preview.unassigned > 0 && <Pill tone="warn">배정 못 함 {fmt(preview.unassigned)}건</Pill>}
          </div>
          <div className="space-y-4">
            {preview.warnings?.length > 0 && (
              <div className="space-y-1 rounded-lg bg-warning-soft p-3 text-sm text-warning">
                {preview.warnings.map((w, i) => <div key={i} className="flex items-start gap-1.5"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {w}</div>)}
              </div>
            )}
            {preview.unassigned > 0 && (
              <p className="text-xs text-muted-foreground">배정 못 한 {fmt(preview.unassigned)}건은 기간을 늘리거나 하루 발행 수를 올리면 들어갑니다.</p>
            )}

            {/* 달력 */}
            {preview.calendar?.length > 0 && (
              <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 md:grid-cols-7">
                {preview.calendar.map((c) => (
                  <div key={c.date} className={`rounded-lg p-2 text-xs ${c.total > 0 ? 'bg-accent text-accent-foreground' : 'bg-muted/60 text-muted-foreground'}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{c.date.slice(5)}</span>
                      <span className="tabular-nums font-semibold">{c.total}</span>
                    </div>
                    {c.total > 0 && (
                      <div className="mt-1 space-y-0.5 text-[10px] opacity-80">
                        {Object.entries(c.blogs || {}).map(([bid, n]) => (
                          <div key={bid} className="flex justify-between gap-1"><span className="truncate">{blogLabel(bid)}</span><span className="tabular-nums">{n}</span></div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {preview.assigned.length === 0 ? (
              <EmptyNote>배정된 원고가 없습니다. 3단계에서 검수 통과 원고가 있는지 확인하세요.</EmptyNote>
            ) : (
              <div className="max-h-[420px] overflow-x-auto overflow-y-auto">
                <Table className={TABLE_CLS}>
                  <TableHeader>
                    <TableRow>
                      <TableHead>제목</TableHead>
                      <TableHead>블로그</TableHead>
                      <TableHead>예약 시각</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.assigned.map((a) => (
                      <TableRow key={`${a.draft_id}-${a.scheduled_at}`}>
                        <TableCell className="max-w-[360px] truncate">{a.title}</TableCell>
                        <TableCell className="text-xs">{a.blog_label}</TableCell>
                        <TableCell className="text-xs tabular-nums">{fmtDateTime(a.scheduled_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </Card>
      )}

      <StepFooter onBack={() => goStep(4)} onNext={() => goStep(6)} nextLabel="현황 보기" />

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{fmt(preview?.assigned.length)}건을 예약합니다</AlertDialogTitle>
            <AlertDialogDescription>
              사진 유니크화가 백그라운드에서 준비됩니다. 예약 후에는 6단계 현황에서 발행을 실행할 수 있어요.
              {alreadyScheduled ? ' 이미 걸린 예약이 있으면 새 예약이 추가됩니다.' : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={doCommit}>예약 걸기</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>예약을 전체 취소할까요?</AlertDialogTitle>
            <AlertDialogDescription>아직 발행되지 않은 대기 건이 모두 취소됩니다. 이미 발행된 글은 그대로 남습니다.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>돌아가기</AlertDialogCancel>
            <AlertDialogAction onClick={doCancel} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">전체 취소</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
