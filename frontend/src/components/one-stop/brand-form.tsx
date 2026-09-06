'use client'

import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { BrandInfo } from '@/lib/api'

const STORE_KEY = 'doctorvoice-brand-info'

/**
 * 원고 차별화의 재료를 받는 곳.
 *
 * 여기가 비어 있으면 "왜 우리에게 문의해야 하는가"를 쓸 수가 없다.
 * 그럴 때 프롬프트는 없는 장점을 지어내는 대신
 * "판단 기준을 제시하는" 방향으로 자동 전환된다.
 */
export function loadBrand(): BrandInfo {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    return raw ? (JSON.parse(raw) as BrandInfo) : {}
  } catch {
    return {}
  }
}

function saveBrand(brand: BrandInfo) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(brand))
  } catch {
    // 몇 KB라 한도에 걸릴 일이 없다. 걸리면 조용히 넘어간다.
  }
}

const toLines = (v?: string[]) => (v || []).join('\n')
const fromLines = (v: string) =>
  v
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)

export function BrandForm({
  value,
  onChange,
  disabled,
}: {
  value: BrandInfo
  onChange: (brand: BrandInfo) => void
  disabled?: boolean
}) {
  const update = (patch: Partial<BrandInfo>) => {
    const next = { ...value, ...patch }
    onChange(next)
    saveBrand(next)
  }

  const filled = (value.differentiators?.length || 0) + (value.proof_points?.length || 0)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">우리 병원 차별점</p>
        <span
          className={`text-xs ${filled ? 'text-emerald-700' : 'text-amber-700'}`}
        >
          {filled
            ? `${filled}개 입력됨 — 원고에 반영됩니다`
            : '비어 있음 — 판단 기준 제시형으로 대체됩니다'}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Input
          value={value.name || ''}
          onChange={(e) => update({ name: e.target.value })}
          placeholder="상호 (예: 플라톤치과)"
          disabled={disabled}
        />
        <Input
          value={value.region || ''}
          onChange={(e) => update({ region: e.target.value })}
          placeholder="지역 (예: 강남)"
          disabled={disabled}
        />
        <Input
          value={value.specialty || ''}
          onChange={(e) => update({ specialty: e.target.value })}
          placeholder="진료 분야"
          disabled={disabled}
        />
      </div>

      <div>
        <label className="text-xs text-muted-foreground">
          우리만 할 수 있는 것 (한 줄에 하나씩) — 이게 차별화의 핵심입니다
        </label>
        <Textarea
          value={toLines(value.differentiators)}
          onChange={(e) => update({ differentiators: fromLines(e.target.value) })}
          placeholder={
            'CT로 잇몸뼈 상태를 먼저 보고 식립 가능 여부부터 판단합니다\n' +
            '타 병원 임플란트 실패 케이스를 주로 다룹니다\n' +
            '식립 후 5년간 정기 점검을 무상으로 진행합니다'
          }
          rows={3}
          disabled={disabled}
          className="mt-1 text-sm"
        />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <label className="text-xs text-muted-foreground">
            숫자로 말할 수 있는 근거 (한 줄에 하나씩)
          </label>
          <Textarea
            value={toLines(value.proof_points)}
            onChange={(e) => update({ proof_points: fromLines(e.target.value) })}
            placeholder={'개원 12년\n임플란트 재수술 누적 900케이스'}
            rows={2}
            disabled={disabled}
            className="mt-1 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">주로 오시는 분</label>
          <Textarea
            value={value.target_patient || ''}
            onChange={(e) => update({ target_patient: e.target.value })}
            placeholder="다른 곳에서 한 임플란트가 문제가 생겨 오시는 분"
            rows={2}
            disabled={disabled}
            className="mt-1 text-sm"
          />
        </div>
      </div>
    </div>
  )
}

export function useBrand() {
  const [brand, setBrand] = useState<BrandInfo>({})
  useEffect(() => {
    setBrand(loadBrand())
  }, [])
  return { brand, setBrand }
}
