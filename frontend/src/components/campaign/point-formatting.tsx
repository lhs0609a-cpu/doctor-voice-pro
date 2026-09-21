'use client'

import { useEffect, useRef, useState } from 'react'
import { campaignAPI, type Draft, type PointFormattingConfig, type FormattedBlock, type FormattedSpan } from '@/lib/campaign-api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { errMsg } from './common'

function Spans({ spans, fallback }: { spans?: FormattedSpan[]; fallback?: string }) {
  return <>{spans?.length ? spans.map((span, index) => <span key={index} style={{
    fontWeight: span.b ? 700 : undefined, fontStyle: span.i ? 'italic' : undefined,
    textDecoration: span.u ? 'underline' : undefined, color: span.color,
    backgroundColor: span.background,
  }}>{span.t}</span>) : fallback}</>
}

export function PointFormattingPanel({ campaignId, drafts, onSavedState }: {
  campaignId: string; drafts: Draft[]; onSavedState?: (saved: boolean) => void
}) {
  const [config, setConfig] = useState<PointFormattingConfig | null>(null)
  const [saved, setSaved] = useState('')
  const [error, setError] = useState('')
  const [draftId, setDraftId] = useState('')
  const [preview, setPreview] = useState<FormattedBlock[] | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [retry, setRetry] = useState(0)
  const queue = useRef(Promise.resolve())
  const current = useRef('')
  const serialized = config ? JSON.stringify(config) : ''
  current.current = serialized
  const clean = !!serialized && serialized === saved
  useEffect(() => { onSavedState?.(clean) }, [clean, onSavedState])
  useEffect(() => {
    let live = true
    campaignAPI.getPointFormatting(campaignId).then(value => {
      if (live) { setConfig(value); setSaved(JSON.stringify(value)) }
    }).catch(e => { if (live) setError(errMsg(e)) })
    return () => { live = false }
  }, [campaignId])
  useEffect(() => {
    if (!config || serialized === saved) return
    const timer = setTimeout(() => {
      // Serialize writes so a slower old response cannot overwrite newer settings.
      queue.current = queue.current.catch(() => {}).then(async () => {
        try {
          await campaignAPI.savePointFormatting(campaignId, config)
          setSaved(serialized)
          if (current.current === serialized) setError('')
        } catch (e) { setError(errMsg(e)) }
      })
    }, 650)
    return () => clearTimeout(timer)
  }, [campaignId, config, serialized, saved, retry])
  const change = (patch: Partial<PointFormattingConfig>) => { if (config) { setConfig({ ...config, ...patch }); setPreview(null) } }
  return <Card className="space-y-4 p-5">
    <div><h3 className="font-semibold">중요 포인트 강조</h3>
      <p className="mt-1 text-sm text-muted-foreground">Word의 기존 서식은 유지하고, 중요한 문구에만 강조를 더합니다. 설정은 자동 저장되며 새로 예약하는 글에 적용됩니다.</p></div>
    {config && <>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config.enabled} onChange={e => change({ enabled: e.target.checked })} />핵심 문구 자동 강조</label>
      <fieldset disabled={!config.enabled} className="space-y-3 disabled:opacity-50">
        <div className="flex flex-wrap gap-4">{(['bold', 'quote', 'color', 'background'] as const).map((key, i) =>
          <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config[key]} onChange={e => change({ [key]: e.target.checked })} />{['굵게', '인용구', '글자색', '글자 배경색'][i]}</label>)}</div>
        <div className="flex flex-wrap gap-5">
          <label className="flex items-center gap-2 text-sm">글자색<input aria-label="강조 글자색" type="color" value={config.text_color} onChange={e => change({ text_color: e.target.value })} /></label>
          <label className="flex items-center gap-2 text-sm">배경색<input aria-label="강조 배경색" type="color" value={config.background_color} onChange={e => change({ background_color: e.target.value })} /></label>
        </div>
        <label className="block text-sm">특히 강조할 문구 (선택 · 한 줄에 하나, 최대 20개)
          <textarea className="mt-2 min-h-24 w-full rounded-md border bg-background p-3" value={config.phrases.join('\n')}
            onChange={e => change({ phrases: e.target.value.split('\n').slice(0,20) })} placeholder={'치료 선택의 기준\n개인별 상태 확인'} /></label>
        <p className="text-xs text-muted-foreground">입력한 문구를 우선합니다. 비워두면 원고의 키워드와 중요·주의·결론 표현을 기준으로 최대 6곳을 고릅니다. 인용구는 짧은 문단에 적용하며, 문장 내용은 바꾸지 않습니다.</p>
      </fieldset>
      <p role="status" className="text-xs text-muted-foreground">{clean ? '설정 저장됨' : error ? '설정을 저장하지 못했습니다.' : '설정 저장 중…'}</p>
      {!clean && error && <Button variant="outline" onClick={() => { setError(''); setRetry(value => value + 1) }}>설정 저장 다시 시도</Button>}
      {!!drafts.length && <div className="flex flex-wrap gap-2">
        <select aria-label="서식 미리보기 원고" className="min-w-0 flex-1 rounded-md border bg-background p-2 text-sm" value={draftId || drafts[0]?.id} onChange={e => { setDraftId(e.target.value); setPreview(null) }}>
          {drafts.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <Button variant="outline" disabled={!clean || previewing} onClick={async () => {
          setPreviewing(true)
          try { const result = await campaignAPI.previewPointFormatting(draftId || drafts[0].id, config); setPreview(result.blocks); setError('') }
          catch (e) { setError(errMsg(e)) } finally { setPreviewing(false) }
        }}>{previewing ? '불러오는 중…' : '강조 미리보기'}</Button>
      </div>}
    </>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {preview && <div aria-label="강조 미리보기" className="max-h-96 space-y-4 overflow-y-auto rounded-lg border bg-white p-5 text-sm leading-7 text-black">
      {preview.map((block, index) => block.type === 'image' ? <div key={index} className="rounded bg-gray-100 p-4 text-center text-gray-500">Word 이미지</div>
        : block.type === 'table' ? <table key={index} className="w-full border-collapse">{<tbody>{block.rows?.map((row, r) => <tr key={r}>{row.map((cell, c) => <td key={c} className="border p-2"><Spans spans={cell} /></td>)}</tr>)}</tbody>}</table>
        : block.type === 'list' ? <ul key={index} className="list-inside list-disc">{block.items?.map((item, i) => <li key={i}><Spans spans={item} /></li>)}</ul>
        : block.type === 'quote' ? <blockquote key={index} className="border-l-4 border-gray-500 bg-gray-50 py-2 pl-4"><Spans spans={block.spans} fallback={block.content} /></blockquote>
        : <p key={index} className={block.type === 'heading' ? 'whitespace-pre-wrap text-lg font-semibold' : 'whitespace-pre-wrap'}><Spans spans={block.spans} fallback={block.content} /></p>)}
    </div>}
  </Card>
}
