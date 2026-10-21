'use client'

// 자유 키워드 검색 — 병원 등록 없이, 넣은 키워드의 네이버 연관 키워드를 검색량과 함께 본다.
//
// 2026-10-21 요청: "키워드 찾기는 병원 등록을 연동 해제해 주실 수 있을까요? … 산후보약을 검색하면
// 산후보약 연관된 지역키워드가 모두 떴으면 하는데(검색량 나오는 것만), 등록한 지역 때문에 위례
// 산후보약·문정산후보약처럼 검색량 10인 키워드만 뜨네요." 병원별로 매달 원하는 키워드가 다르다 —
// 병원 정보(진료 항목·지역)를 섞지 않고 넣은 그대로 네이버 검색광고에 묻는다.

import { useMemo, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { keywordBatchAPI, type KeywordVolumeDTO } from '@/lib/api'
import { campaignAPI, type Campaign } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'

function csv(rows: (string | number)[][]) {
  const cell = (value: string | number) => {
    const text = String(value ?? '')
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  return '﻿' + rows.map(row => row.map(cell).join(',')).join('\r\n')
}

function save(name: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const COMP: Record<string, string> = { low: '낮음', mid: '중간', high: '높음' }

export function FreeKeywordSearch({ campaigns }: { campaigns: Campaign[] }) {
  const [raw, setRaw] = useState('')
  const [minVolume, setMinVolume] = useState(10)
  const [rows, setRows] = useState<KeywordVolumeDTO[]>([])
  const [filter, setFilter] = useState('')
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [target, setTarget] = useState(campaigns[0]?.id || '')

  const search = async () => {
    const seeds = Array.from(new Set(raw.split(/[\n,]/).map(s => s.trim()).filter(Boolean))).slice(0, 50)
    if (!seeds.length) { setError('찾을 키워드를 넣어 주세요 (예: 산후보약)'); return }
    setBusy(true); setError(''); setNote(''); setChecked({})
    try {
      const found = await keywordBatchAPI.getVolumes(seeds, {
        includeRelated: true, relatedLimit: 300, relatedMinVolume: minVolume,
      })
      // 검색량이 있는 것만. 넣은 키워드 자신도 기준에 못 미치면 뺀다.
      const live = found.filter(r => r.monthly_mobile >= minVolume && r.total_volume > 0)
      const seen = new Set<string>()
      const unique = live.filter(r => { const k = r.keyword.replace(/\s/g, ''); if (seen.has(k)) return false; seen.add(k); return true })
      unique.sort((a, b) => b.total_volume - a.total_volume)
      setRows(unique)
      if (!unique.length) setNote(`모바일 월 검색량 ${minVolume} 이상인 연관 키워드가 없습니다. 기준을 낮춰 보세요.`)
    } catch (e) { setError(errMsg(e)) }
    finally { setBusy(false) }
  }

  const shown = useMemo(() => {
    const q = filter.replace(/\s/g, '')
    return q ? rows.filter(r => r.keyword.replace(/\s/g, '').includes(q)) : rows
  }, [rows, filter])
  const picked = shown.filter(r => checked[r.keyword])
  const chosen = picked.length ? picked : shown

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(chosen.map(r => r.keyword).join('\n'))
      setNote(`${chosen.length}개를 복사했습니다`)
    } catch { setNote('브라우저가 복사를 막았습니다 — 엑셀로 내려받아 주세요') }
  }

  const download = () => {
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    save(`연관키워드_${stamp}.csv`, csv([
      ['키워드', '월 검색량(합계)', '모바일', 'PC', '경쟁도', '어느 키워드의 연관어'],
      ...chosen.map(r => [r.keyword, r.total_volume, r.monthly_mobile, r.monthly_pc, COMP[r.competition] || '', r.related_of || '']),
    ]), 'text/csv')
  }

  const addToCampaign = async () => {
    if (!target || !picked.length) return
    setBusy(true); setError(''); setNote('')
    try {
      await campaignAPI.addKeywords(target, picked.map(r => r.keyword))
      setNote(`${picked.length}개를 담았습니다 — 원스톱 화면의 키워드 목록에 보입니다`)
    } catch (e) { setError(errMsg(e)) }
    finally { setBusy(false) }
  }

  return (
    <Card className="space-y-4 p-5">
      <div>
        <h2 className="text-base font-semibold">자유 검색</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          병원 등록 없이 바로 찾습니다. 넣은 키워드와 함께 검색되는 네이버 연관 키워드를 <b>검색량이 있는 것만</b> 많은 순으로 보여 줍니다.
        </p>
      </div>
      <Textarea rows={3} value={raw} onChange={e => setRaw(e.target.value)}
        placeholder={'한 줄에 하나씩 (쉼표도 됩니다)\n예) 산후보약\n다이어트 한약'} />
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">모바일 월 검색량
          <Input type="number" min={0} className="h-9 w-24 tabular-nums" value={minVolume}
            onChange={e => setMinVolume(Math.max(0, Number(e.target.value) || 0))} />이상
        </label>
        <Button onClick={search} disabled={busy} className="ml-auto">
          {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Search className="mr-1 h-4 w-4" />}찾기
        </Button>
      </div>
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {note && <p role="status" className="text-sm text-muted-foreground">{note}</p>}

      {rows.length > 0 && (
        <div className="space-y-3 border-t pt-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium tabular-nums">{shown.length}개</span>
            {picked.length > 0 && <span className="text-muted-foreground tabular-nums">· {picked.length}개 선택</span>}
            <Input className="h-8 w-40" placeholder="걸러 보기 (예: 위례)" value={filter} onChange={e => setFilter(e.target.value)} />
            <div className="ml-auto flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={copy}>{picked.length ? '선택 복사' : '전체 복사'}</Button>
              <Button size="sm" variant="outline" onClick={download}>엑셀로 받기</Button>
            </div>
          </div>
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-[12px] text-muted-foreground">
                  <th className="w-8 py-2" />
                  <th className="py-2 font-medium">키워드</th>
                  <th className="py-2 text-right font-medium">월 검색량</th>
                  <th className="py-2 text-right font-medium">모바일</th>
                  <th className="py-2 text-right font-medium">PC</th>
                  <th className="py-2 text-center font-medium">경쟁도</th>
                </tr>
              </thead>
              <tbody>
                {shown.map(r => (
                  <tr key={r.keyword} className="border-b last:border-0">
                    <td className="py-2"><Checkbox checked={!!checked[r.keyword]} aria-label={`${r.keyword} 선택`}
                      onCheckedChange={v => setChecked(prev => ({ ...prev, [r.keyword]: !!v }))} /></td>
                    <td className="py-2">{r.keyword}{!r.is_related && <span className="ml-2 text-xs text-primary">넣은 키워드</span>}</td>
                    <td className="py-2 text-right font-semibold tabular-nums">{r.total_volume.toLocaleString()}</td>
                    <td className="py-2 text-right tabular-nums text-muted-foreground">{r.monthly_mobile.toLocaleString()}</td>
                    <td className="py-2 text-right tabular-nums text-muted-foreground">{r.monthly_pc.toLocaleString()}</td>
                    <td className="py-2 text-center text-muted-foreground">{COMP[r.competition] || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {campaigns.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
              <span className="text-muted-foreground">고른 키워드를</span>
              <select aria-label="담을 곳" className="h-9 rounded-md border bg-background px-2" value={target}
                onChange={e => setTarget(e.target.value)}>
                {campaigns.map(c => <option key={c.id} value={c.id}>{c.client_name || c.name} · {c.name}</option>)}
              </select>
              <Button size="sm" disabled={busy || !picked.length} onClick={addToCampaign}>에 담기</Button>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
