'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { campaignAPI, type AutopilotConfig, type AutopilotState } from '@/lib/campaign-api'
import { errMsg } from './common'

const defaults: AutopilotConfig = { daily_posts: 2, buffer_days: 3, image_count: 3,
  target_chars: 2000, min_score: 85, max_rewrites: 2, daily_generation_limit: 6,
  landing_url: '', landing_label: '자세한 안내 확인하기', landing_purpose: '', landing_tracking: false }
type NumericConfig = 'daily_posts' | 'buffer_days' | 'image_count' | 'target_chars' | 'min_score' | 'max_rewrites' | 'daily_generation_limit'

// 원스톱 화면(초보용)에서는 링크·유입 추적 같은 설정을 접어 둔다.
function Advanced({ inline, children }: { inline: boolean; children: React.ReactNode }) {
  return inline
    ? <details className="rounded-lg border p-4"><summary className="cursor-pointer text-sm text-muted-foreground">고급 설정 (몰라도 됩니다 · 병원 홈페이지 링크)</summary><div className="mt-3 space-y-3">{children}</div></details>
    : <div className="space-y-3 rounded-lg border p-4">{children}</div>
}

export function AutopilotPanel({ campaignId, onComplete, inline = false, noImages = false }: { campaignId: string; onComplete: () => void; inline?: boolean; noImages?: boolean }) {
  const [state, setState] = useState<AutopilotState | null>(null)
  const [config, setConfig] = useState(defaults)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let disposed = false
    let initial = true
    const load = async () => {
      try {
        const next = await campaignAPI.getAutopilot(campaignId)
        if (disposed) return
        setState(next)
        if (initial) { setConfig({ ...defaults, ...next.config }); initial = false }
      } catch (e) { if (!disposed) setError(errMsg(e)) }
    }
    void load()
    const timer = setInterval(load, 5000)
    return () => { disposed = true; clearInterval(timer) }
  }, [campaignId])

  const save = async (enabled: boolean) => {
    setBusy(true); setError('')
    try {
      const chosen = enabled ? config : state?.config || config
      // 3번에서 '사진 없이 진행'을 골랐으면 글당 사진 0장으로 시작한다(사진이 없는데 3장을 요구하면 시작부터 막힌다).
      const next = await campaignAPI.setAutopilot(campaignId, { ...chosen, ...(enabled && noImages ? { image_count: 0 } : {}), enabled })
      setState(next); setConfig(next.config); onComplete()
      toast.success(enabled ? '자동 운영을 시작했습니다' : '새 작업과 발행 대기를 일시정지했습니다')
    } catch (e: any) {
      const issues = e?.response?.data?.detail?.issues
      setError(Array.isArray(issues) ? issues.join('\n') : errMsg(e))
    } finally { setBusy(false) }
  }
  const numeric = (key: NumericConfig, label: string, min: number, max: number) =>
    <div key={key}><Label htmlFor={`pilot-${key}`}>{label}</Label>
      <Input id={`pilot-${key}`} type="number" min={min} max={max} value={config[key]}
        disabled={busy || state?.enabled} onChange={e => setConfig(c => ({ ...c, [key]: Number(e.target.value) }))} /></div>

  if (!state) return <Card className="p-6"><p role={error ? 'alert' : 'status'} className="text-sm">{error || '저장된 발행 기준을 불러옵니다…'}</p>{error && <p className="mt-2 text-xs text-muted-foreground">잠시 후 자동으로 다시 확인합니다.</p>}</Card>

  if (state.enabled) return <Card className="space-y-4 border-emerald-500/30 bg-emerald-500/5 p-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">자동 운영이 켜져 있습니다</p>
        <h3 className="mt-1 text-xl font-semibold">하루 {state.config.daily_posts}건을 목표로 준비합니다</h3></div>
      <Button variant="outline" disabled={busy} onClick={() => save(false)}>{busy ? '중단 요청 중…' : '일시정지'}</Button>
    </div>
    <p className="text-sm" role="status">{state.task?.status === 'failed' ? state.task.error : state.task?.status === 'running' ? state.task.message : state.message}</p>
    {!!state.task?.result?.needs_review && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">일부 원고가 품질 기준을 통과하지 못해 발행에서 제외되었습니다. {inline ? '아래 5번에서 결과를 확인하세요.' : <Link className="underline" href={`/dashboard/campaign/${campaignId}?step=3`}>원고 확인하기</Link>}</p>}
    <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
      <span>글당 사진 {state.config.image_count}장</span><span>본문 약 {state.config.target_chars.toLocaleString()}자</span>
      <span>오늘 생성 시도 {state.reserved_today}/{state.config.daily_generation_limit}건</span>
      <span>{state.config.landing_url ? '랜딩페이지 안내 포함' : '정보 전달형 글'}</span>
    </div>
    <p className="text-xs text-muted-foreground">원고 준비는 화면을 닫아도 계속됩니다. 네이버 등록을 맡는 PC 실행기는 켜 두세요. 설정 변경은 일시정지 후 가능합니다.</p>
    {error && <p role="alert" className="whitespace-pre-line text-sm text-destructive">{error}</p>}
  </Card>

  return <Card className="space-y-4 border-primary/30 p-5">
    <div><h3 className="section-title">블로그 자동 운영</h3>
      <p className="mt-1 text-sm text-muted-foreground">{inline ? '하루에 몇 개씩 쓸지만 정하고 아래 파란 버튼을 누르세요. 나머지는 알아서 합니다.' : '발행할 양과 안내할 페이지를 정하세요. 품질 검수와 예약 시간 배정은 자동으로 진행합니다.'}</p></div>
    <div className="grid gap-3 sm:grid-cols-2">
      {numeric('daily_posts', '하루에 몇 개 쓸까요?', 1, 10)}
      <div className="rounded-lg bg-muted/50 p-3 text-sm"><span className="font-medium">글쓰기 설정은 준비되어 있어요</span><p className="mt-1 text-xs text-muted-foreground">사진 {config.image_count}장 · 약 {config.target_chars.toLocaleString()}자 · 근거 검수 · 최대 {config.max_rewrites}회 수정</p></div>
    </div>
    <Advanced inline={inline}>
      <div><Label htmlFor="landing-url">글에서 안내할 랜딩페이지 URL</Label><p className="mb-2 text-xs text-muted-foreground">선택 사항 · 독자를 안내할 주소가 있으면 붙여 넣으세요.</p>
        <Input id="landing-url" type="url" placeholder="https://병원홈페이지/상담안내" value={config.landing_url}
          disabled={busy || state?.enabled} onChange={e => setConfig(c => ({ ...c, landing_url: e.target.value }))} /></div>
      {config.landing_url && <div><Label htmlFor="landing-purpose">이 페이지에서 독자가 확인할 수 있는 내용 (선택)</Label>
        <Input id="landing-purpose" placeholder="예: 진료 과정과 예약 방법 안내" value={config.landing_purpose}
          maxLength={300} disabled={busy || state?.enabled} onChange={e => setConfig(c => ({ ...c, landing_purpose: e.target.value }))} /></div>}
      <details className="space-y-3"><summary className="cursor-pointer text-sm text-muted-foreground">링크 문구·유입 추적 설정</summary>
      <div><Label htmlFor="landing-label">링크 안내 문구</Label>
        <Input id="landing-label" value={config.landing_label} maxLength={60}
          disabled={busy || state?.enabled} onChange={e => setConfig(c => ({ ...c, landing_label: e.target.value }))} /></div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config.landing_tracking}
        disabled={busy || state?.enabled} onChange={e => setConfig(c => ({ ...c, landing_tracking: e.target.checked }))} />글별 유입 구분용 UTM 추적값 추가</label>
      <p className="text-xs text-muted-foreground">글의 마무리에 내용과 맞는 연결 문장과 URL을 한 번 넣습니다. UTM 결과는 랜딩페이지의 방문 분석 도구에서 확인할 수 있습니다. 기존에 작성된 글은 바뀌지 않습니다.</p>
      <Button variant="outline" disabled={busy || !state || state.enabled} onClick={async () => {
        setBusy(true)
        try { await campaignAPI.setLanding(campaignId, config); toast.success('새로 작성할 대량 원고의 랜딩 설정을 저장했습니다') }
        catch (e) { setError(errMsg(e)) }
        finally { setBusy(false) }
      }}>랜딩 설정만 저장</Button></details>
    </Advanced>
    <details><summary className="cursor-pointer text-sm">{inline ? '더 세부 설정 (몰라도 됩니다)' : '세부 설정 바꾸기 (선택)'}</summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {numeric('image_count', '글당 사진 수', 0, 10)}
        {numeric('target_chars', '본문 목표 글자 수', 1200, 4000)}
        {numeric('min_score', '각 품질 항목 최소 점수', 80, 95)}
        {numeric('max_rewrites', '검수 실패 시 최대 수정 횟수', 0, 2)}
        {numeric('buffer_days', '미리 준비할 일수', 1, 7)}
        {numeric('daily_generation_limit', '하루 새 원고 시도 한도', 1, 30)}
      </div>
    </details>
    <p className="text-xs text-muted-foreground">{inline ? '매일 정한 개수만큼 알아서 글을 쓰고 예약합니다. AI 사용 요금이 발생하며, 1번의 PC 실행기가 켜져 있어야 네이버에 올라갑니다.' : '병원·진료 항목, 블로그, 사진 세트를 먼저 연결하세요. AI 및 검색 API 설정과 로그인된 실행 기기가 필요합니다. 생성·검수에 API 요금이 발생합니다. 품질 점수는 자동 편집 기준이며 사실의 정확성이나 검색 순위를 보장하지 않습니다.'}</p>
    {error && <p role="alert" className="whitespace-pre-line text-sm text-destructive">{error}</p>}
    <div className="flex flex-col gap-2">
      <Button className="h-12 w-full text-base" disabled={busy || !state} onClick={() => save(!state?.enabled)} variant={state?.enabled ? 'outline' : 'default'}>
        {busy ? '저장 중…' : state?.enabled ? '자동 운영 일시정지' : '자동 운영 시작'}
      </Button>
      <p className="text-center text-xs text-muted-foreground">설정을 저장하고 키워드 찾기부터 시작합니다.</p>
    </div>
    {state && <div className="space-y-1 text-sm" role="status">
      <p>{state.enabled ? '자동 운영 중' : '자동 운영 정지'} · {state.message}</p>
      {state.task && <p>{state.task.status === 'failed' ? state.task.error : state.task.message}</p>}
      <p className="text-xs text-muted-foreground">일시정지해도 이미 네이버에 등록된 예약은 유지되며, 등록 중인 작업은 완료될 수 있습니다. {inline ? '로그인이나 확인이 필요한 글은 아래 5번에 표시됩니다.' : '로그인 만료와 등록 여부 확인 요청은 발행 현황에서 확인하세요.'}</p>
    </div>}
  </Card>
}
