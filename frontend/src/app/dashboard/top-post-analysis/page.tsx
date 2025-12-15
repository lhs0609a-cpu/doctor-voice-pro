'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  TrendingUp,
  Search,
  Database,
  Play,
  Pause,
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

// 카테고리 색상 매핑
const CATEGORY_COLORS: Record<string, string> = {
  hospital: 'bg-blue-100 text-blue-700 border-blue-200',
  restaurant: 'bg-orange-100 text-orange-700 border-orange-200',
  beauty: 'bg-pink-100 text-pink-700 border-pink-200',
  parenting: 'bg-green-100 text-green-700 border-green-200',
  travel: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  tech: 'bg-purple-100 text-purple-700 border-purple-200',
  fitness: 'bg-red-100 text-red-700 border-red-200',
  general: 'bg-gray-100 text-gray-700 border-gray-200',
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
        return <Badge className="bg-green-100 text-green-700">완료</Badge>
      case 'running':
        return <Badge className="bg-blue-100 text-blue-700">진행중</Badge>
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700">대기중</Badge>
      case 'failed':
        return <Badge className="bg-red-100 text-red-700">실패</Badge>
      case 'cancelled':
        return <Badge className="bg-gray-100 text-gray-700">취소됨</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-indigo-600" />
            네이버 상위노출 분석
          </h1>
          <p className="text-muted-foreground mt-1">
            카테고리별 상위 노출 글을 대량으로 분석하여 최적화 규칙을 도출합니다
          </p>
        </div>
        <Button variant="outline" onClick={loadData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          새로고침
        </Button>
      </div>

      {/* 전체 통계 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">분석된 글</p>
                <p className="text-2xl font-bold">{dashboard?.total_posts.toLocaleString() || 0}</p>
              </div>
              <Database className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">수집된 키워드</p>
                <p className="text-2xl font-bold">{dashboard?.total_keywords.toLocaleString() || 0}</p>
              </div>
              <Search className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">활성 카테고리</p>
                <p className="text-2xl font-bold">
                  {categories.filter(c => c.has_rules).length} / {categories.length}
                </p>
              </div>
              <BarChart3 className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 탭 네비게이션 */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 max-w-md">
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
            <Target className="h-5 w-5" />
            분석 설정
          </CardTitle>
          <CardDescription>
            분석할 카테고리와 목표 글 수를 선택하세요
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 카테고리 선택 */}
          <div>
            <label className="text-sm font-medium mb-3 block">카테고리 선택</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {categories.map((cat) => {
                const Icon = CATEGORY_ICONS[cat.id] || FileText
                const isSelected = selectedCategory === cat.id
                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    disabled={analyzing}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    } ${analyzing ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`p-2 rounded-lg ${CATEGORY_COLORS[cat.id] || CATEGORY_COLORS.general}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <span className="font-medium">{cat.name}</span>
                    </div>
                    <div className="text-xs text-muted-foreground space-y-1">
                      <div className="flex justify-between">
                        <span>분석된 글:</span>
                        <span className="font-medium">{cat.posts_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>신뢰도:</span>
                        <span className={`font-medium ${
                          cat.confidence >= 0.7 ? 'text-green-600' :
                          cat.confidence >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                        }`}>
                          {Math.round(cat.confidence * 100)}%
                        </span>
                      </div>
                      {cat.has_rules && (
                        <div className="flex items-center gap-1 text-green-600">
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
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium mb-2 block">분석 규모</label>
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
            <div className="pt-6">
              {analyzing ? (
                <Button variant="destructive" onClick={handleCancelAnalysis}>
                  <X className="h-4 w-4 mr-2" />
                  분석 취소
                </Button>
              ) : (
                <Button onClick={handleStartAnalysis} disabled={!selectedCategory}>
                  <Play className="h-4 w-4 mr-2" />
                  분석 시작
                </Button>
              )}
            </div>
          </div>

          {/* 진행 상황 */}
          {currentJob && analyzing && (
            <div className="p-4 bg-blue-50 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <span className="font-medium">분석 진행 중...</span>
                </div>
                {getStatusBadge(currentJob.status)}
              </div>
              <Progress value={currentJob.progress} className="h-2" />
              <div className="flex justify-between text-sm text-muted-foreground">
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
            <BarChart3 className="h-5 w-5" />
            카테고리별 분석 현황
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {dashboard?.categories.map((cat) => {
              const Icon = CATEGORY_ICONS[cat.category] || FileText
              return (
                <div
                  key={cat.category}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${CATEGORY_COLORS[cat.category] || CATEGORY_COLORS.general}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-medium">{cat.category_name}</p>
                      <p className="text-xs text-muted-foreground">
                        글 {cat.posts_count}개 | 키워드 {cat.keywords_count}개
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm font-medium">샘플 {cat.sample_count}개</p>
                      <p className={`text-xs ${
                        cat.confidence >= 0.7 ? 'text-green-600' :
                        cat.confidence >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        신뢰도 {Math.round(cat.confidence * 100)}%
                      </p>
                    </div>
                    <div className="w-24">
                      <Progress value={cat.confidence * 100} className="h-2" />
                    </div>
                    {cat.sample_count >= 3 ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-yellow-500" />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* 최근 작업 이력 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            최근 분석 작업
          </CardTitle>
        </CardHeader>
        <CardContent>
          {dashboard?.recent_jobs.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              아직 분석 작업이 없습니다
            </p>
          ) : (
            <div className="space-y-2">
              {dashboard?.recent_jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {getStatusBadge(job.status)}
                    <div>
                      <p className="font-medium">{job.category_name}</p>
                      <p className="text-xs text-muted-foreground">
                        목표 {job.target_count}개 | 완료 {job.posts_analyzed}개
                      </p>
                    </div>
                  </div>
                  <div className="text-right text-sm text-muted-foreground">
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
                <Eye className="h-5 w-5" />
                분석 결과 조회
              </CardTitle>
              <CardDescription>
                카테고리를 선택하여 분석된 글과 발견된 공통점을 확인하세요
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
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
                  onClick={() => resultsCategory && loadAnalysisResults(resultsCategory)}
                  disabled={!resultsCategory || loadingResults}
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
            <Card className="border-indigo-200 bg-indigo-50/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-yellow-500" />
                  발견된 공통점
                  <Badge variant="outline" className="ml-2">
                    {patternsSummary.sample_count}개 글 분석
                  </Badge>
                </CardTitle>
                <CardDescription>
                  신뢰도 {Math.round(patternsSummary.confidence * 100)}%
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 요약 텍스트 */}
                {patternsSummary.summary && (
                  <div className="p-4 bg-white rounded-lg border whitespace-pre-line text-sm">
                    {patternsSummary.summary}
                  </div>
                )}

                {/* 인사이트 목록 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {patternsSummary.insights.map((insight, idx) => (
                    <div key={idx} className="p-3 bg-white rounded-lg border">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          {insight.category}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          신뢰도 {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-sm font-medium text-gray-800 mb-1">
                        {insight.finding}
                      </p>
                      <p className="text-xs text-indigo-600">
                        💡 {insight.recommendation}
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
                  <Database className="h-5 w-5" />
                  분석된 글 목록
                  <Badge variant="secondary" className="ml-2">
                    {analyzedPosts.length}개
                  </Badge>
                </CardTitle>
                <CardDescription>
                  키워드별로 상위 1~3위 글의 분석 결과를 확인하세요
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingResults ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  </div>
                ) : Object.keys(postsByKeyword).length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    분석된 글이 없습니다
                  </p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(postsByKeyword).map(([keyword, posts]) => (
                      <div key={keyword} className="border rounded-lg">
                        {/* 키워드 헤더 */}
                        <button
                          onClick={() => toggleKeyword(keyword)}
                          className="w-full p-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Search className="h-4 w-4 text-indigo-500" />
                            <span className="font-medium">{keyword}</span>
                            <Badge variant="outline" className="text-xs">
                              {posts.length}개 글
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-muted-foreground">
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
                          <div className="border-t p-3 space-y-2 bg-gray-50">
                            {posts.sort((a, b) => a.rank - b.rank).map((post) => (
                              <div
                                key={post.id}
                                className="p-3 bg-white rounded-lg border flex items-start gap-3"
                              >
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                                  post.rank === 1 ? 'bg-yellow-100 text-yellow-700' :
                                  post.rank === 2 ? 'bg-gray-100 text-gray-700' :
                                  'bg-orange-100 text-orange-700'
                                }`}>
                                  {post.rank}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <a
                                      href={post.post_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="font-medium text-blue-600 hover:underline truncate"
                                    >
                                      {post.title || '(제목 없음)'}
                                    </a>
                                    <ExternalLink className="h-3 w-3 text-gray-400 flex-shrink-0" />
                                  </div>
                                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                      📝 {post.content_length.toLocaleString()}자
                                    </span>
                                    <span className="flex items-center gap-1">
                                      🖼️ {post.image_count}장
                                    </span>
                                    <span className="flex items-center gap-1">
                                      📑 {post.heading_count}개 소제목
                                    </span>
                                    <span className="flex items-center gap-1">
                                      🔑 {post.keyword_count}회 키워드
                                    </span>
                                    {post.title_has_keyword && (
                                      <Badge variant="outline" className="text-green-600 border-green-300">
                                        제목에 키워드 포함
                                      </Badge>
                                    )}
                                    {post.has_map && (
                                      <Badge variant="outline" className="text-blue-600 border-blue-300">
                                        지도 포함
                                      </Badge>
                                    )}
                                  </div>
                                </div>
                                <Badge
                                  variant="outline"
                                  className={
                                    post.data_quality === 'high' ? 'text-green-600 border-green-300' :
                                    post.data_quality === 'medium' ? 'text-yellow-600 border-yellow-300' :
                                    'text-red-600 border-red-300'
                                  }
                                >
                                  {post.data_quality === 'high' ? '고품질' :
                                   post.data_quality === 'medium' ? '중품질' : '저품질'}
                                </Badge>
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
            <div className="text-center py-12 text-muted-foreground">
              <Eye className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p>카테고리를 선택하여 분석 결과를 확인하세요</p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
