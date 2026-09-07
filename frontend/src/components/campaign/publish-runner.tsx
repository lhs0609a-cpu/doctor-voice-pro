'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { toastExtensionMissing } from '@/lib/extension-toast'
import { Loader2, PlayCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ExtensionStatusCard } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { BLOG_STATUS_LABEL, campaignAPI, type AgentBlogSummary, type Campaign, type ClaimedJob } from '@/lib/campaign-api'
import { Pill, errMsg, fmt, fmtDateTime } from './common'

interface LogItem { at: string; title: string; ok: boolean; uncertain?: boolean; message?: string }

// 확장 프로그램에 메시지 (externally_connectable)
function sendMessageToExtension(extId: string, message: any): Promise<any> {
  return new Promise((resolve, reject) => {
    if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      reject(new Error('Chrome API를 사용할 수 없습니다')); return
    }
    try {
      chrome.runtime.sendMessage(extId, message, (res: any) => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError)
        else resolve(res)
      })
    } catch (e) { reject(e) }
  })
}

const nowHHMM = () => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

export function PublishRunner({ campaign, onJobsChanged }: { campaign: Campaign; onJobsChanged: () => void }) {
  const ext = useExtensionStatus()
  const [summary, setSummary] = useState<AgentBlogSummary[]>([])
  const [blogRef, setBlogRef] = useState('')
  const [starting, setStarting] = useState(false)
  const [batch, setBatch] = useState<{ total: number; done: number; ok: number } | null>(null)
  const [log, setLog] = useState<LogItem[]>([])

  // 확장이 payload 를 요청할 때 돌려줄 전체 작업(사진 base64 포함)
  const jobsRef = useRef<Map<string, ClaimedJob>>(new Map())
  const batchRef = useRef({ total: 0, done: 0, ok: 0 })
  const onJobsChangedRef = useRef(onJobsChanged)
  onJobsChangedRef.current = onJobsChanged

  const loadSummary = useCallback(async () => {
    try {
      const s = await campaignAPI.agentSummary()
      setSummary(s)
      setBlogRef((cur) => {
        if (cur && s.some((x) => x.blog_ref_id === cur)) return cur
        const first = s.find((x) => x.pending > 0) || s[0]
        return first?.blog_ref_id || ''
      })
    } catch (err: any) {
      toast.error('블로그 현황 불러오기 실패', { description: errMsg(err) })
    }
  }, [])

  useEffect(() => { loadSummary() }, [loadSummary, campaign.stats?.queued])

  // 확장 → payload 요청: 잠금 걸린 작업 본문/사진을 그대로 넘긴다
  useEffect(() => {
    const onRequest = (e: any) => {
      const { id, token } = e.detail || {}
      const reply = (job: any) => window.dispatchEvent(new CustomEvent('doctorvoice-job-payload', { detail: { token, job } }))
      const j = jobsRef.current.get(id)
      if (!j) { reply(null); return }
      reply({
        id: j.id, title: j.title, content: j.content, blocks: j.blocks, tags: j.tags, emphasize: j.emphasize,
        options: j.options, finalAction: j.finalAction, schedule: j.schedule, expectedBlogId: j.expectedBlogId,
      })
    }
    window.addEventListener('doctorvoice-job-request', onRequest)
    return () => window.removeEventListener('doctorvoice-job-request', onRequest)
  }, [])

  // 확장 → 결과: 서버에 보고하고 목록 갱신
  useEffect(() => {
    const onResult = async (e: any) => {
      const { id, ok, message, uncertain } = e.detail || {}
      if (!id) return
      const j = jobsRef.current.get(id)
      if (!j) return // 이 화면이 보낸 배치가 아님
      const msg: string = message || ''
      try {
        await campaignAPI.agentResult(id, {
          lock_token: j.lock_token, ok: !!ok, uncertain: !!uncertain, message: msg || undefined,
          captcha: /캡차|captcha/i.test(msg), need_login: /로그인/.test(msg),
        })
      } catch (err: any) {
        toast.error('결과 보고 실패', { description: errMsg(err) })
      }
      jobsRef.current.delete(id)
      const b = batchRef.current
      b.done += 1
      if (ok) b.ok += 1
      setBatch({ ...b })
      setLog((prev) => [{ at: nowHHMM(), title: j.title, ok: !!ok, uncertain: !!uncertain, message: msg }, ...prev].slice(0, 200))
      onJobsChangedRef.current()
      if (b.done >= b.total) {
        const failed = b.total - b.ok
        if (failed > 0) toast.warning(`발행 끝 — ${b.ok}건 성공, ${failed}건 실패/확인 필요`)
        else toast.success(`${b.ok}건 모두 발행 요청을 마쳤어요`)
        batchRef.current = { total: 0, done: 0, ok: 0 }
        setBatch(null)
        loadSummary()
      }
    }
    window.addEventListener('doctorvoice-job-result', onResult)
    return () => window.removeEventListener('doctorvoice-job-result', onResult)
  }, [loadSummary])

  const start = async () => {
    if (!ext.connected || !ext.extensionId) { toastExtensionMissing(); return }
    if (!blogRef) { toast.error('블로그를 고르세요'); return }
    setStarting(true)
    const t = toast.loading('예약 글과 사진을 가져오는 중...')
    try {
      const claimed = await campaignAPI.agentClaim({ blog_ref_id: blogRef, limit: 20, include_images: true })
      if (claimed.length === 0) {
        toast.warning('이 블로그에 지금 가져갈 예약이 없습니다', { id: t, description: '사진 준비가 끝나지 않았거나 예약 시각이 아직 멀 수 있어요.' })
        return
      }
      jobsRef.current = new Map(claimed.map((j) => [j.id, j]))
      batchRef.current = { total: claimed.length, done: 0, ok: 0 }
      setBatch({ ...batchRef.current })

      const metas = claimed.map((j) => ({
        id: j.id, title: j.title, options: j.options, finalAction: 'schedule' as const, schedule: j.schedule, expectedBlogId: j.expectedBlogId,
      }))
      const expectedBlogId = claimed[0]?.expectedBlogId || undefined
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_BATCH', jobs: metas, expectedBlogId })
      if (!res?.success) throw new Error(res?.error || res?.message || '확장이 배치를 받지 않았습니다')
      toast.success(`${claimed.length}건 발행을 시작했어요`, {
        id: t, description: '새 탭에서 한 건씩 네이버 예약발행이 등록됩니다. 끝날 때까지 이 창을 닫지 마세요.',
      })
      onJobsChangedRef.current()
    } catch (err: any) {
      toast.error('발행 시작 실패', { id: t, description: errMsg(err) })
      // 확장이 받지 못했으면 잠금이 걸린 채 남는다 → 서버에 실패로 돌려 잠금 해제
      const pending = Array.from(jobsRef.current.values())
      for (const j of pending) {
        campaignAPI.agentResult(j.id, { lock_token: j.lock_token, ok: false, message: '확장 전송 실패', release: true }).catch(() => { /* noop */ })
      }
      jobsRef.current = new Map()
      batchRef.current = { total: 0, done: 0, ok: 0 }
      setBatch(null)
      onJobsChangedRef.current()
    } finally {
      setStarting(false)
    }
  }

  const current = summary.find((s) => s.blog_ref_id === blogRef)
  const running = !!batch

  return (
    <Card className="space-y-4 p-5">
      <div>
        <h3 className="section-title">발행 실행</h3>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          이 브라우저의 크롬 확장 프로그램이 네이버에 예약발행을 등록합니다. 블로그에 로그인된 상태여야 해요.
        </p>
      </div>
      <div className="space-y-4">
        <ExtensionStatusCard />

        <div className="grid items-end gap-3 md:grid-cols-[1fr_auto]">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label>블로그</Label>
              <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[11px] [&_svg]:h-3 [&_svg]:w-3" onClick={loadSummary}><RefreshCw /> 새로고침</Button>
            </div>
            <Select value={blogRef} onValueChange={setBlogRef} disabled={running}>
              <SelectTrigger><SelectValue placeholder="블로그 선택" /></SelectTrigger>
              <SelectContent>
                {summary.length === 0 && <SelectItem value="__empty__" disabled>대기 중인 예약이 있는 블로그가 없습니다</SelectItem>}
                {summary.map((s) => (
                  <SelectItem key={s.blog_ref_id} value={s.blog_ref_id}>
                    {s.label || s.naver_blog_id} · 대기 {fmt(s.pending)}건{s.next_at ? ` · 다음 ${fmtDateTime(s.next_at)}` : ''}{s.status !== 'active' ? ` · ${BLOG_STATUS_LABEL[s.status] || s.status}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {current && current.status !== 'active' && (
              <p className="text-xs text-warning">이 블로그는 {BLOG_STATUS_LABEL[current.status] || current.status} 상태예요{current.status_reason ? ` · ${current.status_reason}` : ''}. 병원 설정에서 정상으로 바꾼 뒤 시작하세요.</p>
            )}
          </div>
          <Button onClick={start} disabled={starting || running || !ext.connected || !blogRef}>
            {starting || running ? <Loader2 className="animate-spin" /> : <PlayCircle />}
            {running ? `발행 중 ${batch!.done}/${batch!.total}` : '이 블로그 발행 시작'}
          </Button>
        </div>

        {!ext.connected && (
          <p className="text-xs text-danger">확장 프로그램이 연결되어야 발행할 수 있어요. 위 안내대로 설치한 뒤 이 페이지를 새로고침하세요.</p>
        )}

        {running && (
          <p className="text-xs text-muted-foreground">
            확장이 한 건씩 순서대로 처리합니다. 중간에 멈추려면 확장 팝업에서 중단하거나 발행 탭을 닫으세요. 이미 넘어간 건은 결과가 올 때까지 &lsquo;배정됨&rsquo;으로 남습니다.
          </p>
        )}

        {log.length > 0 && (
          <div className="max-h-56 divide-y overflow-y-auto rounded-lg bg-muted/40 text-xs">
            {log.map((l, i) => (
              <div key={i} className="flex items-start gap-2 px-3 py-2">
                <span className="shrink-0 tabular-nums text-muted-foreground">{l.at}</span>
                <span className="flex-1 truncate">{l.title}</span>
                <Pill tone={l.ok ? 'ok' : l.uncertain ? 'warn' : 'crit'}>{l.ok ? '성공' : l.uncertain ? '확인 필요' : '실패'}</Pill>
                {l.message && !l.ok && <span className="max-w-[260px] truncate text-muted-foreground" title={l.message}>{l.message}</span>}
              </div>
            ))}
          </div>
        )}

        <p className="text-[11px] text-muted-foreground">
          3단계 로컬 발행 에이전트가 준비되면 이 화면에서 &lsquo;에이전트로 자동 발행&rsquo;으로 바뀝니다.
        </p>
      </div>
    </Card>
  )
}
