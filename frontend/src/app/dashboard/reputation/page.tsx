'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import {
  Shield,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  AlertCircle,
  Star,
  MessageSquare,
  Eye,
  RefreshCw,
  Loader2,
  Plus,
  Settings,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Bell,
  Zap,
  BarChart3,
} from 'lucide-react'
import { reputationAPI } from '@/lib/api'
import type { MonitorProfile, DashboardData, Mention } from '@/types/reputation'
import { PLATFORM_LABELS, SENTIMENT_LABELS, RISK_LABELS } from '@/types/reputation'
import { toast } from 'sonner'


export default function ReputationPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)
  const [profiles, setProfiles] = useState<MonitorProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [isCrawling, setIsCrawling] = useState(false)

  useEffect(() => {
    loadProfiles()
  }, [])

  useEffect(() => {
    if (selectedProfileId) {
      loadDashboard(selectedProfileId)
    }
  }, [selectedProfileId])

  const loadProfiles = async () => {
    try {
      const data = await reputationAPI.getProfiles()
      setProfiles(data)
      if (data.length > 0) {
        setSelectedProfileId(data[0].id)
      }
    } catch (error) {
      console.error('프로필 로드 실패:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadDashboard = async (profileId: string) => {
    try {
      setIsLoading(true)
      const data = await reputationAPI.getDashboard(profileId, 30)
      setDashboard(data)
    } catch (error) {
      console.error('대시보드 로드 실패:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleTriggerCrawl = async () => {
    if (!selectedProfileId) return
    setIsCrawling(true)
    try {
      const result = await reputationAPI.triggerCrawl({ profile_id: selectedProfileId })
      toast.success(result.message)
      // 크롤링 후 대시보드 새로고침
      setTimeout(() => loadDashboard(selectedProfileId), 3000)
    } catch (error) {
      toast.error('크롤링 실행에 실패했습니다.')
    } finally {
      setIsCrawling(false)
    }
  }

  const getRiskColor = (level: string | null) => {
    switch (level) {
      case 'critical': return 'text-red-600 bg-red-50 border-red-200'
      case 'warning': return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      case 'normal': return 'text-gray-600 bg-gray-50 border-gray-200'
      case 'positive': return 'text-green-600 bg-green-50 border-green-200'
      default: return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const getSentimentIcon = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive': return <ThumbsUp className="h-4 w-4 text-green-500" />
      case 'negative': return <ThumbsDown className="h-4 w-4 text-red-500" />
      case 'mixed': return <Minus className="h-4 w-4 text-yellow-500" />
      default: return <Minus className="h-4 w-4 text-gray-400" />
    }
  }

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-gray-400'
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    if (score >= 40) return 'text-orange-600'
    return 'text-red-600'
  }

  // 프로필 없는 경우
  if (!isLoading && profiles.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50">
        <DashboardNav />
        <main className="container mx-auto px-4 py-8">
          <div className="text-center py-20">
            <Shield className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">평판 모니터링</h2>
            <p className="text-gray-500 mb-6">
              사업장을 등록하고 24시간 평판 모니터링을 시작하세요.<br />
              네이버 플레이스, 구글 리뷰, 커뮤니티 등 전 플랫폼을 감시합니다.
            </p>
            <Button onClick={() => router.push('/dashboard/reputation/settings')}>
              <Plus className="h-4 w-4 mr-2" />
              사업장 등록하기
            </Button>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardNav />
      <main className="container mx-auto px-4 py-6">
        {/* 헤더 */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Shield className="h-6 w-6 text-blue-600" />
              평판 모니터링
            </h1>
            <p className="text-sm text-gray-500 mt-1">실시간 리뷰/멘션 감시 및 AI 대응</p>
          </div>

          <div className="flex items-center gap-3">
            {profiles.length > 0 && (
              <Select value={selectedProfileId || ''} onValueChange={setSelectedProfileId}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="사업장 선택" />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.business_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleTriggerCrawl}
              disabled={isCrawling || !selectedProfileId}
            >
              {isCrawling ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="ml-1 hidden sm:inline">크롤링</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/dashboard/reputation/settings')}
            >
              <Settings className="h-4 w-4" />
              <span className="ml-1 hidden sm:inline">설정</span>
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        ) : dashboard ? (
          <>
            {/* 핵심 지표 카드 */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {/* 평판 점수 */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">평판 점수</span>
                    <Shield className="h-4 w-4 text-blue-500" />
                  </div>
                  <div className={`text-3xl font-bold ${getScoreColor(dashboard.reputation_score)}`}>
                    {dashboard.reputation_score !== null ? Math.round(dashboard.reputation_score) : '-'}
                  </div>
                  <Progress
                    value={dashboard.reputation_score || 0}
                    className="mt-2 h-2"
                  />
                </CardContent>
              </Card>

              {/* 평균 별점 */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">평균 별점</span>
                    <Star className="h-4 w-4 text-yellow-500" />
                  </div>
                  <div className="text-3xl font-bold">
                    {dashboard.stats.avg_rating || '-'}
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    {[1, 2, 3, 4, 5].map(i => (
                      <Star
                        key={i}
                        className={`h-3 w-3 ${i <= Math.round(dashboard.stats.avg_rating) ? 'text-yellow-400 fill-yellow-400' : 'text-gray-200'}`}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* 총 멘션 */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">총 멘션</span>
                    <MessageSquare className="h-4 w-4 text-purple-500" />
                  </div>
                  <div className="text-3xl font-bold">{dashboard.stats.total_mentions}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    미읽음 {dashboard.stats.unread_count}건
                  </div>
                </CardContent>
              </Card>

              {/* 긴급 대응 */}
              <Card className={dashboard.stats.critical_count > 0 ? 'border-red-200 bg-red-50/50' : ''}>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">긴급 대응</span>
                    <AlertTriangle className={`h-4 w-4 ${dashboard.stats.critical_count > 0 ? 'text-red-500' : 'text-gray-400'}`} />
                  </div>
                  <div className={`text-3xl font-bold ${dashboard.stats.critical_count > 0 ? 'text-red-600' : ''}`}>
                    {dashboard.stats.critical_count}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    즉시 대응 필요
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* 감성 분포 + 플랫폼 분포 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* 감성 분포 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">감성 분포</CardTitle>
                  <CardDescription>최근 30일간 멘션 감성 분류</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {[
                      { label: '긍정', count: dashboard.stats.positive, color: 'bg-green-500', textColor: 'text-green-600' },
                      { label: '중립', count: dashboard.stats.neutral, color: 'bg-gray-400', textColor: 'text-gray-600' },
                      { label: '부정', count: dashboard.stats.negative, color: 'bg-red-500', textColor: 'text-red-600' },
                      { label: '혼합', count: dashboard.stats.mixed, color: 'bg-yellow-500', textColor: 'text-yellow-600' },
                    ].map(item => {
                      const total = dashboard.stats.total_mentions || 1
                      const pct = Math.round((item.count / total) * 100)
                      return (
                        <div key={item.label} className="flex items-center gap-3">
                          <span className={`text-sm font-medium w-12 ${item.textColor}`}>{item.label}</span>
                          <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${item.color} rounded-full transition-all`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-sm text-gray-500 w-16 text-right">
                            {item.count}건 ({pct}%)
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* 플랫폼 분포 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">플랫폼별 멘션</CardTitle>
                  <CardDescription>최근 30일간 플랫폼별 수집량</CardDescription>
                </CardHeader>
                <CardContent>
                  {Object.keys(dashboard.platform_distribution).length > 0 ? (
                    <div className="space-y-3">
                      {Object.entries(dashboard.platform_distribution)
                        .sort((a, b) => b[1] - a[1])
                        .map(([platform, count]) => {
                          const total = dashboard.stats.total_mentions || 1
                          const pct = Math.round((count / total) * 100)
                          return (
                            <div key={platform} className="flex items-center gap-3">
                              <span className="text-sm w-28 truncate">
                                {PLATFORM_LABELS[platform as keyof typeof PLATFORM_LABELS] || platform}
                              </span>
                              <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-500 rounded-full transition-all"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="text-sm text-gray-500 w-16 text-right">
                                {count}건
                              </span>
                            </div>
                          )
                        })}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-400">
                      <BarChart3 className="h-8 w-8 mx-auto mb-2" />
                      <p className="text-sm">아직 수집된 멘션이 없습니다.</p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3"
                        onClick={handleTriggerCrawl}
                        disabled={isCrawling}
                      >
                        크롤링 시작
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* 긴급 대응 멘션 */}
            {dashboard.critical_mentions.length > 0 && (
              <Card className="mb-6 border-red-200">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    긴급 대응 필요
                  </CardTitle>
                  <CardDescription>즉시 확인이 필요한 부정적 멘션</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard.critical_mentions.map(mention => (
                      <div
                        key={mention.id}
                        className={`p-4 rounded-lg border cursor-pointer hover:shadow-sm transition-shadow ${getRiskColor(mention.risk_level)}`}
                        onClick={() => router.push(`/dashboard/reputation/mentions?id=${mention.id}`)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="text-xs">
                                {PLATFORM_LABELS[mention.platform as keyof typeof PLATFORM_LABELS] || mention.platform}
                              </Badge>
                              <Badge variant="destructive" className="text-xs">
                                {RISK_LABELS[mention.risk_level as keyof typeof RISK_LABELS] || mention.risk_level}
                              </Badge>
                              {mention.rating && (
                                <span className="flex items-center gap-0.5 text-xs">
                                  <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                                  {mention.rating}
                                </span>
                              )}
                            </div>
                            <p className="text-sm line-clamp-2">{mention.content}</p>
                            <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                              <span>{mention.author_name || '익명'}</span>
                              {mention.created_at && (
                                <span>{new Date(mention.created_at).toLocaleDateString('ko-KR')}</span>
                              )}
                            </div>
                          </div>
                          <ExternalLink className="h-4 w-4 flex-shrink-0 text-gray-400" />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push('/dashboard/reputation/mentions')}
                    >
                      전체 멘션 보기
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 점수 추이 */}
            {dashboard.score_history.length > 0 && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="text-lg">평판 점수 추이</CardTitle>
                  <CardDescription>최근 30일간 일별 평판 점수 변화</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-end gap-1 h-40">
                    {dashboard.score_history.map((item, idx) => {
                      const score = item.score || 0
                      const height = Math.max(4, score)
                      const color = score >= 80 ? 'bg-green-500'
                        : score >= 60 ? 'bg-yellow-500'
                        : score >= 40 ? 'bg-orange-500'
                        : 'bg-red-500'
                      return (
                        <div
                          key={idx}
                          className="flex-1 flex flex-col items-center justify-end group relative"
                        >
                          <div className="hidden group-hover:block absolute -top-8 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                            {new Date(item.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })} - {Math.round(score)}점
                          </div>
                          <div
                            className={`w-full max-w-[12px] ${color} rounded-t transition-all hover:opacity-80`}
                            style={{ height: `${height}%` }}
                          />
                        </div>
                      )
                    })}
                  </div>
                  <div className="flex justify-between text-xs text-gray-400 mt-2">
                    {dashboard.score_history.length > 0 && (
                      <>
                        <span>{new Date(dashboard.score_history[0].date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}</span>
                        <span>{new Date(dashboard.score_history[dashboard.score_history.length - 1].date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}</span>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 빠른 링크 */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Card
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => router.push('/dashboard/reputation/mentions')}
              >
                <CardContent className="pt-6 text-center">
                  <MessageSquare className="h-8 w-8 text-blue-500 mx-auto mb-2" />
                  <h3 className="font-medium text-sm">멘션 관리</h3>
                  <p className="text-xs text-gray-400 mt-1">리뷰/멘션 확인 및 대응</p>
                </CardContent>
              </Card>

              <Card
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => router.push('/dashboard/reputation/settings')}
              >
                <CardContent className="pt-6 text-center">
                  <Bell className="h-8 w-8 text-orange-500 mx-auto mb-2" />
                  <h3 className="font-medium text-sm">알림 설정</h3>
                  <p className="text-xs text-gray-400 mt-1">알림 규칙 관리</p>
                </CardContent>
              </Card>

              <Card
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => router.push('/dashboard/reputation/settings')}
              >
                <CardContent className="pt-6 text-center">
                  <Zap className="h-8 w-8 text-purple-500 mx-auto mb-2" />
                  <h3 className="font-medium text-sm">대응 가이드</h3>
                  <p className="text-xs text-gray-400 mt-1">플랫폼별 신고/삭제 절차</p>
                </CardContent>
              </Card>

              <Card
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => router.push('/dashboard/reputation/settings')}
              >
                <CardContent className="pt-6 text-center">
                  <BarChart3 className="h-8 w-8 text-green-500 mx-auto mb-2" />
                  <h3 className="font-medium text-sm">경쟁사 비교</h3>
                  <p className="text-xs text-gray-400 mt-1">경쟁사 평판 비교 분석</p>
                </CardContent>
              </Card>
            </div>
          </>
        ) : null}
      </main>
    </div>
  )
}
