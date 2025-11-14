'use client'

import { useEffect, useState } from 'react'
import { analyticsAPI } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8']

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
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">분석 데이터를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (!overview || !comparison || !trends) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">데이터를 불러올 수 없습니다.</p>
      </div>
    )
  }

  // Prepare pie chart data
  const statusData = [
    { name: '작성중', value: overview.status_breakdown.draft, color: '#FFBB28' },
    { name: '발행됨', value: overview.status_breakdown.published, color: '#00C49F' },
    { name: '보관됨', value: overview.status_breakdown.archived || 0, color: '#8884D8' },
  ].filter((item) => item.value > 0)

  const renderChangeIndicator = (change: number) => {
    if (change > 0) {
      return (
        <span className="flex items-center text-green-600 text-sm">
          <TrendingUp className="w-4 h-4 mr-1" />
          {change.toFixed(1)}%
        </span>
      )
    } else if (change < 0) {
      return (
        <span className="flex items-center text-red-600 text-sm">
          <TrendingDown className="w-4 h-4 mr-1" />
          {Math.abs(change).toFixed(1)}%
        </span>
      )
    }
    return <span className="text-sm text-muted-foreground">변화 없음</span>
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">분석 대시보드</h1>
          <p className="text-muted-foreground mt-1">
            포스팅 성과 및 통계를 한눈에 확인하세요
          </p>
        </div>
        <Button onClick={loadData} variant="outline">
          새로고침
        </Button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">전체 포스팅</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.total_posts}</div>
            <p className="text-xs text-muted-foreground mt-1">
              이번 달 {overview.posts_this_month}개
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">평균 설득력</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.average_persuasion_score}/100</div>
            <p className="text-xs text-muted-foreground mt-1">
              전체 포스팅 평균
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">시간 절약</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Math.floor(overview.time_saved_minutes / 60)}시간
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {overview.time_saved_minutes % 60}분
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">이번 주</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.posts_this_week}</div>
            <p className="text-xs text-muted-foreground mt-1">
              최근 7일간 작성
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Month Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>월별 비교</CardTitle>
          <CardDescription>이번 달과 지난 달의 성과 비교</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">포스팅 수</p>
              <div className="flex items-baseline space-x-2">
                <span className="text-3xl font-bold">{comparison.this_month.count}</span>
                <span className="text-sm text-muted-foreground">
                  / {comparison.last_month.count} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.count_change_percent)}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">평균 설득력</p>
              <div className="flex items-baseline space-x-2">
                <span className="text-3xl font-bold">
                  {comparison.this_month.avg_score.toFixed(1)}
                </span>
                <span className="text-sm text-muted-foreground">
                  / {comparison.last_month.avg_score.toFixed(1)} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.score_change_percent)}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">발행된 포스팅</p>
              <div className="flex items-baseline space-x-2">
                <span className="text-3xl font-bold">{comparison.this_month.published}</span>
                <span className="text-sm text-muted-foreground">
                  / {comparison.last_month.published} (지난 달)
                </span>
              </div>
              {renderChangeIndicator(comparison.changes.published_change_percent)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  fill="#8884d8"
                  dataKey="value"
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Top Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Hash className="w-5 h-5 mr-2" />
              인기 키워드
            </CardTitle>
            <CardDescription>가장 많이 사용된 키워드 Top 10</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {overview.top_keywords.slice(0, 10).map((item, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Badge variant={index < 3 ? 'default' : 'secondary'}>
                      {index + 1}
                    </Badge>
                    <span className="text-sm font-medium">{item.keyword}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">{item.count}회</span>
                </div>
              ))}
              {overview.top_keywords.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
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
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>설득력 트렌드</CardTitle>
              <CardDescription>
                최근 {trendDays}일간의 설득력 점수 변화
              </CardDescription>
            </div>
            <div className="flex space-x-2">
              <Button
                variant={trendDays === 7 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendDays(7)}
              >
                7일
              </Button>
              <Button
                variant={trendDays === 30 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendDays(30)}
              >
                30일
              </Button>
              <Button
                variant={trendDays === 90 ? 'default' : 'outline'}
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
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return `${date.getMonth() + 1}/${date.getDate()}`
                  }}
                />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  labelFormatter={(value) => {
                    const date = new Date(value)
                    return date.toLocaleDateString('ko-KR')
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="average_score"
                  stroke="#0088FE"
                  name="평균 점수"
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="max_score"
                  stroke="#00C49F"
                  name="최고 점수"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                />
                <Line
                  type="monotone"
                  dataKey="min_score"
                  stroke="#FF8042"
                  name="최저 점수"
                  strokeWidth={1}
                  strokeDasharray="5 5"
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
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return `${date.getMonth() + 1}/${date.getDate()}`
                  }}
                />
                <YAxis />
                <Tooltip
                  labelFormatter={(value) => {
                    const date = new Date(value)
                    return date.toLocaleDateString('ko-KR')
                  }}
                />
                <Bar dataKey="count" fill="#0088FE" name="포스팅 수" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Summary Card */}
      <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Award className="w-5 h-5 mr-2" />
            요약
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground mb-2">분석 기간</p>
              <p className="text-lg font-semibold">최근 {trendDays}일</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-2">일평균 작성량</p>
              <p className="text-lg font-semibold">{trends.daily_average.toFixed(1)}개</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-2">총 작성 포스팅</p>
              <p className="text-lg font-semibold">{trends.total_posts}개</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-2">전체 평균 설득력</p>
              <p className="text-lg font-semibold">
                {overview.average_persuasion_score}/100
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
