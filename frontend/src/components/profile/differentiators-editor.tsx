'use client'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export type DifferentiatorItem = {
  category: string
  text: string
}

export type Differentiators = {
  philosophy: string
  items: DifferentiatorItem[]
}

export const EMPTY_DIFFERENTIATORS: Differentiators = { philosophy: '', items: [] }

const CATEGORIES = ['검사', '장비', '술기', '과정', '경력'] as const

// 원장님이 뭘 적어야 할지 감이 오도록 카테고리별 예시를 붙인다
const PLACEHOLDERS: Record<string, string> = {
  검사: '엑스레이만으로는 초기 연골 손상이 안 보여서 관절 초음파로 한 번 더 확인한다',
  장비: '보행 분석기로 무릎에 실리는 하중 축이 안쪽으로 쏠렸는지 먼저 본다',
  술기: '관절강내 주사는 맹목으로 놓지 않고 초음파 유도로만 놓는다',
  과정: '첫 진료 때 운동 처방지를 종이로 드리고 4주 뒤 근력을 다시 측정한다',
  경력: '관절경 세부전공, 무릎 질환만 15년',
}

export function DifferentiatorsEditor({
  value,
  onChange,
}: {
  value: Differentiators
  onChange: (next: Differentiators) => void
}) {
  const items = value.items ?? []

  const update = (patch: Partial<Differentiators>) => onChange({ ...value, ...patch })

  const setItem = (idx: number, patch: Partial<DifferentiatorItem>) => {
    const next = items.map((it, i) => (i === idx ? { ...it, ...patch } : it))
    update({ items: next })
  }

  const addItem = (category: string) => {
    update({ items: [...items, { category, text: '' }] })
  }

  const removeItem = (idx: number) => {
    update({ items: items.filter((_, i) => i !== idx) })
  }

  return (
    <div className="space-y-5">
      <div className="rounded-md border border-sky-500/30 bg-sky-500/5 p-3 text-xs leading-relaxed">
        <p className="font-medium">여기가 글의 품질을 가장 크게 바꾸는 자리입니다.</p>
        <p className="mt-1 text-muted-foreground">
          이 항목이 비어 있으면 어느 병원에나 해당하는 글이 나옵니다. 채우면 AI가 &quot;그래서 저는
          이렇게 봅니다&quot; 형태로 본문에 녹여 씁니다. 장비 이름 자체보다,{' '}
          <span className="font-medium text-foreground">그것 때문에 환자가 무엇을 덜 겪는지</span>를
          적어주세요.
        </p>
      </div>

      <div className="space-y-2">
        <Label>진료 원칙 한 문장</Label>
        <Input
          value={value.philosophy ?? ''}
          onChange={(e) => update({ philosophy: e.target.value })}
          placeholder="수술을 권하기 전에 왜 그 무릎이 그렇게 됐는지부터 찾는다"
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>우리만 하는 것</Label>
          <span className="text-xs text-muted-foreground">{items.length}개 등록</span>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <Button key={c} type="button" variant="outline" size="sm" onClick={() => addItem(c)}>
              + {c}
            </Button>
          ))}
        </div>

        {items.length === 0 && (
          <p className="py-3 text-center text-xs text-muted-foreground">
            위 버튼으로 항목을 추가하세요. 3~5개면 충분합니다.
          </p>
        )}

        <div className="space-y-2">
          {items.map((it, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <select
                value={it.category}
                onChange={(e) => setItem(idx, { category: e.target.value })}
                className={cn(
                  'h-9 flex-none rounded-md border border-input bg-background px-2 text-xs',
                  'focus:outline-none focus:ring-1 focus:ring-ring'
                )}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <Input
                value={it.text}
                onChange={(e) => setItem(idx, { text: e.target.value })}
                placeholder={PLACEHOLDERS[it.category] ?? '이 병원에서만 하는 것을 한 문장으로'}
                className="flex-1"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeItem(idx)}
                className="flex-none text-muted-foreground"
              >
                삭제
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-relaxed text-muted-foreground">
        <span className="font-medium text-foreground">주의.</span> 여기 적은 내용만 글에 쓰입니다.
        AI가 장비나 경력을 지어내지 않습니다. 그리고 다른 병원과 비교하거나 최고·유일 같은 표현은
        의료법에 걸리므로 자동으로 걸러집니다.
      </div>
    </div>
  )
}
