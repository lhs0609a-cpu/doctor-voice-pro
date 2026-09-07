'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
import {
  Loader2,
  Plus,
  Calendar,
  Play,
  Pause,
  Trash2,
  Zap,
  CalendarDays,
} from 'lucide-react'
import { scheduleAPI, postsAPI, type Schedule, type OptimalTime, type UpcomingPost } from '@/lib/api'
import { toast } from 'sonner'
import { format, parseISO } from 'date-fns'
import { ko } from 'date-fns/locale'

const daysOfWeek = [
  { value: 0, label: '일' },
  { value: 1, label: '월' },
  { value: 2, label: '화' },
  { value: 3, label: '수' },
  { value: 4, label: '목' },
  { value: 5, label: '금' },
  { value: 6, label: '토' },
]

const statusTones: Record<string, 'ok' | 'warn' | 'danger' | 'accent' | 'muted'> = {
  active: 'ok',
  paused: 'warn',
  completed: 'muted',
  cancelled: 'danger',
}

const statusLabels: Record<string, string> = {
  active: '활성',
  paused: '일시정지',
  completed: '완료',
  cancelled: '취소됨',
}

// 예약 발행 프리셋
const SCHEDULE_PRESETS = [
  {
    id: 'weekday_morning',
    name: '평일 오전 발행',
    description: '월~금 오전 9시 자동 발행',
    schedule_type: 'recurring' as const,
    recurrence_pattern: 'weekly' as const,
    days_of_week: [1, 2, 3, 4, 5],
    scheduled_time: '09:00',
    recommended: true,
  },
  {
    id: 'mwf_afternoon',
    name: '월수금 오후 발행',
    description: '월/수/금 오후 2시 발행',
    schedule_type: 'recurring' as const,
    recurrence_pattern: 'weekly' as const,
    days_of_week: [1, 3, 5],
    scheduled_time: '14:00',
  },
  {
    id: 'daily_evening',
    name: '매일 저녁 발행',
    description: '매일 오후 7시 자동 발행',
    schedule_type: 'recurring' as const,
    recurrence_pattern: 'daily' as const,
    days_of_week: [],
    scheduled_time: '19:00',
  },
  {
    id: 'weekend_only',
    name: '주말 발행',
    description: '토/일 오전 10시 발행',
    schedule_type: 'recurring' as const,
    recurrence_pattern: 'weekly' as const,
    days_of_week: [0, 6],
    scheduled_time: '10:00',
  },
]

export default function SchedulePage() {
  const router = useRouter()
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [upcoming, setUpcoming] = useState<UpcomingPost[]>([])
  const [optimalTimes, setOptimalTimes] = useState<OptimalTime[]>([])
  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  // 새 예약 폼 상태
  const [newSchedule, setNewSchedule] = useState({
    name: '',
    schedule_type: 'one_time' as 'one_time' | 'recurring',
    scheduled_time: '10:00',
    scheduled_date: '',
    post_id: '',
    recurrence_pattern: 'weekly' as 'daily' | 'weekly' | 'monthly',
    days_of_week: [1, 3, 5] as number[],
    day_of_month: 1,
    auto_hashtags: true,
  })
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null)

  // 프리셋 적용 함수
  const applyPreset = (presetId: string) => {
    const preset = SCHEDULE_PRESETS.find(p => p.id === presetId)
    if (!preset) return

    setNewSchedule(prev => ({
      ...prev,
      name: preset.name,
      schedule_type: preset.schedule_type,
      recurrence_pattern: preset.recurrence_pattern,
      days_of_week: preset.days_of_week,
      scheduled_time: preset.scheduled_time,
    }))
    setSelectedPreset(presetId)
    toast.success(`"${preset.name}" 프리셋이 적용되었습니다`)
  }

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [schedulesData, upcomingData, optimalData, postsData] = await Promise.all([
        scheduleAPI.getList(),
        scheduleAPI.getUpcoming({ days: 7 }),
        scheduleAPI.getOptimalTimes(),
        postsAPI.list(1, 50),
      ])

      setSchedules(schedulesData)
      setUpcoming(upcomingData)
      setOptimalTimes(optimalData)
      setPosts(postsData.posts || [])
    } catch (error) {
      console.error('Failed to load data:', error)
      toast.error('데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateSchedule = async () => {
    if (!newSchedule.post_id && newSchedule.schedule_type === 'one_time') {
      toast.error('발행할 글을 선택해주세요')
      return
    }

    setCreating(true)
    try {
      const data: any = {
        name: newSchedule.name || undefined,
        schedule_type: newSchedule.schedule_type,
        scheduled_time: newSchedule.scheduled_time,
        auto_hashtags: newSchedule.auto_hashtags,
      }

      if (newSchedule.schedule_type === 'one_time') {
        data.scheduled_date = newSchedule.scheduled_date
        data.post_id = newSchedule.post_id
      } else {
        data.recurrence_pattern = newSchedule.recurrence_pattern
        if (newSchedule.recurrence_pattern === 'weekly') {
          data.days_of_week = newSchedule.days_of_week
        } else if (newSchedule.recurrence_pattern === 'monthly') {
          data.day_of_month = newSchedule.day_of_month
        }
        if (newSchedule.post_id) {
          data.post_id = newSchedule.post_id
        }
      }

      await scheduleAPI.create(data)
      toast.success('예약이 생성되었습니다')
      setShowCreateDialog(false)
      loadData()

      // 폼 초기화
      setNewSchedule({
        name: '',
        schedule_type: 'one_time',
        scheduled_time: '10:00',
        scheduled_date: '',
        post_id: '',
        recurrence_pattern: 'weekly',
        days_of_week: [1, 3, 5],
        day_of_month: 1,
        auto_hashtags: true,
      })
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '예약 생성에 실패했습니다')
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (scheduleId: string) => {
    try {
      await scheduleAPI.toggle(scheduleId)
      toast.success('예약 상태가 변경되었습니다')
      loadData()
    } catch (error) {
      toast.error('상태 변경에 실패했습니다')
    }
  }

  const handleDelete = async (scheduleId: string) => {
    if (!confirm('이 예약을 삭제하시겠습니까?')) return

    try {
      await scheduleAPI.delete(scheduleId)
      toast.success('예약이 삭제되었습니다')
      loadData()
    } catch (error) {
      toast.error('삭제에 실패했습니다')
    }
  }

  const formatScheduleTime = (schedule: Schedule) => {
    if (schedule.schedule_type === 'one_time') {
      return schedule.scheduled_date
        ? `${schedule.scheduled_date} ${schedule.scheduled_time}`
        : schedule.scheduled_time
    }

    if (schedule.recurrence_pattern === 'daily') {
      return `매일 ${schedule.scheduled_time}`
    }

    if (schedule.recurrence_pattern === 'weekly' && schedule.days_of_week) {
      const days = schedule.days_of_week.map(d => daysOfWeek.find(day => day.value === d)?.label).join(', ')
      return `매주 ${days} ${schedule.scheduled_time}`
    }

    if (schedule.recurrence_pattern === 'monthly') {
      return `매월 ${schedule.day_of_month}일 ${schedule.scheduled_time}`
    }

    return schedule.scheduled_time
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="예약 발행"
        description="네이버 블로그 자동 발행 스케줄을 관리하세요"
        actions={
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" />
                새 예약
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>새 예약 만들기</DialogTitle>
                <DialogDescription>
                  네이버 블로그 자동 발행 예약을 설정하세요
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4">
                {/* 원클릭 프리셋 */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-warning" />
                    빠른 설정 (프리셋)
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    {SCHEDULE_PRESETS.map((preset) => (
                      <button
                        key={preset.id}
                        onClick={() => applyPreset(preset.id)}
                        className={`rounded-lg border p-3 text-left transition-colors ${
                          selectedPreset === preset.id
                            ? 'border-primary bg-accent ring-2 ring-ring/30'
                            : 'hover:bg-muted/40'
                        }`}
                      >
                        <div className="mb-1 flex items-center gap-2">
                          <span className="text-sm font-medium">{preset.name}</span>
                          {preset.recommended && (
                            <Pill tone="ok">추천</Pill>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{preset.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">또는 직접 설정</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>예약 이름 (선택)</Label>
                  <Input
                    placeholder="예: 주간 건강정보 발행"
                    value={newSchedule.name}
                    onChange={(e) => setNewSchedule({ ...newSchedule, name: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label>예약 유형</Label>
                  <Select
                    value={newSchedule.schedule_type}
                    onValueChange={(v: any) => setNewSchedule({ ...newSchedule, schedule_type: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="one_time">1회성 예약</SelectItem>
                      <SelectItem value="recurring">반복 예약</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>발행할 글</Label>
                  <Select
                    value={newSchedule.post_id}
                    onValueChange={(v) => setNewSchedule({ ...newSchedule, post_id: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="글 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {posts.map((post) => (
                        <SelectItem key={post.id} value={post.id}>
                          {post.title || '제목 없음'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {newSchedule.schedule_type === 'one_time' && (
                  <div className="space-y-2">
                    <Label>발행 날짜</Label>
                    <Input
                      type="date"
                      value={newSchedule.scheduled_date}
                      onChange={(e) => setNewSchedule({ ...newSchedule, scheduled_date: e.target.value })}
                    />
                  </div>
                )}

                {newSchedule.schedule_type === 'recurring' && (
                  <>
                    <div className="space-y-2">
                      <Label>반복 패턴</Label>
                      <Select
                        value={newSchedule.recurrence_pattern}
                        onValueChange={(v: any) => setNewSchedule({ ...newSchedule, recurrence_pattern: v })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">매일</SelectItem>
                          <SelectItem value="weekly">매주</SelectItem>
                          <SelectItem value="monthly">매월</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {newSchedule.recurrence_pattern === 'weekly' && (
                      <div className="space-y-2">
                        <Label>요일 선택</Label>
                        <div className="flex flex-wrap gap-2">
                          {daysOfWeek.map((day) => (
                            <label
                              key={day.value}
                              className={`flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border-2 text-sm transition-colors ${
                                newSchedule.days_of_week.includes(day.value)
                                  ? 'border-primary bg-primary text-primary-foreground'
                                  : 'hover:border-primary'
                              }`}
                            >
                              <input
                                type="checkbox"
                                className="sr-only"
                                checked={newSchedule.days_of_week.includes(day.value)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setNewSchedule({
                                      ...newSchedule,
                                      days_of_week: [...newSchedule.days_of_week, day.value].sort(),
                                    })
                                  } else {
                                    setNewSchedule({
                                      ...newSchedule,
                                      days_of_week: newSchedule.days_of_week.filter((d) => d !== day.value),
                                    })
                                  }
                                }}
                              />
                              {day.label}
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {newSchedule.recurrence_pattern === 'monthly' && (
                      <div className="space-y-2">
                        <Label>발행일</Label>
                        <Select
                          value={String(newSchedule.day_of_month)}
                          onValueChange={(v) => setNewSchedule({ ...newSchedule, day_of_month: parseInt(v) })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                              <SelectItem key={day} value={String(day)}>
                                매월 {day}일
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </>
                )}

                <div className="space-y-2">
                  <Label>발행 시간</Label>
                  <Input
                    type="time"
                    value={newSchedule.scheduled_time}
                    onChange={(e) => setNewSchedule({ ...newSchedule, scheduled_time: e.target.value })}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Switch
                    id="auto-hashtags"
                    checked={newSchedule.auto_hashtags}
                    onCheckedChange={(checked: boolean) => setNewSchedule({ ...newSchedule, auto_hashtags: checked })}
                  />
                  <Label htmlFor="auto-hashtags">자동 해시태그 추가</Label>
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                  취소
                </Button>
                <Button onClick={handleCreateSchedule} disabled={creating}>
                  {creating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      생성 중...
                    </>
                  ) : (
                    '예약 만들기'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* 예약 목록 */}
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                예약 목록
              </CardTitle>
              <CardDescription>
                등록된 발행 예약 {schedules.length}개
              </CardDescription>
            </CardHeader>
            <CardContent>
              {schedules.length === 0 ? (
                <EmptyState
                  icon={<Calendar className="h-8 w-8" />}
                  title="등록된 예약이 없습니다"
                  description="새 예약을 만들어 블로그 글을 자동으로 발행해보세요"
                  action={
                    <Button variant="outline" onClick={() => setShowCreateDialog(true)}>
                      <Plus className="h-4 w-4" />
                      새 예약 만들기
                    </Button>
                  }
                />
              ) : (
                <div className="rounded-lg border">
                  {schedules.map((schedule) => (
                    <ListRow key={schedule.id} className="justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {schedule.name || schedule.post_title || '제목 없음'}
                          </span>
                          <Pill tone={statusTones[schedule.status] || 'muted'}>
                            {statusLabels[schedule.status]}
                          </Pill>
                          <Pill tone="muted">
                            {schedule.schedule_type === 'one_time' ? '1회' : '반복'}
                          </Pill>
                        </div>
                        <p className="text-sm tabular-nums text-muted-foreground">
                          {formatScheduleTime(schedule)}
                        </p>
                        {schedule.next_execution_at && (
                          <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                            다음 발행: {format(parseISO(schedule.next_execution_at), 'PPpp', { locale: ko })}
                          </p>
                        )}
                        <p className="text-xs tabular-nums text-muted-foreground">
                          실행 횟수: {schedule.execution_count}회
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleToggle(schedule.id)}
                        >
                          {schedule.status === 'active' ? (
                            <Pause className="h-4 w-4" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(schedule.id)}
                        >
                          <Trash2 className="h-4 w-4 text-danger" />
                        </Button>
                      </div>
                    </ListRow>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 예정된 발행 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-muted-foreground" />
                이번 주 예정된 발행
              </CardTitle>
            </CardHeader>
            <CardContent>
              {upcoming.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  예정된 발행이 없습니다
                </p>
              ) : (
                <div className="rounded-lg border">
                  {upcoming.map((item) => (
                    <ListRow key={item.schedule_id} className="justify-between">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{item.post_title || item.schedule_name || '제목 없음'}</p>
                        <p className="text-sm tabular-nums text-muted-foreground">
                          {format(parseISO(item.next_execution_at), 'M월 d일 (E) HH:mm', { locale: ko })}
                        </p>
                      </div>
                      <Pill tone="muted">{item.schedule_type === 'one_time' ? '1회' : '반복'}</Pill>
                    </ListRow>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 최적 시간 추천 */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-warning" />
                최적 발행 시간
              </CardTitle>
              <CardDescription>
                데이터 기반 추천 발행 시간대
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border">
                {optimalTimes.slice(0, 5).map((time, index) => (
                  <ListRow key={index} className="justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-semibold tabular-nums text-primary">
                        {index + 1}
                      </div>
                      <div>
                        <p className="font-medium tabular-nums">
                          {time.day_name}요일 {time.recommended_hour}:
                          {String(time.recommended_minute).padStart(2, '0')}
                        </p>
                        <p className="text-[13px] tabular-nums text-muted-foreground">
                          참여율 {time.engagement_score.toFixed(0)}점
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setNewSchedule({
                          ...newSchedule,
                          schedule_type: 'recurring',
                          recurrence_pattern: 'weekly',
                          days_of_week: [time.day_of_week],
                          scheduled_time: `${String(time.recommended_hour).padStart(2, '0')}:${String(time.recommended_minute).padStart(2, '0')}`,
                        })
                        setShowCreateDialog(true)
                      }}
                    >
                      적용
                    </Button>
                  </ListRow>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
