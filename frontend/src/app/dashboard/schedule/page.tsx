'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
import { Checkbox } from '@/components/ui/checkbox'
import {
  Loader2,
  Plus,
  Calendar,
  Clock,
  Play,
  Pause,
  Trash2,
  RefreshCw,
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

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  paused: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-gray-100 text-gray-800',
  cancelled: 'bg-red-100 text-red-800',
}

const statusLabels: Record<string, string> = {
  active: '활성',
  paused: '일시정지',
  completed: '완료',
  cancelled: '취소됨',
}

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
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">예약 발행</h1>
          <p className="text-muted-foreground">네이버 블로그 자동 발행 스케줄을 관리하세요</p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              새 예약
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>새 예약 생성</DialogTitle>
              <DialogDescription>
                네이버 블로그 자동 발행 예약을 설정하세요
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
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
                            className={`flex items-center justify-center w-10 h-10 rounded-full cursor-pointer border-2 transition-colors ${
                              newSchedule.days_of_week.includes(day.value)
                                ? 'bg-primary text-primary-foreground border-primary'
                                : 'border-gray-200 hover:border-primary'
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

              <div className="flex items-center space-x-2">
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
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    생성 중...
                  </>
                ) : (
                  '예약 생성'
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* 예약 목록 */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                예약 목록
              </CardTitle>
              <CardDescription>
                등록된 발행 예약 {schedules.length}개
              </CardDescription>
            </CardHeader>
            <CardContent>
              {schedules.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  등록된 예약이 없습니다
                </div>
              ) : (
                <div className="space-y-4">
                  {schedules.map((schedule) => (
                    <div
                      key={schedule.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium">
                            {schedule.name || schedule.post_title || '제목 없음'}
                          </span>
                          <Badge className={statusColors[schedule.status]}>
                            {statusLabels[schedule.status]}
                          </Badge>
                          <Badge variant="outline">
                            {schedule.schedule_type === 'one_time' ? '1회' : '반복'}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {formatScheduleTime(schedule)}
                        </p>
                        {schedule.next_execution_at && (
                          <p className="text-xs text-muted-foreground mt-1">
                            다음 발행: {format(parseISO(schedule.next_execution_at), 'PPpp', { locale: ko })}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">
                          실행 횟수: {schedule.execution_count}회
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
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
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 예정된 발행 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarDays className="h-5 w-5" />
                이번 주 예정된 발행
              </CardTitle>
            </CardHeader>
            <CardContent>
              {upcoming.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground">
                  예정된 발행이 없습니다
                </div>
              ) : (
                <div className="space-y-3">
                  {upcoming.map((item) => (
                    <div
                      key={item.schedule_id}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div>
                        <p className="font-medium">{item.post_title || item.schedule_name || '제목 없음'}</p>
                        <p className="text-sm text-muted-foreground">
                          {format(parseISO(item.next_execution_at), 'M월 d일 (E) HH:mm', { locale: ko })}
                        </p>
                      </div>
                      <Badge variant="outline">{item.schedule_type === 'one_time' ? '1회' : '반복'}</Badge>
                    </div>
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
                <Zap className="h-5 w-5 text-yellow-500" />
                최적 발행 시간
              </CardTitle>
              <CardDescription>
                데이터 기반 추천 발행 시간대
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {optimalTimes.slice(0, 5).map((time, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-bold">
                        {index + 1}
                      </div>
                      <div>
                        <p className="font-medium">
                          {time.day_name}요일 {time.recommended_hour}:
                          {String(time.recommended_minute).padStart(2, '0')}
                        </p>
                        <p className="text-sm text-muted-foreground">
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
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
