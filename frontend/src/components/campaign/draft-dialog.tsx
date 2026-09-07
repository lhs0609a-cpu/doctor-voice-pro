'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { CheckCircle2, Loader2, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { campaignAPI, type Draft } from '@/lib/campaign-api'
import { Pill, errMsg, fmt, type Tone } from './common'

// ───────────────────────── 검수 결과 요약 ─────────────────────────
export interface CheckChip { label: string; tone: Tone }

function asArray(v: unknown): any[] { return Array.isArray(v) ? v : [] }

export function summarizeChecks(checks: Record<string, unknown> | null | undefined): CheckChip[] {
  if (!checks) return []
  const chips: CheckChip[] = []
  const law = asArray(checks.medical_law)
  if (law.length) chips.push({ label: `의료광고법 ${law.length}건`, tone: 'crit' })
  const forb = asArray(checks.forbidden)
  if (forb.length) chips.push({ label: `금칙어 ${forb.length}`, tone: 'crit' })
  const flow = checks.flow as any
  if (flow && typeof flow === 'object' && flow.ok === false) chips.push({ label: '흐름 이상', tone: 'warn' })
  const facts = checks.facts as any
  if (facts && typeof facts === 'object' && facts.ok === false) chips.push({ label: '사실 불일치', tone: 'warn' })
  const sim = checks.similarity_to_source
  if (typeof sim === 'number' && sim > 0.35) chips.push({ label: `유사도 높음 ${Math.round(sim * 100)}%`, tone: 'warn' })
  return chips
}

function itemText(v: any): { text: string; suggestion?: string; reason?: string } {
  if (typeof v === 'string') return { text: v }
  if (v && typeof v === 'object') {
    return {
      text: v.text || v.phrase || v.word || v.sentence || v.message || JSON.stringify(v),
      suggestion: v.suggestion || v.replacement || v.fix,
      reason: v.reason || v.rule || v.law,
    }
  }
  return { text: String(v) }
}

function CheckSection({ title, items, tone }: { title: string; items: any[]; tone: Tone }) {
  if (!items.length) return null
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 text-sm font-medium"><Pill tone={tone}>{title} {items.length}건</Pill></div>
      <ul className="space-y-1 text-xs">
        {items.map((it, i) => {
          const t = itemText(it)
          return (
            <li key={i} className="rounded-lg bg-muted/60 p-2">
              <div className="font-medium">&ldquo;{t.text}&rdquo;</div>
              {t.reason && <div className="text-muted-foreground">{t.reason}</div>}
              {t.suggestion && <div className="text-success">제안: {t.suggestion}</div>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function ChecksDetail({ checks }: { checks: Record<string, unknown> | null | undefined }) {
  if (!checks || Object.keys(checks).length === 0) return <p className="text-xs text-muted-foreground">검수 결과가 아직 없습니다.</p>
  const flow = checks.flow as any
  const facts = checks.facts as any
  const sim = checks.similarity_to_source
  const chips = summarizeChecks(checks)
  return (
    <div className="space-y-3">
      {chips.length === 0 && <div className="inline-flex items-center gap-1 text-sm text-success"><CheckCircle2 className="h-4 w-4" /> 특별한 문제가 없습니다.</div>}
      <CheckSection title="의료광고법" items={asArray(checks.medical_law)} tone="crit" />
      <CheckSection title="금칙어" items={asArray(checks.forbidden)} tone="crit" />
      {flow && typeof flow === 'object' && flow.ok === false && (
        <div className="rounded-lg bg-warning-soft p-2 text-xs text-warning">
          <b>흐름 이상</b>{flow.reason || flow.message ? ` — ${flow.reason || flow.message}` : ''}
          {asArray(flow.issues).length > 0 && (
            <ul className="list-disc pl-4 mt-1">{asArray(flow.issues).map((x, i) => <li key={i}>{itemText(x).text}</li>)}</ul>
          )}
        </div>
      )}
      {facts && typeof facts === 'object' && facts.ok === false && (
        <div className="rounded-lg bg-warning-soft p-2 text-xs text-warning">
          <b>사실 불일치</b>{facts.reason || facts.message ? ` — ${facts.reason || facts.message}` : ''}
          {asArray(facts.issues).length > 0 && (
            <ul className="list-disc pl-4 mt-1">{asArray(facts.issues).map((x, i) => <li key={i}>{itemText(x).text}</li>)}</ul>
          )}
        </div>
      )}
      {typeof sim === 'number' && (
        <div className={`text-xs ${sim > 0.35 ? 'text-warning' : 'text-muted-foreground'}`}>
          원본과의 유사도 {Math.round(sim * 100)}% {sim > 0.35 ? '· 너무 비슷하면 검색 노출에 불리해요' : ''}
        </div>
      )}
    </div>
  )
}

// ───────────────────────── 원고 열기 다이얼로그 ─────────────────────────
export function DraftDialog({ draft, onClose, onSaved }: { draft: Draft | null; onClose: () => void; onSaved: (d: Draft) => void }) {
  const [full, setFull] = useState<Draft | null>(null)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const draftId = draft?.id || null

  useEffect(() => {
    if (!draftId) { setFull(null); return }
    let alive = true
    setLoading(true)
    campaignAPI.getDraft(draftId)
      .then((d) => { if (alive) { setFull(d); setTitle(d.title); setBody(d.body || '') } })
      .catch((err) => { if (alive) { toast.error('원고 불러오기 실패', { description: errMsg(err) }); onCloseRef.current() } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [draftId])

  const save = async (status?: string) => {
    if (!full) return
    setSaving(true)
    try {
      const d = await campaignAPI.updateDraft(full.id, { title, body, ...(status ? { status } : {}) })
      setFull(d)
      onSaved(d)
      toast.success(status === 'ready' ? '검수 통과로 표시했어요' : '저장했어요')
      if (status) onClose()
    } catch (err: any) {
      toast.error('저장 실패', { description: errMsg(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={!!draft} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>원고 열기</DialogTitle>
          <DialogDescription>
            {full?.keyword ? `키워드: ${full.keyword} · ` : ''}{fmt(body.length)}자
            {full?.status === 'ready' ? ' · 검수 통과' : full?.status === 'needs_review' ? ' · 확인 필요' : ''}
          </DialogDescription>
        </DialogHeader>
        {loading || !full ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...</div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>제목</Label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>본문</Label>
                <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={22} className="font-mono text-[13px] leading-relaxed" />
              </div>
              {full.error && <div className="rounded-lg bg-danger-soft p-2 text-xs text-danger">{full.error}</div>}
            </div>
            <div className="space-y-3">
              <div className="section-title">검수 결과</div>
              <ChecksDetail checks={full.checks} />
              {full.tags?.length > 0 && (
                <div>
                  <div className="mb-1 text-[13px] font-medium text-muted-foreground">태그</div>
                  <div className="flex flex-wrap gap-1">{full.tags.map((t) => <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-xs">#{t}</span>)}</div>
                </div>
              )}
            </div>
          </div>
        )}
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={onClose}>닫기</Button>
          <Button variant="outline" onClick={() => save()} disabled={saving || !full}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />} 저장
          </Button>
          <Button onClick={() => save('ready')} disabled={saving || !full}>
            <CheckCircle2 /> 검수 통과로 표시
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
