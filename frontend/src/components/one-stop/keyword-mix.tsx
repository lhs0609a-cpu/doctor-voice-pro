'use client'

// 발굴 세부 설정 — 무엇을 찾을지(씨앗)와 어떻게 나눠 뽑을지(비율).
//
// 초보자는 아무것도 안 건드려도 되게 기본값으로 돌아가야 한다. 그래서:
//   · 찾고 싶은 키워드는 비워 두면 병원 진료 항목으로 찾는다
//   · 비율은 접어 두고, 펼쳐야 보인다
// 비율은 '희망'이다. 후보가 모자란 칸은 서버가 다른 성격으로 메워서 개수를 채운다.

import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { campaignAPI } from '@/lib/campaign-api'

export type MixValue = {
  seeds: string[]
  diseaseQuota: Record<string, number>
  categoryRatio: Record<string, number>
}

type Category = { key: string; label: string; default_ratio: number }

export const EMPTY_MIX: MixValue = { seeds: [], diseaseQuota: {}, categoryRatio: {} }

export function KeywordMix({ subjects, target, value, onChange, disabled }: {
  /** 병원에 등록된 진료 질환·치료 항목 */
  subjects: string[]
  target: number
  value: MixValue
  onChange: (next: MixValue) => void
  disabled?: boolean
}) {
  const [draft, setDraft] = useState('')
  const [categories, setCategories] = useState<Category[]>([])

  useEffect(() => {
    let alive = true
    campaignAPI.keywordCategories()
      .then(r => { if (alive) setCategories(r?.categories || []) })   // 응답이 비면 비율 칸만 빠진다(화면은 살아 있어야)
      .catch(() => { /* 비율칸만 안 보인다. 발굴은 기본 비율로 돈다 */ })
    return () => { alive = false }
  }, [])

  // 직접 넣은 키워드가 있으면 그것이 질환 축이 된다 — 서버도 같은 규칙으로 동작한다.
  const axis = value.seeds.length ? value.seeds : subjects

  const addSeeds = (raw: string) => {
    const found = raw.split(/[,\n]/).map(s => s.trim()).filter(Boolean)
    if (!found.length) return
    const next = [...value.seeds]
    for (const s of found) if (!next.includes(s) && next.length < 20) next.push(s)
    onChange({ ...value, seeds: next })
    setDraft('')
  }

  const ratioTotal = useMemo(
    () => Object.values(value.categoryRatio).reduce((a, b) => a + (b || 0), 0),
    [value.categoryRatio])
  const quotaTotal = useMemo(
    () => Object.values(value.diseaseQuota).reduce((a, b) => a + (b || 0), 0),
    [value.diseaseQuota])

  const ratioOf = (c: Category) =>
    value.categoryRatio[c.key] ?? c.default_ratio

  /** 비율 → 실제 개수 미리보기. 서버의 최대잔여법과 같은 결과는 아니고 어림값이다. */
  const preview = (c: Category) =>
    ratioTotal || Object.keys(value.categoryRatio).length
      ? Math.round(target * (ratioOf(c) / (ratioTotal || 1)))
      : Math.round(target * (c.default_ratio / 100))

  return (
    <details className="rounded-xl border">
      <summary className="cursor-pointer px-3 py-2 text-sm">
        세부 설정
        <span className="ml-2 text-xs text-muted-foreground">
          {value.seeds.length ? `찾을 키워드 ${value.seeds.length}개` : '진료 항목으로 찾기'}
          {(ratioTotal || quotaTotal) ? ' · 비율 지정됨' : ''}
        </span>
      </summary>

      <div className="space-y-4 border-t p-3">
        {/* ── 찾고 싶은 키워드 ── */}
        <div>
          <Label htmlFor="mix-seed">찾고 싶은 키워드</Label>
          <p className="mb-2 text-xs text-muted-foreground">
            넣으면 그 키워드와 연관된 것만 싹 찾습니다. 비워 두면 병원에 등록된 진료 항목으로 찾습니다.
          </p>
          <div className="flex gap-2">
            <Input id="mix-seed" value={draft} disabled={disabled}
              placeholder="예: 탈모, 원형탈모 (쉼표로 여러 개)"
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSeeds(draft) } }} />
            <Button type="button" variant="outline" disabled={disabled || !draft.trim()}
              onClick={() => addSeeds(draft)}>추가</Button>
          </div>
          {value.seeds.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {value.seeds.map(s => (
                <li key={s}>
                  <button type="button" disabled={disabled}
                    className="flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-1 text-xs hover:bg-muted"
                    onClick={() => onChange({
                      ...value,
                      seeds: value.seeds.filter(x => x !== s),
                      diseaseQuota: Object.fromEntries(
                        Object.entries(value.diseaseQuota).filter(([k]) => k !== s)),
                    })}>
                    {s}<X className="h-3 w-3" aria-label={`${s} 빼기`} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ── 질환별 개수 ── */}
        {axis.length > 1 && (
          <div>
            <Label>어떤 걸 몇 개씩</Label>
            <p className="mb-2 text-xs text-muted-foreground">
              비워 두면 {axis.length}개에 고르게 나눕니다.
              {quotaTotal > target && ` 합이 ${target}개를 넘어서 비율대로 줄여 뽑습니다.`}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {axis.map(s => (
                <label key={s} className="flex items-center gap-2 text-sm">
                  <span className="min-w-0 flex-1 truncate">{s}</span>
                  <Input type="number" min={0} max={300} disabled={disabled}
                    className="h-8 w-20 text-right"
                    value={value.diseaseQuota[s] ?? ''}
                    placeholder={String(Math.round(target / axis.length))}
                    onChange={e => {
                      const n = Number(e.target.value)
                      const next = { ...value.diseaseQuota }
                      if (!e.target.value || !Number.isFinite(n) || n <= 0) delete next[s]
                      else next[s] = n
                      onChange({ ...value, diseaseQuota: next })
                    }} />
                  <span className="text-xs text-muted-foreground">개</span>
                </label>
              ))}
            </div>
            {quotaTotal > 0 && (
              <p className="mt-1 text-xs text-muted-foreground tabular-nums">합계 {quotaTotal}개 / 목표 {target}개</p>
            )}
          </div>
        )}

        {/* ── 글 성격 비율 ── */}
        {categories.length > 0 && (
          <div>
            <Label>글 성격은 어떤 비율로</Label>
            <p className="mb-2 text-xs text-muted-foreground">
              치료 글만 잔뜩 나오지 않게 성격을 섞습니다. 후보가 모자란 칸은 다른 성격으로 채웁니다.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {categories.filter(c => c.key !== '기타').map(c => (
                <label key={c.key} className="flex items-center gap-2 text-sm">
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  <Input type="number" min={0} max={100} disabled={disabled}
                    className="h-8 w-20 text-right"
                    value={value.categoryRatio[c.key] ?? ''}
                    placeholder={String(c.default_ratio)}
                    onChange={e => {
                      const n = Number(e.target.value)
                      const next = { ...value.categoryRatio }
                      if (!e.target.value || !Number.isFinite(n) || n < 0) delete next[c.key]
                      else next[c.key] = n
                      onChange({ ...value, categoryRatio: next })
                    }} />
                  <span className="w-14 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    ≈{preview(c)}개
                  </span>
                </label>
              ))}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-xs text-muted-foreground tabular-nums">
                {ratioTotal ? `합계 ${ratioTotal} — 합이 100이 아니어도 비율로 계산합니다.` : '기본 비율로 뽑습니다.'}
              </p>
              {(ratioTotal > 0 || quotaTotal > 0) && (
                <Button type="button" variant="ghost" size="sm" disabled={disabled}
                  onClick={() => onChange({ ...value, diseaseQuota: {}, categoryRatio: {} })}>
                  기본값으로
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </details>
  )
}
