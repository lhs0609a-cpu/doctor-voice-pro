'use client'

import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ChipInput } from '@/components/clients/chip-input'
import type { ClientInput } from '@/lib/campaign-api'
import type { PoolCollectionItem } from '@/lib/api'

interface ClientFormProps {
  form: ClientInput
  onChange: (next: ClientInput) => void
  collections: PoolCollectionItem[]
}

const NONE = '__none__'

export function ClientForm({ form, onChange, collections }: ClientFormProps) {
  const set = <K extends keyof ClientInput>(key: K, value: ClientInput[K]) => onChange({ ...form, [key]: value })
  const num = (v: string, fallback: number) => {
    const n = Number(v)
    return Number.isFinite(n) && v !== '' ? Math.max(0, Math.floor(n)) : fallback
  }

  return (
    <div className="space-y-6">
      {/* 기본 정보 */}
      <Card>
        <CardHeader>
          <CardTitle>기본 정보</CardTitle>
          <CardDescription>키워드 확장과 원고 생성에 쓰이는 병원 정보입니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="c-name">병원 이름 *</Label>
              <Input id="c-name" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="예: 로담한의원" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-short">짧은 이름</Label>
              <Input id="c-short" value={form.short_name ?? ''} onChange={(e) => set('short_name', e.target.value)} placeholder="예: 로담" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-spec">진료 과목</Label>
              <Input id="c-spec" value={form.specialty ?? ''} onChange={(e) => set('specialty', e.target.value)} placeholder="예: 한의원, 정형외과" />
            </div>
          </div>

          <div className="space-y-1">
            <Label>중점 질환</Label>
            <ChipInput value={form.diseases} onChange={(v) => set('diseases', v)} placeholder="예: 허리디스크, 목디스크 (Enter 또는 쉼표로 추가)" />
          </div>
          <div className="space-y-1">
            <Label>시술</Label>
            <ChipInput value={form.treatments} onChange={(v) => set('treatments', v)} placeholder="예: 추나, 도수치료" />
          </div>
          <div className="space-y-1">
            <Label>기준 지역</Label>
            <ChipInput value={form.regions} onChange={(v) => set('regions', v)} placeholder="예: 위례, 성남, 하남" />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1">
              <Label>지역 확장 범위</Label>
              <Select value={String(form.region_expand_level)} onValueChange={(v) => set('region_expand_level', Number(v))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">입력한 지역만</SelectItem>
                  <SelectItem value="1">인접 동·역까지</SelectItem>
                  <SelectItem value="2">인접 구까지</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-minr">지역 키워드 최소 검색량</Label>
              <Input
                id="c-minr"
                type="number"
                min={0}
                value={form.min_volume_region}
                onChange={(e) => set('min_volume_region', num(e.target.value, 20))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-minn">전국 키워드 최소 검색량</Label>
              <Input
                id="c-minn"
                type="number"
                min={0}
                value={form.min_volume_national}
                onChange={(e) => set('min_volume_national', num(e.target.value, 100))}
              />
            </div>
          </div>
          <p className="-mt-2 text-xs text-muted-foreground">네이버 검색광고 모바일 검색량 기준</p>

          <div className="space-y-1">
            <Label>금칙어</Label>
            <ChipInput value={form.forbidden_words} onChange={(v) => set('forbidden_words', v)} placeholder="원고에 절대 넣지 않을 표현 (예: 완치, 최고)" />
          </div>

          <div className="space-y-1">
            <Label htmlFor="c-tone">말투 · 톤</Label>
            <Textarea
              id="c-tone"
              rows={3}
              value={form.tone ?? ''}
              onChange={(e) => set('tone', e.target.value)}
              placeholder="예: 원장이 직접 설명하듯 차분하고 친절하게. 과장 없이, 환자 눈높이로."
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="c-facts">병원 고정 사실</Label>
            <Textarea
              id="c-facts"
              rows={6}
              value={form.facts ?? ''}
              onChange={(e) => set('facts', e.target.value)}
              placeholder="주소, 원장 이름과 경력, 보유 장비, 프로그램명, 진료 시간 등"
            />
            <p className="text-xs text-muted-foreground">
              병원 고정 사실: 주소, 원장, 장비, 프로그램명 등. 원고는 이 밖의 병원 정보를 지어내지 않습니다.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 사진 세트 */}
      <Card>
        <CardHeader>
          <CardTitle>사진 세트</CardTitle>
          <CardDescription>캠페인에서 별도 지정이 없으면 이 세트의 사진을 원고에 배치합니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] space-y-1">
              <Label>기본 사진 세트</Label>
              <Select
                value={form.default_collection_id || NONE}
                onValueChange={(v) => set('default_collection_id', v === NONE ? null : v)}
              >
                <SelectTrigger><SelectValue placeholder="세트 선택" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>지정 안 함</SelectItem>
                  {collections.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name} ({c.count}장)</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Link href="/dashboard/media" className="inline-flex items-center gap-1 pb-2 text-sm font-medium text-primary hover:underline">
              사진 풀에서 세트 관리 <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
          {collections.length === 0 && (
            <p className="text-xs text-muted-foreground">아직 사진 세트가 없습니다. 사진 풀에서 세트를 만들고 사진을 올려주세요.</p>
          )}
        </CardContent>
      </Card>

      {/* 구글시트 */}
      <Card>
        <CardHeader>
          <CardTitle>구글시트</CardTitle>
          <CardDescription>이미 발행한 키워드 목록이 있는 시트를 연결하면 키워드 확장 시 중복을 표시합니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="c-sheet">시트 URL</Label>
            <Input
              id="c-sheet"
              value={form.sheet_url ?? ''}
              onChange={(e) => set('sheet_url', e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
            />
            <p className="text-xs text-muted-foreground">시트를 &apos;링크가 있는 모든 사용자 보기&apos;로 공개하면 중복 확인이 됩니다.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="c-btab">블로그 탭 이름</Label>
              <Input id="c-btab" value={form.sheet_blog_tab ?? ''} onChange={(e) => set('sheet_blog_tab', e.target.value)} placeholder="블로그" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="c-ctab">카페 탭 이름</Label>
              <Input id="c-ctab" value={form.sheet_cafe_tab ?? ''} onChange={(e) => set('sheet_cafe_tab', e.target.value)} placeholder="카페" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
