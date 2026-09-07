'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'
import { ArrowLeft, Building2, Check, Loader2, Pencil } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/app-shell/page-header'
import { campaignAPI, type Campaign, type Client } from '@/lib/campaign-api'
import { CAMPAIGN_STATUS_LABEL, Pill, STEP_LABELS, errMsg } from '@/components/campaign/common'
import { Step1Blogs } from '@/components/campaign/step1-blogs'
import { Step2Keywords } from '@/components/campaign/step2-keywords'
import { Step3Drafts } from '@/components/campaign/step3-drafts'
import { Step4Photos } from '@/components/campaign/step4-photos'
import { Step5Schedule } from '@/components/campaign/step5-schedule'
import { Step6Status } from '@/components/campaign/step6-status'

export default function CampaignWizardPage() {
  const params = useParams<{ id: string }>()
  const id = params?.id as string

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState(1)

  const load = useCallback(async () => {
    try {
      const c = await campaignAPI.getCampaign(id)
      const cl = await campaignAPI.getClient(c.client_id)
      setCampaign(c)
      setClient(cl)
      setStep(Math.min(6, Math.max(1, c.step || 1)))
    } catch (err: any) {
      setError(errMsg(err))
    }
  }, [id])

  useEffect(() => { if (id) load() }, [id, load])

  // 단계 이동 → 서버에 step 저장 (실패해도 화면은 이동)
  const goStep = useCallback((n: number) => {
    const next = Math.min(6, Math.max(1, n))
    setStep(next)
    if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' })
    campaignAPI.patchCampaign(id, { step: next })
      .then((c) => setCampaign(c))
      .catch(() => { /* 단계 저장 실패는 조용히 무시 */ })
  }, [id])

  const backLink = (
    <Link href="/dashboard/campaign" className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-3.5 w-3.5" /> 캠페인 목록
    </Link>
  )

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader eyebrow={backLink} title="캠페인을 열 수 없어요" />
        <div className="rounded-lg bg-danger-soft p-4 text-sm text-danger">불러오지 못했습니다: {error}</div>
        <Button asChild variant="outline"><Link href="/dashboard/campaign"><ArrowLeft /> 목록으로</Link></Button>
      </div>
    )
  }

  if (!campaign || !client) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 캠페인을 불러오는 중...
      </div>
    )
  }

  const stepProps = { campaign, client, setCampaign, goStep }
  const st = CAMPAIGN_STATUS_LABEL[campaign.status] || { label: campaign.status, tone: 'muted' as const }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={backLink}
        title={<CampaignNameEditor campaign={campaign} onSaved={setCampaign} />}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1"><Building2 className="h-4 w-4" /> {client.name}</span>
            <Pill tone={st.tone}>{st.label}</Pill>
          </span>
        }
      />

      {/* 스텝 바 */}
      <ol className="flex items-center gap-2">
        {STEP_LABELS.map((s, i) => {
          const state = step === s.n ? 'active' : step > s.n ? 'done' : 'upcoming'
          return (
            <li key={s.n} className="flex min-w-0 flex-1 items-center gap-2">
              <button
                type="button"
                onClick={() => goStep(s.n)}
                className="flex min-w-0 items-center gap-2 rounded-md px-1 py-0.5 transition-colors hover:bg-muted/60"
                title={`${s.n}단계 ${s.label}`}
                aria-current={state === 'active' ? 'step' : undefined}
              >
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold tabular-nums',
                    state === 'active' && 'bg-primary text-primary-foreground',
                    state === 'done' && 'bg-success-soft text-success',
                    state === 'upcoming' && 'bg-muted text-muted-foreground',
                  )}
                >
                  {state === 'done' ? <Check className="h-4 w-4" /> : s.n}
                </span>
                <span className={cn('hidden truncate text-[13px] sm:inline', state === 'active' ? 'font-semibold text-foreground' : 'text-muted-foreground')}>
                  {s.label}
                </span>
              </button>
              {i < STEP_LABELS.length - 1 && <div className="h-px flex-1 bg-border" />}
            </li>
          )
        })}
      </ol>

      {step === 1 && <Step1Blogs {...stepProps} />}
      {step === 2 && <Step2Keywords {...stepProps} />}
      {step === 3 && <Step3Drafts {...stepProps} />}
      {step === 4 && <Step4Photos {...stepProps} />}
      {step === 5 && <Step5Schedule {...stepProps} />}
      {step === 6 && <Step6Status {...stepProps} />}
    </div>
  )
}

function CampaignNameEditor({ campaign, onSaved }: { campaign: Campaign; onSaved: (c: Campaign) => void }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(campaign.name)
  const [saving, setSaving] = useState(false)

  useEffect(() => { setName(campaign.name) }, [campaign.name])

  const save = async () => {
    const v = name.trim()
    if (!v || v === campaign.name) { setEditing(false); setName(campaign.name); return }
    setSaving(true)
    try {
      onSaved(await campaignAPI.patchCampaign(campaign.id, { name: v }))
      setEditing(false)
    } catch (err: any) {
      toast.error('이름 저장 실패', { description: errMsg(err) })
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <Input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setEditing(false); setName(campaign.name) } }}
          onBlur={save}
          className="h-9 w-72 text-lg font-semibold"
        />
        {saving && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </span>
    )
  }
  return (
    <button type="button" onClick={() => setEditing(true)} className="group inline-flex items-center gap-2 text-left" title="이름 바꾸기">
      {campaign.name}
      <Pencil className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </button>
  )
}
