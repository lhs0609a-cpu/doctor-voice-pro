'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import {
  Eye, CalendarClock, Loader2, Trash2, ImageIcon,
  Hash, AlertTriangle, Rocket,
} from 'lucide-react'
import { ExtensionStatusCard, EXTENSION_DOWNLOAD_URL } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { publishQueueAPI, type FormattedPost, type QueuedItem } from '@/lib/api'
import { toast } from 'sonner'
import { toastExtensionMissing } from '@/lib/extension-toast'

// 기본 시작시각 = 내일 오전 9시 (로컬)
function defaultStart(): { date: string; time: string } {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { date, time: '09:00' }
}

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const STATUS_LABEL: Record<string, { label: string; tone: Tone }> = {
  queued: { label: '대기', tone: 'muted' },
  registered: { label: '예약 등록됨', tone: 'accent' },
  published: { label: '발행됨', tone: 'ok' },
  failed: { label: '실패', tone: 'danger' },
}

const LABEL = 'text-[13px] font-medium text-muted-foreground'

export default function BulkPublishPage() {
  const ext = useExtensionStatus()
  const [text, setText] = useState('')
  const [delimiter, setDelimiter] = useState('')
  const [preview, setPreview] = useState<FormattedPost[]>([])
  const [previewing, setPreviewing] = useState(false)

  const start = defaultStart()
  const [startDate, setStartDate] = useState(start.date)
  const [startTime, setStartTime] = useState(start.time)
  const [intervalMin, setIntervalMin] = useState(120)
  const [openType, setOpenType] = useState('public')
  const [assignImages, setAssignImages] = useState(true)
  const [creating, setCreating] = useState(false)

  const [queue, setQueue] = useState<QueuedItem[]>([])
  const [publishing, setPublishing] = useState(false)

  const loadQueue = useCallback(async () => {
    try { setQueue(await publishQueueAPI.list()) } catch { /* noop */ }
  }, [])
  useEffect(() => { loadQueue() }, [loadQueue])

  const doPreview = async () => {
    if (!text.trim()) { toast.error('글을 붙여넣으세요'); return }
    setPreviewing(true)
    try {
      const res = await publishQueueAPI.preview(text, delimiter)
      setPreview(res.posts)
      if (res.count === 0) toast.error('인식된 글이 없습니다')
      else toast.success(`${res.count}개 글 인식됨`)
    } catch (e: any) {
      toast.error('미리보기 실패', { description: e?.message })
    } finally { setPreviewing(false) }
  }

  const doCreate = async () => {
    if (!text.trim()) { toast.error('글을 붙여넣으세요'); return }
    const startAt = new Date(`${startDate}T${startTime}`)
    if (isNaN(startAt.getTime())) { toast.error('시작 시각이 올바르지 않습니다'); return }
    setCreating(true)
    const t = toast.loading('큐에 등록 중...')
    try {
      const res = await publishQueueAPI.bulk({
        text, delimiter,
        start_at: `${startDate}T${startTime}:00`,
        interval_minutes: intervalMin,
        open_type: openType,
        assign_images: assignImages,
      })
      toast.success(`${res.created}개 예약 큐에 등록`, {
        id: t,
        description: `${fmtDT(res.first_at)} ~ ${fmtDT(res.last_at)}`,
      })
      res.warnings?.forEach(w => toast.warning(w))
      setText(''); setPreview([])
      loadQueue()
    } catch (e: any) {
      toast.error('등록 실패', { id: t, description: e?.response?.data?.detail || e?.message })
    } finally { setCreating(false) }
  }

  const removeItem = async (id: string) => {
    try { await publishQueueAPI.remove(id); setQueue(q => q.filter(x => x.id !== id)); toast.success('삭제됨') }
    catch { toast.error('삭제 실패') }
  }

  // 확장으로 배치 전송 → 네이버 예약발행 일괄 등록
  const startPublishing = async () => {
    if (!ext.connected || !ext.extensionId) {
      toastExtensionMissing(); return
    }
    setPublishing(true)
    const t = toast.loading('예약 등록 준비 중... (사진 유니크화 포함)')
    try {
      const jobs = await publishQueueAPI.fetchJobs(50)
      if (jobs.length === 0) { toast.error('대기 중인 글이 없습니다', { id: t }); setPublishing(false); return }
      toast.loading(`${jobs.length}개를 확장으로 전송 중...`, { id: t })

      // 결과 수신 리스너 (content-website 가 CustomEvent 로 전달)
      const onResult = (e: any) => {
        const { id, ok, message } = e.detail || {}
        if (id) publishQueueAPI.reportResult(id, !!ok, message).catch(() => {})
      }
      window.addEventListener('doctorvoice-job-result', onResult)

      chrome.runtime.sendMessage(ext.extensionId, { action: 'SUBMIT_BATCH', jobs }, (res: any) => {
        if (chrome.runtime?.lastError || !res?.success) {
          toast.error('확장 전송 실패', { id: t, description: chrome.runtime?.lastError?.message })
        } else {
          toast.success(`${jobs.length}개 예약 등록을 시작했어요`, {
            id: t, description: '새 탭에서 순차적으로 네이버 예약발행이 등록됩니다. 완료까지 창을 열어두세요.',
          })
        }
        setTimeout(loadQueue, 3000)
        setPublishing(false)
      })
    } catch (e: any) {
      toast.error('시작 실패', { id: t, description: e?.message })
      setPublishing(false)
    }
  }

  const queuedCount = queue.filter(q => q.status === 'queued').length

  return (
    <div className="space-y-6">
      <PageHeader
        title="대량 자동 발행"
        description="글을 붙여넣으면 자동으로 포맷(글·사진·키워드)해 간격 예약발행 큐에 한 번에 등록합니다."
        actions={
          <Button onClick={startPublishing} disabled={publishing || queuedCount === 0 || !ext.connected}>
            {publishing ? <Loader2 className="animate-spin" /> : <Rocket />}
            예약 등록 시작 <span className="tabular-nums">({queuedCount})</span>
          </Button>
        }
      />

      <ExtensionStatusCard />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 좌: 입력 + 설정 */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>1. 글 붙여넣기</CardTitle>
              <CardDescription>첫 줄이 제목이 됩니다. 여러 글은 빈 줄 2개 또는 구분자로 나눠 한 번에 넣으세요.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={text} onChange={e => setText(e.target.value)}
                placeholder={'첫 줄 = 제목\n본문 내용...\n\n\n(빈 줄 3개로 다음 글 구분)\n두 번째 글 제목\n본문...'}
                className="min-h-[220px] font-mono text-sm"
              />
              <div className="flex items-center gap-2">
                <Label className={`${LABEL} whitespace-nowrap`}>구분자(선택)</Label>
                <Input value={delimiter} onChange={e => setDelimiter(e.target.value)} placeholder="예: ---" className="h-8" />
                <Button variant="outline" size="sm" onClick={doPreview} disabled={previewing} className="whitespace-nowrap">
                  {previewing ? <Loader2 className="animate-spin" /> : <Eye />} 미리보기
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>2. 예약 설정</CardTitle>
              <CardDescription>시작 시각부터 정한 간격으로 차례대로 예약됩니다.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1"><Label className={LABEL}>시작 날짜</Label><Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></div>
                <div className="space-y-1"><Label className={LABEL}>시작 시각</Label><Input type="time" step={600} value={startTime} onChange={e => setStartTime(e.target.value)} /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className={LABEL}>글 사이 간격(분)</Label>
                  <Input type="number" min={10} step={10} value={intervalMin} onChange={e => setIntervalMin(Math.max(10, Number(e.target.value) || 10))} className="tabular-nums" />
                </div>
                <div className="space-y-1">
                  <Label className={LABEL}>공개 범위</Label>
                  <select value={openType} onChange={e => setOpenType(e.target.value)} className="h-9 w-full rounded-lg border border-input bg-card px-3 text-sm">
                    <option value="public">전체 공개</option>
                    <option value="neighbor">이웃 공개</option>
                    <option value="both">서로이웃 공개</option>
                    <option value="private">비공개</option>
                  </select>
                </div>
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" checked={assignImages} onChange={e => setAssignImages(e.target.checked)} className="rounded" />
                <ImageIcon className="h-4 w-4 text-muted-foreground" /> 사진 풀에서 자동 배정(중복 회피 유니크화)
              </label>
              <div className="flex gap-2 rounded-lg bg-warning-soft p-3 text-xs text-warning">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                네이버는 계정당 하루 발행량이 많으면 저품질 처리될 수 있어요. 간격을 넉넉히(예: 120분+) 두는 걸 권장합니다.
              </div>
              <div className="flex justify-end">
                <Button variant="outline" onClick={doCreate} disabled={creating}>
                  {creating ? <Loader2 className="animate-spin" /> : <CalendarClock />} 예약 큐에 등록
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 우: 미리보기 */}
        <Card>
          <CardHeader>
            <CardTitle>자동 포맷 미리보기</CardTitle>
            <CardDescription>{preview.length ? <span className="tabular-nums">{preview.length}개 글</span> : '왼쪽에서 "미리보기"를 눌러 확인하세요.'}</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[560px] overflow-y-auto">
            {preview.length === 0 ? (
              <EmptyState
                icon={<Eye className="h-8 w-8" />}
                title="아직 미리보기가 없습니다"
                description="글을 붙여넣고 미리보기를 누르면 제목·사진 위치·키워드가 어떻게 잡히는지 보여줍니다."
                className="py-8"
              />
            ) : (
              <div className="divide-y">
                {preview.map((p, i) => (
                  <div key={i} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold">{p.title}</h3>
                      <Pill tone="muted" className="shrink-0 tabular-nums"><ImageIcon className="h-3 w-3" />{p.image_slots}</Pill>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {p.keywords.map(k => <span key={k} className="inline-flex items-center gap-0.5 text-[11px] text-primary"><Hash className="h-2.5 w-2.5" />{k}</span>)}
                    </div>
                    <div className="mt-2 space-y-1">
                      {p.blocks.map((b, bi) => b.type === 'text'
                        ? <p key={bi} className="line-clamp-2 border-l-2 pl-2 text-xs text-muted-foreground">{b.content}</p>
                        : <div key={bi} className="flex items-center gap-1 pl-2 text-[11px] text-success"><ImageIcon className="h-3 w-3" /> 사진 자동 삽입</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 큐 목록 */}
      <Card>
        <CardHeader>
          <CardTitle>예약 큐 <span className="tabular-nums text-muted-foreground">({queue.length})</span></CardTitle>
          <CardDescription>대기 <span className="tabular-nums">{queuedCount}</span>개 · 상단 ‘예약 등록 시작’을 누르면 확장이 네이버 예약발행에 일괄 등록합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          {!ext.connected && queuedCount > 0 && (
            <p className="mb-3 text-xs text-danger">확장 프로그램 연결 필요 — <a href={EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer" className="underline">설치하기</a></p>
          )}
          {queue.length === 0 ? (
            <EmptyState
              icon={<CalendarClock className="h-8 w-8" />}
              title="등록된 예약이 없습니다"
              description="글을 붙여넣고 ‘예약 큐에 등록’을 누르면 여기에 쌓입니다."
              className="py-8"
            />
          ) : (
            <div className="divide-y">
              {queue.map(q => {
                const st = STATUS_LABEL[q.status] || STATUS_LABEL.queued
                return (
                  <div key={q.id} className="flex items-center gap-3 py-2.5 hover:bg-muted/40">
                    <div className="w-32 shrink-0 text-xs tabular-nums text-muted-foreground">{fmtDT(q.scheduled_at)}</div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{q.title}</p>
                      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center gap-0.5 tabular-nums"><ImageIcon className="h-2.5 w-2.5" />{q.image_slots}</span>
                        <span>· {q.keywords.slice(0, 3).join(', ')}</span>
                      </div>
                    </div>
                    <Pill tone={st.tone}>{st.label}</Pill>
                    <Button variant="ghost" size="sm" className="w-8 px-0" onClick={() => removeItem(q.id)}><Trash2 /></Button>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function fmtDT(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
