'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
import {
  Search,
  Database,
  Play,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  HeartPulse,
  Utensils,
  Sparkles,
  Baby,
  Plane,
  Smartphone,
  Dumbbell,
  FileText,
  BarChart3,
  Target,
  X,
  ExternalLink,
  Lightbulb,
  Eye,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { toast } from 'sonner'
import { topPostsAPI } from '@/lib/api'

// 카테고리 아이콘 매핑
const CATEGORY_ICONS: Record<string, any> = {
  hospital: HeartPulse,
  restaurant: Utensils,
  beauty: Sparkles,
  parenting: Baby,
  travel: Plane,
  tech: Smartphone,
  fitness: Dumbbell,
  general: FileText,
}

interface CategoryWithStats {
  id: string
  name: string
  seeds: string[]
  posts_count: number
  sample_count: number
  confidence: number
  has_rules: boolean
}

interface AnalysisJob {
  id: string
  category: string
  category_name: string
  target_count: number
  status: string
  progress: number
  keywords_collected?: number
  keywords_total?: number
  posts_analyzed: number
  posts_failed?: number
  created_at: string
  completed_at?: string
}

interface Dashboard {
  total_posts: number
  total_keywords: number
  categories: {
    category: string
    category_name: string
    posts_count: number
    keywords_count: number
    sample_count: number
    confidence: number
    last_updated?: string
  }[]
  recent_jobs: AnalysisJob[]
}

interface AnalyzedPost {
  id: number
  keyword: string
  rank: number
  title: string
  post_url: string
  blog_id: string
  category: string
  category_name: string
  content_length: number
  image_count: number
  video_count: number
  heading_count: number
  keyword_count: number
  keyword_density: number
  title_has_keyword: boolean
  has_map: boolean
  data_quality: string
  analyzed_at: string
}

interface PatternInsight {
  category: string
  finding: string
  recommendation: string
  confidence: number
}

interface PatternsSummary {
  status: string
  category: string
  category_name: string
  sample_count: number
  confidence: number
  summary: string | null
  insights: PatternInsight[]
}

const confidenceColor = (confidence: number) =>
  confidence >= 0.7 ? 'text-success' : confidence >= 0.4 ? 'text-warning' : 'text-danger'

export default function TopPostAnalysisPage() {
  const [categories, setCategories] = useState<CategoryWithStats[]>([])
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [targetCount, setTargetCount] = useState<number>(100)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [currentJob, setCurrentJob] = useState<AnalysisJob | null>(null)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // 분석 결과 탭 상태
  const [activeTab, setActiveTab] = useState('analysis')
  const [analyzedPosts, setAnalyzedPosts] = useState<AnalyzedPost[]>([])
  const [patternsSummary, setPatternsSummary] = useState<PatternsSummary | null>(null)
  const [resultsCategory, setResultsCategory] = useState<string>('')
  const [loadingResults, setLoadingResults] = useState(false)
  const [expandedKeywords, setExpandedKeywords] = useState<Set<string>>(new Set())

  // 데이터 로드
  const loadData = useCallback(async () => {
    try {
      const [categoriesRes, dashboardRes] = await Promise.all([
        topPostsAPI.getCategoriesWithStats(),
        topPostsAPI.getDashboard(),
      ])
      setCategories(categoriesRes.categories || [])
      setDashboard(dashboardRes)
    } catch (error) {
      console.error('데이터 로드 실패:', error)
      toast.error('데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // 폴링 중지 함수
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearTimeout(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
  }, [])

  // 작업 상태 폴링 (setTimeout 재귀 방식)
  const startPolling = useCallback((jobId: string) => {
    const poll = async () => {
      try {
        const job = await topPostsAPI.getJobStatus(jobId)
        setCurrentJob(job)

        if (job.status === 'completed') {
          toast.success(`분석 완료! ${job.posts_analyzed}개 글 분석됨`)
          setAnalyzing(false)
          pollingIntervalRef.current = null
          loadData() // 데이터 새로고침
        } else if (job.status === 'failed') {
          toast.error(`분석 실패: ${job.error_message || '알 수 없는 오류'}`)
          setAnalyzing(false)
          pollingIntervalRef.current = null
        } else {
          // 계속 폴링
          pollingIntervalRef.current = setTimeout(poll, 3000)
        }
      } catch (error) {
        console.error('작업 상태 조회 실패:', error)
        // 에러 시에도 폴링 계속
        pollingIntervalRef.current = setTimeout(poll, 3000)
      }
    }

    // 즉시 첫 번째 폴링 시작
    poll()
  }, [loadData])

  // 분석 시작
  const handleStartAnalysis = async () => {
    if (!selectedCategory) {
      toast.error('카테고리를 선택해주세요')
      return
    }

    setAnalyzing(true)
    const loadingToast = toast.loading('분석 작업을 시작합니다...')

    try {
      const response = await topPostsAPI.startBulkAnalysis({
        category: selectedCategory,
        target_count: targetCount,
      })

      toast.success('분석 작업이 시작되었습니다', { id: loadingToast })

      // 폴링 시작
      startPolling(response.job_id)
    } catch (error: any) {
      toast.error(error.message || '분석 시작 실패', { id: loadingToast })
      setAnalyzing(false)
    }
  }

  // 분석 취소
  const handleCancelAnalysis = async () => {
    if (!currentJob) return

    try {
      await topPostsAPI.cancelJob(currentJob.id)
      toast.success('분석이 취소되었습니다')
      setAnalyzing(false)
      setCurrentJob(null)
      stopPolling()
    } catch (error) {
      toast.error('취소 실패')
    }
  }

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearTimeout(pollingIntervalRef.current)
      }
    }
  }, [])

  // 분석 결과 로드
  const loadAnalysisResults = useCallback(async (category: string) => {
    if (!category) return

    setLoadingResults(true)
    try {
      const [postsRes, summaryRes] = await Promise.all([
        topPostsAPI.getAnalyzedPosts({ category, limit: 100 }),
        topPostsAPI.getPatternsSummary(category)
      ])
      setAnalyzedPosts(postsRes.posts || [])
      setPatternsSummary(summaryRes)
    } catch (error) {
      console.error('분석 결과 로드 실패:', error)
      toast.error('분석 결과를 불러오는데 실패했습니다')
    } finally {
      setLoadingResults(false)
    }
  }, [])

  // 결과 카테고리 변경 시 로드
  useEffect(() => {
    if (activeTab === 'results' && resultsCategory) {
      loadAnalysisResults(resultsCategory)
    }
  }, [activeTab, resultsCategory, loadAnalysisResults])

  // 키워드 접기/펼치기 토글
  const toggleKeyword = (keyword: string) => {
    setExpandedKeywords(prev => {
      const next = new Set(prev)
      if (next.has(keyword)) {
        next.delete(keyword)
      } else {
        next.add(keyword)
      }
      return next
    })
  }

  // 키워드별 그룹화
  const postsByKeyword = analyzedPosts.reduce((acc, post) => {
    if (!acc[post.keyword]) {
      acc[post.keyword] = []
    }
    acc[post.keyword].push(post)
    return acc
  }, {} as Record<string, AnalyzedPost[]>)

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Pill tone="ok">완료</Pill>
      case 'running':
        return <Pill tone="accent">진행중</Pill>
      case 'pending':
        return <Pill tone="warn">대기중</Pill>
      case 'failed':
        return <Pill tone="danger">실패</Pill>
      case 'cancelled':
        return <Pill tone="muted">취소됨</Pill>
      default:
        return <Pill tone="muted">{status}</Pill>
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="네이버 상위노출 분석"
        description="카테고리별 상위 노출 글을 대량으로 분석해 최적화 규칙을 찾습니다"
        actions={
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
        }
      />

      {/* 전체 통계 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatTile
          label="분석된 글"
          value={(dashboard?.total_posts || 0).toLocaleString()}
          icon={<Database className="h-4 w-4" />}
        />
        <StatTile
          label="수집된 키워드"
          value={(dashboard?.total_keywords || 0).toLocaleString()}
          icon={<Search className="h-4 w-4" />}
        />
        <StatTile
          label="활성 카테고리"
          value={`${categories.filter(c => c.has_rules).length} / ${categories.length}`}
          hint="규칙이 생성된 카테고리"
          icon={<BarChart3 className="h-4 w-4" />}
        />
      </div>

      {/* 탭 네비게이션 */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="analysis" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            분석 실행
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center gap-2">
            <Eye className="h-4 w-4" />
            분석 결과
          </TabsTrigger>
        </TabsList>

        {/* 분석 실행 탭 */}
        <TabsContent value="analysis" className="space-y-6">
          {/* 분석 설정 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-4 w-4 text-muted-foreground" />
                분석 설정
              </CardTitle>
              <CardDescription>
                분석할 카테고리와 목표 글 수를 선택하세요
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 카테고리 선택 */}
              <div className="space-y-3">
                <label className="block text-[13px] font-medium text-muted-foreground">카테고리 선택</label>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  {categories.map((cat) => {
                    const Icon = CATEGORY_ICONS[cat.id] || FileText
                    const isSelected = selectedCategory === cat.id
                    return (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => setSelectedCategory(cat.id)}
                        disabled={analyzing}
                        className={`rounded-lg border p-4 text-left transition-colors ${
                          isSelected ? 'border-primary bg-accent' : 'hover:bg-muted/40'
                        } ${analyzing ? 'cursor-not-allowed opacity-50' : ''}`}
                      >
                        <div className="mb-2 flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-primary">
                            <Icon className="h-4 w-4" />
                          </div>
                          <span className="text-sm font-medium">{cat.name}</span>
                        </div>
                        <div className="space-y-1 text-xs text-muted-foreground">
                          <div className="flex justify-between">
                            <span>분석된 글</span>
                            <span className="font-medium tabular-nums text-foreground">{cat.posts_count}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>신뢰도</span>
                            <span className={`font-medium tabular-nums ${confidenceColor(cat.confidence)}`}>
                              {Math.round(cat.confidence * 100)}%
                            </span>
                          </div>
                          {cat.has_rules && (
                            <div className="flex items-center gap-1 text-success">
                              <CheckCircle2 className="h-3 w-3" />
                              <span>규칙 생성됨</span>
                            </div>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 분석 규모 선택 */}
              <div className="flex items-end gap-4">
                <div className="flex-1 space-y-2">
                  <label className="block text-[13px] font-medium text-muted-foreground">분석 규모</label>
                  <Select
                    value={targetCount.toString()}
                    onValueChange={(v) => setTargetCount(Number(v))}
                    disabled={analyzing}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="100">100개 (빠른 분석, 약 5분)</SelectItem>
                      <SelectItem value="500">500개 (중간 분석, 약 20분)</SelectItem>
                      <SelectItem value="1000">1000개 (정밀 분석, 약 40분)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {analyzing ? (
                  <Button variant="outline" onClick={handleCancelAnalysis}>
                    <X className="h-4 w-4" />
                    분석 취소
                  </Button>
                ) : (
                  <Button onClick={handleStartAnalysis} disabled={!selectedCategory}>
                    <Play className="h-4 w-4" />
                    분석 시작
                  </Button>
                )}
              </div>

              {/* 진행 상황 */}
              {currentJob && analyzing && (
                <div className="space-y-3 rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      <span className="font-medium">분석 진행 중</span>
                    </div>
                    {getStatusBadge(currentJob.status)}
                  </div>
                  <Progress value={currentJob.progress} className="h-2 bg-muted" />
                  <div className="flex justify-between text-xs tabular-nums text-muted-foreground">
                    <span>키워드 수집: {currentJob.keywords_collected}개</span>
                    <span>글 분석: {currentJob.posts_analyzed} / {currentJob.target_count}</span>
                    <span>진행률: {currentJob.progress}%</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 카테고리별 규칙 현황 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                카테고리별 분석 현황
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {!dashboard?.categories.length ? (
                <p className="py-6 text-center text-sm text-muted-foreground">아직 분석된 카테고리가 없습니다</p>
              ) : (
                <div className="divide-y rounded-lg border">
                  {dashboard.categories.map((cat) => {
                    const Icon = CATEGORY_ICONS[cat.category] || FileText
                    return (
                      <div
                        key={cat.category}
                        className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                            <Icon className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate font-medium">{cat.category_name}</p>
                            <p className="text-xs tabular-nums text-muted-foreground">
                              글 {cat.posts_count}개 · 키워드 {cat.keywords_count}개
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-4">
                          <div className="text-right">
                            <p className="text-sm font-medium tabular-nums">샘플 {cat.sample_count}개</p>
                            <p className={`text-xs tabular-nums ${confidenceColor(cat.confidence)}`}>
                              신뢰도 {Math.round(cat.confidence * 100)}%
                            </p>
                          </div>
                          <div className="hidden w-24 sm:block">
                            <Progress value={cat.confidence * 100} className="h-2 bg-muted" />
                          </div>
                          {cat.sample_count >= 3 ? (
                            <CheckCircle2 className="h-4 w-4 text-success" />
                          ) : (
                            <AlertCircle className="h-4 w-4 text-warning" />
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 최근 작업 이력 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                최근 분석 작업
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {dashboard?.recent_jobs.length === 0 ? (
                <EmptyState
                  icon={<Clock className="h-8 w-8" />}
                  title="아직 분석 작업이 없습니다"
                  description="위에서 카테고리를 선택하고 분석을 시작하세요"
                />
              ) : (
                <div className="divide-y rounded-lg border">
                  {dashboard?.recent_jobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        {getStatusBadge(job.status)}
                        <div className="min-w-0">
                          <p className="truncate font-medium">{job.category_name}</p>
                          <p className="text-xs tabular-nums text-muted-foreground">
                            목표 {job.target_count}개 · 완료 {job.posts_analyzed}개
                          </p>
                        </div>
                      </div>
                      <div className="shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                        <p>{new Date(job.created_at).toLocaleDateString('ko-KR')}</p>
                        <p>{new Date(job.created_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 분석 결과 탭 */}
        <TabsContent value="results" className="space-y-6">
          {/* 카테고리 선택 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-4 w-4 text-muted-foreground" />
                분석 결과 조회
              </CardTitle>
              <CardDescription>
                카테고리를 선택해 분석된 글과 발견된 공통점을 확인하세요
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <Select
                    value={resultsCategory}
                    onValueChange={setResultsCategory}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="카테고리 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {categories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>
                          {cat.name} ({cat.posts_count}개 분석됨)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => resultsCategory && loadAnalysisResults(resultsCategory)}
                  disabled={!resultsCategory || loadingResults}
                  aria-label="새로고침"
                >
                  {loadingResults ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 공통점 요약 */}
          {patternsSummary && patternsSummary.status === 'data_driven' && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-muted-foreground" />
                  발견된 공통점
                  <Pill tone="muted">{patternsSummary.sample_count}개 글 분석</Pill>
                </CardTitle>
                <CardDescription>
                  신뢰도 {Math.round(patternsSummary.confidence * 100)}%
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 요약 텍스트 */}
                {patternsSummary.summary && (
                  <div className="whitespace-pre-line rounded-lg border bg-muted/40 p-4 text-sm">
                    {patternsSummary.summary}
                  </div>
                )}

                {/* 인사이트 목록 */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {patternsSummary.insights.map((insight, idx) => (
                    <div key={idx} className="rounded-lg border bg-muted/40 p-4">
                      <div className="mb-1.5 flex items-center gap-2">
                        <Pill tone="muted">{insight.category}</Pill>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          신뢰도 {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                      <p className="mb-1 text-sm font-medium">
                        {insight.finding}
                      </p>
                      <p className="text-xs text-primary">
                        {insight.recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 분석된 글 목록 */}
          {resultsCategory && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  분석된 글 목록
                  <Pill tone="muted">{analyzedPosts.length}개</Pill>
                </CardTitle>
                <CardDescription>
                  키워드별로 상위 1~3위 글의 분석 결과를 확인하세요
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingResults ? (
                  <div className="flex justify-center py-8">
                    <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                  </div>
                ) : Object.keys(postsByKeyword).length === 0 ? (
                  <EmptyState
                    icon={<Database className="h-8 w-8" />}
                    title="분석된 글이 없습니다"
                    description="분석 실행 탭에서 이 카테고리를 먼저 분석하세요"
                    action={
                      <Button variant="outline" onClick={() => setActiveTab('analysis')}>
                        <Target className="h-4 w-4" />
                        분석 실행으로 이동
                      </Button>
                    }
                  />
                ) : (
                  <div className="space-y-3">
                    {Object.entries(postsByKeyword).map(([keyword, posts]) => (
                      <div key={keyword} className="overflow-hidden rounded-lg border">
                        {/* 키워드 헤더 */}
                        <button
                          type="button"
                          onClick={() => toggleKeyword(keyword)}
                          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-sm transition-colors hover:bg-muted/40"
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                            <span className="truncate font-medium">{keyword}</span>
                            <Pill tone="muted">{posts.length}개 글</Pill>
                          </div>
                          <div className="flex shrink-0 items-center gap-4 text-xs tabular-nums text-muted-foreground">
                            <span>
                              평균 {Math.round(posts.reduce((sum, p) => sum + p.content_length, 0) / posts.length)}자
                            </span>
                            <span>
                              이미지 {Math.round(posts.reduce((sum, p) => sum + p.image_count, 0) / posts.length * 10) / 10}장
                            </span>
                            {expandedKeywords.has(keyword) ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </div>
                        </button>

                        {/* 글 목록 (펼친 경우) */}
                        {expandedKeywords.has(keyword) && (
                          <div className="space-y-2 border-t bg-muted/40 p-3">
                            {posts.sort((a, b) => a.rank - b.rank).map((post) => (
                              <div
                                key={post.id}
                                className="flex items-start gap-3 rounded-lg border bg-card p-3"
                              >
                                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold tabular-nums ${
                                  post.rank === 1 ? 'bg-accent text-primary' : 'bg-muted text-muted-foreground'
                                }`}>
                                  {post.rank}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="mb-1 flex items-center gap-2">
                                    <a
                                      href={post.post_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="truncate text-sm font-medium text-primary hover:underline"
                                    >
                                      {post.title || '(제목 없음)'}
                                    </a>
                                    <ExternalLink className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                                  </div>
                                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums text-muted-foreground">
                                    <span>본문 {post.content_length.toLocaleString()}자</span>
                                    <span>이미지 {post.image_count}장</span>
                                    <span>소제목 {post.heading_count}개</span>
                                    <span>키워드 {post.keyword_count}회</span>
                                    {post.title_has_keyword && (
                                      <Pill tone="ok">제목에 키워드 포함</Pill>
                                    )}
                                    {post.has_map && (
                                      <Pill tone="accent">지도 포함</Pill>
                                    )}
                                  </div>
                                </div>
                                <Pill
                                  tone={
                                    post.data_quality === 'high' ? 'ok' :
                                    post.data_quality === 'medium' ? 'warn' : 'danger'
                                  }
                                >
                                  {post.data_quality === 'high' ? '고품질' :
                                   post.data_quality === 'medium' ? '중품질' : '저품질'}
                                </Pill>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 카테고리 미선택 안내 */}
          {!resultsCategory && (
            <EmptyState
              icon={<Eye className="h-8 w-8" />}
              title="카테고리를 선택하세요"
              description="위에서 카테고리를 고르면 분석된 글과 공통점을 보여드립니다"
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
