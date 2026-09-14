'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { campaignAPI, type Task } from '@/lib/campaign-api'
import { errMsg } from './common'
import { AutopilotPanel } from './autopilot-panel'

export function AutomationPanel({ campaignId, onComplete }: { campaignId: string; onComplete: () => void }) {
  const [task, setTask] = useState<Task | null>(null)
  const [busy, setBusy] = useState(false)
  const [autoSchedule, setAutoSchedule] = useState(false)
  const [count, setCount] = useState(10)
  const [images, setImages] = useState(5)
  const [startDate, setStartDate] = useState(() => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' }))
  const running = task?.status === 'pending' || task?.status === 'running'

  useEffect(() => {
    let disposed = false
    campaignAPI.listTasks({ campaign_id: campaignId, active_only: false, limit: 20 })
      .then(rows => { if (!disposed) setTask(rows.find(t => t.type === 'automation_pipeline') || null) })
      .catch(() => {})
    return () => { disposed = true }
  }, [campaignId])

  useEffect(() => {
    if (!running || !task) return
    let disposed = false
    const timer = setInterval(async () => {
      try {
        const next = await campaignAPI.getTask(task.id)
        if (disposed) return
        setTask(next)
        if (!['pending', 'running'].includes(next.status)) onComplete()
      } catch { /* Next poll retries a transient read failure. */ }
    }, 3000)
    return () => { disposed = true; clearInterval(timer) }
  }, [running, task?.id, onComplete])

  const start = async () => {
    setBusy(true)
    try {
      setTask(await campaignAPI.startAutomation(campaignId, {
        max_keywords: count, image_count: images, auto_schedule: autoSchedule, start_date: startDate, days: 14,
      }))
      toast.success('서버 자동화를 시작했습니다. 이 화면을 닫아도 계속 진행됩니다.')
    } catch (e) { toast.error('자동화 시작 실패', { description: errMsg(e) }) }
    finally { setBusy(false) }
  }

  return <div className="space-y-4"><AutopilotPanel campaignId={campaignId} onComplete={onComplete} />
    <details><summary className="cursor-pointer text-sm">기존 선택 키워드로 한 번만 준비</summary><Card className="mt-3 space-y-4 p-5">
    <div>
      <h3 className="section-title">선택한 키워드로 자동 준비</h3>
      <p className="mt-1 text-sm text-muted-foreground">원고 생성 → 검수 → 사진 배치를 서버에서 진행합니다. 예약을 켜면 검수 통과 원고를 연결된 블로그의 운영 시간에 배정합니다.</p>
    </div>
    <div className="grid gap-3 sm:grid-cols-3">
      <div><Label htmlFor="auto-count">최대 원고 수</Label><Input id="auto-count" type="number" min={1} max={50} value={count} onChange={e => setCount(Number(e.target.value))} disabled={running} /></div>
      <div><Label htmlFor="auto-images">글당 사진 수</Label><Input id="auto-images" type="number" min={0} max={20} value={images} onChange={e => setImages(Number(e.target.value))} disabled={running} /></div>
      <div><Label htmlFor="auto-date">예약 시작일 (한국 시간)</Label><Input id="auto-date" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} disabled={running} /></div>
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={autoSchedule} onChange={e => setAutoSchedule(e.target.checked)} disabled={running} />검수 통과 원고를 자동 예약 대기열에 등록</label>
    <p className="text-xs text-muted-foreground">사진을 사용하려면 캠페인에 사진 세트를 연결하세요. 생성에는 설정된 AI 사용 요금이 발생하며, 네이버 등록에는 로그인된 실행 기기가 필요합니다.</p>
    <div className="flex gap-3">
      <Button onClick={start} disabled={busy || running || count < 1 || count > 50 || images < 0 || images > 20 || !startDate}>{running ? '자동 준비 중' : '자동 준비 시작'}</Button>
      {running && task && <Button variant="outline" onClick={async () => {
        try { await campaignAPI.cancelTask(task.id); setTask({ ...task, status: 'cancelled' }); onComplete() }
        catch (e) { toast.error('중단 요청 실패', { description: errMsg(e) }) }
      }}>준비 중단</Button>}
    </div>
    {task && <p className="text-sm" role="status">{task.status === 'done' ? '준비 완료 — 원고함과 예약 목록을 확인하세요.' : task.status === 'failed' ? task.error : task.status === 'cancelled' ? '준비가 중단되었습니다.' : task.message || '작업 대기 중'}</p>}
  </Card></details></div>
}
