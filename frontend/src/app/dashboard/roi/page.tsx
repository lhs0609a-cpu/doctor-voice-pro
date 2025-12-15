'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  CircleDollarSign,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Users,
  Eye,
  Phone,
  Calendar,
  Loader2,
  Plus,
  RefreshCw,
  ArrowRight,
  Target,
  Percent
} from 'lucide-react'
import { roiAPI, ROIDashboard, KeywordROI, EventType } from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'

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
        keyword: eventForm.keyword,
        event_type: eventForm.event_type,
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
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
        <DashboardNav />
        <main className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        </main>
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <DashboardNav />

      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <CircleDollarSign className="h-8 w-8 text-green-600" />
              마케팅 ROI 트래커
            </h1>
            <p className="text-gray-600 mt-1">
              블로그 마케팅의 투자 대비 수익률을 분석하세요
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleRefresh} disabled={isRefreshing}>
              {isRefreshing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              새로고침
            </Button>
            <Dialog open={isEventDialogOpen} onOpenChange={setIsEventDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
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
                    {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    기록하기
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">총 조회</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {summary.total_views.toLocaleString()}
                  </p>
                </div>
                <Eye className="h-8 w-8 text-blue-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">상담문의</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {summary.total_inquiries.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-400">
                    전환율 {formatPercent(summary.conversion_rate_inquiry)}
                  </p>
                </div>
                <Phone className="h-8 w-8 text-purple-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">내원</p>
                  <p className="text-2xl font-bold text-green-600">
                    {summary.total_visits.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-400">
                    전환율 {formatPercent(summary.conversion_rate_visit)}
                  </p>
                </div>
                <Users className="h-8 w-8 text-green-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">총 매출</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {formatCurrency(summary.total_revenue)}
                  </p>
                </div>
                <CircleDollarSign className="h-8 w-8 text-orange-200" />
              </div>
            </CardContent>
          </Card>
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
                  <Target className="h-5 w-5" />
                  전환 퍼널
                </CardTitle>
                <CardDescription>
                  조회부터 매출까지의 전환 과정을 분석합니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col md:flex-row items-center justify-center gap-4 py-8">
                  {/* View Stage */}
                  <div className="flex flex-col items-center">
                    <div className="w-32 h-32 bg-blue-100 rounded-lg flex flex-col items-center justify-center">
                      <Eye className="h-8 w-8 text-blue-600 mb-2" />
                      <span className="text-2xl font-bold text-blue-700">
                        {summary.total_views.toLocaleString()}
                      </span>
                      <span className="text-sm text-blue-600">조회</span>
                    </div>
                    <span className="text-xs text-gray-500 mt-2">100%</span>
                  </div>

                  <ArrowRight className="h-6 w-6 text-gray-300 hidden md:block" />
                  <div className="text-center md:hidden py-2">
                    <span className="text-sm text-gray-500">
                      {formatPercent(summary.conversion_rate_inquiry)} 전환
                    </span>
                  </div>

                  {/* Inquiry Stage */}
                  <div className="flex flex-col items-center">
                    <div className="w-28 h-28 bg-purple-100 rounded-lg flex flex-col items-center justify-center">
                      <Phone className="h-7 w-7 text-purple-600 mb-2" />
                      <span className="text-xl font-bold text-purple-700">
                        {summary.total_inquiries.toLocaleString()}
                      </span>
                      <span className="text-sm text-purple-600">상담</span>
                    </div>
                    <span className="text-xs text-gray-500 mt-2">
                      {formatPercent(summary.conversion_rate_inquiry)}
                    </span>
                  </div>

                  <ArrowRight className="h-6 w-6 text-gray-300 hidden md:block" />
                  <div className="text-center md:hidden py-2">
                    <span className="text-sm text-gray-500">
                      {formatPercent(summary.conversion_rate_visit)} 전환
                    </span>
                  </div>

                  {/* Visit Stage */}
                  <div className="flex flex-col items-center">
                    <div className="w-24 h-24 bg-green-100 rounded-lg flex flex-col items-center justify-center">
                      <Users className="h-6 w-6 text-green-600 mb-2" />
                      <span className="text-lg font-bold text-green-700">
                        {summary.total_visits.toLocaleString()}
                      </span>
                      <span className="text-sm text-green-600">내원</span>
                    </div>
                    <span className="text-xs text-gray-500 mt-2">
                      {formatPercent(summary.conversion_rate_visit)}
                    </span>
                  </div>

                  <ArrowRight className="h-6 w-6 text-gray-300 hidden md:block" />
                  <div className="text-center md:hidden py-2">
                    <span className="text-sm text-gray-500">
                      {formatPercent(summary.conversion_rate_reservation)} 전환
                    </span>
                  </div>

                  {/* Revenue Stage */}
                  <div className="flex flex-col items-center">
                    <div className="w-20 h-20 bg-orange-100 rounded-lg flex flex-col items-center justify-center">
                      <CircleDollarSign className="h-5 w-5 text-orange-600 mb-1" />
                      <span className="text-sm font-bold text-orange-700">
                        {(summary.total_revenue / 10000).toFixed(0)}만
                      </span>
                      <span className="text-xs text-orange-600">매출</span>
                    </div>
                    <span className="text-xs text-gray-500 mt-2">
                      {formatPercent(summary.conversion_rate_reservation)}
                    </span>
                  </div>
                </div>

                {/* Conversion Rate Summary */}
                <div className="grid grid-cols-3 gap-4 mt-8 border-t pt-6">
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <span className="text-sm text-gray-500">조회 → 상담</span>
                    </div>
                    <div className="text-xl font-bold text-purple-600">
                      {formatPercent(summary.conversion_rate_inquiry)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <span className="text-sm text-gray-500">상담 → 내원</span>
                    </div>
                    <div className="text-xl font-bold text-green-600">
                      {formatPercent(summary.conversion_rate_visit)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <span className="text-sm text-gray-500">전체 전환율</span>
                    </div>
                    <div className="text-xl font-bold text-orange-600">
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
                  <BarChart3 className="h-5 w-5" />
                  키워드별 ROI 분석
                </CardTitle>
                <CardDescription>
                  각 키워드의 투자 대비 수익률을 분석합니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                {keywordROIs.length === 0 ? (
                  <div className="text-center py-12">
                    <BarChart3 className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">아직 키워드 ROI 데이터가 없습니다</p>
                    <p className="text-sm text-gray-400 mt-1">
                      전환 이벤트를 기록하면 키워드별 ROI를 분석할 수 있습니다
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>키워드</TableHead>
                        <TableHead className="text-right">조회</TableHead>
                        <TableHead className="text-right">상담</TableHead>
                        <TableHead className="text-right">내원</TableHead>
                        <TableHead className="text-right">매출</TableHead>
                        <TableHead className="text-right">비용</TableHead>
                        <TableHead className="text-right">ROI</TableHead>
                        <TableHead className="text-right">전환율</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {keywordROIs.map((kw, index) => (
                        <TableRow key={index}>
                          <TableCell className="font-medium">{kw.keyword}</TableCell>
                          <TableCell className="text-right">
                            {kw.views.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            {kw.inquiries.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            {kw.visits.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatCurrency(kw.revenue)}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatCurrency(kw.cost)}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge
                              variant={kw.roi_percentage >= 100 ? 'default' : 'secondary'}
                              className={
                                kw.roi_percentage >= 200
                                  ? 'bg-green-100 text-green-700'
                                  : kw.roi_percentage >= 100
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-gray-100 text-gray-700'
                              }
                            >
                              {kw.roi_percentage >= 0 ? '+' : ''}
                              {kw.roi_percentage.toFixed(0)}%
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            {formatPercent(kw.conversion_rate)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Channels Tab */}
          <TabsContent value="channels">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Percent className="h-5 w-5" />
                  채널별 성과 분석
                </CardTitle>
                <CardDescription>
                  각 마케팅 채널의 성과를 비교 분석합니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!dashboard?.channel_breakdown ||
                Object.keys(dashboard.channel_breakdown).length === 0 ? (
                  <div className="text-center py-12">
                    <BarChart3 className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">아직 채널별 데이터가 없습니다</p>
                    <p className="text-sm text-gray-400 mt-1">
                      전환 이벤트를 기록하면 채널별 성과를 분석할 수 있습니다
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {Object.entries(dashboard.channel_breakdown).map(
                      ([channel, data]) => {
                        const channelLabel =
                          CHANNELS.find((c) => c.value === channel)?.label || channel
                        const conversionRate =
                          data.views > 0
                            ? ((data.visits / data.views) * 100).toFixed(1)
                            : '0'

                        return (
                          <div
                            key={channel}
                            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                          >
                            <div className="flex items-center gap-4">
                              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                                <span className="text-lg font-bold text-blue-600">
                                  {channelLabel.charAt(0)}
                                </span>
                              </div>
                              <div>
                                <div className="font-medium">{channelLabel}</div>
                                <div className="text-sm text-gray-500">
                                  조회 {data.views.toLocaleString()} · 상담{' '}
                                  {data.inquiries.toLocaleString()} · 내원{' '}
                                  {data.visits.toLocaleString()}
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold text-green-600">
                                {formatCurrency(data.revenue)}
                              </div>
                              <div className="text-sm text-gray-500">
                                전환율 {conversionRate}%
                              </div>
                            </div>
                          </div>
                        )
                      }
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
