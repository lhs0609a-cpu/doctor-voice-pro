'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { postsAPI, systemAPI } from '@/lib/api'
import type { Post } from '@/types'
import {
  FileText,
  TrendingUp,
  Eye,
  PenTool,
  ArrowRight,
  Calendar,
  Sparkles,
  CheckCircle2,
  XCircle,
  Server,
  Send,
  DollarSign,
  Clock,
  Zap,
  Trophy,
  Settings,
  X,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import UsageWidget from '@/components/dashboard/UsageWidget'
import { toast } from 'sonner'

// ROI 설정 기본값
const DEFAULT_ROI_SETTINGS = {
  outsourcingCost: 25000,  // 글당 외주비
  hourlyRate: 30000,       // 시급 (시간 환산용)
  subscriptionFee: 79000,  // 월 구독료
}

export default function DashboardPage() {
  const router = useRouter()
  const [posts, setPosts] = useState<Post[]>([])
  const [stats, setStats] = useState({
    total: 0,
    thisMonth: 0,
    avgScore: 0,
  })
  const [loading, setLoading] = useState(true)
  const [systemInfo, setSystemInfo] = useState<{
    version: string
    status: string
    aiConnected: boolean
  } | null>(null)

  // ROI 설정 상태
  const [roiSettings, setRoiSettings] = useState(DEFAULT_ROI_SETTINGS)
  const [showRoiSettings, setShowRoiSettings] = useState(false)
  const [tempRoiSettings, setTempRoiSettings] = useState(DEFAULT_ROI_SETTINGS)

  useEffect(() => {
    loadPosts()
    loadSystemInfo()
    loadRoiSettings()
  }, [])

  // ROI 설정 로드
  const loadRoiSettings = () => {
    try {
      const saved = localStorage.getItem('roi-settings')
      if (saved) {
        const parsed = JSON.parse(saved)
        setRoiSettings({ ...DEFAULT_ROI_SETTINGS, ...parsed })
        setTempRoiSettings({ ...DEFAULT_ROI_SETTINGS, ...parsed })
      }
    } catch (error) {
      console.error('Failed to load ROI settings:', error)
    }
  }

  // ROI 설정 저장
  const saveRoiSettings = () => {
    try {
      localStorage.setItem('roi-settings', JSON.stringify(tempRoiSettings))
      setRoiSettings(tempRoiSettings)
      setShowRoiSettings(false)
      toast.success('ROI 설정이 저장되었습니다')
    } catch (error) {
      console.error('Failed to save ROI settings:', error)
      toast.error('설정 저장에 실패했습니다')
    }
  }

  // Post를 SavedPost 형식으로 변환하여 localStorage에 저장하고 발행 페이지로 이동
  const handlePublish = (post: Post) => {
    // SavedPost 형식으로 변환
    const savedPost = {
      id: `db-post-${post.id}`,
      savedAt: new Date().toISOString(),
      suggested_titles: post.suggested_titles || (post.title ? [post.title] : []),
      generated_content: post.generated_content || '',
      seo_keywords: post.seo_keywords || [],
      original_content: post.original_content || '',
      title: post.title || '',
      content: post.generated_content || '',
      // DB Post 식별을 위한 추가 필드
      sourcePostId: post.id,
      sourceType: 'database',
    }

    try {
      // 기존 저장된 글 로드
      const existing = localStorage.getItem('saved-posts')
      const posts = existing ? JSON.parse(existing) : []

      // 이미 같은 Post가 저장되어 있는지 확인
      const existingIndex = posts.findIndex((p: any) => p.sourcePostId === post.id)

      if (existingIndex >= 0) {
        // 기존 항목 업데이트
        posts[existingIndex] = savedPost
      } else {
        // 새로 추가 (맨 앞에)
        posts.unshift(savedPost)
      }

      localStorage.setItem('saved-posts', JSON.stringify(posts))

      // 선택할 글 ID를 저장 (저장된 글 페이지에서 자동 선택용)
      localStorage.setItem('saved-posts-select', savedPost.id)

      toast.success('발행 준비 완료', {
        description: '저장된 글 페이지로 이동합니다',
      })

      // 저장된 글 페이지로 이동
      router.push('/dashboard/saved')
    } catch (error) {
      console.error('발행 준비 실패:', error)
      toast.error('발행 준비에 실패했습니다')
    }
  }

  const loadSystemInfo = async () => {
    try {
      const [info, health] = await Promise.all([
        systemAPI.getInfo(),
        systemAPI.healthCheck(),
      ])
      setSystemInfo({
        version: info.version,
        status: health.status,
        aiConnected: health.ai?.connected || false,
      })
    } catch (error) {
      console.error('Failed to load system info:', error)
      setSystemInfo({
        version: '-',
        status: 'offline',
        aiConnected: false,
      })
    }
  }

  const loadPosts = async () => {
    try {
      const response = await postsAPI.list(1, 5)
      setPosts(response.posts)

      // Calculate stats
      const thisMonth = response.posts.filter((post) => {
        const postDate = new Date(post.created_at)
        const now = new Date()
        return (
          postDate.getMonth() === now.getMonth() &&
          postDate.getFullYear() === now.getFullYear()
        )
      }).length

      const avgScore =
        response.posts.length > 0
          ? response.posts.reduce((sum, p) => sum + p.persuasion_score, 0) /
            response.posts.length
          : 0

      setStats({
        total: response.total,
        thisMonth,
        avgScore: Math.round(avgScore),
      })
    } catch (error) {
      console.error('Failed to load posts:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Welcome Section */}
      <div className="pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold mb-3 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">대시보드</h1>
          <p className="text-lg text-gray-600">AI 블로그 각색 현황을 한눈에 확인하세요</p>
        </div>
        {/* System Status */}
        <div className="flex items-center gap-4 bg-white rounded-xl px-5 py-3 shadow-md border border-gray-100">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-600">v{systemInfo?.version || '...'}</span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          <div className="flex items-center gap-2">
            {systemInfo?.status === 'healthy' ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : systemInfo?.status === 'offline' ? (
              <XCircle className="h-4 w-4 text-red-500" />
            ) : (
              <div className="h-4 w-4 rounded-full border-2 border-gray-300 border-t-transparent animate-spin" />
            )}
            <span className={`text-sm font-medium ${
              systemInfo?.status === 'healthy' ? 'text-green-600' :
              systemInfo?.status === 'offline' ? 'text-red-600' : 'text-gray-500'
            }`}>
              {systemInfo?.status === 'healthy' ? '서버 정상' :
               systemInfo?.status === 'offline' ? '서버 오프라인' : '확인 중...'}
            </span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          <div className="flex items-center gap-2">
            {systemInfo?.aiConnected ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <span className={`text-sm font-medium ${
              systemInfo?.aiConnected ? 'text-green-600' : 'text-red-600'
            }`}>
              AI {systemInfo?.aiConnected ? '연결됨' : '미연결'}
            </span>
          </div>
        </div>
      </div>

      {/* Quick Action */}
      <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50 via-purple-50 to-white shadow-lg hover:shadow-xl transition-all duration-300 animate-fade-in-up animation-delay-200">
        <CardContent className="pt-8 pb-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <PenTool className="h-6 w-6 text-blue-600" />
                <h3 className="text-2xl font-bold text-gray-800">새 포스팅 작성</h3>
              </div>
              <p className="text-base text-gray-600">
                AI가 5분 만에 설득력 있는 블로그 글을 만들어드립니다
              </p>
            </div>
            <Link href="/dashboard/create">
              <Button size="lg" className="gap-2 px-8 py-6 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all">
                <Sparkles className="h-5 w-5" />
                글 작성하기
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* P3: 통합된 통계 카드 (4개 → 2개로 축소) */}
      <div className="grid md:grid-cols-2 gap-6 animate-fade-in-up animation-delay-400">
        {/* 작성 현황 통합 카드 */}
        <Card className="border-2 border-transparent hover:border-blue-200 shadow-md hover:shadow-xl transition-all duration-300 bg-gradient-to-br from-blue-50 via-purple-50 to-white">
          <CardContent className="pt-5 pb-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <FileText className="h-4 w-4 text-blue-600" />
                  </div>
                  <span className="text-sm font-semibold text-gray-700">작성 현황</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-2xl font-bold text-blue-600">{stats.total}개</div>
                    <p className="text-xs text-gray-500">총 포스팅</p>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-purple-600">{stats.thisMonth}개</div>
                    <p className="text-xs text-gray-500">이번 달</p>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-1.5 mb-1">
                  <TrendingUp className="h-4 w-4 text-gray-400" />
                  <span className="text-xs text-gray-500">평균 설득력</span>
                </div>
                <div className="flex items-baseline gap-1.5 justify-end">
                  <span className={`text-2xl font-bold ${
                    stats.avgScore >= 80 ? 'text-emerald-600' :
                    stats.avgScore >= 60 ? 'text-purple-600' : 'text-amber-600'
                  }`}>{stats.avgScore}</span>
                  <span className="text-sm text-gray-500">점</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  stats.avgScore >= 80 ? 'bg-emerald-100 text-emerald-700' :
                  stats.avgScore >= 60 ? 'bg-purple-100 text-purple-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {stats.avgScore >= 80 ? '상위 10%' : stats.avgScore >= 60 ? '상위 25%' : '평균'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 시간/사용량 통합 카드 */}
        <Card className="border-2 border-transparent hover:border-green-200 shadow-md hover:shadow-xl transition-all duration-300 bg-gradient-to-br from-green-50 via-teal-50 to-white">
          <CardContent className="pt-5 pb-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="h-8 w-8 rounded-full bg-green-100 flex items-center justify-center">
                    <Clock className="h-4 w-4 text-green-600" />
                  </div>
                  <span className="text-sm font-semibold text-gray-700">시간 절약</span>
                </div>
                <div className="text-2xl font-bold text-green-600">{Math.round(stats.thisMonth * 55 / 60 * 10) / 10}시간</div>
                <p className="text-xs text-gray-500">이번 달 기준 (글당 55분 절약)</p>
              </div>
              <div className="w-px h-16 bg-gray-200 mx-4" />
              <UsageWidget compact inline />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ROI Dashboard - 구독 가치 시각화 */}
      <Card className="border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 via-teal-50 to-white shadow-lg animate-fade-in-up animation-delay-500">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-10 w-10 rounded-full bg-emerald-100 flex items-center justify-center">
                <Trophy className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <CardTitle className="text-xl font-bold text-gray-800">이번 달 ROI 분석</CardTitle>
                <CardDescription className="text-sm text-gray-600">닥터보이스 프로로 절약한 비용과 시간</CardDescription>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-gray-500 hover:text-gray-700"
              onClick={() => {
                setTempRoiSettings(roiSettings)
                setShowRoiSettings(true)
              }}
            >
              <Settings className="h-4 w-4" />
              설정
            </Button>
          </div>
        </CardHeader>

        {/* ROI 설정 패널 */}
        {showRoiSettings && (
          <div className="mx-6 mb-4 p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold text-gray-800">ROI 계산 설정</h4>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setShowRoiSettings(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="outsourcingCost" className="text-sm font-medium text-gray-700">
                  글당 외주비 (원)
                </Label>
                <Input
                  id="outsourcingCost"
                  type="number"
                  value={tempRoiSettings.outsourcingCost}
                  onChange={(e) => setTempRoiSettings(prev => ({
                    ...prev,
                    outsourcingCost: Number(e.target.value) || 0
                  }))}
                  className="text-right"
                />
                <p className="text-xs text-gray-500">블로그 글 1건당 외주 비용</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="hourlyRate" className="text-sm font-medium text-gray-700">
                  내 시급 (원)
                </Label>
                <Input
                  id="hourlyRate"
                  type="number"
                  value={tempRoiSettings.hourlyRate}
                  onChange={(e) => setTempRoiSettings(prev => ({
                    ...prev,
                    hourlyRate: Number(e.target.value) || 0
                  }))}
                  className="text-right"
                />
                <p className="text-xs text-gray-500">절약 시간의 가치 환산용</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="subscriptionFee" className="text-sm font-medium text-gray-700">
                  월 구독료 (원)
                </Label>
                <Input
                  id="subscriptionFee"
                  type="number"
                  value={tempRoiSettings.subscriptionFee}
                  onChange={(e) => setTempRoiSettings(prev => ({
                    ...prev,
                    subscriptionFee: Number(e.target.value) || 0
                  }))}
                  className="text-right"
                />
                <p className="text-xs text-gray-500">현재 구독 플랜 기준</p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setTempRoiSettings(DEFAULT_ROI_SETTINGS)
                }}
              >
                기본값
              </Button>
              <Button
                size="sm"
                onClick={saveRoiSettings}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                저장
              </Button>
            </div>
          </div>
        )}
        <CardContent>
          {/* P3: ROI 카드 통합 (4개 → 2개로 축소) */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* 비용 절약 통합 */}
            <div className="bg-white rounded-xl p-4 border border-emerald-100 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <DollarSign className="h-5 w-5 text-emerald-600" />
                    <span className="text-sm font-semibold text-gray-700">비용 절약</span>
                  </div>
                  <p className="text-3xl font-bold text-emerald-600">
                    ₩{((stats.thisMonth * roiSettings.outsourcingCost) + (Math.round(stats.thisMonth * 55 / 60) * roiSettings.hourlyRate)).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    외주비 ₩{(stats.thisMonth * roiSettings.outsourcingCost).toLocaleString()} + 시간가치 ₩{(Math.round(stats.thisMonth * 55 / 60) * roiSettings.hourlyRate).toLocaleString()}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500 mb-1">시간 절약</div>
                  <div className="text-xl font-bold text-blue-600">{Math.round(stats.thisMonth * 55 / 60 * 10) / 10}h</div>
                </div>
              </div>
            </div>

            {/* ROI & 효율성 통합 */}
            <div className="bg-white rounded-xl p-4 border border-purple-100 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Trophy className="h-5 w-5 text-purple-600" />
                    <span className="text-sm font-semibold text-gray-700">투자 대비 효과</span>
                  </div>
                  <div className="flex items-baseline gap-3">
                    <p className="text-3xl font-bold text-purple-600">
                      {stats.thisMonth > 0 && roiSettings.subscriptionFee > 0
                        ? `${Math.round((stats.thisMonth * roiSettings.outsourcingCost) / roiSettings.subscriptionFee * 100)}%`
                        : '0%'}
                    </p>
                    <span className={`text-sm font-medium px-2 py-0.5 rounded-full ${
                      (() => {
                        const breakEven = roiSettings.subscriptionFee > 0 ? Math.ceil(roiSettings.subscriptionFee / roiSettings.outsourcingCost) : 4
                        return stats.thisMonth >= breakEven ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                      })()
                    }`}>
                      {(() => {
                        const breakEven = roiSettings.subscriptionFee > 0 ? Math.ceil(roiSettings.subscriptionFee / roiSettings.outsourcingCost) : 4
                        return stats.thisMonth >= breakEven ? '✓ 본전 달성!' : `${breakEven - stats.thisMonth}건 더 필요`
                      })()}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">구독료 ₩{roiSettings.subscriptionFee.toLocaleString()} 대비</p>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500 mb-1">생산성</div>
                  <div className="text-xl font-bold text-amber-600">{stats.thisMonth > 0 ? '12x' : '-'}</div>
                  <div className="text-[10px] text-gray-400">빠른 속도</div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Posts */}
      <Card className="shadow-lg border-2 animate-fade-in-up animation-delay-600">
        <CardHeader className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl font-bold text-gray-800">최근 포스팅</CardTitle>
              <CardDescription className="text-base text-gray-600">최근 작성한 블로그 글 목록</CardDescription>
            </div>
            <Link href="/dashboard/posts">
              <Button variant="ghost" size="sm" className="gap-2 hover:bg-white transition-all">
                전체 보기
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="text-gray-600 mt-4 font-medium">로딩 중...</p>
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-12">
              <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 flex items-center justify-center mx-auto mb-4">
                <FileText className="h-10 w-10 text-blue-600" />
              </div>
              <p className="text-gray-600 mb-6 text-lg">아직 작성한 포스팅이 없습니다</p>
              <Link href="/dashboard/create">
                <Button size="lg" className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all">
                  <Sparkles className="h-5 w-5 mr-2" />
                  첫 포스팅 작성하기
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((post, index) => (
                <div
                  key={post.id}
                  className="flex flex-col md:flex-row items-start md:items-center justify-between p-5 rounded-xl border-2 border-gray-100 hover:border-blue-200 hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 transition-all duration-300 shadow-sm hover:shadow-md"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="flex-1 mb-3 md:mb-0">
                    <h4 className="font-bold text-lg mb-2 text-gray-800">
                      {post.title || '제목 없음'}
                    </h4>
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <span className="flex items-center gap-1.5 text-gray-600 font-medium">
                        <Calendar className="h-4 w-4 text-blue-600" />
                        {formatDate(post.created_at)}
                      </span>
                      <span className="flex items-center gap-1.5 text-gray-600 font-medium">
                        <TrendingUp className="h-4 w-4 text-purple-600" />
                        설득력 {Math.round(post.persuasion_score)}점
                      </span>
                      {/* P3: DIA/CRANK 점수 요약 */}
                      {post.dia_crank_analysis && (
                        <div className="flex items-center gap-2 px-2 py-1 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-100">
                          <div className="flex items-center gap-1" title="DIA 점수 (체험·정보·독창·시의성)">
                            <span className="text-[10px] font-bold text-blue-600">DIA</span>
                            <span className={`text-xs font-bold ${
                              post.dia_crank_analysis.dia_score.total >= 80 ? 'text-emerald-600' :
                              post.dia_crank_analysis.dia_score.total >= 60 ? 'text-blue-600' : 'text-amber-600'
                            }`}>{Math.round(post.dia_crank_analysis.dia_score.total)}</span>
                          </div>
                          <div className="w-px h-3 bg-gray-300" />
                          <div className="flex items-center gap-1" title="C-RANK 점수 (맥락·콘텐츠·연결·창작자)">
                            <span className="text-[10px] font-bold text-purple-600">CRANK</span>
                            <span className={`text-xs font-bold ${
                              post.dia_crank_analysis.crank_score.total >= 80 ? 'text-emerald-600' :
                              post.dia_crank_analysis.crank_score.total >= 60 ? 'text-purple-600' : 'text-amber-600'
                            }`}>{Math.round(post.dia_crank_analysis.crank_score.total)}</span>
                          </div>
                          {post.dia_crank_analysis.overall_grade && (
                            <>
                              <div className="w-px h-3 bg-gray-300" />
                              <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                                post.dia_crank_analysis.overall_grade === 'A' ? 'bg-emerald-100 text-emerald-700' :
                                post.dia_crank_analysis.overall_grade === 'B' ? 'bg-blue-100 text-blue-700' :
                                post.dia_crank_analysis.overall_grade === 'C' ? 'bg-amber-100 text-amber-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>{post.dia_crank_analysis.overall_grade}등급</span>
                            </>
                          )}
                        </div>
                      )}
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold ${
                          post.status === 'published'
                            ? 'bg-green-100 text-green-700 border border-green-300'
                            : 'bg-gray-100 text-gray-700 border border-gray-300'
                        }`}
                      >
                        {post.status === 'published' ? '발행됨' : '임시저장'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 text-white font-medium gap-1.5"
                      onClick={() => handlePublish(post)}
                    >
                      <Send className="h-3.5 w-3.5" />
                      발행하기
                    </Button>
                    <Link href={`/dashboard/posts/${post.id}`}>
                      <Button variant="ghost" size="sm" className="hover:bg-blue-100 transition-all font-medium">
                        상세보기
                        <ArrowRight className="h-4 w-4 ml-1" />
                      </Button>
                    </Link>
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
