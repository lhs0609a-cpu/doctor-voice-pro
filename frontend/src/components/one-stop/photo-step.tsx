'use client'

// 3단계 사진 — 이 자리에서 바로 올린다(사진 풀 화면으로 가지 않는다).
// 올린 사진은 이 운영의 사진 세트로 묶이고, 글마다 알아서 골라 조금씩 다르게 바꿔 넣는다.

import { useCallback, useEffect, useState } from 'react'
import { ImagePlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { campaignAPI, type Campaign, type Client } from '@/lib/campaign-api'
import { mediaPoolAPI, type PoolCollectionItem } from '@/lib/api'
import { errMsg } from '@/components/campaign/common'

export function PhotoStep({ campaign, client, setCampaign, skipped, onSkip }: {
  campaign: Campaign
  client: Client
  setCampaign: (campaign: Campaign) => void
  skipped: boolean
  onSkip: () => void
}) {
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [inputKey, setInputKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const currentId = campaign.collection_id || client.default_collection_id || ''

  const load = useCallback(async () => {
    try { setCollections((await mediaPoolAPI.listCollections(false)).collections || []) } catch { /* 목록은 표시용 */ }
  }, [])
  useEffect(() => { void load() }, [load])
  const current = collections.find(c => c.id === currentId)

  const upload = async () => {
    if (!files.length || busy) return
    setBusy(true); setError(''); setMessage(`사진 ${files.length}장을 올리는 중입니다. 잠시만 기다려 주세요.`)
    try {
      let id = currentId
      if (!id) id = (await mediaPoolAPI.createCollection(`${client.name} 운영 사진`)).id
      const res = await mediaPoolAPI.upload(files, id)
      if (!campaign.collection_id) {
        setCampaign(await campaignAPI.patchCampaign(campaign.id, { blog_ids: campaign.blog_ids, collection_id: id }))
      }
      setFiles([]); setInputKey(k => k + 1)
      setMessage(`${res.uploaded}장 올렸습니다${res.failed ? ` · ${res.failed}장은 실패했습니다(다시 골라 올려 주세요)` : ''}.`)
      await load()
    } catch (e) {
      setError(errMsg(e)); setMessage('')
    } finally { setBusy(false) }
  }

  return <div className="space-y-3">
    {current
      ? <p className="text-sm">지금 준비된 사진: <b className="tabular-nums">{current.count}</b>장 <span className="text-muted-foreground">({current.name})</span></p>
      : !skipped && <p className="text-sm">아직 올린 사진이 없습니다.</p>}
    <ol className="list-decimal space-y-1 pl-5 text-sm">
      <li><b>사진 고르기</b>를 눌러 진료실·시술 사진을 여러 장 고릅니다(JPG·PNG).</li>
      <li><b>사진 올리기</b>를 누르면 끝입니다. 글마다 알아서 골라 넣습니다(기본 3장).</li>
    </ol>
    {/* 브라우저 기본 파일 칸은 영어(Choose Files)로 뜰 수 있어 한글 버튼으로 감싼다 */}
    <label className={cn('flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-4 text-sm hover:bg-muted/40', busy && 'pointer-events-none opacity-60')}>
      <input key={inputKey} type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={busy} className="sr-only"
        onChange={e => setFiles(Array.from(e.target.files || []))} />
      <ImagePlus className="h-5 w-5 text-muted-foreground" />
      {files.length ? <span><b className="tabular-nums">{files.length}</b>장 골랐습니다 · 다시 고르려면 누르세요</span> : <b>사진 고르기</b>}
    </label>
    <div className="flex flex-wrap gap-2">
      <Button onClick={upload} disabled={busy || !files.length}>
        {busy ? '올리는 중…' : files.length ? `사진 ${files.length}장 올리기` : '사진 올리기'}
      </Button>
      {!current && !skipped && <Button variant="ghost" onClick={onSkip} disabled={busy}>사진 없이 진행</Button>}
    </div>
    {skipped && !current && <p className="text-xs text-muted-foreground">사진 없이 글만 준비합니다. 나중에 사진을 올리면 그다음 글부터 들어갑니다.</p>}
    {message && <p role="status" className="text-sm">{message}</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </div>
}
