'use client'

import { useCallback, useEffect, useState } from 'react'
import { Building2, Loader2, Plus, Save, Sparkles, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { ClientForm } from '@/components/clients/client-form'
import { BlogAccounts } from '@/components/clients/blog-accounts'
import { Briefs } from '@/components/clients/briefs'
import { EMPTY_CLIENT, errorMessage } from '@/components/clients/utils'
import { campaignAPI, type Client, type ClientInput } from '@/lib/campaign-api'
import { mediaPoolAPI, type PoolCollectionItem } from '@/lib/api'
import { cn } from '@/lib/utils'

function toInput(c: Client): ClientInput {
  return {
    name: c.name,
    short_name: c.short_name ?? '',
    specialty: c.specialty ?? '',
    diseases: c.diseases || [],
    treatments: c.treatments || [],
    regions: c.regions || [],
    region_expand_level: c.region_expand_level ?? 1,
    suffixes: c.suffixes || [],
    min_volume_region: c.min_volume_region ?? 20,
    min_volume_national: c.min_volume_national ?? 100,
    forbidden_words: c.forbidden_words || [],
    tone: c.tone ?? '',
    facts: c.facts ?? '',
    default_collection_id: c.default_collection_id ?? null,
    sheet_url: c.sheet_url ?? '',
    sheet_blog_tab: c.sheet_blog_tab || '블로그',
    sheet_cafe_tab: c.sheet_cafe_tab || '카페',
  }
}

/** 빈 문자열은 null 로 보내 서버 기본값과 맞춘다. */
function toBody(f: ClientInput): ClientInput {
  const s = (v?: string | null) => (v && v.trim() ? v.trim() : null)
  return {
    ...f,
    name: f.name.trim(),
    short_name: s(f.short_name),
    specialty: s(f.specialty),
    tone: s(f.tone),
    facts: s(f.facts),
    sheet_url: s(f.sheet_url),
    sheet_blog_tab: s(f.sheet_blog_tab) || '블로그',
    sheet_cafe_tab: s(f.sheet_cafe_tab) || '카페',
  }
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [form, setForm] = useState<ClientInput>(EMPTY_CLIENT)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])

  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const selected = clients.find((c) => c.id === selectedId) || null

  const loadClients = useCallback(async () => {
    try {
      const list = await campaignAPI.listClients()
      setClients(list)
      return list
    } catch (e) {
      toast.error('병원 목록을 불러오지 못했습니다', { description: errorMessage(e) })
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadClients().then((list) => {
      if (list.length && !selectedId) setSelectedId(list[0].id)
    })
    mediaPoolAPI.listCollections().then((r) => setCollections(r.collections)).catch(() => { /* 세트 없이도 동작 */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadClients])

  // 선택이 바뀌면 폼을 서버 값으로 되돌린다
  useEffect(() => {
    if (selected) {
      setForm(toInput(selected))
      setDirty(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  /** 하위 목록(블로그/브리프) 변경 후 선택된 병원만 다시 읽는다. 폼 입력은 유지. */
  const refreshSelected = useCallback(async () => {
    if (!selectedId) return
    try {
      const c = await campaignAPI.getClient(selectedId)
      setClients((prev) => prev.map((p) => (p.id === c.id ? c : p)))
    } catch (e) {
      toast.error('병원 정보를 다시 불러오지 못했습니다', { description: errorMessage(e) })
    }
  }, [selectedId])

  const selectClient = (id: string) => {
    if (id === selectedId) return
    if (dirty && !confirm('저장하지 않은 변경이 있습니다. 이동할까요?')) return
    setSelectedId(id)
  }

  const onFormChange = (next: ClientInput) => { setForm(next); setDirty(true) }

  const save = async () => {
    if (!selected) return
    if (!form.name.trim()) { toast.error('병원 이름을 입력하세요'); return }
    setSaving(true)
    try {
      const updated = await campaignAPI.updateClient(selected.id, toBody(form))
      setClients((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      setForm(toInput(updated))
      setDirty(false)
      toast.success('병원 정보를 저장했습니다')
    } catch (e) {
      toast.error('저장 실패', { description: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  const create = async () => {
    const name = newName.trim()
    if (!name) { toast.error('병원 이름을 입력하세요'); return }
    setCreating(true)
    try {
      const c = await campaignAPI.createClient({ ...EMPTY_CLIENT, name, short_name: null, specialty: null, tone: null, facts: null, sheet_url: null })
      setClients((prev) => [...prev, c])
      setCreateOpen(false)
      setNewName('')
      setSelectedId(c.id)
      toast.success(`'${name}' 병원을 추가했습니다. 정보를 채우고 저장하세요.`)
    } catch (e) {
      toast.error('병원 추가 실패', { description: errorMessage(e) })
    } finally {
      setCreating(false)
    }
  }

  const seed = async () => {
    setSeeding(true)
    try {
      const created = await campaignAPI.seedExampleClients()
      const list = await loadClients()
      if (!selectedId && list.length) setSelectedId((created[0] || list[0]).id)
      toast.success(`예시 병원 ${created.length}곳을 넣었습니다`)
    } catch (e) {
      toast.error('예시 병원 추가 실패', { description: errorMessage(e) })
    } finally {
      setSeeding(false)
    }
  }

  const remove = async () => {
    if (!selected) return
    if (!confirm(`'${selected.name}' 병원을 삭제할까요? 블로그 계정·브리프·캠페인 정보도 함께 지워집니다.`)) return
    try {
      await campaignAPI.deleteClient(selected.id)
      const rest = clients.filter((c) => c.id !== selected.id)
      setClients(rest)
      setSelectedId(rest[0]?.id ?? null)
      setDirty(false)
      toast.success('병원을 삭제했습니다')
    } catch (e) {
      toast.error('삭제 실패', { description: errorMessage(e) })
    }
  }

  return (
    <div>
      <PageHeader
        title="병원 관리"
        description="병원 정보·블로그 계정·원고 브리프를 한곳에서 관리합니다. 캠페인은 여기 등록한 병원 단위로 진행됩니다."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus /> 병원 추가
          </Button>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 불러오는 중...
        </div>
      ) : clients.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-10 w-10" />}
          title="아직 등록된 병원이 없습니다"
          description="병원을 추가하거나, 예시 병원 5곳(로담 · 소잠 · 위례 · 다은 · 키네스)으로 먼저 흐름을 살펴보세요."
          action={
            <div className="flex justify-center gap-2">
              <Button onClick={() => setCreateOpen(true)}>
                <Plus /> 병원 추가
              </Button>
              <Button variant="outline" onClick={seed} disabled={seeding}>
                {seeding ? <Loader2 className="animate-spin" /> : <Sparkles />}
                예시 병원 5곳 넣기
              </Button>
            </div>
          }
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          {/* 왼쪽: 병원 목록 */}
          <aside className="space-y-2">
            <div className="surface divide-y overflow-hidden">
              {clients.map((c) => {
                const active = c.id === selectedId
                return (
                  <button
                    key={c.id}
                    onClick={() => selectClient(c.id)}
                    className={cn(
                      'w-full px-3 py-2.5 text-left text-sm transition-colors',
                      active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/40'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{c.name}</span>
                      {!c.active && <Pill tone="muted">비활성</Pill>}
                    </div>
                    <div className={cn('mt-0.5 truncate text-[11px]', active ? 'text-accent-foreground/80' : 'text-muted-foreground')}>
                      {[c.specialty, c.regions?.slice(0, 2).join('·')].filter(Boolean).join(' · ') || '정보 없음'}
                    </div>
                    <div className={cn('text-[11px] tabular-nums', active ? 'text-accent-foreground/80' : 'text-muted-foreground')}>
                      블로그 {c.blogs?.length ?? 0} · 브리프 {c.briefs?.length ?? 0}
                    </div>
                  </button>
                )
              })}
            </div>
            <Button variant="ghost" size="sm" className="w-full" onClick={seed} disabled={seeding}>
              {seeding ? <Loader2 className="animate-spin" /> : <Sparkles />}
              예시 병원 5곳 넣기
            </Button>
          </aside>

          {/* 오른쪽: 편집기 */}
          {selected ? (
            <section className="min-w-0 space-y-6">
              <div className="sticky top-16 z-20 -mx-1 border-b bg-background/95 px-1 py-2 backdrop-blur">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h2 className="section-title">{selected.name}</h2>
                    {dirty && <Pill tone="warn">저장 안 됨</Pill>}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={remove}>
                      <Trash2 /> 삭제
                    </Button>
                    <Button size="sm" onClick={save} disabled={saving || !dirty}>
                      {saving ? <Loader2 className="animate-spin" /> : <Save />}
                      저장
                    </Button>
                  </div>
                </div>
              </div>

              <ClientForm form={form} onChange={onFormChange} collections={collections} />
              <BlogAccounts clientId={selected.id} blogs={selected.blogs || []} onChanged={refreshSelected} />
              <Briefs clientId={selected.id} briefs={selected.briefs || []} onChanged={refreshSelected} />
            </section>
          ) : (
            <EmptyState title="왼쪽에서 병원을 선택하세요" />
          )}
        </div>
      )}

      {/* 병원 추가 다이얼로그 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>병원 추가</DialogTitle>
            <DialogDescription>이름만 먼저 넣고, 나머지 정보는 편집 화면에서 채웁니다.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="new-client-name">병원 이름</Label>
            <Input
              id="new-client-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') create() }}
              placeholder="예: 로담한의원"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>취소</Button>
            <Button onClick={create} disabled={creating}>
              {creating && <Loader2 className="animate-spin" />} 추가
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
