'use client'

// 키워드 찾기 — 원스톱(발행)과 떼어 낸 조사 화면.
//
// 발굴은 300개 기준 30분~1시간이 걸리고, 원고를 올리는 일과는 순서가 묶여 있지 않다.
// 그래서 발행 마법사에서 빼내어 따로 둔다. 찾은 결과는 원스톱 화면에도 그대로 보인다.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, Plus } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { PageHeader } from '@/components/app-shell/page-header'
import { EmptyState } from '@/components/app-shell/ui-kit'
import { campaignAPI, type Campaign, type Client, type Keyword } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'
import { KeywordStep } from './keyword-step'
import { KeywordSummary } from './keyword-summary'

export function KeywordHuntPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [selected, setSelected] = useState('')
  const [client, setClient] = useState<Client | null>(null)
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    campaignAPI.listCampaigns()
      .then(rows => {
        if (!alive) return
        setCampaigns(rows)
        setSelected(value => rows.some(r => r.id === value) ? value : rows[0]?.id || '')
      })
      .catch(e => { if (alive) setError(errMsg(e)) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const campaign = useMemo(() => campaigns.find(c => c.id === selected) || null, [campaigns, selected])

  const reload = useCallback(async () => {
    if (!selected) return
    try { setKeywords(await campaignAPI.listKeywords(selected)) }
    catch (e) { setError(errMsg(e)) }
  }, [selected])

  useEffect(() => {
    if (!selected) { setKeywords([]); setClient(null); return }
    let alive = true
    setKeywords([])
    const load = async () => {
      try {
        const next = await campaignAPI.getCampaign(selected)
        const [hospital, rows] = await Promise.all([
          campaignAPI.getClient(next.client_id), campaignAPI.listKeywords(selected),
        ])
        if (alive) { setClient(hospital); setKeywords(rows); setError('') }
      } catch (e) { if (alive) setError(errMsg(e)) }
    }
    void load()
    return () => { alive = false }
  }, [selected])

  const subjects = useMemo(
    () => [...(client?.diseases || []), ...(client?.treatments || [])], [client])

  return (
    <div className="mx-auto max-w-3xl space-y-4 pb-10">
      <PageHeader
        title="키워드 찾기"
        description="우리 블로그로 뚫리는 키워드를 찾아 둡니다. 여기서 찾아 두면 원스톱 화면에서 원고를 올릴 때 그대로 보입니다."
      />

      {loading ? (
        <div className="flex items-center gap-2 py-10 text-sm" role="status">
          <Loader2 className="h-4 w-4 animate-spin" />불러오는 중…
        </div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          icon={<Plus className="h-8 w-8" />}
          title="운영할 병원이 아직 없습니다"
          description="원스톱 자동화에서 병원과 블로그를 먼저 등록해 주세요."
          action={<Button asChild><Link href="/dashboard/one-stop">원스톱 자동화로 가기</Link></Button>}
        />
      ) : (
        <>
          {campaigns.length > 1 && (
            <select aria-label="운영할 병원" className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
              value={selected} onChange={e => setSelected(e.target.value)}>
              {campaigns.map(c => <option key={c.id} value={c.id}>{c.client_name || c.name} · {c.name}</option>)}
            </select>
          )}
          {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}

          {campaign && (
            <Card className="p-5">
              <KeywordStep key={selected} campaignId={selected} keywords={keywords}
                subjects={subjects} onChanged={() => { void reload() }} />
            </Card>
          )}

          {keywords.length > 0 && (
            <KeywordSummary keywords={keywords} campaignId={selected} onChanged={() => { void reload() }} />
          )}
        </>
      )}
    </div>
  )
}
