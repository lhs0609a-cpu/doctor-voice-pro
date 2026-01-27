'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
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

  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'text-red-500'
    if (percent >= 70) return 'text-yellow-500'
    return 'text-green-500'
  }

  const getProgressColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500'
    if (percent >= 70) return 'bg-yellow-500'
    return 'bg-green-500'
  }

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
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="outline" className="text-xs">{planName}</Badge>
          <span className="text-xs text-gray-500">사용량</span>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="h-3 w-3 text-blue-500" />
            <span className="text-xs text-gray-600 w-12">글 생성</span>
            <span className={`text-xs font-medium ${getUsageColor(postsPercent)}`}>
              {usage.posts_used}/{usage.posts_limit === -1 ? '∞' : usage.posts_limit}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Search className="h-3 w-3 text-green-500" />
            <span className="text-xs text-gray-600 w-12">분석</span>
            <span className={`text-xs font-medium ${getUsageColor(analysisPercent)}`}>
              {usage.analysis_used}/{usage.analysis_limit === -1 ? '∞' : usage.analysis_limit}
            </span>
          </div>
        </div>
      </div>
    )
  }

  // Compact version for sidebar
  if (compact) {
    return (
      <Card className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-0">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium">이번 달 사용량</span>
            <Badge variant="outline" className="text-xs">
              {planName}
            </Badge>
          </div>

          <div className="space-y-3">
            {/* Posts */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  글 생성
                </span>
                <span className={getUsageColor(postsPercent)}>
                  {usage.posts_used}/{usage.posts_limit === -1 ? '∞' : usage.posts_limit}
                </span>
              </div>
              {usage.posts_limit !== -1 && (
                <Progress value={postsPercent} className={`h-1.5 ${getProgressColor(postsPercent)}`} />
              )}
            </div>

            {/* Analysis */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="flex items-center gap-1">
                  <Search className="h-3 w-3" />
                  분석
                </span>
                <span className={getUsageColor(analysisPercent)}>
                  {usage.analysis_used}/{usage.analysis_limit === -1 ? '∞' : usage.analysis_limit}
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
              className="w-full mt-3 h-8 text-xs"
              onClick={() => router.push('/pricing')}
            >
              <Crown className="mr-1 h-3 w-3" />
              업그레이드
            </Button>
          )}
        </CardContent>
      </Card>
    )
  }

  // Full version for dashboard
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            이번 달 사용량
          </CardTitle>
          <Badge variant="secondary">{planName} 플랜</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Warning Banner */}
        {isLowUsage && (
          <div className="flex items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 rounded-lg mb-4">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">사용량이 거의 소진되었습니다. 업그레이드를 고려해보세요.</span>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {/* Posts */}
          <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
            <FileText className="h-8 w-8 mx-auto mb-2 text-blue-500" />
            <p className="text-2xl font-bold">
              {usage.posts_used}
              <span className="text-sm font-normal text-muted-foreground">
                /{usage.posts_limit === -1 ? '∞' : usage.posts_limit}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">글 생성</p>
            {usage.posts_limit !== -1 && (
              <Progress value={postsPercent} className="mt-2 h-1.5" />
            )}
          </div>

          {/* Analysis */}
          <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-xl">
            <Search className="h-8 w-8 mx-auto mb-2 text-green-500" />
            <p className="text-2xl font-bold">
              {usage.analysis_used}
              <span className="text-sm font-normal text-muted-foreground">
                /{usage.analysis_limit === -1 ? '∞' : usage.analysis_limit}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">상위노출 분석</p>
            {usage.analysis_limit !== -1 && (
              <Progress value={analysisPercent} className="mt-2 h-1.5" />
            )}
          </div>

          {/* Keywords */}
          <div className="text-center p-4 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
            <Key className="h-8 w-8 mx-auto mb-2 text-purple-500" />
            <p className="text-2xl font-bold">
              {usage.keywords_used}
              <span className="text-sm font-normal text-muted-foreground">
                /{usage.keywords_limit === -1 ? '∞' : usage.keywords_limit}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">키워드 연구</p>
            {usage.keywords_limit !== -1 && (
              <Progress value={keywordsPercent} className="mt-2 h-1.5" />
            )}
          </div>
        </div>

        {/* CTA */}
        <div className="flex gap-2 mt-4">
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
            <Crown className="mr-2 h-4 w-4" />
            업그레이드
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
