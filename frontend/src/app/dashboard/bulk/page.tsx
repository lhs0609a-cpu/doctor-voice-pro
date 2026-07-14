'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect, useCallback } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Layers, Eye, CalendarClock, Loader2, Trash2, ImageIcon,
  Hash, FileText, Sparkles, AlertTriangle, Rocket,
} from 'lucide-react'
import { ExtensionStatusCard, EXTENSION_DOWNLOAD_URL } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { publishQueueAPI, type FormattedPost, type QueuedItem } from '@/lib/api'
import { toast } from 'sonner'

// 기본 시작시각 = 내일 오전 9시 (로컬)
function defaultStart(): { date: string; time: string } {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { date, time: '09:00' }
}

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  queued: { label: '대기', cls: 'bg-slate-100 text-slate-700' },
  registered: { label: '예약 등록됨', cls: 'bg-blue-100 text-blue-700' },
  published: { label: '발행됨', cls: 'bg-emerald-100 text-emerald-700' },
  failed: { label: '실패', cls: 'bg-rose-100 text-rose-700' },
}

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
      toast.error('확장 프로그램이 연결되지 않았습니다'); return
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
    <div className="min-h-screen bg-background">
      <DashboardNav />
      <main className="container mx-auto px-4 py-8 max-w-6xl space-y-5">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10"><Layers className="h-6 w-6 text-primary" /></div>
          <div>
            <h1 className="text-2xl font-bold">대량 자동 발행</h1>
            <p className="text-sm text-muted-foreground">글 붙여넣기 → 자동 포맷(글·사진·키워드) → 간격 예약발행 큐에 싹 등록</p>
          </div>
        </div>

        <ExtensionStatusCard />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* 좌: 입력 + 설정 */}
          <div className="space-y-5">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> 글 붙여넣기</CardTitle>
                <CardDescription>첫 줄이 제목이 됩니다. 여러 글은 빈 줄 2개 또는 구분자로 나눠 한 번에 넣으세요.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  value={text} onChange={e => setText(e.target.value)}
                  placeholder={'첫 줄 = 제목\n본문 내용...\n\n\n(빈 줄 3개로 다음 글 구분)\n두 번째 글 제목\n본문...'}
                  className="min-h-[220px] font-mono text-sm"
                />
                <div className="flex items-center gap-2">
                  <Label className="text-xs whitespace-nowrap">구분자(선택)</Label>
                  <Input value={delimiter} onChange={e => setDelimiter(e.target.value)} placeholder="예: ---" className="h-8" />
                  <Button variant="outline" size="sm" onClick={doPreview} disabled={previewing} className="gap-1 whitespace-nowrap">
                    {previewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />} 미리보기
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" /> 예약 설정</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs">시작 날짜</Label><Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="mt-1" /></div>
                  <div><Label className="text-xs">시작 시각</Label><Input type="time" step={600} value={startTime} onChange={e => setStartTime(e.target.value)} className="mt-1" /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">글 사이 간격(분)</Label>
                    <Input type="number" min={10} step={10} value={intervalMin} onChange={e => setIntervalMin(Math.max(10, Number(e.target.value) || 10))} className="mt-1" />
                  </div>
                  <div>
                    <Label className="text-xs">공개 범위</Label>
                    <select value={openType} onChange={e => setOpenType(e.target.value)} className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                      <option value="public">전체 공개</option>
                      <option value="neighbor">이웃 공개</option>
                      <option value="both">서로이웃 공개</option>
                      <option value="private">비공개</option>
                    </select>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={assignImages} onChange={e => setAssignImages(e.target.checked)} className="rounded" />
                  <ImageIcon className="h-4 w-4" /> 사진 풀에서 자동 배정(중복 회피 유니크화)
                </label>
                <div className="rounded-md bg-amber-50 border border-amber-200 p-2.5 text-[11px] text-amber-700 flex gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  네이버는 계정당 하루 발행량이 많으면 저품질 처리될 수 있어요. 간격을 넉넉히(예: 120분+) 두는 걸 권장합니다.
                </div>
                <Button onClick={doCreate} disabled={creating} className="w-full gap-2 bg-emerald-600 hover:bg-emerald-700">
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarClock className="h-4 w-4" />} 예약 큐에 등록
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* 우: 미리보기 */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base"><Sparkles className="h-4 w-4" /> 자동 포맷 미리보기</CardTitle>
              <CardDescription>{preview.length ? `${preview.length}개 글` : '왼쪽에서 "미리보기"를 눌러 확인'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 max-h-[560px] overflow-y-auto">
              {preview.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                  <Eye className="h-10 w-10 mx-auto mb-2 opacity-40" />
                  <p>글을 붙여넣고 미리보기를 눌러보세요</p>
                </div>
              ) : preview.map((p, i) => (
                <div key={i} className="border rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-sm">{p.title}</h3>
                    <Badge variant="secondary" className="shrink-0 gap-1"><ImageIcon className="h-3 w-3" />{p.image_slots}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {p.keywords.map(k => <span key={k} className="inline-flex items-center gap-0.5 text-[11px] text-blue-600"><Hash className="h-2.5 w-2.5" />{k}</span>)}
                  </div>
                  <div className="mt-2 space-y-1">
                    {p.blocks.map((b, bi) => b.type === 'text'
                      ? <p key={bi} className="text-xs text-gray-600 line-clamp-2 pl-2 border-l-2 border-gray-200">{b.content}</p>
                      : <div key={bi} className="text-[11px] text-emerald-600 flex items-center gap-1 pl-2"><ImageIcon className="h-3 w-3" /> 사진 자동 삽입</div>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* 큐 목록 + 발행 시작 */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">예약 큐 ({queue.length})</CardTitle>
                <CardDescription>대기 {queuedCount}개 · 확장으로 네이버 예약발행에 일괄 등록</CardDescription>
              </div>
              <Button onClick={startPublishing} disabled={publishing || queuedCount === 0 || !ext.connected} className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />} 예약 등록 시작 ({queuedCount})
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {!ext.connected && queuedCount > 0 && (
              <p className="mb-3 text-xs text-rose-600">확장 프로그램 연결 필요 — <a href={EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer" className="underline">설치하기</a></p>
            )}
            {queue.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground"><CalendarClock className="h-10 w-10 mx-auto mb-2 opacity-40" /><p>등록된 예약이 없습니다</p></div>
            ) : (
              <div className="divide-y">
                {queue.map(q => {
                  const st = STATUS_LABEL[q.status] || STATUS_LABEL.queued
                  return (
                    <div key={q.id} className="flex items-center gap-3 py-2.5">
                      <div className="text-xs text-muted-foreground tabular-nums w-32 shrink-0">{fmtDT(q.scheduled_at)}</div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{q.title}</p>
                        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                          <span className="inline-flex items-center gap-0.5"><ImageIcon className="h-2.5 w-2.5" />{q.image_slots}</span>
                          <span>· {q.keywords.slice(0, 3).join(', ')}</span>
                        </div>
                      </div>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full ${st.cls}`}>{st.label}</span>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeItem(q.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

function fmtDT(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
