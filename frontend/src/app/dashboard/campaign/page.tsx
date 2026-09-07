'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Building2, Loader2, Plus, Trash2, ArrowRight, Sparkles, Rocket } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { PageHeader, SectionHeader } from '@/components/app-shell/page-header'
import { EmptyState } from '@/components/app-shell/ui-kit'
import { campaignAPI, type Campaign, type Client } from '@/lib/campaign-api'
import { CAMPAIGN_STATUS_LABEL, Pill, errMsg, fmt, fmtDateTime } from '@/components/campaign/common'

export default function CampaignListPage() {
  const router = useRouter()
  const [clients, setClients] = useState<Client[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [seeding, setSeeding] = useState(false)

  const [newOpen, setNewOpen] = useState(false)
  const [newClientId, setNewClientId] = useState('')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cs, cps] = await Promise.all([campaignAPI.listClients(), campaignAPI.listCampaigns()])
      setClients(cs)
      setCampaigns(cps)
      if (!newClientId && cs.length) setNewClientId(cs[0].id)
    } catch (err: any) {
      toast.error('불러오기 실패', { description: errMsg(err) })
    } finally {
      setLoading(false)
    }
  }, [newClientId])

  useEffect(() => { load() }, [load])

  const grouped = useMemo(() => {
    const byClient = new Map<string, Campaign[]>()
    for (const c of campaigns) {
      const arr = byClient.get(c.client_id) || []
      arr.push(c)
      byClient.set(c.client_id, arr)
    }
    const order = [...clients.map((c) => c.id), ...Array.from(byClient.keys()).filter((id) => !clients.some((c) => c.id === id))]
    return order
      .filter((id) => byClient.has(id))
      .map((id) => ({
        clientId: id,
        clientName: clients.find((c) => c.id === id)?.name || byClient.get(id)![0].client_name || '(병원 없음)',
        items: byClient.get(id)!.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')),
      }))
  }, [campaigns, clients])

  const create = async () => {
    if (!newClientId) { toast.error('병원을 선택하세요'); return }
    setCreating(true)
    try {
      const c = await campaignAPI.createCampaign(newClientId, newName.trim() || undefined)
      toast.success('캠페인을 만들었어요')
      setNewOpen(false)
      router.push(`/dashboard/campaign/${c.id}`)
    } catch (err: any) {
      toast.error('만들기 실패', { description: errMsg(err) })
    } finally {
      setCreating(false)
    }
  }

  const remove = async () => {
    if (!deleteTarget) return
    try {
      await campaignAPI.deleteCampaign(deleteTarget.id)
      setCampaigns((prev) => prev.filter((c) => c.id !== deleteTarget.id))
      toast.success('삭제했어요')
    } catch (err: any) {
      toast.error('삭제 실패', { description: errMsg(err) })
    } finally {
      setDeleteTarget(null)
    }
  }

  const seed = async () => {
    setSeeding(true)
    try {
      await campaignAPI.seedExampleClients()
      toast.success('예시 병원을 넣었어요')
      await load()
    } catch (err: any) {
      toast.error('예시 병원 만들기 실패', { description: errMsg(err) })
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="캠페인"
        description="병원 하나를 골라 키워드 → 원고 → 사진 → 예약 → 발행까지 6단계로 진행합니다. 진행 상황은 자동 저장됩니다."
        actions={
          <Button onClick={() => setNewOpen(true)} disabled={clients.length === 0}>
            <Plus /> 새 캠페인
          </Button>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...
        </div>
      ) : clients.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-8 w-8" />}
          title="먼저 병원을 등록하세요"
          description="캠페인은 병원 단위로 진행됩니다. 진료 질환·지역·블로그 계정을 먼저 넣어 주세요."
          action={
            <div className="flex items-center justify-center gap-2">
              <Button asChild>
                <Link href="/dashboard/clients">병원 등록하기 <ArrowRight /></Link>
              </Button>
              <Button variant="outline" onClick={seed} disabled={seeding}>
                {seeding ? <Loader2 className="animate-spin" /> : <Sparkles />}
                예시 병원으로 시작
              </Button>
            </div>
          }
        />
      ) : campaigns.length === 0 ? (
        <EmptyState
          icon={<Rocket className="h-8 w-8" />}
          title="아직 캠페인이 없어요"
          description="새 캠페인을 만들면 키워드부터 발행까지 단계별로 안내합니다."
          action={<Button onClick={() => setNewOpen(true)}><Plus /> 새 캠페인</Button>}
        />
      ) : (
        <div className="space-y-8">
          {grouped.map((g) => (
            <section key={g.clientId}>
              <SectionHeader
                title={<span className="inline-flex items-center gap-2"><Building2 className="h-4 w-4 text-muted-foreground" />{g.clientName}</span>}
                description={`캠페인 ${fmt(g.items.length)}개`}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                {g.items.map((c) => (
                  <CampaignCard key={c.id} c={c} onDelete={() => setDeleteTarget(c)} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* 새 캠페인 */}
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>새 캠페인</DialogTitle>
            <DialogDescription>어느 병원의 캠페인인가요? 이름은 비워두면 자동으로 붙습니다.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>병원</Label>
              <Select value={newClientId} onValueChange={setNewClientId}>
                <SelectTrigger><SelectValue placeholder="병원 선택" /></SelectTrigger>
                <SelectContent>
                  {clients.map((cl) => (
                    <SelectItem key={cl.id} value={cl.id}>{cl.name}{cl.blogs?.length ? ` · 블로그 ${cl.blogs.length}개` : ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>캠페인 이름 (선택)</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="예: 9월 무릎통증 시리즈" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewOpen(false)}>닫기</Button>
            <Button onClick={create} disabled={creating || !newClientId}>
              {creating && <Loader2 className="animate-spin" />} 만들고 시작
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 삭제 확인 */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>캠페인을 삭제할까요?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{deleteTarget?.name}&rdquo;의 키워드·원고·예약이 모두 지워집니다. 되돌릴 수 없습니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={remove} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">삭제</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function CampaignCard({ c, onDelete }: { c: Campaign; onDelete: () => void }) {
  const st = CAMPAIGN_STATUS_LABEL[c.status] || { label: c.status, tone: 'muted' as const }
  const s = c.stats || {}
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold">{c.name}</h3>
          <p className="truncate text-[13px] text-muted-foreground">{c.client_name || ''}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Pill tone={st.tone}>{st.label}</Pill>
          <Pill tone="info">{c.step}/6 단계</Pill>
        </div>
      </div>
      <p className="text-xs tabular-nums text-muted-foreground">
        키워드 {fmt(s.keywords)} · 원고 {fmt(s.drafts)} · 예약 {fmt(s.queued ?? s.jobs)} · 발행 {fmt(s.published)} · 실패 {fmt(s.failed)}
      </p>
      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="text-[11px] tabular-nums text-muted-foreground">수정 {fmtDateTime(c.updated_at)}</span>
        <div className="flex items-center gap-1.5">
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-danger" onClick={onDelete} title="삭제">
            <Trash2 />
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/dashboard/campaign/${c.id}`}>이어서 <ArrowRight /></Link>
          </Button>
        </div>
      </div>
    </Card>
  )
}
