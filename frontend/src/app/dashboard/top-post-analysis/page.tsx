'use client'

import { useState, useEffect, useCallback } from 'react'
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
  keywords_collected: number
  posts_analyzed: number
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

export default function TopPostAnalysisPage() {
  const [categories, setCategories] = useState<CategoryWithStats[]>([])
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [targetCount, setTargetCount] = useState<number>(100)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [currentJob, setCurrentJob] = useState<AnalysisJob | null>(null)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

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

  // 작업 상태 폴링
  const pollJobStatus = useCallback(async (jobId: string) => {
    try {
      const job = await topPostsAPI.getJobStatus(jobId)
      setCurrentJob(job)

      if (job.status === 'completed') {
        toast.success(`분석 완료! ${job.posts_analyzed}개 글 분석됨`)
        setAnalyzing(false)
        if (pollingInterval) {
          clearInterval(pollingInterval)
          setPollingInterval(null)
        }
        loadData() // 데이터 새로고침
      } else if (job.status === 'failed') {
        toast.error(`분석 실패: ${job.error_message || '알 수 없는 오류'}`)
        setAnalyzing(false)
        if (pollingInterval) {
          clearInterval(pollingInterval)
          setPollingInterval(null)
        }
      }
    } catch (error) {
      console.error('작업 상태 조회 실패:', error)
    }
  }, [pollingInterval, loadData])

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
      const jobId = response.job_id
      pollJobStatus(jobId)
      const interval = setInterval(() => pollJobStatus(jobId), 3000)
      setPollingInterval(interval)
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
      if (pollingInterval) {
        clearInterval(pollingInterval)
        setPollingInterval(null)
      }
    } catch (error) {
      toast.error('취소 실패')
    }
  }

  // 정리
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

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
    </div>
  )
}
