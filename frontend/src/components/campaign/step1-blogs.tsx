'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { ExternalLink, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { EmptyState } from '@/components/app-shell/ui-kit'
import { mediaPoolAPI, type PoolCollectionItem } from '@/lib/api'
import { BLOG_STATUS_LABEL, campaignAPI, type Brief } from '@/lib/campaign-api'
import { Pill, StepFooter, errMsg, type StepProps, type Tone } from './common'

const NONE = '__none__'

const BLOG_TONE: Record<string, Tone> = { active: 'ok', paused: 'muted', captcha: 'warn', login_required: 'warn', disabled: 'crit' }

export function Step1Blogs({ campaign, client, setCampaign, goStep }: StepProps) {
  const [briefs, setBriefs] = useState<Brief[]>(client.briefs || [])
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    campaignAPI.listBriefs(client.id)
      .then((list) => {
        const merged = new Map<string, Brief>()
        ;[...(client.briefs || []), ...list].forEach((b) => merged.set(b.id, b))
        setBriefs(Array.from(merged.values()))
      })
      .catch(() => { /* client.briefs 로 대체 */ })
    mediaPoolAPI.listCollections(false)
      .then((r) => setCollections(r.collections || []))
      .catch(() => { /* noop */ })
  }, [client.id, client.briefs])

  const patch = async (key: string, body: Parameters<typeof campaignAPI.patchCampaign>[1]) => {
    setSaving(key)
    try {
      setCampaign(await campaignAPI.patchCampaign(campaign.id, body))
    } catch (err: any) {
      toast.error('저장 실패', { description: errMsg(err) })
    } finally {
      setSaving(null)
    }
  }

  const toggleBlog = (id: string, on: boolean) => {
    const cur = new Set(campaign.blog_ids || [])
    if (on) cur.add(id); else cur.delete(id)
    patch('blogs', { blog_ids: Array.from(cur) })
  }

  const activeSelected = useMemo(
    () => (client.blogs || []).filter((b) => b.status === 'active' && campaign.blog_ids?.includes(b.id)).length,
    [client.blogs, campaign.blog_ids],
  )

  return (
    <div className="space-y-6">
      {/* 병원 요약 */}
      <Card className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="section-title">{client.name}</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">{client.specialty || '진료과 미입력'}{client.short_name ? ` · ${client.short_name}` : ''}</p>
          </div>
          <Link href="/dashboard/clients" className="inline-flex shrink-0 items-center gap-1 text-xs text-primary hover:underline">
            병원 설정 바꾸기 <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
        <div className="grid gap-4 text-sm sm:grid-cols-3">
          <SummaryRow label="진료 질환" items={client.diseases} />
          <SummaryRow label="지역" items={client.regions} />
          <SummaryRow label="치료·시술" items={client.treatments} />
        </div>
      </Card>

      {/* 블로그 선택 */}
      <Card className="space-y-4 p-5">
        <div>
          <h3 className="section-title">발행할 블로그</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">이 캠페인의 글을 올릴 블로그를 고르세요. 정상 상태인 블로그만 선택할 수 있습니다.</p>
        </div>
        {(client.blogs || []).length === 0 ? (
          <EmptyState
            title="등록된 블로그가 없어요"
            description="병원 설정에서 네이버 블로그 계정을 먼저 추가하세요."
            action={<Button asChild variant="outline" size="sm"><Link href="/dashboard/clients">병원 설정 열기</Link></Button>}
            className="py-8"
          />
        ) : (
          <div className="divide-y">
            {client.blogs.map((b) => {
              const ok = b.status === 'active'
              const checked = campaign.blog_ids?.includes(b.id) ?? false
              return (
                <label
                  key={b.id}
                  className={`flex items-center gap-3 py-3 ${ok ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}`}
                >
                  <Checkbox checked={checked} disabled={!ok || saving === 'blogs'} onCheckedChange={(v) => toggleBlog(b.id, v === true)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium">{b.label || b.blog_id}</span>
                      <span className="text-xs text-muted-foreground">{b.blog_id}</span>
                      <Pill tone={BLOG_TONE[b.status] || 'muted'}>{BLOG_STATUS_LABEL[b.status] || b.status}</Pill>
                    </div>
                    <div className="mt-0.5 text-xs tabular-nums text-muted-foreground">
                      하루 {b.daily_limit}건 · {b.window_start}~{b.window_end} · 간격 {b.min_gap_minutes}분
                      {!ok && b.status_reason ? ` · ${b.status_reason}` : ''}
                      {!ok && !b.status_reason ? ' · 병원 설정에서 상태를 정상으로 바꾸면 선택할 수 있어요' : ''}
                    </div>
                  </div>
                </label>
              )
            })}
          </div>
        )}
        {saving === 'blogs' && <div className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" /> 저장 중</div>}
      </Card>

      {/* 브리프 / 사진 세트 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-4 p-5">
          <div>
            <h3 className="section-title">글 브리프</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">원고의 흐름·규칙·글자수 기준입니다. 비우면 기본 브리프를 씁니다.</p>
          </div>
          <Select value={campaign.brief_id || NONE} onValueChange={(v) => patch('brief', { brief_id: v === NONE ? null : v })}>
            <SelectTrigger><SelectValue placeholder="브리프 선택" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>기본 브리프 (자동)</SelectItem>
              {briefs.map((b) => (
                <SelectItem key={b.id} value={b.id}>{b.name}{b.is_default ? ' · 기본' : ''} · {b.target_chars.toLocaleString('ko-KR')}자</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Card>
        <Card className="space-y-4 p-5">
          <div>
            <h3 className="section-title">사진 세트</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">4단계에서 원고에 자동 배치할 사진 목록입니다.</p>
          </div>
          <div className="space-y-2">
            <Select value={campaign.collection_id || NONE} onValueChange={(v) => patch('collection', { collection_id: v === NONE ? null : v })}>
              <SelectTrigger><SelectValue placeholder="사진 세트 선택" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>선택 안 함 (전체 사진 풀)</SelectItem>
                {collections.map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.name} · {c.count.toLocaleString('ko-KR')}장</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              사진은 <Link href="/dashboard/media" className="text-primary underline">사진 풀</Link>에서 올리고 세트로 묶을 수 있어요.
            </p>
          </div>
        </Card>
      </div>

      <StepFooter onNext={() => goStep(2)} nextLabel="다음: 키워드">
        {activeSelected === 0 && <span className="text-xs text-warning">블로그를 하나 이상 고르면 예약 단계가 편해요</span>}
      </StepFooter>
    </div>
  )
}

function SummaryRow({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <Label className="text-[13px] font-medium text-muted-foreground">{label}</Label>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {items?.length ? items.map((x) => (
          <span key={x} className="rounded-full bg-muted px-2 py-0.5 text-xs">{x}</span>
        )) : <span className="text-xs text-muted-foreground">없음</span>}
      </div>
    </div>
  )
}
