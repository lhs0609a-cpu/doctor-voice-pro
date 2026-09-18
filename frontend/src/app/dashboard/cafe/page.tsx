'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
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
    const statusConfig: Record<string, { label: string; tone: 'ok' | 'warn' | 'danger' | 'accent' | 'muted' }> = {
      new: { label: '신규', tone: 'accent' },
      analyzed: { label: '분석됨', tone: 'muted' },
      commented: { label: '댓글완료', tone: 'ok' },
      skipped: { label: '건너뜀', tone: 'muted' },
      draft: { label: '초안', tone: 'muted' },
      approved: { label: '승인됨', tone: 'accent' },
      posted: { label: '등록됨', tone: 'ok' },
      rejected: { label: '반려됨', tone: 'danger' },
      failed: { label: '실패', tone: 'danger' },
    }
    const config = statusConfig[status] || { label: status, tone: 'muted' as const }
    return <Pill tone={config.tone}>{config.label}</Pill>
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
    return <Pill tone="muted">{categoryConfig[category] || category}</Pill>
  }

  const getContentTypeBadge = (type: string) => {
    const typeConfig: Record<string, { label: string; tone: 'accent' | 'muted' }> = {
      comment: { label: '댓글', tone: 'accent' },
      reply: { label: '대댓글', tone: 'muted' },
      post: { label: '새 글', tone: 'accent' },
    }
    const config = typeConfig[type] || { label: type, tone: 'muted' as const }
    return <Pill tone={config.tone}>{config.label}</Pill>
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="카페 바이럴 자동화"
        description="네이버 카페에 글과 댓글을 자동으로 수집하고 등록하세요"
        actions={
          <>
            <Button variant="outline" onClick={loadData}>
              <RefreshCw className="h-4 w-4" />
              새로고침
            </Button>
            <Button onClick={handleCollect} disabled={isCollecting}>
              {isCollecting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              게시글 수집
            </Button>
          </>
        }
      />

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="활성 카페" value={dashboard?.active_cafes || 0} icon={<Users className="h-4 w-4" />} />
        <StatTile label="오늘 수집" value={dashboard?.posts_collected_today || 0} icon={<Search className="h-4 w-4" />} />
        <StatTile label="대기 콘텐츠" value={dashboard?.pending_contents || 0} icon={<FileText className="h-4 w-4" />} />
        <StatTile
          label="오늘 등록"
          value={(dashboard?.posts_published_today || 0) + (dashboard?.comments_published_today || 0)}
          tone="ok"
          icon={<TrendingUp className="h-4 w-4" />}
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
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
          <div className="grid gap-4 md:grid-cols-2">
            {/* 타겟 카페 */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Coffee className="h-4 w-4 text-muted-foreground" />
                    타겟 카페
                  </CardTitle>
                  <Dialog open={isCafeDialogOpen} onOpenChange={setIsCafeDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Plus className="h-4 w-4" />
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
                  <EmptyState
                    icon={<Coffee className="h-8 w-8" />}
                    title="등록된 카페가 없습니다"
                    description="바이럴 대상 카페를 먼저 추가하세요"
                    action={
                      <Button variant="outline" size="sm" onClick={() => setIsCafeDialogOpen(true)}>
                        <Plus className="h-4 w-4" />
                        카페 추가
                      </Button>
                    }
                  />
                ) : (
                  <div className="rounded-lg border">
                    {cafes.map((cafe) => (
                      <ListRow key={cafe.id} className="justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`h-2 w-2 rounded-full ${cafe.is_active ? 'bg-success' : 'bg-muted-foreground/40'}`} />
                          <span className="font-medium">{cafe.cafe_name}</span>
                          {getCategoryBadge(cafe.category)}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm tabular-nums text-muted-foreground">
                            {cafe.total_comments}개 댓글
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteCafe(cafe.id)}
                          >
                            <Trash2 className="h-4 w-4 text-danger" />
                          </Button>
                        </div>
                      </ListRow>
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
                    <Hash className="h-4 w-4 text-muted-foreground" />
                    모니터링 키워드
                  </CardTitle>
                  <Dialog open={isKeywordDialogOpen} onOpenChange={setIsKeywordDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Plus className="h-4 w-4" />
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
                  <EmptyState
                    icon={<Hash className="h-8 w-8" />}
                    title="등록된 키워드가 없습니다"
                    description="모니터링할 키워드를 추가하면 게시글을 자동으로 찾습니다"
                    action={
                      <Button variant="outline" size="sm" onClick={() => setIsKeywordDialogOpen(true)}>
                        <Plus className="h-4 w-4" />
                        키워드 추가
                      </Button>
                    }
                  />
                ) : (
                  <div className="rounded-lg border">
                    {keywords.map((kw) => (
                      <ListRow key={kw.id} className="justify-between">
                        <div className="flex items-center gap-3">
                          <Pill tone="muted">{kw.priority}</Pill>
                          <span className="font-medium">{kw.keyword}</span>
                          {kw.category && (
                            <Pill tone="muted">{kw.category}</Pill>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm tabular-nums text-muted-foreground">
                            {kw.matched_count}개 발견
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteKeyword(kw.id)}
                          >
                            <Trash2 className="h-4 w-4 text-danger" />
                          </Button>
                        </div>
                      </ListRow>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 추천 게시글 */}
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Star className="h-4 w-4 text-muted-foreground" />
                고관련성 게시글 TOP 5
              </CardTitle>
              <CardDescription>
                댓글을 달면 효과적인 게시글들입니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              {topPosts.length === 0 ? (
                <EmptyState
                  icon={<Star className="h-8 w-8" />}
                  title="수집된 게시글이 없습니다"
                  description="게시글을 수집하면 관련성이 높은 글을 여기에 추천합니다"
                  action={
                    <Button variant="outline" size="sm" onClick={handleCollect} disabled={isCollecting}>
                      <Search className="h-4 w-4" />
                      게시글 수집
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-2">
                  {topPosts.map((post) => (
                    <div
                      key={post.id}
                      className="cursor-pointer rounded-lg border p-3 transition-colors hover:bg-muted/40"
                      onClick={() => {
                        setSelectedPost(post)
                        setActiveTab('posts')
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{post.title}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Pill tone="muted">
                              관련성 {(post.relevance_score * 100).toFixed(0)}%
                            </Pill>
                            <span className="text-xs tabular-nums text-muted-foreground">
                              조회 {post.view_count} / 댓글 {post.comment_count}
                            </span>
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleGenerateContent(post.id)
                          }}
                          disabled={isGenerating}
                        >
                          <Sparkles className="h-3 w-3" />
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
                <EmptyState
                  icon={<Coffee className="h-8 w-8" />}
                  title="수집된 게시글이 없습니다"
                  description="타겟 카페와 키워드를 설정한 뒤 게시글을 수집하세요"
                  action={
                    <Button variant="outline" onClick={handleCollect} disabled={isCollecting}>
                      <Search className="h-4 w-4" />
                      게시글 수집하기
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {posts.map((post) => (
                    <div
                      key={post.id}
                      className="rounded-lg border p-4 transition-colors hover:bg-muted/40"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {getStatusBadge(post.status)}
                            <Pill tone="muted">관련성 {(post.relevance_score * 100).toFixed(0)}%</Pill>
                            {post.sentiment && (
                              <Pill tone="muted">{post.sentiment}</Pill>
                            )}
                          </div>
                          <h3 className="mb-1 text-sm font-semibold">{post.title}</h3>
                          {post.content && (
                            <p className="text-sm text-muted-foreground line-clamp-2">{post.content}</p>
                          )}
                          <div className="mt-2 flex items-center gap-4 text-xs tabular-nums text-muted-foreground">
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
                            variant="outline"
                            size="sm"
                            onClick={() => handleGenerateContent(post.id)}
                            disabled={isGenerating || post.status === 'commented'}
                          >
                            {isGenerating ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <>
                                <Sparkles className="h-4 w-4" />
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
                <EmptyState
                  icon={<FileText className="h-8 w-8" />}
                  title="생성된 콘텐츠가 없습니다"
                  description="수집된 게시글에서 댓글을 생성하면 여기에 모입니다"
                  action={
                    <Button variant="outline" onClick={() => setActiveTab('posts')}>
                      <Sparkles className="h-4 w-4" />
                      게시글에서 댓글 생성하기
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {contents.map((content) => (
                    <div
                      key={content.id}
                      className="rounded-lg border p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {getContentTypeBadge(content.content_type)}
                            {getStatusBadge(content.status)}
                            {content.quality_score && (
                              <Pill tone="muted">
                                품질 {(content.quality_score * 100).toFixed(0)}점
                              </Pill>
                            )}
                          </div>
                          <p className="text-sm whitespace-pre-wrap line-clamp-4">
                            {content.content}
                          </p>
                          {content.blog_link && (
                            <p className="mt-2 text-xs text-primary">
                              블로그: {content.blog_link}
                            </p>
                          )}
                          <div className="mt-2 flex items-center gap-4 text-xs tabular-nums text-muted-foreground">
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
                                variant="outline"
                                title="승인"
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
                              variant="outline"
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
          <div className="grid gap-4 md:grid-cols-2">
            {/* 스케줄러 상태 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-muted-foreground" />
                  자동 수집 스케줄러
                </CardTitle>
                <CardDescription>
                  주기적으로 게시글을 수집하고 콘텐츠를 생성합니다
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {schedulerStatus ? (
                  <>
                    <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-3">
                      <div className="flex items-center gap-2">
                        <div className={`h-2.5 w-2.5 rounded-full ${schedulerStatus.is_running ? 'bg-success animate-pulse' : 'bg-muted-foreground/40'}`} />
                        <span className="text-sm font-medium">
                          {schedulerStatus.is_running ? '실행 중' : '중지됨'}
                        </span>
                      </div>
                      {schedulerStatus.is_running ? (
                        <Button variant="outline" size="sm" onClick={handleStopScheduler}>
                          <Square className="h-4 w-4" />
                          중지
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" onClick={handleStartScheduler}>
                          <Play className="h-4 w-4" />
                          시작
                        </Button>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-lg bg-muted/40 p-3 text-center">
                        <p className="kpi">
                          {schedulerStatus.today?.collected || 0}
                        </p>
                        <p className="text-xs text-muted-foreground">오늘 수집</p>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3 text-center">
                        <p className="kpi">
                          {schedulerStatus.today?.generated || 0}
                        </p>
                        <p className="text-xs text-muted-foreground">오늘 생성</p>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-3 text-center">
                        <p className="kpi text-success">
                          {schedulerStatus.today?.posted || 0}
                        </p>
                        <p className="text-xs text-muted-foreground">오늘 등록</p>
                      </div>
                    </div>

                    <div className="space-y-1 text-xs text-muted-foreground">
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
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Search className="h-4 w-4" />
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
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        수동 생성
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center gap-2 py-8">
                    <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                    <p className="text-sm text-muted-foreground">상태 불러오는 중...</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 자동 등록 (포스터) */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="h-4 w-4 text-muted-foreground" />
                  자동 콘텐츠 등록
                </CardTitle>
                <CardDescription>
                  승인된 콘텐츠를 자동으로 네이버 카페에 등록합니다
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 네이버 로그인 상태 */}
                <div className="rounded-lg border p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-medium">네이버 계정</span>
                    {posterStatus?.logged_in ? (
                      <Pill tone="ok">
                        <CheckCircle className="mr-1 h-3 w-3" />
                        로그인됨
                      </Pill>
                    ) : (
                      <Pill tone="muted">
                        <XCircle className="mr-1 h-3 w-3" />
                        로그아웃
                      </Pill>
                    )}
                  </div>

                  {posterStatus?.logged_in ? (
                    <Button variant="outline" size="sm" onClick={handlePosterLogout} className="w-full">
                      <LogOut className="h-4 w-4" />
                      로그아웃
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => setIsLoginDialogOpen(true)} className="w-full">
                      <LogIn className="h-4 w-4" />
                      네이버 로그인
                    </Button>
                  )}
                </div>

                {/* 대기중인 콘텐츠 */}
                {schedulerStatus?.pending && (
                  <div className="rounded-lg bg-accent p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-accent-foreground">등록 대기</p>
                        <p className="text-sm tabular-nums text-muted-foreground">
                          승인된 콘텐츠 {schedulerStatus.pending.contents}개
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkPost}
                        disabled={!posterStatus?.logged_in || isPosting || schedulerStatus.pending.contents === 0}
                      >
                        {isPosting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Upload className="h-4 w-4" />
                        )}
                        일괄 등록
                      </Button>
                    </div>
                  </div>
                )}

                {!posterStatus?.logged_in && (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    네이버 계정에 로그인하면 자동 콘텐츠 등록을 사용할 수 있습니다
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 안내 메시지 */}
          <div className="surface mt-4 p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                  <Bot className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="mb-1 text-sm font-semibold">자동화 작동 방식</h3>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    <li>1. 스케줄러가 설정된 카페에서 키워드로 게시글을 자동 수집합니다</li>
                    <li>2. 관련성 높은 게시글에 대해 AI가 자동으로 댓글을 생성합니다</li>
                    <li>3. 생성된 콘텐츠를 검토하고 승인하면 자동 등록됩니다</li>
                    <li>4. 업무 시간(09:00-22:00) 내에만 자동 작업이 실행됩니다</li>
                  </ul>
                </div>
              </div>
          </div>
        </TabsContent>

        {/* 계정 관리 탭 */}
        <TabsContent value="accounts">
          <div className="mb-4 grid gap-4 md:grid-cols-3">
            <StatTile label="전체 계정" value={accountStats?.total || 0} icon={<Users className="h-4 w-4" />} />
            <StatTile label="활성 계정" value={accountStats?.active || 0} tone="ok" icon={<CheckCircle className="h-4 w-4" />} />
            <StatTile
              label="오늘 활동"
              value={`${accountStats?.today_comments || 0} / ${accountStats?.today_posts || 0}`}
              hint="댓글 / 글"
              icon={<TrendingUp className="h-4 w-4" />}
            />
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    네이버 계정 관리
                  </CardTitle>
                  <CardDescription>
                    다중 계정 로테이션으로 안전하게 콘텐츠를 등록합니다
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleBulkRotatedPost}
                    disabled={isPosting || accounts.length === 0}
                  >
                    {isPosting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    로테이션 일괄등록
                  </Button>
                  <Dialog open={isAccountDialogOpen} onOpenChange={setIsAccountDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Plus className="h-4 w-4" />
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
                        <p className="text-xs text-muted-foreground">
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
                <EmptyState
                  icon={<Users className="h-8 w-8" />}
                  title="등록된 계정이 없습니다"
                  description="계정을 추가하면 다중 계정 로테이션으로 안전하게 콘텐츠를 등록할 수 있습니다"
                  action={
                    <Button variant="outline" onClick={() => setIsAccountDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      계정 추가
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {accounts.map((account) => (
                    <div
                      key={account.id}
                      className="rounded-lg border p-4 transition-colors hover:bg-muted/40"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={`h-2.5 w-2.5 rounded-full ${
                            account.status === 'active' ? 'bg-success' :
                            account.status === 'resting' ? 'bg-warning' :
                            account.status === 'error' ? 'bg-danger' :
                            'bg-muted-foreground/40'
                          }`} />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{account.account_name || account.account_id}</span>
                              {account.is_warming_up && (
                                <Pill tone="accent">
                                  워밍업 {account.warming_day}일차
                                </Pill>
                              )}
                              {account.status === 'resting' && (
                                <Pill tone="warn">휴식중</Pill>
                              )}
                              {account.status === 'error' && (
                                <Pill tone="danger">오류</Pill>
                              )}
                            </div>
                            <p className="text-sm tabular-nums text-muted-foreground">
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
                            <Trash2 className="h-4 w-4 text-danger" />
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
          <div className="surface mt-4 p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                  <Users className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="mb-1 text-sm font-semibold">다중 계정 로테이션</h3>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    <li>• 여러 계정을 순환하며 콘텐츠를 등록합니다</li>
                    <li>• 각 계정별 일일 한도를 설정하여 차단을 방지합니다</li>
                    <li>• 워밍업 기능으로 신규 계정을 안전하게 활성화합니다</li>
                    <li>• 휴식 상태의 계정은 자동 게시에서 제외됩니다</li>
                  </ul>
                </div>
              </div>
          </div>
        </TabsContent>

        {/* 설정 탭 */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-4 w-4 text-muted-foreground" />
                콘텐츠 생성 설정
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold">기본 콘텐츠 스타일</h3>
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
                  <h3 className="text-sm font-semibold">기본 링크</h3>
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
                  <Pill tone="muted">
                    품질 점수: {(selectedContent.quality_score * 100).toFixed(0)}
                  </Pill>
                )}
              </div>
              <div className="rounded-lg border bg-muted/40 p-4">
                <p className="whitespace-pre-wrap text-sm">
                  {selectedContent.content}
                </p>
              </div>
              {selectedContent.promotion_text && (
                <div className="rounded-lg bg-accent p-3">
                  <p className="text-sm text-accent-foreground">{selectedContent.promotion_text}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => selectedContent && copyToClipboard(selectedContent.content)}
            >
              <Copy className="h-4 w-4" />
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
            <p className="text-xs text-muted-foreground">
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
