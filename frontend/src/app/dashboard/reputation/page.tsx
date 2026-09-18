'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
import {
  Shield,
  AlertTriangle,
  Star,
  MessageSquare,
  RefreshCw,
  Loader2,
  Plus,
  Settings,
  ExternalLink,
  Bell,
  Zap,
  BarChart3,
} from 'lucide-react'
import { reputationAPI } from '@/lib/api'
import type { MonitorProfile, DashboardData } from '@/types/reputation'
import { PLATFORM_LABELS, RISK_LABELS } from '@/types/reputation'
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
      case 'critical': return 'border-danger/30 bg-danger-soft/40'
      case 'warning': return 'border-warning/30 bg-warning-soft/40'
      case 'positive': return 'border-success/30 bg-success-soft/40'
      default: return 'bg-muted/40'
    }
  }

  const getRiskTone = (level: string | null): 'ok' | 'warn' | 'danger' | 'muted' => {
    switch (level) {
      case 'critical': return 'danger'
      case 'warning': return 'warn'
      case 'positive': return 'ok'
      default: return 'muted'
    }
  }

  const getScoreTone = (score: number | null): 'ok' | 'warn' | 'danger' | 'muted' | undefined => {
    if (score === null) return 'muted'
    if (score >= 80) return 'ok'
    if (score >= 60) return 'warn'
    return 'danger'
  }

  const getScoreBar = (score: number) => {
    if (score >= 80) return 'bg-success'
    if (score >= 60) return 'bg-warning'
    return 'bg-danger'
  }

  const headerActions = (
    <>
      {profiles.length > 0 && (
        <Select value={selectedProfileId || ''} onValueChange={setSelectedProfileId}>
          <SelectTrigger className="h-9 w-[200px]">
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
        onClick={() => router.push('/dashboard/reputation/settings')}
      >
        <Settings className="h-4 w-4" />
        <span className="hidden sm:inline">설정</span>
      </Button>

      <Button
        size="sm"
        onClick={handleTriggerCrawl}
        disabled={isCrawling || !selectedProfileId}
      >
        {isCrawling ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        <span className="hidden sm:inline">지금 수집</span>
      </Button>
    </>
  )

  // 프로필 없는 경우
  if (!isLoading && profiles.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="평판 모니터링"
          description="리뷰와 멘션을 실시간으로 감시하고 AI로 대응합니다."
        />
        <EmptyState
          icon={<Shield className="h-8 w-8" />}
          title="사업장을 등록하고 모니터링을 시작하세요"
          description="네이버 플레이스, 구글 리뷰, 커뮤니티 등 전 플랫폼을 24시간 감시합니다."
          action={
            <Button onClick={() => router.push('/dashboard/reputation/settings')}>
              <Plus className="h-4 w-4" />
              사업장 등록하기
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="평판 모니터링"
        description="리뷰와 멘션을 실시간으로 감시하고 AI로 대응합니다."
        actions={headerActions}
      />

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
        </div>
      ) : dashboard ? (
        <>
          {/* 핵심 지표 */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile
              label="평판 점수"
              value={dashboard.reputation_score !== null ? Math.round(dashboard.reputation_score) : '-'}
              tone={getScoreTone(dashboard.reputation_score)}
              icon={<Shield className="h-4 w-4" />}
              hint={<Progress value={dashboard.reputation_score || 0} className="mt-1 h-1.5" />}
            />

            <StatTile
              label="평균 별점"
              value={dashboard.stats.avg_rating || '-'}
              icon={<Star className="h-4 w-4" />}
              hint={
                <span className="flex items-center gap-0.5">
                  {[1, 2, 3, 4, 5].map(i => (
                    <Star
                      key={i}
                      className={`h-3 w-3 ${i <= Math.round(dashboard.stats.avg_rating) ? 'fill-current text-warning' : 'text-muted-foreground/30'}`}
                    />
                  ))}
                </span>
              }
            />

            <StatTile
              label="총 멘션"
              value={dashboard.stats.total_mentions}
              icon={<MessageSquare className="h-4 w-4" />}
              hint={`미읽음 ${dashboard.stats.unread_count}건`}
            />

            <StatTile
              label="긴급 대응"
              value={dashboard.stats.critical_count}
              tone={dashboard.stats.critical_count > 0 ? 'danger' : undefined}
              icon={<AlertTriangle className="h-4 w-4" />}
              hint="즉시 대응 필요"
              className={dashboard.stats.critical_count > 0 ? 'border-danger/30' : undefined}
            />
          </div>

          {/* 감성 분포 + 플랫폼 분포 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* 감성 분포 */}
            <Card>
              <CardHeader>
                <CardTitle>감성 분포</CardTitle>
                <CardDescription>최근 30일간 멘션 감성 분류</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[
                    { label: '긍정', count: dashboard.stats.positive, color: 'bg-success', textColor: 'text-success' },
                    { label: '중립', count: dashboard.stats.neutral, color: 'bg-muted-foreground', textColor: 'text-muted-foreground' },
                    { label: '부정', count: dashboard.stats.negative, color: 'bg-danger', textColor: 'text-danger' },
                    { label: '혼합', count: dashboard.stats.mixed, color: 'bg-warning', textColor: 'text-warning' },
                  ].map(item => {
                    const total = dashboard.stats.total_mentions || 1
                    const pct = Math.round((item.count / total) * 100)
                    return (
                      <div key={item.label} className="flex items-center gap-3">
                        <span className={`w-12 text-sm font-medium ${item.textColor}`}>{item.label}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full ${item.color} rounded-full transition-all`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-20 text-right text-sm tabular-nums text-muted-foreground">
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
                <CardTitle>플랫폼별 멘션</CardTitle>
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
                            <span className="w-28 truncate text-sm">
                              {PLATFORM_LABELS[platform as keyof typeof PLATFORM_LABELS] || platform}
                            </span>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-primary transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="w-20 text-right text-sm tabular-nums text-muted-foreground">
                              {count}건
                            </span>
                          </div>
                        )
                      })}
                  </div>
                ) : (
                  <EmptyState
                    icon={<BarChart3 className="h-6 w-6" />}
                    title="아직 수집된 멘션이 없습니다"
                    description="지금 수집을 실행하면 플랫폼별 멘션이 여기에 표시됩니다."
                    action={
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleTriggerCrawl}
                        disabled={isCrawling}
                      >
                        지금 수집
                      </Button>
                    }
                    className="py-8"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* 긴급 대응 멘션 */}
          {dashboard.critical_mentions.length > 0 && (
            <Card className="border-danger/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-danger" />
                  긴급 대응 필요
                </CardTitle>
                <CardDescription>즉시 확인이 필요한 부정적 멘션</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dashboard.critical_mentions.map(mention => (
                    <div
                      key={mention.id}
                      className={`cursor-pointer rounded-lg border p-4 transition-colors hover:bg-muted/40 ${getRiskColor(mention.risk_level)}`}
                      onClick={() => router.push(`/dashboard/reputation/mentions?id=${mention.id}`)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="mb-1 flex flex-wrap items-center gap-2">
                            <Pill tone="muted">
                              {PLATFORM_LABELS[mention.platform as keyof typeof PLATFORM_LABELS] || mention.platform}
                            </Pill>
                            <Pill tone={getRiskTone(mention.risk_level)}>
                              {RISK_LABELS[mention.risk_level as keyof typeof RISK_LABELS] || mention.risk_level}
                            </Pill>
                            {mention.rating && (
                              <span className="flex items-center gap-0.5 text-xs tabular-nums text-muted-foreground">
                                <Star className="h-3 w-3 fill-current text-warning" />
                                {mention.rating}
                              </span>
                            )}
                          </div>
                          <p className="line-clamp-2 text-sm">{mention.content}</p>
                          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                            <span>{mention.author_name || '익명'}</span>
                            {mention.created_at && (
                              <span>{new Date(mention.created_at).toLocaleDateString('ko-KR')}</span>
                            )}
                          </div>
                        </div>
                        <ExternalLink className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
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
            <Card>
              <CardHeader>
                <CardTitle>평판 점수 추이</CardTitle>
                <CardDescription>최근 30일간 일별 평판 점수 변화</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex h-40 items-end gap-1">
                  {dashboard.score_history.map((item, idx) => {
                    const score = item.score || 0
                    const height = Math.max(4, score)
                    return (
                      <div
                        key={idx}
                        className="group relative flex flex-1 flex-col items-center justify-end"
                      >
                        <div className="absolute -top-8 z-10 hidden whitespace-nowrap rounded-lg border bg-card px-2 py-1 text-xs text-foreground shadow-card group-hover:block">
                          {new Date(item.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })} - {Math.round(score)}점
                        </div>
                        <div
                          className={`w-full max-w-[12px] ${getScoreBar(score)} rounded-t transition-all hover:opacity-80`}
                          style={{ height: `${height}%` }}
                        />
                      </div>
                    )
                  })}
                </div>
                <div className="mt-2 flex justify-between text-xs text-muted-foreground">
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
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              { icon: MessageSquare, title: '멘션 관리', desc: '리뷰/멘션 확인 및 대응', href: '/dashboard/reputation/mentions' },
              { icon: Bell, title: '알림 설정', desc: '알림 규칙 관리', href: '/dashboard/reputation/settings' },
              { icon: Zap, title: '대응 가이드', desc: '플랫폼별 신고/삭제 절차', href: '/dashboard/reputation/settings' },
              { icon: BarChart3, title: '경쟁사 비교', desc: '경쟁사 평판 비교 분석', href: '/dashboard/reputation/settings' },
            ].map(link => (
              <Card
                key={link.title}
                className="cursor-pointer transition-colors hover:bg-muted/40"
                onClick={() => router.push(link.href)}
              >
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <link.icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium">{link.title}</h3>
                    <p className="truncate text-xs text-muted-foreground">{link.desc}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
