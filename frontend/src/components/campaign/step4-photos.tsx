'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @next/next/no-img-element */
import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { ImageIcon, Loader2, Tags, Wand2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { mediaPoolAPI, type PoolCollectionItem } from '@/lib/api'
import { campaignAPI, type Draft, type ImageSlot, type PhotoMeta, type Task } from '@/lib/campaign-api'
import { EmptyNote, Pill, StepFooter, TaskProgress, errMsg, fmt, taskOutcome, type StepProps } from './common'

const NONE = '__none__'

export function Step4Photos({ campaign, setCampaign, goStep }: StepProps) {
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])
  const [collectionId, setCollectionId] = useState<string>(campaign.collection_id || NONE)
  const [imageCount, setImageCount] = useState<string>(
    typeof campaign.settings?.image_count === 'number' ? String(campaign.settings.image_count) : '',
  )
  const [photos, setPhotos] = useState<PhotoMeta[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [loading, setLoading] = useState(true)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [chooser, setChooser] = useState<{ draft: Draft; slot: ImageSlot } | null>(null)

  const colId = collectionId === NONE ? null : collectionId

  const loadAll = useCallback(async () => {
    try {
      const [ds, ps] = await Promise.all([campaignAPI.listDrafts(campaign.id), campaignAPI.listPhotos(colId)])
      setDrafts(ds); setPhotos(ps)
    } catch (err: any) {
      toast.error('불러오기 실패', { description: errMsg(err) })
    } finally { setLoading(false) }
  }, [campaign.id, colId])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => {
    mediaPoolAPI.listCollections(false).then((r) => setCollections(r.collections || [])).catch(() => { /* noop */ })
    campaignAPI.listTasks({ campaign_id: campaign.id, active_only: true, limit: 5 })
      .then((ts) => { const t = ts.find((x) => x.type.includes('photo') || x.type.includes('image') || x.type.includes('tag')); if (t) setTaskId(t.id) })
      .catch(() => { /* noop */ })
  }, [campaign.id])

  const photoMap = useMemo(() => new Map(photos.map((p) => [p.id, p])), [photos])
  const untagged = photos.filter((p) => !p.tagged).length

  const changeCollection = async (v: string) => {
    setCollectionId(v)
    try { setCampaign(await campaignAPI.patchCampaign(campaign.id, { collection_id: v === NONE ? null : v })) }
    catch (err: any) { toast.error('저장 실패', { description: errMsg(err) }) }
  }

  const saveImageCount = async () => {
    const n = imageCount.trim() ? Number(imageCount) : null
    const cur = campaign.settings?.image_count ?? null
    if (n === cur) return
    try {
      setCampaign(await campaignAPI.patchCampaign(campaign.id, { settings: { ...(campaign.settings || {}), image_count: n } }))
    } catch (err: any) { toast.error('저장 실패', { description: errMsg(err) }) }
  }

  const startPlan = async () => {
    setStarting(true)
    try {
      const t = await campaignAPI.planPhotos(campaign.id, { collection_id: colId, image_count: imageCount.trim() ? Number(imageCount) : null })
      setTaskId(t.id)
    } catch (err: any) {
      toast.error('사진 배치 시작 실패', { description: errMsg(err) })
    } finally { setStarting(false) }
  }

  const startTag = async () => {
    try { const t = await campaignAPI.tagPhotos(colId); setTaskId(t.id) }
    catch (err: any) { toast.error('태그 달기 시작 실패', { description: errMsg(err) }) }
  }

  const onTaskDone = (t: Task) => {
    const o = taskOutcome(t)
    if (o.ok) toast.success(o.text); else toast.error(o.text)
    setTaskId(null)
    loadAll()
  }

  const chooseForSlot = async (photo: PhotoMeta) => {
    if (!chooser) return
    const { draft, slot } = chooser
    const slots = draft.image_plan.map((s) => ({
      slot: s.slot,
      after_paragraph: s.after_paragraph,
      pool_image_id: s.slot === slot.slot ? photo.id : (s.pool_image_id || undefined),
    }))
    try {
      const d = await campaignAPI.setImagePlan(draft.id, slots)
      setDrafts((prev) => prev.map((x) => (x.id === d.id ? { ...x, image_plan: d.image_plan } : x)))
      toast.success('사진을 바꿨어요')
    } catch (err: any) {
      toast.error('사진 바꾸기 실패', { description: errMsg(err) })
    } finally { setChooser(null) }
  }

  const planned = drafts.filter((d) => d.image_plan && d.image_plan.length > 0)
  const unplanned = drafts.filter((d) => (!d.image_plan || d.image_plan.length === 0) && d.status !== 'generating')
  const running = !!taskId

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-5">
        <div>
          <h3 className="section-title">사진 자동 배치</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">원고 문단마다 어울리는 사진을 골라 넣습니다. 사진에 태그가 없으면 먼저 태그를 달고 배치합니다.</p>
        </div>
        <div className="space-y-4">
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_160px_auto]">
            <div className="space-y-1.5">
              <Label>사진 세트</Label>
              <Select value={collectionId} onValueChange={changeCollection}>
                <SelectTrigger><SelectValue placeholder="사진 세트 선택" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>전체 사진 풀</SelectItem>
                  {collections.map((c) => <SelectItem key={c.id} value={c.id}>{c.name} · {fmt(c.count)}장</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>글당 사진 수</Label>
              <Input type="number" min={0} max={30} value={imageCount} onChange={(e) => setImageCount(e.target.value)} onBlur={saveImageCount} placeholder="자동(통검 권장)" />
            </div>
            <Button onClick={startPlan} disabled={running || starting || drafts.length === 0}>
              {starting ? <Loader2 className="animate-spin" /> : <Wand2 />} 사진 자동 배치
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>이 세트 사진 {fmt(photos.length)}장</span>
            {untagged > 0 && (
              <span className="inline-flex items-center gap-2 text-warning">
                태그 없는 사진 {fmt(untagged)}장 · 배치 시 자동으로 태그를 답니다
                <Button variant="outline" size="sm" className="h-6 px-2 text-[11px] [&_svg]:h-3 [&_svg]:w-3" onClick={startTag} disabled={running}><Tags /> 지금 태그 달기</Button>
              </span>
            )}
            {photos.length === 0 && <span>사진이 없어요. <Link href="/dashboard/media" className="text-primary underline">사진 풀</Link>에서 올려 주세요.</span>}
          </div>
          <TaskProgress taskId={taskId} onDone={onTaskDone} />
        </div>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...</div>
      ) : planned.length === 0 ? (
        <EmptyNote>{drafts.length === 0 ? '원고가 없습니다. 3단계에서 원고를 먼저 만드세요.' : '아직 배치된 사진이 없습니다. 위에서 사진 자동 배치를 눌러 주세요.'}</EmptyNote>
      ) : (
        <Card className="p-5">
          <div className="mb-2 text-sm tabular-nums text-muted-foreground">배치된 원고 {fmt(planned.length)}건{unplanned.length > 0 ? ` · 아직 배치 안 된 원고 ${fmt(unplanned.length)}건` : ''}. 사진을 누르면 바꿀 수 있어요.</div>
          <div className="divide-y">
          {planned.map((d) => (
            <div key={d.id} className="space-y-2 py-4">
              <div>
                <div className="truncate text-sm font-medium">{d.title}</div>
                <div className="text-xs tabular-nums text-muted-foreground">{d.keyword || ''} · 사진 {fmt(d.image_plan.filter((s) => s.pool_image_id).length)}/{fmt(d.image_plan.length)}</div>
              </div>
              <div>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {d.image_plan.map((s) => {
                    const p = s.pool_image_id ? photoMap.get(s.pool_image_id) : undefined
                    return (
                      <button
                        key={s.slot}
                        type="button"
                        onClick={() => setChooser({ draft: d, slot: s })}
                        className="w-32 shrink-0 overflow-hidden rounded-lg border text-left transition hover:ring-2 hover:ring-primary/50"
                        title={s.reason || ''}
                      >
                        <div className="aspect-[4/3] bg-muted flex items-center justify-center">
                          {p?.thumbnail ? <img src={p.thumbnail} alt="" className="h-full w-full object-cover" /> : <ImageIcon className="h-6 w-6 text-muted-foreground" />}
                        </div>
                        <div className="p-1.5 space-y-0.5">
                          <div className="flex items-center gap-1">
                            <span className="text-[10px] text-muted-foreground tabular-nums">#{s.slot + 1}</span>
                            {s.stage && <Pill tone="muted" className="text-[10px] px-1.5">{s.stage}</Pill>}
                          </div>
                          <div className="text-[10px] text-muted-foreground line-clamp-2">{s.reason || s.need || (p ? p.caption || p.scene || '' : '사진 없음')}</div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          ))}
          </div>
        </Card>
      )}

      <StepFooter onBack={() => goStep(3)} onNext={() => goStep(5)} nextLabel="다음: 예약" />

      <PhotoChooserDialog
        open={!!chooser}
        photos={photos}
        current={chooser?.slot.pool_image_id || null}
        title={chooser ? `${chooser.draft.title} · 사진 #${chooser.slot.slot + 1}` : ''}
        onClose={() => setChooser(null)}
        onPick={chooseForSlot}
      />
    </div>
  )
}

function PhotoChooserDialog({ open, photos, current, title, onClose, onPick }: {
  open: boolean; photos: PhotoMeta[]; current: string | null; title: string; onClose: () => void; onPick: (p: PhotoMeta) => void
}) {
  const [q, setQ] = useState('')
  useEffect(() => { if (open) setQ('') }, [open])
  const needle = q.trim().toLowerCase()
  const list = photos.filter((p) => !needle || [p.scene, p.caption, ...(p.tags || []), ...(p.suitable_for || [])].filter(Boolean).some((t) => String(t).toLowerCase().includes(needle)))
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>사진 고르기</DialogTitle>
          <DialogDescription className="truncate">{title}</DialogDescription>
        </DialogHeader>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="태그·설명으로 찾기 (예: 진료실, 상담)" />
        {list.length === 0 ? (
          <EmptyNote>맞는 사진이 없어요.</EmptyNote>
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
            {list.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onPick(p)}
                className={`overflow-hidden rounded-lg border text-left hover:ring-2 hover:ring-primary/50 ${current === p.id ? 'ring-2 ring-primary' : ''}`}
              >
                <div className="aspect-[4/3] bg-muted flex items-center justify-center">
                  {p.thumbnail ? <img src={p.thumbnail} alt="" className="h-full w-full object-cover" /> : <ImageIcon className="h-5 w-5 text-muted-foreground" />}
                </div>
                <div className="p-1.5 space-y-0.5">
                  <div className="text-[11px] font-medium truncate">{p.scene || p.caption || '(설명 없음)'}</div>
                  <div className="text-[10px] text-muted-foreground line-clamp-2">{(p.tags || []).slice(0, 6).join(' · ') || p.caption || ''}</div>
                  <div className="text-[10px] text-muted-foreground tabular-nums">사용 {p.use_count}회{p.tagged ? '' : ' · 태그 없음'}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
