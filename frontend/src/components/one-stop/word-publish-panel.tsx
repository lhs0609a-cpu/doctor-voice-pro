'use client'

// Word 원고 올리기 → 예약. 원스톱의 마지막 칸.
//
// 묻는 것은 둘뿐이다. 어떤 원고를 올릴지, 언제·몇 시간 간격으로 올릴지.
// 강조 서식은 한 번 정해 두면 그대로 쓰이므로 접어 둔다(바꾸고 싶을 때만 편다).

import { useEffect, useState } from 'react'
import { Loader2, Upload } from 'lucide-react'
import { campaignAPI, type Campaign, type Client, type Draft } from '@/lib/campaign-api'
import { PointFormattingPanel } from '@/components/campaign/point-formatting'
import { Button } from '@/components/ui/button'
import { errMsg } from '@/components/campaign/common'
import { QuickSchedule } from './quick-schedule'

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
    campaignAPI.listDrafts(campaign.id)
      .then(rows => setDrafts(rows.filter(d => d.source === 'upload')))
      .catch(e => setError(errMsg(e)))
  }, [campaign.id])

  if (step === 'done') return (
    <div className="space-y-3">
      <p role="status">예약을 걸었습니다. PC 실행기가 네이버 예약 등록을 진행합니다. 아래 발행 현황에서 결과를 확인하세요.</p>
      <Button variant="outline" onClick={() => { setSelected([]); setStep('upload') }}>다른 Word 원고 올리기</Button>
    </div>
  )

  if (step === 'schedule') return (
    <QuickSchedule campaign={campaign} client={client} draftIds={selected}
      onUpdated={onUpdated} onScheduled={() => setStep('done')} onBack={() => setStep('upload')} />
  )

  const upload = async (files: File[]) => {
    setUploading(true); setError('')
    try {
      const rows = await campaignAPI.uploadDrafts(campaign.id, files)
      setDrafts(previous => [...previous, ...rows])
      setSelected(previous => [...previous, ...rows.filter(d => d.status === 'ready').map(d => d.id)])
    } catch (err) { setError(errMsg(err)) } finally { setUploading(false) }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Word 파일을 올리면 글·표·사진이 그대로 저장됩니다. 그다음 언제부터 몇 시간 간격으로 올릴지만 고르면 끝입니다.
      </p>

      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-6 text-center text-sm hover:bg-muted/30">
        <Upload className="h-6 w-6 text-muted-foreground" />
        <span className="font-medium">Word 파일 선택 (.docx, 여러 개 가능)</span>
        <input aria-label="예약할 Word 파일" className="sr-only" type="file" accept=".docx" multiple disabled={uploading}
          onChange={async e => {
            const input = e.currentTarget
            const files = Array.from(input.files || [])
            if (files.length) await upload(files)
            input.value = ''
          }} />
      </label>

      {uploading && (
        <p className="flex items-center gap-2 text-sm" role="status">
          <Loader2 className="h-4 w-4 animate-spin" />Word 원고와 사진을 저장하는 중…
        </p>
      )}

      {drafts.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {drafts.map(d => (
            <li key={d.id}>
              <label className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm">
                <input type="checkbox" checked={selected.includes(d.id)} disabled={d.status !== 'ready'}
                  onChange={e => setSelected(value => e.target.checked ? [...value, d.id] : value.filter(id => id !== d.id))} />
                <span className="min-w-0 flex-1 truncate">{d.title}</span>
                {d.status !== 'ready' && <span className="shrink-0 text-xs text-warning">원고 검토 필요</span>}
              </label>
            </li>
          ))}
        </ul>
      )}

      <details className="rounded-lg border px-3 py-2">
        <summary className="cursor-pointer text-sm text-muted-foreground">글자 강조 설정 바꾸기</summary>
        <div className="mt-3">
          <PointFormattingPanel campaignId={campaign.id} drafts={drafts} onSavedState={setSaved} />
        </div>
      </details>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      <div className="space-y-2">
        <Button disabled={!saved || uploading || selected.length === 0} onClick={() => setStep('schedule')}>
          선택한 {selected.length}개 원고 예약하기
        </Button>
        {/* 강조 설정은 접혀 있어 저장이 막히면 이유가 보이지 않는다 — 여기서 알려 준다. */}
        {!saved && selected.length > 0 && (
          <p className="text-xs text-muted-foreground">강조 설정을 저장하는 중입니다. 잠시 뒤 눌러 주세요(멈춰 있으면 위 설정을 펴서 확인하세요).</p>
        )}
      </div>
    </div>
  )
}
