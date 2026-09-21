'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { campaignAPI, type AutopilotConfig, type Task } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'

export function BulkPublishPanel({ campaignId, onRecurring, noImages = false, huntedCount = 0, onStarted }: {
  campaignId: string; onRecurring: () => void; noImages?: boolean
  /** 3번에서 발굴해 고른 키워드 수. 있으면 새로 찾지 않고 이것부터 쓴다. */
  huntedCount?: number
  onStarted?: () => void
}) {
  const [count, setCount] = useState(30)
  const [config, setConfig] = useState<AutopilotConfig | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [recurring, setRecurring] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const running = task?.status === 'pending' || task?.status === 'running'
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const [policy, tasks] = await Promise.all([campaignAPI.getAutopilot(campaignId), campaignAPI.listTasks({ campaign_id: campaignId, limit: 20 })])
        if (!alive) return
        setConfig(policy.config); setRecurring(policy.enabled)
        const latest = tasks.find(t => t.type === 'automation_pipeline') || null
        setTask(latest)
        if (typeof latest?.result?.requested === 'number') setCount(latest.result.requested)
        setLoaded(true); setError('')
      } catch (e) { if (alive) setError(errMsg(e)) }
    }
    void load()
    return () => { alive = false }
  }, [campaignId])
  useEffect(() => {
    if (!task || !running) return
    let alive = true
    const timer = setInterval(async () => {
      try { const next = await campaignAPI.getTask(task.id); if (alive) setTask(next) }
      catch (e) { if (alive) setError(errMsg(e)) }
    }, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [task?.id, running])
  const start = async () => {
    if (!config || busy || running) return
    setBusy(true); setError('')
    try {
      setTask(await campaignAPI.startAutomation(campaignId, {
        // 4단계에서 '사진 없이 진행'을 골랐으면 글당 사진 0장으로 준비한다(사진이 없는데 3장을 요구하면 시작부터 막힌다).
        max_keywords: count,
        // 발굴해 둔 키워드가 있으면 그걸 쓴다. 없을 때만 파이프라인이 직접 찾는다.
        discover_keywords: !huntedCount, strict_quality: huntedCount > 0,
        quality: noImages ? { ...config, image_count: 0 } : config,
        image_count: noImages ? 0 : config.image_count, auto_schedule: true, days: 90,
        start_date: new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' }),
      }))
      onStarted?.()
    } catch (e: any) {
      const issues = e?.response?.data?.detail?.issues
      setError(Array.isArray(issues) ? issues.join('\n') : errMsg(e))
    } finally { setBusy(false) }
  }
  return <Card className="space-y-5 border-primary/30 p-5">
    <div><h2 className="text-xl font-semibold">글 여러 개, 한 번에 준비하고 발행</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        {huntedCount
          ? `3번에서 찾아 둔 키워드 ${huntedCount}개 중에서 씁니다. 검수를 통과한 글은 블로그별 발행 한도에 맞춰 나눠 예약합니다.`
          : '키워드는 자동으로 찾습니다. 검수를 통과한 글은 블로그별 발행 한도에 맞춰 나눠 예약합니다.'}
      </p></div>
    {recurring && <div className="rounded-lg bg-amber-500/10 p-3 text-sm">매일 자동 운영이 켜져 있습니다. 중복 작업을 막기 위해 먼저 일시정지해 주세요.<Button variant="link" onClick={onRecurring}>매일 자동 운영 관리</Button></div>}
    {!loaded ? <p role="status">{error || '저장된 설정을 불러옵니다…'}</p> : running ? <div className="space-y-3" role="status">
      <p className="font-medium">글을 준비하는 중입니다</p><p className="text-sm">{task?.message || '키워드 찾기를 기다리고 있습니다.'}</p>
      <p className="text-xs text-muted-foreground">화면을 닫아도 서버에서 계속 준비합니다. 네이버 등록을 위해 PC 실행기는 켜두세요.</p>
      <Button variant="outline" disabled={busy} onClick={async () => {
        if (!task) return
        setBusy(true)
        try { await campaignAPI.cancelTask(task.id); setTask({ ...task, status: 'cancelled' }) }
        catch (e) { setError(errMsg(e)) }
        finally { setBusy(false) }
      }}>새 원고 준비 중단</Button>
      <p className="text-xs text-muted-foreground">이미 잡힌 예약은 그대로 둡니다. 결과는 아래 5번에서 확인하세요.</p>
    </div> : config && <>
      <div><Label htmlFor="bulk-total">총 몇 개의 글을 준비할까요?</Label>
        <div className="my-2 flex gap-2">{[10, 30, 50].map(n => <Button key={n} variant={count === n ? 'default' : 'outline'} disabled={busy} aria-pressed={count === n} onClick={() => setCount(n)}>{n}개</Button>)}</div>
        <Input id="bulk-total" type="number" min={1} max={50} value={count} disabled={busy} onChange={e => setCount(Number(e.target.value))} /></div>
      <details><summary className="cursor-pointer text-sm text-muted-foreground">고급 설정 (몰라도 됩니다 · 병원 홈페이지 링크, 글당 사진 수)</summary>
        <div className="mt-3 space-y-3"><div><Label htmlFor="bulk-url">글 끝에 안내할 병원 홈페이지 주소 (선택)</Label><Input id="bulk-url" type="url" value={config.landing_url} placeholder="https://..." disabled={busy} onChange={e => setConfig({ ...config, landing_url: e.target.value })} /></div><div><Label htmlFor="bulk-images">글당 사진 수</Label><Input id="bulk-images" type="number" min={0} max={10} value={config.image_count} disabled={busy} onChange={e => setConfig({ ...config, image_count: Number(e.target.value) })} /></div>
          <div><Label htmlFor="bulk-purpose">그 페이지가 어떤 페이지인지 한 줄 (선택)</Label><Input id="bulk-purpose" value={config.landing_purpose} disabled={busy} onChange={e => setConfig({ ...config, landing_purpose: e.target.value })} /></div></div>
      </details>
      {noImages && <p className="rounded-lg bg-muted/50 p-2 text-xs">3번에서 &lsquo;사진 없이 진행&rsquo;을 골라 사진 없이 글만 준비합니다.</p>}
      <p className="text-xs leading-5 text-muted-foreground">최대 {count || 0}개 글을 씁니다. 품질 검사를 통과한 글만 예약하므로 실제 예약 수는 조금 적을 수 있어요. AI 사용 요금이 발생하며, 1번의 PC 실행기가 켜져 있어야 네이버에 올라갑니다.
        {huntedCount > 50 && ' 한 번에 50개까지 쓸 수 있으니, 나머지는 끝난 뒤 다시 시작하면 이어서 씁니다.'}</p>
      <Button className="h-12 w-full text-base" disabled={busy || recurring || !Number.isInteger(count) || count < 1 || count > 50 || !Number.isInteger(config.image_count) || config.image_count < 0 || config.image_count > 10} onClick={start}>{busy ? '시작하는 중…' : `${count || 0}개 글 자동 작성·예약 시작`}</Button>
    </>}
    {task && !running && <div role="status" className="rounded-lg bg-muted/50 p-3 text-sm">{task.status === 'failed' ? task.error : task.status === 'cancelled' ? '새 원고 준비가 중단되었습니다.' : `끝났습니다 · 예약 ${Number(task.result?.scheduled || 0)}개${Number(task.result?.unassigned || 0) ? ` · 하루 발행 한도가 차서 예약하지 못한 글 ${Number(task.result?.unassigned || 0)}개` : ''}`}
      {task.status === 'done' && typeof task.result?.selected === 'number' && <p>적합한 키워드 {task.result.selected}개 · 검수 통과 {Number(task.result.ready || 0)}개</p>}
      {!!task.result?.needs_review && <p>품질 검사를 통과하지 못한 글은 예약하지 않았습니다.</p>}</div>}
    {error && loaded && <p role="alert" className="whitespace-pre-line text-sm text-destructive">{error}</p>}
  </Card>
}
