'use client'

import { useState, useEffect } from 'react'
import { postsAPIExtended } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { toast } from 'sonner'
import { BarChart3, CheckCircle2, AlertCircle, TrendingUp } from 'lucide-react'

interface SEOScorePanelProps {
  postId: string
}

interface SEOAnalysis {
  overall_score: number
  title_score: number
  content_score: number
  keyword_score: number
  readability_score: number
  recommendations: string[]
}

export function SEOScorePanel({ postId }: SEOScorePanelProps) {
  const [loading, setLoading] = useState(true)
  const [analysis, setAnalysis] = useState<SEOAnalysis | null>(null)

  useEffect(() => {
    loadAnalysis()
  }, [postId])

  const loadAnalysis = async () => {
    try {
      setLoading(true)
      const data = await postsAPIExtended.getSeoAnalysis(postId)
      setAnalysis(data)
    } catch (error) {
      toast.error('SEO 분석 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getScoreBadge = (score: number) => {
    if (score >= 80) return 'bg-green-100 text-green-800'
    if (score >= 60) return 'bg-yellow-100 text-yellow-800'
    return 'bg-red-100 text-red-800'
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-sm text-muted-foreground">SEO 분석 중...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!analysis) return null

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              전체 SEO 점수
            </span>
            <Badge className={getScoreBadge(analysis.overall_score)}>
              {analysis.overall_score}/100
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Progress value={analysis.overall_score} className="h-4" />
          <p className="text-sm text-muted-foreground mt-2">
            {analysis.overall_score >= 80 && '우수한 SEO 최적화 상태입니다!'}
            {analysis.overall_score >= 60 &&
              analysis.overall_score < 80 &&
              '양호한 SEO 최적화 상태입니다.'}
            {analysis.overall_score < 60 && 'SEO 최적화가 필요합니다.'}
          </p>
        </CardContent>
      </Card>

      {/* Individual Scores */}
      <Card>
        <CardHeader>
          <CardTitle>세부 점수</CardTitle>
          <CardDescription>각 영역별 SEO 점수</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">제목</span>
              <span className={`text-sm font-bold ${getScoreColor(analysis.title_score)}`}>
                {analysis.title_score}/100
              </span>
            </div>
            <Progress value={analysis.title_score} className="h-2" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">콘텐츠 구조</span>
              <span className={`text-sm font-bold ${getScoreColor(analysis.content_score)}`}>
                {analysis.content_score}/100
              </span>
            </div>
            <Progress value={analysis.content_score} className="h-2" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">키워드 밀도</span>
              <span className={`text-sm font-bold ${getScoreColor(analysis.keyword_score)}`}>
                {analysis.keyword_score}/100
              </span>
            </div>
            <Progress value={analysis.keyword_score} className="h-2" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">가독성</span>
              <span
                className={`text-sm font-bold ${getScoreColor(analysis.readability_score)}`}
              >
                {analysis.readability_score}/100
              </span>
            </div>
            <Progress value={analysis.readability_score} className="h-2" />
          </div>
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            개선 권장사항
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {analysis.recommendations.map((recommendation, index) => (
              <li key={index} className="flex items-start gap-3">
                {recommendation.includes('잘') || recommendation.includes('우수') ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-orange-600 flex-shrink-0 mt-0.5" />
                )}
                <span className="text-sm flex-1">{recommendation}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
