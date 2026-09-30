'use client'

// 카페 질문글 세트 — 질문글 1개 + 댓글 N개를 만들고, 고치고, 복사한다.
//
// 1단계(2026-09-30 결정)는 원고까지다. 카페에 올리는 것은 사람이 한다.
// 그래서 이 화면의 목표는 하나다: **고치고 복사하기 쉬울 것.**
// 검수는 고칠 때마다 서버가 다시 돌려 준다 — 고친 뒤에도 '통과'라고 적혀 있으면 거짓말이다.

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Check, Copy, Loader2, Sparkles, Trash2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { campaignAPI, type CafeThread, type Client } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'

export function CafeThreadPanel({ clients }: { clients: Client[] }) {
  const [clientId, setClientId] = useState('')
  const [topic, setTopic] = useState('')
  const [cafeName, setCafeName] = useState('')
  const [commentCount, setCommentCount] = useState(6)
  const [promoIndex, setPromoIndex] = useState(2)
  const [threads, setThreads] = useState<CafeThread[]>([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => { if (!clientId && clients.length) setClientId(clients[0].id) }, [clients, clientId])

  const load = useCallback(async () => {
    if (!clientId) { setLoading(false); return }
    try { setThreads(await campaignAPI.cafeThreads(clientId)) }
    catch (e) { toast.error('불러오기 실패', { description: errMsg(e) }) }
    finally { setLoading(false) }
  }, [clientId])
  useEffect(() => { void load() }, [load])

  const generate = async () => {
    if (!clientId || topic.trim().length < 2) { toast.error('병원과 고민 주제를 넣어 주세요'); return }
    setBusy(true)
    try {
      const made = await campaignAPI.generateCafeThread({
        client_id: clientId, topic: topic.trim(), cafe_name: cafeName.trim() || undefined,
        comment_count: commentCount, promo_index: promoIndex,
      })
      setThreads((prev) => [made, ...prev])
      setTopic('')
      toast.success(made.checks?.ok ? '만들었습니다 — 검수 통과' : '만들었습니다 — 고칠 곳이 있습니다')
    } catch (e) { toast.error('만들지 못했습니다', { description: errMsg(e) }) }
    finally { setBusy(false) }
  }

  const clinic = clients.find((c) => c.id === clientId)
  const clinicName = (clinic?.brand_keyword || clinic?.short_name || clinic?.name || '').trim()

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-5">
        <div>
          <h3 className="section-title">카페 질문글 세트 만들기</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            질문글 1개와 댓글 {commentCount}개를 한 번에 만듭니다.
            병원 이름은 <b>{promoIndex}번 댓글에서만</b> 말합니다 — 나머지 댓글에 이름이 새어 나가면
            검수에서 걸립니다. 링크·전화번호·가격은 어느 댓글에도 넣지 않습니다.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="ct-client">병원</Label>
            <select id="ct-client" className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              value={clientId} onChange={(e) => setClientId(e.target.value)} disabled={busy}>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {clinicName
              ? <p className="text-xs text-muted-foreground">댓글에 들어갈 이름: <b>{clinicName}</b></p>
              : <p className="text-xs text-warning">병원 키워드나 약칭을 병원 관리에서 정해 주세요.</p>}
          </div>
          <div className="space-y-1">
            <Label htmlFor="ct-cafe">카페 (참고용)</Label>
            <Input id="ct-cafe" value={cafeName} disabled={busy}
              placeholder="예: 송파맘 카페" onChange={(e) => setCafeName(e.target.value)} />
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="ct-topic">고민 주제</Label>
          <Input id="ct-topic" value={topic} disabled={busy}
            placeholder="예: 두 달째 두피 각질과 가려움"
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void generate() } }} />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="ct-count">댓글 개수</Label>
            <Input id="ct-count" type="number" min={3} max={12} value={commentCount} disabled={busy}
              onChange={(e) => setCommentCount(Number(e.target.value) || 6)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ct-promo">병원을 말할 댓글 번호</Label>
            <Input id="ct-promo" type="number" min={1} max={commentCount} value={promoIndex} disabled={busy}
              onChange={(e) => setPromoIndex(Number(e.target.value) || 2)} />
          </div>
        </div>

        <Button className="h-11 w-full" onClick={() => void generate()} disabled={busy || !clientId}>
          {busy ? <><Loader2 className="animate-spin" /> 만드는 중…</> : <><Sparkles /> 질문글 + 댓글 {commentCount}개 만들기</>}
        </Button>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
        </div>
      ) : threads.map((t) => (
        <ThreadCard key={t.id} thread={t}
          onChanged={(next) => setThreads((prev) => prev.map((x) => (x.id === next.id ? next : x)))}
          onRemoved={() => setThreads((prev) => prev.filter((x) => x.id !== t.id))} />
      ))}
    </div>
  )
}

function ThreadCard({ thread, onChanged, onRemoved }: {
  thread: CafeThread
  onChanged: (next: CafeThread) => void
  onRemoved: () => void
}) {
  const [draft, setDraft] = useState(thread)
  const [saving, setSaving] = useState(false)
  useEffect(() => { setDraft(thread) }, [thread])

  const dirty = JSON.stringify(draft) !== JSON.stringify(thread)
  const issues = thread.checks?.issues || []

  const save = async (approved?: boolean) => {
    setSaving(true)
    try {
      const next = await campaignAPI.updateCafeThread(thread.id, {
        title: draft.title, body: draft.body, comments: draft.comments,
        ...(approved === undefined ? {} : { approved }),
      })
      onChanged(next)
      toast.success(next.checks?.ok ? '저장했습니다 — 검수 통과' : '저장했습니다 — 고칠 곳이 남아 있습니다')
    } catch (e) { toast.error('저장 실패', { description: errMsg(e) }) }
    finally { setSaving(false) }
  }

  const copyAll = async () => {
    // 카페에 올릴 때 쓰는 모양 그대로 — 제목, 본문, 댓글 순서.
    const text = [
      `[제목] ${draft.title}`, '', draft.body, '',
      ...draft.comments.map((c) => `[댓글 ${c.seq}${c.seq === draft.promo_index ? ' · 병원 언급' : ''}] ${c.body}`),
    ].join('\n')
    try { await navigator.clipboard.writeText(text); toast.success('전체를 복사했습니다') }
    catch { toast.error('복사하지 못했습니다') }
  }

  const setComment = (seq: number, body: string) =>
    setDraft({ ...draft, comments: draft.comments.map((c) => (c.seq === seq ? { ...c, body } : c)) })

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted-foreground">{thread.topic}{thread.cafe_name ? ` · ${thread.cafe_name}` : ''}</p>
          <Input className="mt-1 font-medium" value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        </div>
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => void copyAll()}><Copy /> 전체 복사</Button>
          <Button variant="ghost" size="sm" onClick={async () => {
            if (!confirm('이 세트를 지울까요?')) return
            try { await campaignAPI.deleteCafeThread(thread.id); onRemoved() }
            catch (e) { toast.error('삭제 실패', { description: errMsg(e) }) }
          }}><Trash2 /></Button>
        </div>
      </div>

      {issues.length > 0 ? (
        <div className="rounded-lg bg-warning-soft p-3 text-sm">
          <p className="flex items-center gap-1.5 font-medium"><AlertTriangle className="h-4 w-4" /> 고칠 곳 {issues.length}가지</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px]">
            {issues.map((i) => <li key={i}>{i}</li>)}
          </ul>
        </div>
      ) : (
        <p className="flex items-center gap-1.5 rounded-lg bg-muted/40 p-3 text-sm">
          <Check className="h-4 w-4" /> 검수 통과 — 병원 이름은 {thread.promo_index}번 댓글에만 있습니다.
        </p>
      )}

      <div className="space-y-1">
        <Label>질문글 본문</Label>
        <Textarea rows={6} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
      </div>

      <div className="space-y-2">
        <Label>댓글 {draft.comments.length}개</Label>
        {draft.comments.map((c) => (
          <div key={c.seq} className={`rounded-lg border p-2 ${c.seq === draft.promo_index ? 'border-primary/50 bg-primary/5' : ''}`}>
            <p className="mb-1 text-xs text-muted-foreground">
              댓글 {c.seq}{c.seq === draft.promo_index ? ' · 여기서만 병원 이름' : ''}
              {c.persona ? ` · ${c.persona}` : ''}
            </p>
            <Textarea rows={2} value={c.body} onChange={(e) => setComment(c.seq, e.target.value)} />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void save()} disabled={saving || !dirty}>
          {saving ? <Loader2 className="animate-spin" /> : null} 저장하고 다시 검수
        </Button>
        {thread.checks?.ok && !thread.approved && !dirty && (
          <Button variant="outline" onClick={() => void save(true)} disabled={saving}><Check /> 쓸 수 있음으로 표시</Button>
        )}
        {thread.approved && <span className="self-center text-sm text-muted-foreground">✓ 쓸 수 있음</span>}
      </div>
    </Card>
  )
}
