'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
import {
  CircleDollarSign,
  BarChart3,
  Users,
  Eye,
  Phone,
  Loader2,
  Plus,
  RefreshCw,
  ArrowRight,
  Target,
  Percent
} from 'lucide-react'
import { roiAPI, ROIDashboard, KeywordROI, EventType } from '@/lib/api'
import { toast } from 'sonner'

interface EventFormData {
  keyword: string
  event_type: EventType
  source: string
  channel: string
  revenue: string
}

const EVENT_TYPES = [
  { value: 'view', label: '조회' },
  { value: 'inquiry', label: '상담문의' },
  { value: 'visit', label: '내원' },
  { value: 'reservation', label: '예약' },
]

const CHANNELS = [
  { value: 'naver_blog', label: '네이버 블로그' },
  { value: 'naver_place', label: '네이버 플레이스' },
  { value: 'instagram', label: '인스타그램' },
  { value: 'facebook', label: '페이스북' },
  { value: 'youtube', label: '유튜브' },
  { value: 'other', label: '기타' },
]

const SOURCES = [
  { value: 'blog', label: '블로그' },
  { value: 'place', label: '플레이스' },
  { value: 'sns', label: 'SNS' },
  { value: 'referral', label: '소개' },
  { value: 'direct', label: '직접방문' },
]

const TABLE_HEAD = 'text-[12px] font-medium uppercase tracking-wide text-muted-foreground'

export default function ROIPage() {
  const [dashboard, setDashboard] = useState<ROIDashboard | null>(null)
  const [keywordROIs, setKeywordROIs] = useState<KeywordROI[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [isEventDialogOpen, setIsEventDialogOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [eventForm, setEventForm] = useState<EventFormData>({
    keyword: '',
    event_type: 'view',
    source: 'blog',
    channel: 'naver_blog',
    revenue: '',
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [dashboardData, keywordsData] = await Promise.all([
        roiAPI.getDashboard(),
        roiAPI.getKeywordROI(),
      ])
      setDashboard(dashboardData)
      setKeywordROIs(keywordsData || [])
    } catch (error) {
      console.error('Failed to load ROI data:', error)
      toast.error('데이터 로딩 실패', {
        description: 'ROI 데이터를 불러오는데 실패했습니다.',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      const now = new Date()
      await roiAPI.calculateMonthly(now.getFullYear(), now.getMonth() + 1)
      await loadData()
      toast.success('데이터 새로고침 완료')
    } catch (error) {
      toast.error('새로고침 실패')
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleCreateEvent = async () => {
    if (!eventForm.keyword) {
      toast.error('키워드를 입력해주세요')
      return
    }

    setIsSubmitting(true)
    try {
      await roiAPI.createEvent({
        event_type: eventForm.event_type,
        event_date: new Date().toISOString().split('T')[0],
        keyword: eventForm.keyword,
        source: eventForm.source,
        channel: eventForm.channel,
        revenue: eventForm.revenue ? parseInt(eventForm.revenue) : undefined,
      })
      toast.success('전환 이벤트 기록됨')
      setIsEventDialogOpen(false)
      setEventForm({
        keyword: '',
        event_type: 'view',
        source: 'blog',
        channel: 'naver_blog',
        revenue: '',
      })
      loadData()
    } catch (error: any) {
      toast.error('이벤트 기록 실패', {
        description: error.response?.data?.detail || '오류가 발생했습니다.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
    }).format(value)
  }

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  const summary = dashboard?.summary || {
    total_views: 0,
    total_inquiries: 0,
    total_visits: 0,
    total_reservations: 0,
    total_revenue: 0,
    conversion_rate_inquiry: 0,
    conversion_rate_visit: 0,
    conversion_rate_reservation: 0,
  }

  const funnelStages = [
    {
      key: 'view',
      icon: <Eye className="h-5 w-5" />,
      value: summary.total_views.toLocaleString(),
      label: '조회',
      rate: '100%',
      transition: null as string | null,
    },
    {
      key: 'inquiry',
      icon: <Phone className="h-5 w-5" />,
      value: summary.total_inquiries.toLocaleString(),
      label: '상담',
      rate: formatPercent(summary.conversion_rate_inquiry),
      transition: `${formatPercent(summary.conversion_rate_inquiry)} 전환`,
    },
    {
      key: 'visit',
      icon: <Users className="h-5 w-5" />,
      value: summary.total_visits.toLocaleString(),
      label: '내원',
      rate: formatPercent(summary.conversion_rate_visit),
      transition: `${formatPercent(summary.conversion_rate_visit)} 전환`,
    },
    {
      key: 'revenue',
      icon: <CircleDollarSign className="h-5 w-5" />,
      value: `${(summary.total_revenue / 10000).toFixed(0)}만`,
      label: '매출',
      rate: formatPercent(summary.conversion_rate_reservation),
      transition: `${formatPercent(summary.conversion_rate_reservation)} 전환`,
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="마케팅 ROI"
        description="블로그 마케팅의 투자 대비 수익률을 확인하세요"
        actions={
          <>
            <Button variant="outline" onClick={handleRefresh} disabled={isRefreshing}>
              {isRefreshing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              새로고침
            </Button>
            <Dialog open={isEventDialogOpen} onOpenChange={setIsEventDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4" />
                  전환 이벤트 기록
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>전환 이벤트 기록</DialogTitle>
                  <DialogDescription>
                    조회, 상담문의, 내원, 예약 등 전환 이벤트를 기록하세요
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="keyword">키워드</Label>
                    <Input
                      id="keyword"
                      placeholder="예: 강남 피부과"
                      value={eventForm.keyword}
                      onChange={(e) => setEventForm({ ...eventForm, keyword: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="event_type">이벤트 유형</Label>
                    <Select
                      value={eventForm.event_type}
                      onValueChange={(value) => setEventForm({ ...eventForm, event_type: value as EventType })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {EVENT_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="source">유입 소스</Label>
                      <Select
                        value={eventForm.source}
                        onValueChange={(value) => setEventForm({ ...eventForm, source: value })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SOURCES.map((source) => (
                            <SelectItem key={source.value} value={source.value}>
                              {source.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="channel">채널</Label>
                      <Select
                        value={eventForm.channel}
                        onValueChange={(value) => setEventForm({ ...eventForm, channel: value })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CHANNELS.map((channel) => (
                            <SelectItem key={channel.value} value={channel.value}>
                              {channel.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  {(eventForm.event_type === 'visit' || eventForm.event_type === 'reservation') && (
                    <div className="grid gap-2">
                      <Label htmlFor="revenue">매출액 (원)</Label>
                      <Input
                        id="revenue"
                        type="number"
                        placeholder="예: 500000"
                        value={eventForm.revenue}
                        onChange={(e) => setEventForm({ ...eventForm, revenue: e.target.value })}
                      />
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsEventDialogOpen(false)}>
                    취소
                  </Button>
                  <Button onClick={handleCreateEvent} disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    기록하기
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile
          label="총 조회"
          value={summary.total_views.toLocaleString()}
          icon={<Eye className="h-4 w-4" />}
        />
        <StatTile
          label="상담문의"
          value={summary.total_inquiries.toLocaleString()}
          hint={`전환율 ${formatPercent(summary.conversion_rate_inquiry)}`}
          icon={<Phone className="h-4 w-4" />}
        />
        <StatTile
          label="내원"
          value={summary.total_visits.toLocaleString()}
          hint={`전환율 ${formatPercent(summary.conversion_rate_visit)}`}
          icon={<Users className="h-4 w-4" />}
        />
        <StatTile
          label="총 매출"
          value={formatCurrency(summary.total_revenue)}
          tone="ok"
          icon={<CircleDollarSign className="h-4 w-4" />}
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="overview">전환 퍼널</TabsTrigger>
          <TabsTrigger value="keywords">키워드별 ROI</TabsTrigger>
          <TabsTrigger value="channels">채널 분석</TabsTrigger>
        </TabsList>

        {/* Funnel Tab */}
        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-4 w-4 text-muted-foreground" />
                전환 퍼널
              </CardTitle>
              <CardDescription>
                조회부터 매출까지의 전환 과정을 분석합니다
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col items-center justify-center gap-4 py-6 md:flex-row">
                {funnelStages.map((stage, index) => (
                  <div key={stage.key} className="contents">
                    {index > 0 && (
                      <>
                        <ArrowRight className="hidden h-5 w-5 text-muted-foreground md:block" />
                        <div className="py-1 text-center md:hidden">
                          <span className="text-sm tabular-nums text-muted-foreground">{stage.transition}</span>
                        </div>
                      </>
                    )}
                    <div className="flex flex-col items-center">
                      <div className="flex h-28 w-28 flex-col items-center justify-center gap-1 rounded-lg border bg-muted/40">
                        <div className="text-primary">{stage.icon}</div>
                        <span className="text-lg font-semibold tabular-nums">{stage.value}</span>
                        <span className="text-[13px] text-muted-foreground">{stage.label}</span>
                      </div>
                      <span className="mt-2 text-xs tabular-nums text-muted-foreground">{stage.rate}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Conversion Rate Summary */}
              <div className="grid grid-cols-3 gap-4 border-t pt-4">
                <div className="text-center">
                  <div className="mb-1 text-[13px] font-medium text-muted-foreground">조회 → 상담</div>
                  <div className="kpi">
                    {formatPercent(summary.conversion_rate_inquiry)}
                  </div>
                </div>
                <div className="text-center">
                  <div className="mb-1 text-[13px] font-medium text-muted-foreground">상담 → 내원</div>
                  <div className="kpi">
                    {formatPercent(summary.conversion_rate_visit)}
                  </div>
                </div>
                <div className="text-center">
                  <div className="mb-1 text-[13px] font-medium text-muted-foreground">전체 전환율</div>
                  <div className="kpi">
                    {summary.total_views > 0
                      ? formatPercent((summary.total_visits / summary.total_views) * 100)
                      : '0%'}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Keywords Tab */}
        <TabsContent value="keywords">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                키워드별 ROI 분석
              </CardTitle>
              <CardDescription>
                각 키워드의 투자 대비 수익률을 분석합니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              {keywordROIs.length === 0 ? (
                <EmptyState
                  icon={<BarChart3 className="h-8 w-8" />}
                  title="아직 키워드 ROI 데이터가 없습니다"
                  description="전환 이벤트를 기록하면 키워드별 ROI를 분석할 수 있습니다"
                  action={
                    <Button variant="outline" onClick={() => setIsEventDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      전환 이벤트 기록
                    </Button>
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table className="text-sm">
                    <TableHeader>
                      <TableRow>
                        <TableHead className={TABLE_HEAD}>키워드</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>조회</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>상담</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>내원</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>매출</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>비용</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>ROI</TableHead>
                        <TableHead className={`${TABLE_HEAD} text-right`}>전환율</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {keywordROIs.map((kw, index) => (
                        <TableRow key={index} className="hover:bg-muted/40">
                          <TableCell className="py-2.5 font-medium">{kw.keyword}</TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {kw.views.toLocaleString()}
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {kw.inquiries.toLocaleString()}
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {kw.visits.toLocaleString()}
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {formatCurrency(kw.revenue)}
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {formatCurrency(kw.cost)}
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            <Pill
                              tone={
                                kw.roi_percentage >= 200
                                  ? 'ok'
                                  : kw.roi_percentage >= 100
                                  ? 'accent'
                                  : 'muted'
                              }
                            >
                              {kw.roi_percentage >= 0 ? '+' : ''}
                              {kw.roi_percentage.toFixed(0)}%
                            </Pill>
                          </TableCell>
                          <TableCell className="py-2.5 text-right tabular-nums">
                            {formatPercent(kw.conversion_rate)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Channels Tab */}
        <TabsContent value="channels">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Percent className="h-4 w-4 text-muted-foreground" />
                채널별 성과 분석
              </CardTitle>
              <CardDescription>
                각 마케팅 채널의 성과를 비교합니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!dashboard?.channel_breakdown ||
              Object.keys(dashboard.channel_breakdown).length === 0 ? (
                <EmptyState
                  icon={<BarChart3 className="h-8 w-8" />}
                  title="아직 채널별 데이터가 없습니다"
                  description="전환 이벤트를 기록하면 채널별 성과를 분석할 수 있습니다"
                  action={
                    <Button variant="outline" onClick={() => setIsEventDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      전환 이벤트 기록
                    </Button>
                  }
                />
              ) : (
                <div className="rounded-lg border">
                  {Object.entries(dashboard.channel_breakdown).map(
                    ([channel, data]) => {
                      const channelLabel =
                        CHANNELS.find((c) => c.value === channel)?.label || channel
                      const conversionRate =
                        data.views > 0
                          ? ((data.visits / data.views) * 100).toFixed(1)
                          : '0'

                      return (
                        <ListRow key={channel} className="justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-primary">
                              <span className="text-sm font-semibold">
                                {channelLabel.charAt(0)}
                              </span>
                            </div>
                            <div>
                              <div className="font-medium">{channelLabel}</div>
                              <div className="text-[13px] tabular-nums text-muted-foreground">
                                조회 {data.views.toLocaleString()} · 상담{' '}
                                {data.inquiries.toLocaleString()} · 내원{' '}
                                {data.visits.toLocaleString()}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold tabular-nums text-success">
                              {formatCurrency(data.revenue)}
                            </div>
                            <div className="text-[13px] tabular-nums text-muted-foreground">
                              전환율 {conversionRate}%
                            </div>
                          </div>
                        </ListRow>
                      )
                    }
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
