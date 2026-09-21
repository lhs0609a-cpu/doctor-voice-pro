'use client'

import { useEffect, useState } from 'react'
import { campaignAPI, type Campaign, type Client, type Draft } from '@/lib/campaign-api'
import { PointFormattingPanel } from '@/components/campaign/point-formatting'
import { Step5Schedule } from '@/components/campaign/step5-schedule'
import { Button } from '@/components/ui/button'
import { errMsg } from '@/components/campaign/common'

export function WordPublishPanel({ campaign, client, onUpdated }: {
  campaign: Campaign; client: Client; onUpdated: (value: Campaign) => void
}) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [saved, setSaved] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState<'upload' | 'schedule' | 'done'>('upload')
  useEffect(() => {
    campaignAPI.listDrafts(campaign.id).then(rows => setDrafts(rows.filter(d => d.source === 'upload'))).catch(e => setError(errMsg(e)))
  }, [campaign.id])
  if (step === 'done') return <div className="space-y-3"><p role="status">예약을 저장했습니다. PC 실행기가 네이버 등록을 진행합니다. 아래 발행 현황에서 결과를 확인하세요.</p><Button variant="outline" onClick={() => { setSelected([]); setStep('upload') }}>다른 Word 원고 올리기</Button></div>
  if (step === 'schedule') return <Step5Schedule campaign={campaign} client={client} setCampaign={onUpdated} draftIds={selected}
    goStep={next => setStep(next === 6 ? 'done' : 'upload')} />
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">Word를 올리면 원고와 사진이 저장됩니다. 강조를 확인한 뒤 블로그와 예약 일정을 정하세요.</p>
    <label className="block rounded-xl border-2 border-dashed p-5 text-sm">Word 파일 선택 (.docx, 여러 개 가능)
      <input aria-label="예약할 Word 파일" className="mt-3 block w-full" type="file" accept=".docx" multiple disabled={uploading} onChange={async e => {
        const input = e.currentTarget
        const files = Array.from(input.files || [])
        if (!files.length) return
        setUploading(true); setError('')
        try {
          const rows = await campaignAPI.uploadDrafts(campaign.id, files)
          setDrafts(previous => [...previous, ...rows]); setSelected(previous => [...previous, ...rows.filter(d => d.status === 'ready').map(d => d.id)])
        } catch (err) { setError(errMsg(err)) } finally { setUploading(false); input.value = '' }
      }} />
    </label>
    {uploading && <p role="status">Word 원고와 사진을 저장하는 중…</p>}
    {drafts.map(d => <label key={d.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.includes(d.id)} disabled={d.status !== 'ready'}
      onChange={e => setSelected(value => e.target.checked ? [...value, d.id] : value.filter(id => id !== d.id))} />{d.title}{d.status !== 'ready' && ' · 원고 검토 필요'}</label>)}
    <PointFormattingPanel campaignId={campaign.id} drafts={drafts} onSavedState={setSaved} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <Button disabled={!saved || uploading || selected.length === 0} onClick={() => setStep('schedule')}>선택한 {selected.length}개 원고 예약 설정</Button>
  </div>
}
