'use client'

import { useEffect, useState } from 'react'
import { analyticsAPI } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import {
  TrendingUp,
  TrendingDown,
  FileText,
  Clock,
  Target,
  Calendar,
  Hash,
  Award,
} from 'lucide-react'

interface OverviewData {
  total_posts: number
  average_persuasion_score: number
  posts_this_month: number
  posts_this_week: number
  time_saved_minutes: number
  status_breakdown: {
    draft: number
    published: number
    archived: number
  }
  top_keywords: Array<{ keyword: string; count: number }>
  persuasion_trend: Array<{ date: string; score: number; count: number }>
}

interface ComparisonData {
  this_month: {
    count: number
    avg_score: number
    published: number
  }
  last_month: {
    count: number
    avg_score: number
    published: number
  }
  changes: {
    count_change_percent: number
    score_change_percent: number
    published_change_percent: number
  }
}

interface TrendsData {
  period_days: number
  total_posts: number
  daily_average: number
  score_trend: Array<{
    date: string
    average_score: number
    max_score: number
    min_score: number
  }>
  volume_trend: Array<{
    date: string
    count: number
  }>
}

const CHART = {
  primary: 'hsl(var(--primary))',
  secondary: 'hsl(var(--muted-foreground))',
  success: 'hsl(var(--success))',
  warning: 'hsl(var(--warning))',
  danger: 'hsl(var(--danger))',
  grid: 'hsl(var(--border))',
}

const AXIS_TICK = { fill: 'hsl(var(--muted-foreground))', fontSize: 12 }

const TOOLTIP_STYLE = {
  background: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: 10,
  fontSize: 13,
}

const LEGEND_STYLE = { fontSize: 12 }

const formatShortDate = (value: string) => {
  const date = new Date(value)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const formatFullDate = (value: string) => new Date(value).toLocaleDateString('ko-KR')

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [comparison, setComparison] = useState<ComparisonData | null>(null)
  const [trends, setTrends] = useState<TrendsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [trendDays, setTrendDays] = useState(30)

  useEffect(() => {
    loadData()
  }, [trendDays])

  const loadData = async () => {
    try {
      setLoading(true)
      const [overviewData, comparisonData, trendsData] = await Promise.all([
        analyticsAPI.getOverview(),
        analyticsAPI.getComparison(),
        analyticsAPI.getTrends(trendDays),
      ])
      setOverview(overviewData)
      setComparison(comparisonData)
      setTrends(trendsData)
    } catch (error) {
      console.error('Failed to load analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  if (!overview || !comparison || !trends) {
    return (
      <div className="space-y-6">
        <PageHeader title="분석" description="포스팅 성과와 통계를 한눈에 확인하세요" />
        <EmptyState
          title="데이터를 불러올 수 없습니다"
          description="잠시 후 다시 시도해 주세요."
          action={<Button onClick={loadData}>다시 불러오기</Button>}
        />
      </div>
    )
  }

  // Prepare pie chart data
  const statusData = [
    { name: '작성중', value: overview.status_breakdown.draft, color: CHART.warning },
    { name: '발행됨', value: overview.status_breakdown.published, color: CHART.success },
    { name: '보관됨', value: overview.status_breakdown.archived || 0, color: CHART.secondary },
  ].filter((item) => item.value > 0)

  const renderChangeIndicator = (change: number) => {
    if (change > 0) {
      return (
        <span className="flex items-center text-sm tabular-nums text-success">
          <TrendingUp className="mr-1 h-4 w-4" />
          {change.toFixed(1)}%
        </span>
      )
    } else if (change < 0) {
      return (
        <span className="flex items-center text-sm tabular-nums text-danger">
          <TrendingDown className="mr-1 h-4 w-4" />
          {Math.abs(change).toFixed(1)}%
        </span>
      )
    }
    return <span className="text-sm text-muted-foreground">변화 없음</span>
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="분석"
        description="포스팅 성과와 통계를 한눈에 확인하세요"
        actions={
          <Button onClick={loadData} variant="outline">
            새로고침
          </Button>
        }
      />

      {/* Overview Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="전체 포스팅"
          value={overview.total_posts}
          hint={`이번 달 ${overview.posts_this_month}개`}
          icon={<FileText className="h-4 w-4" />}
        />
        <StatTile
          label="평균 설득력"
          value={`${overview.average_persuasion_score}/100`}
          hint="전체 포스팅 평균"
          icon={<Target className="h-4 w-4" />}
        />
        <StatTile
          label="시간 절약"
          value={`${Math.floor(overview.time_saved_minutes / 60)}시간`}
          hint={`${overview.time_saved_minutes % 60}분`}
          icon={<Clock className="h-4 w-4" />}
        />
        <StatTile
          label="이번 주"
          value={overview.posts_this_week}
          hint="최근 7일간 작성"
          icon={<Calendar className="h-4 w-4" />}
        />
      </div>

      {/* Month Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>월별 비교</CardTitle>
          <CardDescription>이번 달과 지난 달의 성과를 비교합니다</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <p className="text-[13px] font-medium text-muted-foreground">포스팅 수</p>
              <div className="flex items-baseline gap-2">
                <span className="kpi">{comparison.this_month.count}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  / {comparison.last_month.count} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.count_change_percent)}
            </div>

            <div className="space-y-2">
              <p className="text-[13px] font-medium text-muted-foreground">평균 설득력</p>
              <div className="flex items-baseline gap-2">
                <span className="kpi">{comparison.this_month.avg_score.toFixed(1)}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  / {comparison.last_month.avg_score.toFixed(1)} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.score_change_percent)}
            </div>

            <div className="space-y-2">
              <p className="text-[13px] font-medium text-muted-foreground">발행된 포스팅</p>
              <div className="flex items-baseline gap-2">
                <span className="kpi">{comparison.this_month.published}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  / {comparison.last_month.published} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.published_change_percent)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Status Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>포스팅 상태</CardTitle>
            <CardDescription>전체 포스팅의 상태 분포</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill={CHART.primary}
                  stroke="hsl(var(--card))"
                  dataKey="value"
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Top Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-muted-foreground" />
              인기 키워드
            </CardTitle>
            <CardDescription>가장 많이 사용된 키워드 Top 10</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {overview.top_keywords.slice(0, 10).map((item, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Pill tone={index < 3 ? 'accent' : 'muted'}>{index + 1}</Pill>
                    <span className="text-sm font-medium">{item.keyword}</span>
                  </div>
                  <span className="text-sm tabular-nums text-muted-foreground">{item.count}회</span>
                </div>
              ))}
              {overview.top_keywords.length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  아직 키워드 데이터가 없습니다
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Trends Section */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>설득력 트렌드</CardTitle>
              <CardDescription>
                최근 {trendDays}일간의 설득력 점수 변화
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant={trendDays === 7 ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setTrendDays(7)}
              >
                7일
              </Button>
              <Button
                variant={trendDays === 30 ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setTrendDays(30)}
              >
                30일
              </Button>
              <Button
                variant={trendDays === 90 ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setTrendDays(90)}
              >
                90일
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trends.score_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  tick={AXIS_TICK}
                  axisLine={{ stroke: CHART.grid }}
                  tickLine={false}
                />
                <YAxis domain={[0, 100]} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={formatFullDate} />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <Line
                  type="monotone"
                  dataKey="average_score"
                  stroke={CHART.primary}
                  name="평균 점수"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="max_score"
                  stroke={CHART.success}
                  name="최고 점수"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="min_score"
                  stroke={CHART.warning}
                  name="최저 점수"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Volume Trend */}
      <Card>
        <CardHeader>
          <CardTitle>작성량 트렌드</CardTitle>
          <CardDescription>
            최근 {trendDays}일간의 일별 포스팅 작성 수
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends.volume_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  tick={AXIS_TICK}
                  axisLine={{ stroke: CHART.grid }}
                  tickLine={false}
                />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ fill: 'hsl(var(--muted))' }}
                  labelFormatter={formatFullDate}
                />
                <Bar dataKey="count" fill={CHART.primary} name="포스팅 수" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Summary Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Award className="h-4 w-4 text-muted-foreground" />
            요약
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="mb-1 text-[13px] font-medium text-muted-foreground">분석 기간</p>
              <p className="text-base font-semibold tabular-nums">최근 {trendDays}일</p>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-medium text-muted-foreground">일평균 작성량</p>
              <p className="text-base font-semibold tabular-nums">{trends.daily_average.toFixed(1)}개</p>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-medium text-muted-foreground">총 작성 포스팅</p>
              <p className="text-base font-semibold tabular-nums">{trends.total_posts}개</p>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-medium text-muted-foreground">전체 평균 설득력</p>
              <p className="text-base font-semibold tabular-nums">
                {overview.average_persuasion_score}/100
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
