'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import {
  Coffee,
  Search,
  Plus,
  RefreshCw,
  Loader2,
  Eye,
  MessageSquare,
  CheckCircle,
  XCircle,
  Star,
  ExternalLink,
  Sparkles,
  FileText,
  Settings,
  TrendingUp,
  Clock,
  Trash2,
  Copy,
  Play,
  Square,
  Zap,
  LogIn,
  LogOut,
  Upload,
  Bot,
  Users,
  Heart,
  Hash
} from 'lucide-react'
import {
  cafeAPI,
  CafeCommunity,
  CafeKeyword,
  CafePost,
  CafeContent,
  CafeDashboard,
  CafePostStatus,
  CafeContentStatus,
  CafeTone,
  CafeCategory,
  CafeAccount,
  CafeAccountStats
} from '@/lib/api'
import { toast } from 'sonner'

const TONE_OPTIONS = [
  { value: 'friendly', label: '친근한' },
  { value: 'casual', label: '캐주얼' },
  { value: 'professional', label: '전문적' },
  { value: 'empathetic', label: '공감하는' },
  { value: 'humorous', label: '유머러스' },
]

const CATEGORY_OPTIONS = [
  { value: 'mom', label: '맘카페' },
  { value: 'beauty', label: '뷰티/미용' },
  { value: 'health', label: '건강/의료' },
  { value: 'regional', label: '지역' },
  { value: 'hobby', label: '취미/관심사' },
  { value: 'general', label: '일반' },
]

export default function CafePage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [isLoading, setIsLoading] = useState(true)

  // Data states
  const [dashboard, setDashboard] = useState<CafeDashboard | null>(null)
  const [cafes, setCafes] = useState<CafeCommunity[]>([])
  const [keywords, setKeywords] = useState<CafeKeyword[]>([])
  const [posts, setPosts] = useState<CafePost[]>([])
  const [contents, setContents] = useState<CafeContent[]>([])
  const [topPosts, setTopPosts] = useState<CafePost[]>([])

  // UI states
  const [isCollecting, setIsCollecting] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedPost, setSelectedPost] = useState<CafePost | null>(null)
  const [selectedContent, setSelectedContent] = useState<CafeContent | null>(null)

  // Automation states
  const [schedulerStatus, setSchedulerStatus] = useState<{
    is_running: boolean
    is_enabled: boolean
    is_working_hours: boolean
    today: { collected: number; generated: number; posted: number; collect_limit: number; post_limit: number }
    pending: { posts: number; contents: number }
  } | null>(null)
  const [posterStatus, setPosterStatus] = useState<{ initialized: boolean; logged_in: boolean } | null>(null)
  const [isPosting, setIsPosting] = useState(false)

  // Account states
  const [accounts, setAccounts] = useState<CafeAccount[]>([])
  const [accountStats, setAccountStats] = useState<CafeAccountStats | null>(null)
  const [isAccountDialogOpen, setIsAccountDialogOpen] = useState(false)
  const [newAccount, setNewAccount] = useState({
    account_id: '',
    password: '',
    account_name: '',
    daily_comment_limit: 10,
    daily_post_limit: 2,
    memo: ''
  })

  // Dialog states
  const [isCafeDialogOpen, setIsCafeDialogOpen] = useState(false)
  const [isKeywordDialogOpen, setIsKeywordDialogOpen] = useState(false)
  const [isContentDialogOpen, setIsContentDialogOpen] = useState(false)
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false)

  // Login form
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })

  // Form states
  const [newCafe, setNewCafe] = useState({
    cafe_id: '',
    cafe_name: '',
    cafe_url: '',
    category: 'general' as CafeCategory,
    posting_enabled: false,
    commenting_enabled: true
  })
  const [newKeyword, setNewKeyword] = useState({ keyword: '', category: '', priority: 1 })
  const [contentSettings, setContentSettings] = useState({
    tone: 'friendly' as CafeTone,
    include_promotion: true,
    blog_link: '',
    place_link: ''
  })

  // Filters
  const [postFilter, setPostFilter] = useState<CafePostStatus | ''>('')
  const [contentFilter, setContentFilter] = useState<CafeContentStatus | ''>('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [dashboardData, cafesData, keywordsData, topPostsData] = await Promise.all([
        cafeAPI.getDashboard(),
        cafeAPI.getCafes(),
        cafeAPI.getKeywords(),
        cafeAPI.getTopPosts(5)
      ])
      setDashboard(dashboardData)
      setCafes(cafesData)
      setKeywords(keywordsData)
      setTopPosts(topPostsData)
    } catch (error) {
      console.error('Failed to load data:', error)
      toast.error('데이터 로딩 실패')
    } finally {
      setIsLoading(false)
    }
  }

  const loadPosts = async () => {
    try {
      const data = await cafeAPI.getPosts({
        status: postFilter || undefined,
        limit: 50
      })
      setPosts(data)
    } catch (error) {
      toast.error('게시글 로딩 실패')
    }
  }

  const loadContents = async () => {
    try {
      const data = await cafeAPI.getContents({
        status: contentFilter || undefined,
        limit: 50
      })
      setContents(data)
    } catch (error) {
      toast.error('콘텐츠 로딩 실패')
    }
  }

  useEffect(() => {
    if (activeTab === 'posts') loadPosts()
    if (activeTab === 'contents') {
      loadContents()
      loadAutomationStatus()
    }
    if (activeTab === 'automation') loadAutomationStatus()
    if (activeTab === 'accounts') loadAccounts()
  }, [activeTab, postFilter, contentFilter])

  // 게시글 수집
  const handleCollect = async () => {
    setIsCollecting(true)
    try {
      const result = await cafeAPI.collectPosts()
      toast.success(result.message)
      loadData()
      if (activeTab === 'posts') loadPosts()
    } catch (error) {
      toast.error('게시글 수집 실패')
    } finally {
      setIsCollecting(false)
    }
  }

  // 콘텐츠 생성
  const handleGenerateContent = async (postId: string) => {
    setIsGenerating(true)
    try {
      const content = await cafeAPI.generateContent({
        post_id: postId,
        tone: contentSettings.tone,
        include_promotion: contentSettings.include_promotion,
        blog_link: contentSettings.blog_link || undefined,
        place_link: contentSettings.place_link || undefined
      })
      toast.success('콘텐츠가 생성되었습니다')
      setSelectedContent(content)
      setIsContentDialogOpen(true)
      loadPosts()
    } catch (error) {
      toast.error('콘텐츠 생성 실패')
    } finally {
      setIsGenerating(false)
    }
  }

  // 카페 추가
  const handleAddCafe = async () => {
    if (!newCafe.cafe_id || !newCafe.cafe_name) {
      toast.error('카페 ID와 이름을 입력해주세요')
      return
    }
    try {
      await cafeAPI.createCafe(newCafe)
      toast.success('카페가 추가되었습니다')
      setIsCafeDialogOpen(false)
      setNewCafe({
        cafe_id: '',
        cafe_name: '',
        cafe_url: '',
        category: 'general',
        posting_enabled: false,
        commenting_enabled: true
      })
      loadData()
    } catch (error) {
      toast.error('카페 추가 실패')
    }
  }

  // 카페 삭제
  const handleDeleteCafe = async (cafeId: string) => {
    try {
      await cafeAPI.deleteCafe(cafeId)
      toast.success('카페가 삭제되었습니다')
      loadData()
    } catch (error) {
      toast.error('카페 삭제 실패')
    }
  }

  // 키워드 추가
  const handleAddKeyword = async () => {
    if (!newKeyword.keyword) {
      toast.error('키워드를 입력해주세요')
      return
    }
    try {
      await cafeAPI.createKeyword({
        keyword: newKeyword.keyword,
        category: newKeyword.category || undefined,
        priority: newKeyword.priority
      })
      toast.success('키워드가 추가되었습니다')
      setIsKeywordDialogOpen(false)
      setNewKeyword({ keyword: '', category: '', priority: 1 })
      loadData()
    } catch (error) {
      toast.error('키워드 추가 실패')
    }
  }

  // 키워드 삭제
  const handleDeleteKeyword = async (keywordId: string) => {
    try {
      await cafeAPI.deleteKeyword(keywordId)
      toast.success('키워드가 삭제되었습니다')
      loadData()
    } catch (error) {
      toast.error('키워드 삭제 실패')
    }
  }

  // 콘텐츠 승인
  const handleApproveContent = async (contentId: string) => {
    try {
      await cafeAPI.approveContent(contentId)
      toast.success('콘텐츠가 승인되었습니다')
      loadContents()
    } catch (error) {
      toast.error('승인 실패')
    }
  }

  // 콘텐츠 반려
  const handleRejectContent = async (contentId: string) => {
    try {
      await cafeAPI.rejectContent(contentId)
      toast.success('콘텐츠가 반려되었습니다')
      loadContents()
    } catch (error) {
      toast.error('반려 실패')
    }
  }

  // 클립보드 복사
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('클립보드에 복사되었습니다')
  }

  // 자동화 상태 로드
  const loadAutomationStatus = async () => {
    try {
      const [schedulerData, posterData] = await Promise.all([
        cafeAPI.getSchedulerStatus(),
        cafeAPI.getPosterStatus()
      ])
      setSchedulerStatus(schedulerData)
      setPosterStatus(posterData)
    } catch (error) {
      console.error('Failed to load automation status:', error)
    }
  }

  // 계정 로드
  const loadAccounts = async () => {
    try {
      const [accountsData, statsData] = await Promise.all([
        cafeAPI.getAccounts(),
        cafeAPI.getAccountStats()
      ])
      setAccounts(accountsData)
      setAccountStats(statsData)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    }
  }

  // 계정 추가
  const handleAddAccount = async () => {
    if (!newAccount.account_id || !newAccount.password) {
      toast.error('아이디와 비밀번호를 입력해주세요')
      return
    }
    try {
      await cafeAPI.createAccount(newAccount)
      toast.success('계정이 추가되었습니다')
      setIsAccountDialogOpen(false)
      setNewAccount({
        account_id: '',
        password: '',
        account_name: '',
        daily_comment_limit: 10,
        daily_post_limit: 2,
        memo: ''
      })
      loadAccounts()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '계정 추가 실패')
    }
  }

  // 계정 삭제
  const handleDeleteAccount = async (accountId: string) => {
    try {
      await cafeAPI.deleteAccount(accountId)
      toast.success('계정이 삭제되었습니다')
      loadAccounts()
    } catch (error) {
      toast.error('계정 삭제 실패')
    }
  }

  // 계정 워밍업
  const handleStartWarmup = async (accountId: string) => {
    try {
      await cafeAPI.startAccountWarmup(accountId)
      toast.success('워밍업이 시작되었습니다')
      loadAccounts()
    } catch (error) {
      toast.error('워밍업 시작 실패')
    }
  }

  // 계정 상태 변경
  const handleAccountStatusChange = async (accountId: string, status: string) => {
    try {
      await cafeAPI.updateAccountStatus(accountId, { status })
      toast.success('상태가 변경되었습니다')
      loadAccounts()
    } catch (error) {
      toast.error('상태 변경 실패')
    }
  }

  // 다중 계정 로테이션 게시
  const handleRotatedPost = async (contentId: string) => {
    setIsPosting(true)
    try {
      const result = await cafeAPI.postContentRotated(contentId)
      if (result.success) {
        toast.success(`${result.account_name || '계정'}으로 등록 완료`)
        loadContents()
        loadAccounts()
      } else {
        toast.error(result.message || '등록 실패')
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '로테이션 게시 실패')
    } finally {
      setIsPosting(false)
    }
  }

  // 다중 계정 일괄 게시
  const handleBulkRotatedPost = async () => {
    setIsPosting(true)
    try {
      const result = await cafeAPI.postMultipleRotated(5)
      toast.success(`${result.posted || 0}개 등록 완료, ${result.failed || 0}개 실패`)
      loadContents()
      loadAccounts()
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '일괄 게시 실패')
    } finally {
      setIsPosting(false)
    }
  }

  // 풀 자동화 시작
  const handleStartFullAutomation = async () => {
    try {
      await cafeAPI.startFullAutomation()
      toast.success('풀 자동화가 시작되었습니다')
      loadAutomationStatus()
    } catch (error) {
      toast.error('풀 자동화 시작 실패')
    }
  }

  // 스케줄러 시작
  const handleStartScheduler = async () => {
    try {
      await cafeAPI.startScheduler()
      toast.success('스케줄러가 시작되었습니다')
      loadAutomationStatus()
    } catch (error) {
      toast.error('스케줄러 시작 실패')
    }
  }

  // 스케줄러 중지
  const handleStopScheduler = async () => {
    try {
      await cafeAPI.stopScheduler()
      toast.success('스케줄러가 중지되었습니다')
      loadAutomationStatus()
    } catch (error) {
      toast.error('스케줄러 중지 실패')
    }
  }

  // 수동 수집 실행
  const handleRunCollection = async () => {
    setIsCollecting(true)
    try {
      const result = await cafeAPI.runCollectionJob()
      toast.success(`${result.collected || 0}개 게시글 수집 완료`)
      loadData()
      loadAutomationStatus()
    } catch (error) {
      toast.error('수집 작업 실패')
    } finally {
      setIsCollecting(false)
    }
  }

  // 수동 콘텐츠 생성 실행
  const handleRunGeneration = async () => {
    setIsGenerating(true)
    try {
      const result = await cafeAPI.runGenerationJob()
      toast.success(`${result.generated || 0}개 콘텐츠 생성 완료`)
      loadData()
      loadAutomationStatus()
    } catch (error) {
      toast.error('콘텐츠 생성 작업 실패')
    } finally {
      setIsGenerating(false)
    }
  }

  // 포스터 로그인
  const handlePosterLogin = async () => {
    if (!loginForm.username || !loginForm.password) {
      toast.error('아이디와 비밀번호를 입력해주세요')
      return
    }
    try {
      await cafeAPI.posterLogin(loginForm)
      toast.success('네이버 로그인 성공')
      setIsLoginDialogOpen(false)
      setLoginForm({ username: '', password: '' })
      loadAutomationStatus()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '로그인 실패')
    }
  }

  // 포스터 로그아웃
  const handlePosterLogout = async () => {
    try {
      await cafeAPI.posterLogout()
      toast.success('로그아웃되었습니다')
      loadAutomationStatus()
    } catch (error) {
      toast.error('로그아웃 실패')
    }
  }

  // 자동 콘텐츠 등록
  const handleAutoPost = async (contentId: string) => {
    setIsPosting(true)
    try {
      const result = await cafeAPI.postContent(contentId)
      if (result.success) {
        toast.success('콘텐츠가 등록되었습니다')
        loadContents()
        loadData()
      } else {
        toast.error(result.message || '등록 실패')
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '콘텐츠 등록 실패')
    } finally {
      setIsPosting(false)
    }
  }

  // 일괄 콘텐츠 등록
  const handleBulkPost = async () => {
    setIsPosting(true)
    try {
      const result = await cafeAPI.postMultipleContents({ limit: 5, delay_between: 30 })
      toast.success(`${result.posted || 0}개 등록 완료, ${result.failed || 0}개 실패`)
      loadContents()
      loadData()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '일괄 등록 실패')
    } finally {
      setIsPosting(false)
    }
  }

  const getStatusBadge = (status: CafePostStatus | CafeContentStatus) => {
    const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      new: { label: '신규', variant: 'default' },
      analyzed: { label: '분석됨', variant: 'secondary' },
      commented: { label: '댓글완료', variant: 'outline' },
      skipped: { label: '건너뜀', variant: 'destructive' },
      draft: { label: '초안', variant: 'secondary' },
      approved: { label: '승인됨', variant: 'default' },
      posted: { label: '등록됨', variant: 'outline' },
      rejected: { label: '반려됨', variant: 'destructive' },
      failed: { label: '실패', variant: 'destructive' },
    }
    const config = statusConfig[status] || { label: status, variant: 'secondary' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
  }

  const getCategoryBadge = (category: CafeCategory) => {
    const categoryConfig: Record<string, string> = {
      mom: '맘카페',
      beauty: '뷰티',
      health: '건강',
      regional: '지역',
      hobby: '취미',
      general: '일반',
    }
    return <Badge variant="outline">{categoryConfig[category] || category}</Badge>
  }

  const getContentTypeBadge = (type: string) => {
    const typeConfig: Record<string, { label: string; color: string }> = {
      comment: { label: '댓글', color: 'bg-blue-100 text-blue-800' },
      reply: { label: '대댓글', color: 'bg-purple-100 text-purple-800' },
      post: { label: '새 글', color: 'bg-green-100 text-green-800' },
    }
    const config = typeConfig[type] || { label: type, color: 'bg-gray-100 text-gray-800' }
    return <Badge className={config.color}>{config.label}</Badge>
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
        <DashboardNav />
        <main className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-orange-600" />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
      <DashboardNav />

      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Coffee className="h-8 w-8 text-orange-600" />
              카페 바이럴 자동화
            </h1>
            <p className="text-gray-600 mt-1">
              네이버 카페에 자동으로 글과 댓글을 등록하세요
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={loadData}>
              <RefreshCw className="h-4 w-4 mr-2" />
              새로고침
            </Button>
            <Button onClick={handleCollect} disabled={isCollecting}>
              {isCollecting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Search className="h-4 w-4 mr-2" />
              )}
              게시글 수집
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">활성 카페</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {dashboard?.active_cafes || 0}
                  </p>
                </div>
                <Users className="h-8 w-8 text-orange-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">오늘 수집</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {dashboard?.posts_collected_today || 0}
                  </p>
                </div>
                <Search className="h-8 w-8 text-blue-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">대기 콘텐츠</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {dashboard?.pending_contents || 0}
                  </p>
                </div>
                <FileText className="h-8 w-8 text-purple-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">오늘 등록</p>
                  <p className="text-2xl font-bold text-green-600">
                    {(dashboard?.posts_published_today || 0) + (dashboard?.comments_published_today || 0)}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-green-200" />
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="overview">개요</TabsTrigger>
            <TabsTrigger value="posts">게시글 모니터링</TabsTrigger>
            <TabsTrigger value="contents">콘텐츠 관리</TabsTrigger>
            <TabsTrigger value="automation">
              <Bot className="h-4 w-4 mr-1" />
              자동화
            </TabsTrigger>
            <TabsTrigger value="accounts">
              <Users className="h-4 w-4 mr-1" />
              계정
            </TabsTrigger>
            <TabsTrigger value="settings">설정</TabsTrigger>
          </TabsList>

          {/* 개요 탭 */}
          <TabsContent value="overview">
            <div className="grid md:grid-cols-2 gap-6">
              {/* 타겟 카페 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Coffee className="h-5 w-5" />
                      타겟 카페
                    </CardTitle>
                    <Dialog open={isCafeDialogOpen} onOpenChange={setIsCafeDialogOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="h-4 w-4 mr-1" />
                          추가
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>카페 추가</DialogTitle>
                          <DialogDescription>
                            바이럴 대상 카페를 추가하세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>카페 ID</Label>
                            <Input
                              placeholder="예: imsanbu"
                              value={newCafe.cafe_id}
                              onChange={(e) => setNewCafe({ ...newCafe, cafe_id: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>카페 이름</Label>
                            <Input
                              placeholder="예: 맘스홀릭 베이비"
                              value={newCafe.cafe_name}
                              onChange={(e) => setNewCafe({ ...newCafe, cafe_name: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>카테고리</Label>
                            <Select
                              value={newCafe.category}
                              onValueChange={(v) => setNewCafe({ ...newCafe, category: v as CafeCategory })}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="선택하세요" />
                              </SelectTrigger>
                              <SelectContent>
                                {CATEGORY_OPTIONS.map((opt) => (
                                  <SelectItem key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="flex items-center justify-between">
                            <Label>댓글 허용</Label>
                            <Switch
                              checked={newCafe.commenting_enabled}
                              onCheckedChange={(v) => setNewCafe({ ...newCafe, commenting_enabled: v })}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <Label>글 작성 허용</Label>
                            <Switch
                              checked={newCafe.posting_enabled}
                              onCheckedChange={(v) => setNewCafe({ ...newCafe, posting_enabled: v })}
                            />
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsCafeDialogOpen(false)}>
                            취소
                          </Button>
                          <Button onClick={handleAddCafe}>추가</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardHeader>
                <CardContent>
                  {cafes.length === 0 ? (
                    <p className="text-center text-gray-500 py-8">
                      등록된 카페가 없습니다
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {cafes.map((cafe) => (
                        <div
                          key={cafe.id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${cafe.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                            <span className="font-medium">{cafe.cafe_name}</span>
                            {getCategoryBadge(cafe.category)}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-500">
                              {cafe.total_comments}개 댓글
                            </span>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteCafe(cafe.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 모니터링 키워드 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Hash className="h-5 w-5" />
                      모니터링 키워드
                    </CardTitle>
                    <Dialog open={isKeywordDialogOpen} onOpenChange={setIsKeywordDialogOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="h-4 w-4 mr-1" />
                          추가
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>키워드 추가</DialogTitle>
                          <DialogDescription>
                            모니터링할 키워드를 추가하세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>키워드</Label>
                            <Input
                              placeholder="예: 피부과 추천"
                              value={newKeyword.keyword}
                              onChange={(e) => setNewKeyword({ ...newKeyword, keyword: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>카테고리</Label>
                            <Select
                              value={newKeyword.category}
                              onValueChange={(v) => setNewKeyword({ ...newKeyword, category: v })}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="선택하세요" />
                              </SelectTrigger>
                              <SelectContent>
                                {CATEGORY_OPTIONS.map((opt) => (
                                  <SelectItem key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2">
                            <Label>우선순위 (1-5)</Label>
                            <Input
                              type="number"
                              min={1}
                              max={5}
                              value={newKeyword.priority}
                              onChange={(e) => setNewKeyword({ ...newKeyword, priority: parseInt(e.target.value) || 1 })}
                            />
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsKeywordDialogOpen(false)}>
                            취소
                          </Button>
                          <Button onClick={handleAddKeyword}>추가</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardHeader>
                <CardContent>
                  {keywords.length === 0 ? (
                    <p className="text-center text-gray-500 py-8">
                      등록된 키워드가 없습니다
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {keywords.map((kw) => (
                        <div
                          key={kw.id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <Badge variant="outline">{kw.priority}</Badge>
                            <span className="font-medium">{kw.keyword}</span>
                            {kw.category && (
                              <Badge variant="secondary">{kw.category}</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-500">
                              {kw.matched_count}개 발견
                            </span>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteKeyword(kw.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* 추천 게시글 */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Star className="h-5 w-5 text-yellow-500" />
                  고관련성 게시글 TOP 5
                </CardTitle>
                <CardDescription>
                  댓글을 달면 효과적인 게시글들입니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                {topPosts.length === 0 ? (
                  <p className="text-center text-gray-500 py-8">
                    수집된 게시글이 없습니다
                  </p>
                ) : (
                  <div className="space-y-3">
                    {topPosts.map((post) => (
                      <div
                        key={post.id}
                        className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer"
                        onClick={() => {
                          setSelectedPost(post)
                          setActiveTab('posts')
                        }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{post.title}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-xs">
                                관련성 {(post.relevance_score * 100).toFixed(0)}%
                              </Badge>
                              <span className="text-xs text-gray-500">
                                조회 {post.view_count} / 댓글 {post.comment_count}
                              </span>
                            </div>
                          </div>
                          <Button
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleGenerateContent(post.id)
                            }}
                            disabled={isGenerating}
                          >
                            <Sparkles className="h-3 w-3 mr-1" />
                            댓글
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 게시글 모니터링 탭 */}
          <TabsContent value="posts">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>수집된 게시글</CardTitle>
                  <Select
                    value={postFilter}
                    onValueChange={(v) => setPostFilter(v as CafePostStatus | '')}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="상태 필터" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">전체</SelectItem>
                      <SelectItem value="new">신규</SelectItem>
                      <SelectItem value="analyzed">분석됨</SelectItem>
                      <SelectItem value="commented">댓글완료</SelectItem>
                      <SelectItem value="skipped">건너뜀</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {posts.length === 0 ? (
                  <div className="text-center py-12">
                    <Coffee className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">수집된 게시글이 없습니다</p>
                    <Button className="mt-4" onClick={handleCollect} disabled={isCollecting}>
                      게시글 수집하기
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {posts.map((post) => (
                      <div
                        key={post.id}
                        className="p-4 border rounded-lg hover:border-orange-300 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {getStatusBadge(post.status)}
                              <Badge variant="outline">관련성 {(post.relevance_score * 100).toFixed(0)}%</Badge>
                              {post.sentiment && (
                                <Badge variant="secondary">{post.sentiment}</Badge>
                              )}
                            </div>
                            <h3 className="font-semibold mb-1">{post.title}</h3>
                            {post.content && (
                              <p className="text-sm text-gray-600 line-clamp-2">{post.content}</p>
                            )}
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span>조회 {post.view_count}</span>
                              <span>댓글 {post.comment_count}개</span>
                              <span>좋아요 {post.like_count}</span>
                              {post.matched_keywords && post.matched_keywords.length > 0 && (
                                <span>키워드: {post.matched_keywords.join(', ')}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col gap-2">
                            {post.url && (
                              <Button variant="outline" size="sm" asChild>
                                <a href={post.url} target="_blank" rel="noopener noreferrer">
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              </Button>
                            )}
                            <Button
                              size="sm"
                              onClick={() => handleGenerateContent(post.id)}
                              disabled={isGenerating || post.status === 'commented'}
                            >
                              {isGenerating ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <Sparkles className="h-4 w-4 mr-1" />
                                  댓글 생성
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 콘텐츠 관리 탭 */}
          <TabsContent value="contents">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>생성된 콘텐츠</CardTitle>
                  <Select
                    value={contentFilter}
                    onValueChange={(v) => setContentFilter(v as CafeContentStatus | '')}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="상태 필터" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">전체</SelectItem>
                      <SelectItem value="draft">초안</SelectItem>
                      <SelectItem value="approved">승인됨</SelectItem>
                      <SelectItem value="posted">등록됨</SelectItem>
                      <SelectItem value="rejected">반려됨</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {contents.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">생성된 콘텐츠가 없습니다</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {contents.map((content) => (
                      <div
                        key={content.id}
                        className="p-4 border rounded-lg"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {getContentTypeBadge(content.content_type)}
                              {getStatusBadge(content.status)}
                              {content.quality_score && (
                                <Badge variant="outline">
                                  품질 {(content.quality_score * 100).toFixed(0)}점
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-4">
                              {content.content}
                            </p>
                            {content.blog_link && (
                              <p className="text-xs text-blue-600 mt-2">
                                블로그: {content.blog_link}
                              </p>
                            )}
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span className="flex items-center gap-1">
                                <Heart className="h-3 w-3" /> {content.likes_received}
                              </span>
                              <span className="flex items-center gap-1">
                                <MessageSquare className="h-3 w-3" /> {content.replies_received}
                              </span>
                            </div>
                          </div>
                          <div className="flex flex-col gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => copyToClipboard(content.content)}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                            {content.status === 'draft' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => handleApproveContent(content.id)}
                                >
                                  <CheckCircle className="h-4 w-4" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => handleRejectContent(content.id)}
                                >
                                  <XCircle className="h-4 w-4" />
                                </Button>
                              </>
                            )}
                            {content.status === 'approved' && (
                              <Button
                                size="sm"
                                variant="default"
                                onClick={() => handleAutoPost(content.id)}
                                disabled={!posterStatus?.logged_in || isPosting}
                                title={posterStatus?.logged_in ? '자동 등록' : '로그인 필요'}
                              >
                                {isPosting ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Upload className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 자동화 탭 */}
          <TabsContent value="automation">
            <div className="grid md:grid-cols-2 gap-6">
              {/* 스케줄러 상태 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="h-5 w-5 text-yellow-500" />
                    자동 수집 스케줄러
                  </CardTitle>
                  <CardDescription>
                    주기적으로 게시글을 수집하고 콘텐츠를 생성합니다
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {schedulerStatus ? (
                    <>
                      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${schedulerStatus.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                          <span className="font-medium">
                            {schedulerStatus.is_running ? '실행 중' : '중지됨'}
                          </span>
                        </div>
                        {schedulerStatus.is_running ? (
                          <Button variant="outline" size="sm" onClick={handleStopScheduler}>
                            <Square className="h-4 w-4 mr-1" />
                            중지
                          </Button>
                        ) : (
                          <Button size="sm" onClick={handleStartScheduler}>
                            <Play className="h-4 w-4 mr-1" />
                            시작
                          </Button>
                        )}
                      </div>

                      <div className="grid grid-cols-3 gap-3">
                        <div className="p-3 bg-blue-50 rounded-lg text-center">
                          <p className="text-2xl font-bold text-blue-600">
                            {schedulerStatus.today?.collected || 0}
                          </p>
                          <p className="text-xs text-gray-500">오늘 수집</p>
                        </div>
                        <div className="p-3 bg-purple-50 rounded-lg text-center">
                          <p className="text-2xl font-bold text-purple-600">
                            {schedulerStatus.today?.generated || 0}
                          </p>
                          <p className="text-xs text-gray-500">오늘 생성</p>
                        </div>
                        <div className="p-3 bg-green-50 rounded-lg text-center">
                          <p className="text-2xl font-bold text-green-600">
                            {schedulerStatus.today?.posted || 0}
                          </p>
                          <p className="text-xs text-gray-500">오늘 등록</p>
                        </div>
                      </div>

                      <div className="text-xs text-gray-500 space-y-1">
                        <p>일일 수집 한도: {schedulerStatus.today?.collect_limit || 100}개</p>
                        <p>일일 등록 한도: {schedulerStatus.today?.post_limit || 20}개</p>
                        <p className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          업무 시간: {schedulerStatus.is_working_hours ? '내 (활성)' : '외 (비활성)'}
                        </p>
                      </div>

                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRunCollection}
                          disabled={isCollecting}
                          className="flex-1"
                        >
                          {isCollecting ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Search className="h-4 w-4 mr-1" />
                          )}
                          수동 수집
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRunGeneration}
                          disabled={isGenerating}
                          className="flex-1"
                        >
                          {isGenerating ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4 mr-1" />
                          )}
                          수동 생성
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-8">
                      <Loader2 className="h-8 w-8 mx-auto animate-spin text-gray-300" />
                      <p className="text-gray-500 mt-2">상태 로딩 중...</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 자동 등록 (포스터) */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="h-5 w-5 text-green-500" />
                    자동 콘텐츠 등록
                  </CardTitle>
                  <CardDescription>
                    승인된 콘텐츠를 자동으로 네이버 카페에 등록합니다
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 네이버 로그인 상태 */}
                  <div className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium">네이버 계정</span>
                      {posterStatus?.logged_in ? (
                        <Badge className="bg-green-100 text-green-800">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          로그인됨
                        </Badge>
                      ) : (
                        <Badge variant="secondary">
                          <XCircle className="h-3 w-3 mr-1" />
                          로그아웃
                        </Badge>
                      )}
                    </div>

                    {posterStatus?.logged_in ? (
                      <Button variant="outline" size="sm" onClick={handlePosterLogout} className="w-full">
                        <LogOut className="h-4 w-4 mr-2" />
                        로그아웃
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => setIsLoginDialogOpen(true)} className="w-full">
                        <LogIn className="h-4 w-4 mr-2" />
                        네이버 로그인
                      </Button>
                    )}
                  </div>

                  {/* 대기중인 콘텐츠 */}
                  {schedulerStatus?.pending && (
                    <div className="p-4 bg-orange-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-orange-800">등록 대기</p>
                          <p className="text-sm text-orange-600">
                            승인된 콘텐츠 {schedulerStatus.pending.contents}개
                          </p>
                        </div>
                        <Button
                          size="sm"
                          onClick={handleBulkPost}
                          disabled={!posterStatus?.logged_in || isPosting || schedulerStatus.pending.contents === 0}
                        >
                          {isPosting ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Upload className="h-4 w-4 mr-1" />
                          )}
                          일괄 등록
                        </Button>
                      </div>
                    </div>
                  )}

                  {!posterStatus?.logged_in && (
                    <p className="text-sm text-gray-500 text-center py-4">
                      네이버 계정에 로그인하면 자동 콘텐츠 등록을 사용할 수 있습니다
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* 안내 메시지 */}
            <Card className="mt-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
                    <Bot className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">자동화 작동 방식</h3>
                    <ul className="text-sm text-gray-600 space-y-1">
                      <li>1. 스케줄러가 설정된 카페에서 키워드로 게시글을 자동 수집합니다</li>
                      <li>2. 관련성 높은 게시글에 대해 AI가 자동으로 댓글을 생성합니다</li>
                      <li>3. 생성된 콘텐츠를 검토하고 승인하면 자동 등록됩니다</li>
                      <li>4. 업무 시간(09:00-22:00) 내에만 자동 작업이 실행됩니다</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* 계정 관리 탭 */}
          <TabsContent value="accounts">
            <div className="grid md:grid-cols-3 gap-6 mb-6">
              {/* 계정 통계 카드 */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-500">전체 계정</p>
                      <p className="text-2xl font-bold text-blue-600">
                        {accountStats?.total || 0}
                      </p>
                    </div>
                    <Users className="h-8 w-8 text-blue-200" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-500">활성 계정</p>
                      <p className="text-2xl font-bold text-green-600">
                        {accountStats?.active || 0}
                      </p>
                    </div>
                    <CheckCircle className="h-8 w-8 text-green-200" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-500">오늘 활동</p>
                      <p className="text-2xl font-bold text-orange-600">
                        댓글 {accountStats?.today_comments || 0} / 글 {accountStats?.today_posts || 0}
                      </p>
                    </div>
                    <TrendingUp className="h-8 w-8 text-orange-200" />
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" />
                      네이버 계정 관리
                    </CardTitle>
                    <CardDescription>
                      다중 계정 로테이션으로 안전하게 콘텐츠를 등록합니다
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={handleBulkRotatedPost}
                      disabled={isPosting || accounts.length === 0}
                    >
                      {isPosting ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4 mr-2" />
                      )}
                      로테이션 일괄등록
                    </Button>
                    <Dialog open={isAccountDialogOpen} onOpenChange={setIsAccountDialogOpen}>
                      <DialogTrigger asChild>
                        <Button>
                          <Plus className="h-4 w-4 mr-2" />
                          계정 추가
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>네이버 계정 추가</DialogTitle>
                          <DialogDescription>
                            자동 게시에 사용할 네이버 계정을 추가하세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>네이버 아이디</Label>
                            <Input
                              placeholder="아이디 입력"
                              value={newAccount.account_id}
                              onChange={(e) => setNewAccount({ ...newAccount, account_id: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>비밀번호</Label>
                            <Input
                              type="password"
                              placeholder="비밀번호 입력"
                              value={newAccount.password}
                              onChange={(e) => setNewAccount({ ...newAccount, password: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>별명 (선택)</Label>
                            <Input
                              placeholder="예: 카페용 계정1"
                              value={newAccount.account_name}
                              onChange={(e) => setNewAccount({ ...newAccount, account_name: e.target.value })}
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                              <Label>일일 댓글 한도</Label>
                              <Input
                                type="number"
                                min={1}
                                max={50}
                                value={newAccount.daily_comment_limit}
                                onChange={(e) => setNewAccount({ ...newAccount, daily_comment_limit: parseInt(e.target.value) || 10 })}
                              />
                            </div>
                            <div className="grid gap-2">
                              <Label>일일 글 한도</Label>
                              <Input
                                type="number"
                                min={1}
                                max={10}
                                value={newAccount.daily_post_limit}
                                onChange={(e) => setNewAccount({ ...newAccount, daily_post_limit: parseInt(e.target.value) || 2 })}
                              />
                            </div>
                          </div>
                          <p className="text-xs text-gray-500">
                            * 비밀번호는 암호화되어 저장됩니다
                          </p>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsAccountDialogOpen(false)}>
                            취소
                          </Button>
                          <Button onClick={handleAddAccount}>추가</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {accounts.length === 0 ? (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">등록된 계정이 없습니다</p>
                    <p className="text-sm text-gray-400 mt-1">
                      계정을 추가하면 다중 계정 로테이션으로 안전하게 콘텐츠를 등록할 수 있습니다
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {accounts.map((account) => (
                      <div
                        key={account.id}
                        className="p-4 border rounded-lg hover:border-orange-300 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className={`w-3 h-3 rounded-full ${
                              account.status === 'active' ? 'bg-green-500' :
                              account.status === 'resting' ? 'bg-yellow-500' :
                              account.status === 'error' ? 'bg-red-500' :
                              'bg-gray-400'
                            }`} />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{account.account_name || account.account_id}</span>
                                {account.is_warming_up && (
                                  <Badge className="bg-blue-100 text-blue-800">
                                    워밍업 {account.warming_day}일차
                                  </Badge>
                                )}
                                {account.status === 'resting' && (
                                  <Badge variant="secondary">휴식중</Badge>
                                )}
                                {account.status === 'error' && (
                                  <Badge variant="destructive">오류</Badge>
                                )}
                              </div>
                              <p className="text-sm text-gray-500">
                                오늘: 댓글 {account.today_comments}/{account.daily_comment_limit},
                                글 {account.today_posts}/{account.daily_post_limit}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {!account.is_warming_up && account.status === 'active' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleStartWarmup(account.id)}
                              >
                                워밍업
                              </Button>
                            )}
                            {account.status === 'active' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleAccountStatusChange(account.id, 'resting')}
                              >
                                휴식
                              </Button>
                            )}
                            {account.status === 'resting' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleAccountStatusChange(account.id, 'active')}
                              >
                                활성화
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteAccount(account.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 안내 */}
            <Card className="mt-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
                    <Users className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">다중 계정 로테이션</h3>
                    <ul className="text-sm text-gray-600 space-y-1">
                      <li>• 여러 계정을 순환하며 콘텐츠를 등록합니다</li>
                      <li>• 각 계정별 일일 한도를 설정하여 차단을 방지합니다</li>
                      <li>• 워밍업 기능으로 신규 계정을 안전하게 활성화합니다</li>
                      <li>• 휴식 상태의 계정은 자동 게시에서 제외됩니다</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* 설정 탭 */}
          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  콘텐츠 생성 설정
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h3 className="font-semibold">기본 콘텐츠 스타일</h3>
                    <div className="grid gap-4">
                      <div className="grid gap-2">
                        <Label>댓글 톤</Label>
                        <Select
                          value={contentSettings.tone}
                          onValueChange={(v) => setContentSettings({ ...contentSettings, tone: v as CafeTone })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TONE_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex items-center justify-between">
                        <Label>홍보 문구 포함</Label>
                        <Switch
                          checked={contentSettings.include_promotion}
                          onCheckedChange={(v) => setContentSettings({ ...contentSettings, include_promotion: v })}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h3 className="font-semibold">기본 링크</h3>
                    <div className="grid gap-4">
                      <div className="grid gap-2">
                        <Label>블로그 링크</Label>
                        <Input
                          placeholder="https://blog.naver.com/..."
                          value={contentSettings.blog_link}
                          onChange={(e) => setContentSettings({ ...contentSettings, blog_link: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>플레이스 링크</Label>
                        <Input
                          placeholder="https://place.naver.com/..."
                          value={contentSettings.place_link}
                          onChange={(e) => setContentSettings({ ...contentSettings, place_link: e.target.value })}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* 콘텐츠 확인 다이얼로그 */}
      <Dialog open={isContentDialogOpen} onOpenChange={setIsContentDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>생성된 콘텐츠</DialogTitle>
          </DialogHeader>
          {selectedContent && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                {getContentTypeBadge(selectedContent.content_type)}
                {selectedContent.quality_score && (
                  <Badge variant="outline">
                    품질 점수: {(selectedContent.quality_score * 100).toFixed(0)}
                  </Badge>
                )}
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="whitespace-pre-wrap text-sm">
                  {selectedContent.content}
                </p>
              </div>
              {selectedContent.promotion_text && (
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm text-blue-800">{selectedContent.promotion_text}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => selectedContent && copyToClipboard(selectedContent.content)}
            >
              <Copy className="h-4 w-4 mr-2" />
              복사
            </Button>
            <Button
              onClick={() => {
                if (selectedContent) handleApproveContent(selectedContent.id)
                setIsContentDialogOpen(false)
              }}
            >
              승인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 네이버 로그인 다이얼로그 */}
      <Dialog open={isLoginDialogOpen} onOpenChange={setIsLoginDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <LogIn className="h-5 w-5" />
              네이버 로그인
            </DialogTitle>
            <DialogDescription>
              자동 콘텐츠 등록을 위해 네이버 계정으로 로그인하세요
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="naver-id">네이버 아이디</Label>
              <Input
                id="naver-id"
                placeholder="아이디 입력"
                value={loginForm.username}
                onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="naver-pw">비밀번호</Label>
              <Input
                id="naver-pw"
                type="password"
                placeholder="비밀번호 입력"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
              />
            </div>
            <p className="text-xs text-gray-500">
              * 비밀번호는 서버에 저장되지 않으며, 로그인 세션만 유지됩니다.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsLoginDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={handlePosterLogin}>
              로그인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
