'use client'

import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronDown, Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { ChipInput } from '@/components/clients/chip-input'
import { campaignAPI, type Brief, type BriefFlowStep, type BriefInput } from '@/lib/campaign-api'
import { errorMessage } from '@/components/clients/utils'

interface BriefsProps {
  clientId: string
  briefs: Brief[]
  onChanged: () => Promise<void> | void
}

type BuiltinBrief = { key: string; label: string; preset: BriefInput }

const EMPTY_BRIEF: BriefInput = {
  client_id: null,
  name: '',
  description: '',
  flow: [{ title: '도입', goal: '', min_chars: 300 }],
  rules: '',
  must_include: [],
  avoid: [],
  source_text: '',
  target_chars: 2000,
  heading_count: 4,
  keyword_count: 5,
  is_default: false,
}

function toInput(b: Brief): BriefInput {
  return {
    client_id: b.client_id ?? null,
    name: b.name,
    description: b.description ?? '',
    flow: (b.flow || []).map((s) => ({ title: s.title, goal: s.goal ?? '', min_chars: s.min_chars ?? 0 })),
    rules: b.rules ?? '',
    must_include: b.must_include || [],
    avoid: b.avoid || [],
    source_text: b.source_text ?? '',
    target_chars: b.target_chars,
    heading_count: b.heading_count,
    keyword_count: b.keyword_count,
    is_default: b.is_default,
  }
}

export function Briefs({ clientId, briefs, onChanged }: BriefsProps) {
  const [builtin, setBuiltin] = useState<BuiltinBrief[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Brief | null>(null)
  const [form, setForm] = useState<BriefInput>(EMPTY_BRIEF)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    campaignAPI.builtinBriefs().then(setBuiltin).catch(() => { /* 프리셋 없어도 화면은 동작 */ })
  }, [])

  const set = <K extends keyof BriefInput>(key: K, value: BriefInput[K]) => setForm((f) => ({ ...f, [key]: value }))
  const setStep = (i: number, patch: Partial<BriefFlowStep>) =>
    setForm((f) => ({ ...f, flow: f.flow.map((s, idx) => (idx === i ? { ...s, ...patch } : s)) }))
  const moveStep = (i: number, dir: -1 | 1) =>
    setForm((f) => {
      const j = i + dir
      if (j < 0 || j >= f.flow.length) return f
      const flow = [...f.flow]
      ;[flow[i], flow[j]] = [flow[j], flow[i]]
      return { ...f, flow }
    })
  const removeStep = (i: number) => setForm((f) => ({ ...f, flow: f.flow.filter((_, idx) => idx !== i) }))
  const addStep = () => setForm((f) => ({ ...f, flow: [...f.flow, { title: '', goal: '', min_chars: 300 }] }))

  const openNew = () => { setEditing(null); setForm({ ...EMPTY_BRIEF, client_id: clientId, is_default: briefs.length === 0 }); setOpen(true) }
  const openEdit = (b: Brief) => { setEditing(b); setForm(toInput(b)); setOpen(true) }

  const normalize = (f: BriefInput): BriefInput => ({
    ...f,
    client_id: clientId,
    name: f.name.trim(),
    description: f.description?.trim() || null,
    flow: f.flow
      .filter((s) => s.title.trim())
      .map((s) => ({ title: s.title.trim(), goal: s.goal?.trim() || undefined, min_chars: s.min_chars || undefined })),
    rules: f.rules?.trim() || null,
    source_text: f.source_text?.trim() || null,
  })

  const save = async () => {
    if (!form.name.trim()) { toast.error('브리프 이름을 입력하세요'); return }
    setSaving(true)
    try {
      const body = normalize(form)
      if (editing) {
        await campaignAPI.updateBrief(editing.id, body)
        toast.success('브리프를 저장했습니다')
      } else {
        await campaignAPI.createBrief(body)
        toast.success('브리프를 추가했습니다')
      }
      setOpen(false)
      await onChanged()
    } catch (e) {
      toast.error('저장 실패', { description: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  const addFromBuiltin = async (preset: BuiltinBrief) => {
    setAdding(true)
    try {
      const hasDefault = briefs.some((b) => b.is_default)
      await campaignAPI.createBrief({ ...preset.preset, client_id: clientId, is_default: !hasDefault })
      toast.success(`'${preset.label}' 프리셋을 추가했습니다`)
      await onChanged()
    } catch (e) {
      toast.error('프리셋 추가 실패', { description: errorMessage(e) })
    } finally {
      setAdding(false)
    }
  }

  const remove = async (b: Brief) => {
    if (!confirm(`'${b.name}' 브리프를 삭제할까요?`)) return
    setBusyId(b.id)
    try {
      await campaignAPI.deleteBrief(b.id)
      toast.success('브리프를 삭제했습니다')
      await onChanged()
    } catch (e) {
      toast.error('삭제 실패', { description: errorMessage(e) })
    } finally {
      setBusyId(null)
    }
  }

  const presetMenu = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline" disabled={adding || builtin.length === 0}>
          {adding ? <Loader2 className="animate-spin" /> : null}
          내장 프리셋에서 추가 <ChevronDown />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {builtin.map((p) => (
          <DropdownMenuItem key={p.key} className="cursor-pointer" onClick={() => addFromBuiltin(p)}>
            {p.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>원고 브리프</CardTitle>
            <CardDescription>원고의 흐름·규칙·길이를 정하는 틀입니다. 캠페인마다 브리프를 골라 원고를 생성합니다.</CardDescription>
          </div>
          <div className="flex gap-2">
            {presetMenu}
            <Button size="sm" variant="outline" onClick={openNew}>
              <Plus /> 직접 만들기
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {briefs.length === 0 ? (
          <EmptyState
            title="아직 브리프가 없습니다"
            description="내장 프리셋을 추가하면 바로 원고를 만들 수 있습니다."
            action={presetMenu}
            className="py-8"
          />
        ) : (
          <div className="divide-y">
            {briefs.map((b) => (
              <div key={b.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{b.name}</span>
                    {b.is_default && <Pill tone="accent">기본</Pill>}
                  </div>
                  {b.description && <p className="line-clamp-2 text-xs text-muted-foreground">{b.description}</p>}
                  <div className="flex flex-wrap gap-1.5">
                    <Pill tone="muted">흐름 {b.flow?.length ?? 0}단계</Pill>
                    <Pill tone="muted">{b.target_chars.toLocaleString()}자</Pill>
                    <Pill tone="muted">소제목 {b.heading_count}</Pill>
                    <Pill tone="muted">키워드 {b.keyword_count}회</Pill>
                    {b.source_text && <Pill tone="muted">원본 원고 있음</Pill>}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(b)}>
                    <Pencil /> 편집
                  </Button>
                  <Button variant="ghost" size="sm" className="text-danger hover:text-danger" disabled={busyId === b.id} onClick={() => remove(b)}>
                    {busyId === b.id ? <Loader2 className="animate-spin" /> : <Trash2 />} 삭제
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? '브리프 편집' : '새 브리프'}</DialogTitle>
            <DialogDescription>원고 생성 시 이 흐름과 규칙을 따릅니다.</DialogDescription>
          </DialogHeader>
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="br-name">이름 *</Label>
                <Input id="br-name" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="예: 증상 설명형" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="br-desc">설명</Label>
                <Input id="br-desc" value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} placeholder="언제 쓰는 브리프인지 한 줄" />
              </div>
            </div>

            {/* 흐름 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>글 흐름 (단계)</Label>
                <Button type="button" variant="outline" size="sm" onClick={addStep}>
                  <Plus /> 단계 추가
                </Button>
              </div>
              {form.flow.length === 0 && (
                <p className="text-xs text-muted-foreground">단계가 없으면 AI가 흐름을 자유롭게 정합니다.</p>
              )}
              <div className="divide-y rounded-lg border">
                {form.flow.map((s, i) => (
                  <div key={i} className="space-y-2 p-2">
                    <div className="flex items-center gap-2">
                      <span className="w-5 text-center text-xs tabular-nums text-muted-foreground">{i + 1}</span>
                      <Input className="h-8 flex-1" value={s.title} onChange={(e) => setStep(i, { title: e.target.value })} placeholder="단계 제목 (예: 증상 소개)" />
                      <Input
                        className="h-8 w-24 tabular-nums"
                        type="number"
                        min={0}
                        step={50}
                        value={s.min_chars ?? 0}
                        onChange={(e) => setStep(i, { min_chars: Math.max(0, Number(e.target.value) || 0) })}
                        title="최소 글자 수"
                      />
                      <span className="text-xs text-muted-foreground">자↑</span>
                      <Button type="button" variant="ghost" size="sm" className="w-8 px-0" disabled={i === 0} onClick={() => moveStep(i, -1)} title="위로">
                        <ArrowUp />
                      </Button>
                      <Button type="button" variant="ghost" size="sm" className="w-8 px-0" disabled={i === form.flow.length - 1} onClick={() => moveStep(i, 1)} title="아래로">
                        <ArrowDown />
                      </Button>
                      <Button type="button" variant="ghost" size="sm" className="w-8 px-0 text-danger hover:text-danger" onClick={() => removeStep(i)} title="삭제">
                        <Trash2 />
                      </Button>
                    </div>
                    <Input className="ml-7 h-8" value={s.goal ?? ''} onChange={(e) => setStep(i, { goal: e.target.value })} placeholder="이 단계에서 다룰 내용 · 목표" />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="br-rules">작성 규칙</Label>
              <Textarea id="br-rules" rows={4} value={form.rules ?? ''} onChange={(e) => set('rules', e.target.value)} placeholder="예: 첫 문단에 키워드 자연스럽게 포함. 치료 효과 단정 금지. 마지막에 상담 안내." />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>꼭 넣을 표현</Label>
                <ChipInput value={form.must_include} onChange={(v) => set('must_include', v)} placeholder="Enter 또는 쉼표로 추가" />
              </div>
              <div className="space-y-1">
                <Label>피할 표현</Label>
                <ChipInput value={form.avoid} onChange={(v) => set('avoid', v)} placeholder="Enter 또는 쉼표로 추가" />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="br-src">원본 원고</Label>
              <Textarea id="br-src" rows={6} value={form.source_text ?? ''} onChange={(e) => set('source_text', e.target.value)} placeholder="참고할 원고 전문을 붙여넣으세요" />
              <p className="text-xs text-muted-foreground">원본 원고: 여기 적힌 사실만 사용합니다.</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="br-chars">목표 글자 수</Label>
                <Input id="br-chars" type="number" min={300} step={100} value={form.target_chars} onChange={(e) => set('target_chars', Math.max(0, Number(e.target.value) || 0))} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="br-head">소제목 수</Label>
                <Input id="br-head" type="number" min={0} value={form.heading_count} onChange={(e) => set('heading_count', Math.max(0, Number(e.target.value) || 0))} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="br-kw">키워드 반복 횟수</Label>
                <Input id="br-kw" type="number" min={0} value={form.keyword_count} onChange={(e) => set('keyword_count', Math.max(0, Number(e.target.value) || 0))} />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label htmlFor="br-default">기본 브리프</Label>
                <p className="text-xs text-muted-foreground">새 캠페인에서 별도 선택이 없으면 이 브리프를 씁니다.</p>
              </div>
              <Switch id="br-default" checked={form.is_default} onCheckedChange={(v) => set('is_default', v)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>취소</Button>
            <Button onClick={save} disabled={saving}>
              {saving && <Loader2 className="animate-spin" />}
              {editing ? '저장' : '추가'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
