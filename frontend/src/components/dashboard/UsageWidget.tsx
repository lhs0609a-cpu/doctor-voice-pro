'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Pill } from '@/components/app-shell/ui-kit'
import {
  FileText,
  Search,
  Key,
  AlertTriangle,
  Crown,
  Loader2,
  TrendingUp
} from 'lucide-react'
import { subscriptionAPI, type UsageSummary } from '@/lib/api'

interface UsageWidgetProps {
  compact?: boolean
  inline?: boolean  // P3: 다른 카드에 내장될 때 카드 래퍼 없이 렌더링
}

export default function UsageWidget({ compact = false, inline = false }: UsageWidgetProps) {
  const router = useRouter()
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [planName, setPlanName] = useState<string>('Free')

  useEffect(() => {
    loadUsage()
  }, [])

  const loadUsage = async () => {
    try {
      const [usageData, subData] = await Promise.all([
        subscriptionAPI.getUsage(),
        subscriptionAPI.getCurrentSubscription()
      ])
      setUsage(usageData)
      if (subData?.plan?.name) {
        setPlanName(subData.plan.name)
      }
    } catch (error) {
      console.error('Failed to load usage:', error)
    } finally {
      setLoading(false)
    }
  }

  const getUsagePercent = (used: number, limit: number) => {
    if (limit === -1) return 0 // 무제한
    if (limit === 0) return 100
    return Math.min((used / limit) * 100, 100)
  }

  // 사용량 비율에 따른 의미색(텍스트)
  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'text-danger'
    if (percent >= 70) return 'text-warning'
    return 'text-success'
  }

  // 사용량 비율에 따른 진행 바 색(인디케이터)
  const getProgressColor = (percent: number) => {
    if (percent >= 90) return '[&>div]:bg-danger'
    if (percent >= 70) return '[&>div]:bg-warning'
    return '[&>div]:bg-success'
  }

  const formatLimit = (limit: number) => (limit === -1 ? '∞' : limit)

  if (loading) {
    if (inline) {
      return (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )
    }
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  if (!usage) {
    return null
  }

  const postsPercent = getUsagePercent(usage.posts_used, usage.posts_limit)
  const analysisPercent = getUsagePercent(usage.analysis_used, usage.analysis_limit)
  const keywordsPercent = getUsagePercent(usage.keywords_used, usage.keywords_limit)

  const isLowUsage = postsPercent >= 80 || analysisPercent >= 80

  // P3: Inline version (카드 없이 다른 컴포넌트에 내장)
  if (inline) {
    return (
      <div className="flex-1">
        <div className="mb-2 flex items-center gap-2">
          <Pill tone="muted">{planName}</Pill>
          <span className="text-xs text-muted-foreground">사용량</span>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="w-12 text-xs text-muted-foreground">글 생성</span>
            <span className={`text-xs font-medium tabular-nums ${getUsageColor(postsPercent)}`}>
              {usage.posts_used}/{formatLimit(usage.posts_limit)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="w-12 text-xs text-muted-foreground">분석</span>
            <span className={`text-xs font-medium tabular-nums ${getUsageColor(analysisPercent)}`}>
              {usage.analysis_used}/{formatLimit(usage.analysis_limit)}
            </span>
          </div>
        </div>
      </div>
    )
  }

  // Compact version for sidebar
  if (compact) {
    return (
      <div className="surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[13px] font-medium text-muted-foreground">이번 달 사용량</span>
          <Pill tone="muted">{planName}</Pill>
        </div>

        <div className="space-y-3">
          {/* Posts */}
          <div>
            <div className="mb-1 flex justify-between text-xs">
              <span className="flex items-center gap-1 text-muted-foreground">
                <FileText className="h-3.5 w-3.5" />
                글 생성
              </span>
              <span className={`font-medium tabular-nums ${getUsageColor(postsPercent)}`}>
                {usage.posts_used}/{formatLimit(usage.posts_limit)}
              </span>
            </div>
            {usage.posts_limit !== -1 && (
              <Progress value={postsPercent} className={`h-1.5 ${getProgressColor(postsPercent)}`} />
            )}
          </div>

          {/* Analysis */}
          <div>
            <div className="mb-1 flex justify-between text-xs">
              <span className="flex items-center gap-1 text-muted-foreground">
                <Search className="h-3.5 w-3.5" />
                분석
              </span>
              <span className={`font-medium tabular-nums ${getUsageColor(analysisPercent)}`}>
                {usage.analysis_used}/{formatLimit(usage.analysis_limit)}
              </span>
            </div>
            {usage.analysis_limit !== -1 && (
              <Progress value={analysisPercent} className={`h-1.5 ${getProgressColor(analysisPercent)}`} />
            )}
          </div>
        </div>

        {isLowUsage && (
          <Button
            size="sm"
            className="mt-3 w-full"
            onClick={() => router.push('/pricing')}
          >
            <Crown />
            업그레이드
          </Button>
        )}
      </div>
    )
  }

  // Full version for dashboard
  const tiles = [
    { icon: FileText, label: '글 생성', used: usage.posts_used, limit: usage.posts_limit, percent: postsPercent },
    { icon: Search, label: '상위노출 분석', used: usage.analysis_used, limit: usage.analysis_limit, percent: analysisPercent },
    { icon: Key, label: '키워드 연구', used: usage.keywords_used, limit: usage.keywords_limit, percent: keywordsPercent },
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            이번 달 사용량
          </CardTitle>
          <Pill tone="accent">{planName} 플랜</Pill>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Warning Banner */}
        {isLowUsage && (
          <div className="flex items-center gap-2 rounded-lg bg-warning-soft p-3 text-warning">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">사용량이 거의 소진되었습니다. 업그레이드를 고려해 보세요.</span>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {tiles.map(({ icon: Icon, label, used, limit, percent }) => (
            <div key={label} className="rounded-lg bg-muted/40 p-4">
              <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground">
                <Icon className="h-4 w-4" />
                {label}
              </div>
              <p className="kpi">
                {used}
                <span className="text-sm font-normal text-muted-foreground">
                  /{formatLimit(limit)}
                </span>
              </p>
              {limit !== -1 && (
                <Progress value={percent} className={`mt-2 h-1.5 ${getProgressColor(percent)}`} />
              )}
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => router.push('/dashboard/subscription')}
          >
            상세 보기
          </Button>
          <Button
            className="flex-1"
            onClick={() => router.push('/pricing')}
          >
            <Crown />
            업그레이드
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
