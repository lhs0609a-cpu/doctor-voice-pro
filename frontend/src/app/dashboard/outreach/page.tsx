'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  outreachAPI,
  type NaverBlogLead,
  type OutreachDashboard,
  type OutreachEmailTemplate,
  type OutreachCampaign,
  type OutreachSearchKeyword,
  type OutreachSetting,
  type ScoringStats,
  type SchedulerStatus,
} from '@/lib/api'
import {
  Search,
  Users,
  Mail,
  Target,
  Settings,
  RefreshCw,
  Plus,
  Trash2,
  Send,
  Eye,
  Download,
  Filter,
  Star,
  TrendingUp,
  BarChart3,
  PlayCircle,
  PauseCircle,
  ExternalLink,
  Sparkles,
  Zap,
  Globe,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  MousePointerClick,
  MessageSquare,
  ChevronRight,
  Pencil,
  Power,
  Activity,
  History,
  StopCircle,
  HelpCircle,
} from 'lucide-react'
import { toast } from 'sonner'

const BLOG_CATEGORIES = [
  { value: 'beauty', label: '뷰티/패션', icon: '💄' },
  { value: 'food', label: '맛집/카페', icon: '🍽️' },
  { value: 'travel', label: '여행', icon: '✈️' },
  { value: 'parenting', label: '육아/교육', icon: '👶' },
  { value: 'living', label: '리빙/인테리어', icon: '🏠' },
  { value: 'health', label: '건강/의료', icon: '💊' },
  { value: 'it', label: 'IT/테크', icon: '💻' },
  { value: 'finance', label: '재테크/금융', icon: '💰' },
  { value: 'lifestyle', label: '라이프스타일', icon: '🌿' },
  { value: 'other', label: '기타', icon: '📌' },
]

const LEAD_GRADES = [
  { value: 'A', label: 'A등급', color: 'from-emerald-400 to-green-500', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  { value: 'B', label: 'B등급', color: 'from-blue-400 to-indigo-500', bg: 'bg-blue-50', text: 'text-blue-700' },
  { value: 'C', label: 'C등급', color: 'from-amber-400 to-orange-500', bg: 'bg-amber-50', text: 'text-amber-700' },
  { value: 'D', label: 'D등급', color: 'from-gray-400 to-slate-500', bg: 'bg-gray-50', text: 'text-gray-700' },
]

const BLOG_STATUSES = [
  { value: 'new', label: '신규', color: 'bg-sky-100 text-sky-700' },
  { value: 'contact_found', label: '연락처 발견', color: 'bg-emerald-100 text-emerald-700' },
  { value: 'contacted', label: '연락함', color: 'bg-violet-100 text-violet-700' },
  { value: 'responded', label: '회신받음', color: 'bg-fuchsia-100 text-fuchsia-700' },
  { value: 'converted', label: '전환됨', color: 'bg-green-100 text-green-700' },
  { value: 'not_interested', label: '관심없음', color: 'bg-gray-100 text-gray-600' },
  { value: 'invalid', label: '유효하지 않음', color: 'bg-red-100 text-red-700' },
]

export default function OutreachPage() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [dashboard, setDashboard] = useState<OutreachDashboard | null>(null)
  const [scoringStats, setScoringStats] = useState<ScoringStats | null>(null)
  const [blogs, setBlogs] = useState<NaverBlogLead[]>([])
  const [blogsTotal, setBlogsTotal] = useState(0)
  const [templates, setTemplates] = useState<OutreachEmailTemplate[]>([])
  const [campaigns, setCampaigns] = useState<OutreachCampaign[]>([])
  const [keywords, setKeywords] = useState<OutreachSearchKeyword[]>([])
  const [settings, setSettings] = useState<OutreachSetting | null>(null)
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(false)

  // Filters
  const [blogFilter, setBlogFilter] = useState({
    category: '',
    grade: '',
    status: '',
    has_contact: undefined as boolean | undefined,
  })

  // Search
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchCategory, setSearchCategory] = useState('')

  // Template Dialog
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<OutreachEmailTemplate | null>(null)
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    template_type: 'introduction',
    subject: '',
    body: '',
  })

  // Keyword Dialog
  const [keywordDialogOpen, setKeywordDialogOpen] = useState(false)
  const [newKeyword, setNewKeyword] = useState({
    keyword: '',
    category: '',
    priority: 1,
  })

  // Load functions
  const loadDashboard = useCallback(async () => {
    try {
      const data = await outreachAPI.getDashboard()
      setDashboard(data)
    } catch (error) {
      console.error('Dashboard load error:', error)
    }
  }, [])

  const loadScoringStats = useCallback(async () => {
    try {
      const data = await outreachAPI.getScoringStats()
      setScoringStats(data)
    } catch (error) {
      console.error('Scoring stats load error:', error)
    }
  }, [])

  const loadBlogs = useCallback(async () => {
    try {
      const params: any = { limit: 50 }
      if (blogFilter.category) params.category = blogFilter.category
      if (blogFilter.grade) params.grade = blogFilter.grade
      if (blogFilter.status) params.status = blogFilter.status
      if (blogFilter.has_contact !== undefined) params.has_contact = blogFilter.has_contact

      const data = await outreachAPI.getBlogs(params)
      setBlogs(data.blogs)
      setBlogsTotal(data.total)
    } catch (error) {
      console.error('Blogs load error:', error)
    }
  }, [blogFilter])

  const loadTemplates = useCallback(async () => {
    try {
      const data = await outreachAPI.getTemplates()
      setTemplates(data.templates)
    } catch (error) {
      console.error('Templates load error:', error)
    }
  }, [])

  const loadCampaigns = useCallback(async () => {
    try {
      const data = await outreachAPI.getCampaigns()
      setCampaigns(data.campaigns)
    } catch (error) {
      console.error('Campaigns load error:', error)
    }
  }, [])

  const loadKeywords = useCallback(async () => {
    try {
      const data = await outreachAPI.getKeywords()
      setKeywords(data.keywords)
    } catch (error) {
      console.error('Keywords load error:', error)
    }
  }, [])

  const loadSettings = useCallback(async () => {
    try {
      const data = await outreachAPI.getSettings()
      setSettings(data.settings)
    } catch (error) {
      console.error('Settings load error:', error)
    }
  }, [])

  const loadSchedulerStatus = useCallback(async () => {
    try {
      const data = await outreachAPI.getSchedulerStatus()
      setSchedulerStatus(data)
    } catch (error) {
      console.error('Scheduler status load error:', error)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
    loadScoringStats()
    loadBlogs()
    loadTemplates()
    loadCampaigns()
    loadKeywords()
    loadSettings()
    loadSchedulerStatus()
  }, [loadDashboard, loadScoringStats, loadBlogs, loadTemplates, loadCampaigns, loadKeywords, loadSettings, loadSchedulerStatus])

  useEffect(() => {
    loadBlogs()
  }, [blogFilter, loadBlogs])

  // Actions
  const handleSearchBlogs = async () => {
    if (!searchKeyword) {
      toast.error('검색 키워드를 입력하세요')
      return
    }
    setLoading(true)
    try {
      const result = await outreachAPI.searchBlogs({
        keyword: searchKeyword,
        category: searchCategory || undefined,
        max_results: 50,
      })
      if (result.success) {
        toast.success(`${result.collected || 0}개 블로그 수집 완료`)
        loadBlogs()
        loadDashboard()
      } else {
        toast.error(result.message || '수집 실패')
      }
    } catch (error) {
      toast.error('블로그 수집 중 오류 발생')
    } finally {
      setLoading(false)
    }
  }

  const handleExtractContactsBatch = async () => {
    setLoading(true)
    try {
      const result = await outreachAPI.extractContactsBatch(50)
      if (result.success) {
        toast.success(`${result.processed || 0}개 처리, ${result.with_contacts || 0}개 연락처 발견`)
        loadBlogs()
        loadDashboard()
      }
    } catch (error) {
      toast.error('연락처 추출 중 오류 발생')
    } finally {
      setLoading(false)
    }
  }

  const handleScoreBatch = async () => {
    setLoading(true)
    try {
      const result = await outreachAPI.scoreBlogsBatch({}, 100)
      if (result.success) {
        toast.success('스코어링 완료')
        loadBlogs()
        loadScoringStats()
      }
    } catch (error) {
      toast.error('스코어링 중 오류 발생')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTemplate = async () => {
    if (!newTemplate.name || !newTemplate.subject || !newTemplate.body) {
      toast.error('필수 필드를 입력하세요')
      return
    }
    try {
      const result = await outreachAPI.createTemplate(newTemplate)
      if (result.success) {
        toast.success('템플릿 생성 완료')
        setTemplateDialogOpen(false)
        setNewTemplate({ name: '', description: '', template_type: 'introduction', subject: '', body: '' })
        loadTemplates()
      }
    } catch (error) {
      toast.error('템플릿 생성 실패')
    }
  }

  const handleUpdateTemplate = async () => {
    if (!editingTemplate) return
    try {
      const result = await outreachAPI.updateTemplate(editingTemplate.id, {
        name: editingTemplate.name,
        description: editingTemplate.description,
        template_type: editingTemplate.template_type,
        subject: editingTemplate.subject,
        body: editingTemplate.body,
      })
      if (result.success) {
        toast.success('템플릿 수정 완료')
        setEditingTemplate(null)
        loadTemplates()
      }
    } catch (error) {
      toast.error('템플릿 수정 실패')
    }
  }

  const handleDeleteTemplate = async (templateId: string) => {
    if (!confirm('템플릿을 삭제하시겠습니까?')) return
    try {
      await outreachAPI.deleteTemplate(templateId)
      toast.success('템플릿 삭제 완료')
      loadTemplates()
    } catch (error) {
      toast.error('템플릿 삭제 실패')
    }
  }

  const handleCreateKeyword = async () => {
    if (!newKeyword.keyword) {
      toast.error('키워드를 입력하세요')
      return
    }
    try {
      const result = await outreachAPI.createKeyword(newKeyword)
      if (result.success) {
        toast.success('키워드 추가 완료')
        setKeywordDialogOpen(false)
        setNewKeyword({ keyword: '', category: '', priority: 1 })
        loadKeywords()
      }
    } catch (error) {
      toast.error('키워드 추가 실패')
    }
  }

  const handleDeleteKeyword = async (keywordId: string) => {
    try {
      await outreachAPI.deleteKeyword(keywordId)
      toast.success('키워드 삭제 완료')
      loadKeywords()
    } catch (error) {
      toast.error('키워드 삭제 실패')
    }
  }

  const handleStartCampaign = async (campaignId: string) => {
    try {
      const result = await outreachAPI.startCampaign(campaignId)
      toast.success(result.message)
      loadCampaigns()
    } catch (error) {
      toast.error('캠페인 시작 실패')
    }
  }

  const handlePauseCampaign = async (campaignId: string) => {
    try {
      const result = await outreachAPI.pauseCampaign(campaignId)
      toast.success(result.message)
      loadCampaigns()
    } catch (error) {
      toast.error('캠페인 일시정지 실패')
    }
  }

  const handleStartScheduler = async () => {
    try {
      const result = await outreachAPI.startScheduler()
      toast.success(result.message)
      loadSchedulerStatus()
    } catch (error) {
      toast.error('스케줄러 시작 실패')
    }
  }

  const handleStopScheduler = async () => {
    try {
      const result = await outreachAPI.stopScheduler()
      toast.success(result.message)
      loadSchedulerStatus()
    } catch (error) {
      toast.error('스케줄러 중지 실패')
    }
  }

  // Badge components
  const GradeBadge = ({ grade }: { grade: string | null }) => {
    if (!grade) return <span className="text-gray-400">-</span>
    const gradeInfo = LEAD_GRADES.find(g => g.value === grade)
    return (
      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${gradeInfo?.bg} ${gradeInfo?.text}`}>
        {grade}
      </span>
    )
  }

  const StatusBadge = ({ status }: { status: string }) => {
    const statusInfo = BLOG_STATUSES.find(s => s.value === status)
    return (
      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${statusInfo?.color || 'bg-gray-100 text-gray-600'}`}>
        {statusInfo?.label || status}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex justify-between items-start mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">블로그 아웃리치</h1>
            </div>
            <p className="text-gray-500 text-sm">인플루언서 발굴부터 이메일 캠페인까지, 스마트한 영업 자동화</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadDashboard()
              loadBlogs()
              loadScoringStats()
            }}
            className="rounded-full border-gray-200 hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            새로고침
          </Button>
        </div>

        {/* Modern Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="inline-flex h-11 items-center justify-start rounded-full bg-gray-100/80 p-1 gap-1">
            {[
              { value: 'dashboard', icon: BarChart3, label: '대시보드' },
              { value: 'blogs', icon: Users, label: '블로그' },
              { value: 'templates', icon: Mail, label: '템플릿' },
              { value: 'campaigns', icon: Target, label: '캠페인' },
              { value: 'keywords', icon: Search, label: '키워드' },
              { value: 'settings', icon: Settings, label: '설정' },
            ].map(tab => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="inline-flex items-center justify-center whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-all data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-sm text-gray-600 hover:text-gray-900"
              >
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6 mt-6">
            {/* Hero Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[
                {
                  label: '수집된 블로그',
                  value: dashboard?.blogs?.total || 0,
                  sub: `연락처 보유 ${dashboard?.blogs?.with_contact || 0}개`,
                  icon: Globe,
                  gradient: 'from-blue-500 to-cyan-400',
                },
                {
                  label: '활성 캠페인',
                  value: dashboard?.campaigns?.active || 0,
                  sub: '진행 중인 이메일 캠페인',
                  icon: Zap,
                  gradient: 'from-violet-500 to-purple-400',
                },
                {
                  label: '오늘 발송',
                  value: dashboard?.email?.today?.sent || 0,
                  sub: `오픈 ${dashboard?.email?.today?.opened || 0} · 회신 ${dashboard?.email?.today?.replied || 0}`,
                  icon: Send,
                  gradient: 'from-emerald-500 to-teal-400',
                },
                {
                  label: '전체 회신율',
                  value: `${dashboard?.email?.total?.reply_rate || 0}%`,
                  sub: `오픈율 ${dashboard?.email?.total?.open_rate || 0}%`,
                  icon: MessageSquare,
                  gradient: 'from-orange-500 to-amber-400',
                },
              ].map((stat, i) => (
                <div
                  key={i}
                  className="relative overflow-hidden rounded-2xl bg-white border border-gray-100 p-5 hover:shadow-lg hover:shadow-gray-100/50 transition-all duration-300"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-gray-500 mb-1">{stat.label}</p>
                      <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
                      <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
                    </div>
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.gradient} flex items-center justify-center`}>
                      <stat.icon className="w-5 h-5 text-white" />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Grade Distribution & Scores */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Grade Distribution */}
              <div className="rounded-2xl bg-white border border-gray-100 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">등급별 분포</h3>
                <div className="space-y-3">
                  {LEAD_GRADES.map(grade => {
                    const count = dashboard?.blogs?.grades?.[grade.value] || 0
                    const total = dashboard?.blogs?.total || 1
                    const percentage = Math.round((count / total) * 100)
                    return (
                      <div key={grade.value} className="flex items-center gap-4">
                        <span className={`w-8 h-8 rounded-lg bg-gradient-to-br ${grade.color} flex items-center justify-center text-white font-bold text-sm`}>
                          {grade.value}
                        </span>
                        <div className="flex-1">
                          <div className="flex justify-between mb-1">
                            <span className="text-sm text-gray-600">{grade.label}</span>
                            <span className="text-sm font-medium text-gray-900">{count}개</span>
                          </div>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full bg-gradient-to-r ${grade.color} rounded-full transition-all duration-500`}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Score Overview */}
              <div className="rounded-2xl bg-white border border-gray-100 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">평균 스코어</h3>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: '리드 점수', value: scoringStats?.avg_lead_score || 0, icon: Star, color: 'text-amber-500' },
                    { label: '영향력', value: scoringStats?.avg_influence_score || 0, icon: TrendingUp, color: 'text-blue-500' },
                    { label: '활동성', value: scoringStats?.avg_activity_score || 0, icon: Zap, color: 'text-emerald-500' },
                    { label: '관련성', value: scoringStats?.avg_relevance_score || 0, icon: Target, color: 'text-violet-500' },
                  ].map((score, i) => (
                    <div key={i} className="bg-gray-50 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <score.icon className={`w-4 h-4 ${score.color}`} />
                        <span className="text-sm text-gray-600">{score.label}</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">
                        {typeof score.value === 'number' ? score.value.toFixed(1) : score.value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="rounded-2xl bg-gradient-to-br from-gray-50 to-white border border-gray-100 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">빠른 실행</h3>
              <div className="flex flex-wrap gap-4">
                <div className="flex items-center gap-2 flex-1 min-w-[300px]">
                  <Input
                    placeholder="검색할 키워드 입력..."
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    className="rounded-xl border-gray-200 bg-white"
                  />
                  <Select value={searchCategory} onValueChange={setSearchCategory}>
                    <SelectTrigger className="w-36 rounded-xl border-gray-200 bg-white">
                      <SelectValue placeholder="카테고리" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">전체</SelectItem>
                      {BLOG_CATEGORIES.map(cat => (
                        <SelectItem key={cat.value} value={cat.value}>
                          <span className="flex items-center gap-2">
                            <span>{cat.icon}</span>
                            {cat.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={handleSearchBlogs}
                    disabled={loading}
                    className="rounded-xl bg-gray-900 hover:bg-gray-800 text-white px-6"
                  >
                    <Search className="w-4 h-4 mr-2" />
                    수집
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleExtractContactsBatch}
                    disabled={loading}
                    className="rounded-xl border-gray-200 hover:bg-gray-50"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    연락처 추출
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleScoreBatch}
                    disabled={loading}
                    className="rounded-xl border-gray-200 hover:bg-gray-50"
                  >
                    <Star className="w-4 h-4 mr-2" />
                    스코어링
                  </Button>
                </div>
              </div>
            </div>

            {/* Scheduler Control */}
            <div className="rounded-2xl bg-white border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    schedulerStatus?.running ? 'bg-gradient-to-br from-emerald-500 to-green-600' : 'bg-gray-200'
                  }`}>
                    <Activity className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">자동화 스케줄러</h3>
                    <p className="text-sm text-gray-500">블로그 수집, 연락처 추출, 캠페인 발송 자동화</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
                    schedulerStatus?.running
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {schedulerStatus?.running ? (
                      <>
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        실행 중
                      </>
                    ) : (
                      <>
                        <span className="w-2 h-2 rounded-full bg-gray-400" />
                        중지됨
                      </>
                    )}
                  </span>
                  {schedulerStatus?.running ? (
                    <Button
                      variant="outline"
                      onClick={handleStopScheduler}
                      className="rounded-xl border-red-200 text-red-600 hover:bg-red-50"
                    >
                      <StopCircle className="w-4 h-4 mr-2" />
                      중지
                    </Button>
                  ) : (
                    <Button
                      onClick={handleStartScheduler}
                      className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white"
                    >
                      <PlayCircle className="w-4 h-4 mr-2" />
                      시작
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={loadSchedulerStatus}
                    className="rounded-lg"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {schedulerStatus && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
                  <div className="bg-gray-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Globe className="w-4 h-4 text-blue-500" />
                      <span className="text-sm text-gray-600">블로그 수집</span>
                    </div>
                    <p className="text-2xl font-bold text-gray-900">{schedulerStatus.blogs_collected}</p>
                    {schedulerStatus.last_collection && (
                      <p className="text-xs text-gray-400 mt-1">
                        마지막: {new Date(schedulerStatus.last_collection).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="bg-gray-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Users className="w-4 h-4 text-violet-500" />
                      <span className="text-sm text-gray-600">연락처 추출</span>
                    </div>
                    <p className="text-2xl font-bold text-gray-900">{schedulerStatus.contacts_extracted}</p>
                  </div>
                  <div className="bg-gray-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Send className="w-4 h-4 text-emerald-500" />
                      <span className="text-sm text-gray-600">이메일 발송</span>
                    </div>
                    <p className="text-2xl font-bold text-gray-900">{schedulerStatus.emails_sent}</p>
                    {schedulerStatus.last_campaign_run && (
                      <p className="text-xs text-gray-400 mt-1">
                        마지막: {new Date(schedulerStatus.last_campaign_run).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="bg-gray-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="w-4 h-4 text-amber-500" />
                      <span className="text-sm text-gray-600">시작 시간</span>
                    </div>
                    <p className="text-sm font-medium text-gray-900">
                      {schedulerStatus.started_at
                        ? new Date(schedulerStatus.started_at).toLocaleString()
                        : '-'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Blogs Tab */}
          <TabsContent value="blogs" className="space-y-4 mt-6">
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3 p-4 bg-gray-50 rounded-2xl">
              <Filter className="w-4 h-4 text-gray-400" />
              {[
                { value: blogFilter.category, setter: (v: string) => setBlogFilter({...blogFilter, category: v}), placeholder: '카테고리', options: BLOG_CATEGORIES.map(c => ({ value: c.value, label: `${c.icon} ${c.label}` })) },
                { value: blogFilter.grade, setter: (v: string) => setBlogFilter({...blogFilter, grade: v}), placeholder: '등급', options: LEAD_GRADES.map(g => ({ value: g.value, label: g.label })) },
                { value: blogFilter.status, setter: (v: string) => setBlogFilter({...blogFilter, status: v}), placeholder: '상태', options: BLOG_STATUSES.map(s => ({ value: s.value, label: s.label })) },
              ].map((filter, i) => (
                <Select key={i} value={filter.value} onValueChange={filter.setter}>
                  <SelectTrigger className="w-32 rounded-xl border-gray-200 bg-white text-sm">
                    <SelectValue placeholder={filter.placeholder} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">전체</SelectItem>
                    {filter.options.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ))}
              <Select
                value={blogFilter.has_contact?.toString() || ''}
                onValueChange={(v) => setBlogFilter({
                  ...blogFilter,
                  has_contact: v === '' ? undefined : v === 'true'
                })}
              >
                <SelectTrigger className="w-32 rounded-xl border-gray-200 bg-white text-sm">
                  <SelectValue placeholder="연락처" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">전체</SelectItem>
                  <SelectItem value="true">있음</SelectItem>
                  <SelectItem value="false">없음</SelectItem>
                </SelectContent>
              </Select>
              <span className="ml-auto text-sm text-gray-500">
                총 <span className="font-semibold text-gray-900">{blogsTotal}</span>개
              </span>
            </div>

            {/* Blogs Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {blogs.map(blog => (
                <div
                  key={blog.id}
                  className="group bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-lg hover:shadow-gray-100/50 hover:border-gray-200 transition-all duration-300"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <a
                        href={blog.blog_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-gray-900 hover:text-violet-600 transition-colors flex items-center gap-1 truncate"
                      >
                        {blog.blog_name || blog.owner_nickname || blog.blog_id}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                      <p className="text-xs text-gray-400 truncate">@{blog.blog_id}</p>
                    </div>
                    <GradeBadge grade={blog.lead_grade} />
                  </div>

                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs px-2 py-1 rounded-lg bg-gray-100 text-gray-600">
                      {BLOG_CATEGORIES.find(c => c.value === blog.category)?.icon} {BLOG_CATEGORIES.find(c => c.value === blog.category)?.label || '기타'}
                    </span>
                    <StatusBadge status={blog.status} />
                  </div>

                  <div className="grid grid-cols-3 gap-2 mb-3 text-center">
                    <div className="bg-gray-50 rounded-lg py-2">
                      <p className="text-xs text-gray-500">점수</p>
                      <p className="font-semibold text-gray-900">{blog.lead_score?.toFixed(0) || 0}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg py-2">
                      <p className="text-xs text-gray-500">방문자</p>
                      <p className="font-semibold text-gray-900">{(blog.visitor_daily || 0).toLocaleString()}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg py-2">
                      <p className="text-xs text-gray-500">이웃</p>
                      <p className="font-semibold text-gray-900">{(blog.neighbor_count || 0).toLocaleString()}</p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    {blog.has_contact ? (
                      <span className="text-xs text-emerald-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        연락처 보유
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">연락처 없음</span>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => window.open(blog.blog_url, '_blank')}
                    >
                      <ArrowUpRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          {/* Templates Tab */}
          <TabsContent value="templates" className="space-y-4 mt-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">이메일 템플릿</h3>
              <Dialog open={templateDialogOpen} onOpenChange={setTemplateDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="rounded-xl bg-gray-900 hover:bg-gray-800">
                    <Plus className="w-4 h-4 mr-2" />
                    새 템플릿
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl rounded-2xl">
                  <DialogHeader>
                    <DialogTitle className="text-xl font-semibold">새 이메일 템플릿</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-sm text-gray-600">템플릿 이름</Label>
                        <Input
                          value={newTemplate.name}
                          onChange={(e) => setNewTemplate({...newTemplate, name: e.target.value})}
                          placeholder="예: 협찬 제안 초기 연락"
                          className="mt-1 rounded-xl"
                        />
                      </div>
                      <div>
                        <Label className="text-sm text-gray-600">유형</Label>
                        <Select
                          value={newTemplate.template_type}
                          onValueChange={(v) => setNewTemplate({...newTemplate, template_type: v})}
                        >
                          <SelectTrigger className="mt-1 rounded-xl">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="introduction">첫 연락</SelectItem>
                            <SelectItem value="follow_up">후속 연락</SelectItem>
                            <SelectItem value="reminder">리마인더</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div>
                      <Label className="text-sm text-gray-600">설명</Label>
                      <Input
                        value={newTemplate.description}
                        onChange={(e) => setNewTemplate({...newTemplate, description: e.target.value})}
                        placeholder="템플릿 설명 (선택)"
                        className="mt-1 rounded-xl"
                      />
                    </div>
                    <div>
                      <Label className="text-sm text-gray-600">제목</Label>
                      <Input
                        value={newTemplate.subject}
                        onChange={(e) => setNewTemplate({...newTemplate, subject: e.target.value})}
                        placeholder="예: [협찬 제안] {{blog_name}}님께 드리는 특별한 제안"
                        className="mt-1 rounded-xl"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        변수: {'{{blog_name}}'}, {'{{blog_nickname}}'}, {'{{sender_name}}'}, {'{{company_name}}'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm text-gray-600">본문</Label>
                      <Textarea
                        value={newTemplate.body}
                        onChange={(e) => setNewTemplate({...newTemplate, body: e.target.value})}
                        placeholder="이메일 본문 내용..."
                        rows={8}
                        className="mt-1 rounded-xl"
                      />
                    </div>
                    <div className="flex justify-end gap-2 pt-4">
                      <Button variant="outline" onClick={() => setTemplateDialogOpen(false)} className="rounded-xl">
                        취소
                      </Button>
                      <Button onClick={handleCreateTemplate} className="rounded-xl bg-gray-900 hover:bg-gray-800">
                        저장
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map(template => (
                <div key={template.id} className="bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-lg hover:shadow-gray-100/50 transition-all duration-300">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h4 className="font-semibold text-gray-900">{template.name}</h4>
                      <span className="text-xs px-2 py-1 rounded-lg bg-violet-50 text-violet-600">
                        {template.template_type === 'introduction' ? '첫 연락' : template.template_type === 'follow_up' ? '후속' : '리마인더'}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="rounded-lg h-8 w-8 text-gray-400 hover:text-violet-600"
                        onClick={() => setEditingTemplate(template)}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="rounded-lg h-8 w-8 text-gray-400 hover:text-red-500"
                        onClick={() => handleDeleteTemplate(template.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 line-clamp-2 mb-4">
                    {template.description || template.subject}
                  </p>
                  <div className="flex items-center justify-between text-xs text-gray-400">
                    <span>사용 {template.usage_count}회</span>
                    {template.open_rate && <span>오픈율 {template.open_rate}%</span>}
                  </div>
                </div>
              ))}
              {templates.length === 0 && (
                <div className="col-span-full py-12 text-center text-gray-400">
                  <Mail className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>아직 템플릿이 없습니다</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Campaigns Tab */}
          <TabsContent value="campaigns" className="space-y-4 mt-6">
            <div className="rounded-2xl bg-white border border-gray-100 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50/50">
                    <TableHead className="font-semibold">캠페인</TableHead>
                    <TableHead className="font-semibold">상태</TableHead>
                    <TableHead className="font-semibold text-center">발송</TableHead>
                    <TableHead className="font-semibold text-center">오픈</TableHead>
                    <TableHead className="font-semibold text-center">회신</TableHead>
                    <TableHead className="font-semibold">시작일</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.map(campaign => (
                    <TableRow key={campaign.id} className="hover:bg-gray-50/50">
                      <TableCell>
                        <div>
                          <p className="font-medium text-gray-900">{campaign.name}</p>
                          <p className="text-xs text-gray-400">{campaign.description}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                          campaign.status === 'active' ? 'bg-emerald-100 text-emerald-700' :
                          campaign.status === 'paused' ? 'bg-amber-100 text-amber-700' :
                          campaign.status === 'completed' ? 'bg-gray-100 text-gray-600' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {campaign.status === 'active' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
                          {campaign.status === 'active' ? '활성' :
                           campaign.status === 'paused' ? '일시정지' :
                           campaign.status === 'completed' ? '완료' : '초안'}
                        </span>
                      </TableCell>
                      <TableCell className="text-center font-medium">{campaign.total_sent}</TableCell>
                      <TableCell className="text-center font-medium">{campaign.total_opened}</TableCell>
                      <TableCell className="text-center font-medium">{campaign.total_replied}</TableCell>
                      <TableCell className="text-gray-500 text-sm">
                        {campaign.started_at ? new Date(campaign.started_at).toLocaleDateString() : '-'}
                      </TableCell>
                      <TableCell>
                        {campaign.status === 'active' ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="rounded-lg"
                            onClick={() => handlePauseCampaign(campaign.id)}
                          >
                            <PauseCircle className="w-4 h-4" />
                          </Button>
                        ) : campaign.status !== 'completed' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="rounded-lg"
                            onClick={() => handleStartCampaign(campaign.id)}
                          >
                            <PlayCircle className="w-4 h-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {campaigns.length === 0 && (
                <div className="py-12 text-center text-gray-400">
                  <Target className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>아직 캠페인이 없습니다</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Keywords Tab */}
          <TabsContent value="keywords" className="space-y-4 mt-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">검색 키워드</h3>
              <Dialog open={keywordDialogOpen} onOpenChange={setKeywordDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="rounded-xl bg-gray-900 hover:bg-gray-800">
                    <Plus className="w-4 h-4 mr-2" />
                    키워드 추가
                  </Button>
                </DialogTrigger>
                <DialogContent className="rounded-2xl">
                  <DialogHeader>
                    <DialogTitle className="text-xl font-semibold">검색 키워드 추가</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div>
                      <Label className="text-sm text-gray-600">키워드</Label>
                      <Input
                        value={newKeyword.keyword}
                        onChange={(e) => setNewKeyword({...newKeyword, keyword: e.target.value})}
                        placeholder="예: 성형외과, 피부과, 맛집"
                        className="mt-1 rounded-xl"
                      />
                    </div>
                    <div>
                      <Label className="text-sm text-gray-600">카테고리</Label>
                      <Select
                        value={newKeyword.category}
                        onValueChange={(v) => setNewKeyword({...newKeyword, category: v})}
                      >
                        <SelectTrigger className="mt-1 rounded-xl">
                          <SelectValue placeholder="선택 (선택사항)" />
                        </SelectTrigger>
                        <SelectContent>
                          {BLOG_CATEGORIES.map(cat => (
                            <SelectItem key={cat.value} value={cat.value}>
                              <span className="flex items-center gap-2">
                                <span>{cat.icon}</span>
                                {cat.label}
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex justify-end gap-2 pt-4">
                      <Button variant="outline" onClick={() => setKeywordDialogOpen(false)} className="rounded-xl">
                        취소
                      </Button>
                      <Button onClick={handleCreateKeyword} className="rounded-xl bg-gray-900 hover:bg-gray-800">
                        추가
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {keywords.map(keyword => (
                <div
                  key={keyword.id}
                  className="group flex items-center justify-between bg-white rounded-xl border border-gray-100 px-4 py-3 hover:shadow-md hover:shadow-gray-100/50 transition-all duration-300"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">
                      {BLOG_CATEGORIES.find(c => c.value === keyword.category)?.icon || '🔍'}
                    </span>
                    <div>
                      <p className="font-medium text-gray-900">{keyword.keyword}</p>
                      <p className="text-xs text-gray-400">
                        수집 {keyword.total_collected}개
                        {keyword.last_collected_at && ` · ${new Date(keyword.last_collected_at).toLocaleDateString()}`}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="rounded-lg h-8 w-8 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                    onClick={() => handleDeleteKeyword(keyword.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))}
              {keywords.length === 0 && (
                <div className="col-span-full py-12 text-center text-gray-400">
                  <Search className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>아직 키워드가 없습니다</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="space-y-6 mt-6">
            {/* Sender Info */}
            <div className="rounded-2xl bg-white border border-gray-100 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">발신자 정보</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm text-gray-600">발신자 이름</Label>
                  <Input
                    value={settings?.sender_name || ''}
                    onChange={(e) => setSettings(s => s ? {...s, sender_name: e.target.value} : null)}
                    placeholder="홍길동"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">발신자 이메일</Label>
                  <Input
                    type="email"
                    value={settings?.sender_email || ''}
                    onChange={(e) => setSettings(s => s ? {...s, sender_email: e.target.value} : null)}
                    placeholder="example@company.com"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">회사명</Label>
                  <Input
                    value={settings?.company_name || ''}
                    onChange={(e) => setSettings(s => s ? {...s, company_name: e.target.value} : null)}
                    placeholder="회사명"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">서비스명</Label>
                  <Input
                    value={settings?.service_name || ''}
                    onChange={(e) => setSettings(s => s ? {...s, service_name: e.target.value} : null)}
                    placeholder="서비스명"
                    className="mt-1 rounded-xl"
                  />
                </div>
              </div>
            </div>

            {/* SMTP Settings */}
            <div className="rounded-2xl bg-white border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">SMTP 설정</h3>
                <a
                  href="/dashboard/outreach/smtp-guide"
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <HelpCircle className="h-4 w-4" />
                  설정 가이드 보기
                </a>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm text-gray-600">SMTP 호스트</Label>
                  <Input
                    value={settings?.smtp_host || ''}
                    onChange={(e) => setSettings(s => s ? {...s, smtp_host: e.target.value} : null)}
                    placeholder="smtp.gmail.com"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">포트</Label>
                  <Input
                    type="number"
                    value={settings?.smtp_port || 587}
                    onChange={(e) => setSettings(s => s ? {...s, smtp_port: parseInt(e.target.value)} : null)}
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">사용자명</Label>
                  <Input
                    value={settings?.smtp_username || ''}
                    onChange={(e) => setSettings(s => s ? {...s, smtp_username: e.target.value} : null)}
                    placeholder="이메일 주소"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">비밀번호</Label>
                  <Input
                    type="password"
                    placeholder={settings?.smtp_configured ? '●●●●●●●●' : '앱 비밀번호'}
                    className="mt-1 rounded-xl"
                  />
                </div>
              </div>
              <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-100">
                <Switch checked={settings?.smtp_use_tls || false} />
                <Label className="text-sm text-gray-600">TLS 암호화 사용</Label>
              </div>
            </div>

            {/* Sending Limits */}
            <div className="rounded-2xl bg-white border border-gray-100 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">발송 제한</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-sm text-gray-600">일일 발송 한도</Label>
                  <Input
                    type="number"
                    value={settings?.daily_limit || 50}
                    onChange={(e) => setSettings(s => s ? {...s, daily_limit: parseInt(e.target.value)} : null)}
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">시간당 발송 한도</Label>
                  <Input
                    type="number"
                    value={settings?.hourly_limit || 10}
                    onChange={(e) => setSettings(s => s ? {...s, hourly_limit: parseInt(e.target.value)} : null)}
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">최소 발송 간격 (초)</Label>
                  <Input
                    type="number"
                    value={settings?.min_interval_seconds || 300}
                    onChange={(e) => setSettings(s => s ? {...s, min_interval_seconds: parseInt(e.target.value)} : null)}
                    className="mt-1 rounded-xl"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                onClick={async () => {
                  if (settings) {
                    try {
                      await outreachAPI.updateSettings(settings)
                      toast.success('설정이 저장되었습니다')
                    } catch (error) {
                      toast.error('설정 저장에 실패했습니다')
                    }
                  }
                }}
                className="rounded-xl bg-gray-900 hover:bg-gray-800 px-8"
              >
                설정 저장
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Template Edit Dialog */}
      <Dialog open={!!editingTemplate} onOpenChange={(open) => !open && setEditingTemplate(null)}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold">템플릿 수정</DialogTitle>
          </DialogHeader>
          {editingTemplate && (
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm text-gray-600">템플릿 이름</Label>
                  <Input
                    value={editingTemplate.name}
                    onChange={(e) => setEditingTemplate({...editingTemplate, name: e.target.value})}
                    placeholder="예: 협찬 제안 초기 연락"
                    className="mt-1 rounded-xl"
                  />
                </div>
                <div>
                  <Label className="text-sm text-gray-600">유형</Label>
                  <Select
                    value={editingTemplate.template_type}
                    onValueChange={(v) => setEditingTemplate({...editingTemplate, template_type: v})}
                  >
                    <SelectTrigger className="mt-1 rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="introduction">첫 연락</SelectItem>
                      <SelectItem value="follow_up">후속 연락</SelectItem>
                      <SelectItem value="reminder">리마인더</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label className="text-sm text-gray-600">설명</Label>
                <Input
                  value={editingTemplate.description || ''}
                  onChange={(e) => setEditingTemplate({...editingTemplate, description: e.target.value})}
                  placeholder="템플릿 설명 (선택)"
                  className="mt-1 rounded-xl"
                />
              </div>
              <div>
                <Label className="text-sm text-gray-600">제목</Label>
                <Input
                  value={editingTemplate.subject}
                  onChange={(e) => setEditingTemplate({...editingTemplate, subject: e.target.value})}
                  placeholder="예: [협찬 제안] {{blog_name}}님께 드리는 특별한 제안"
                  className="mt-1 rounded-xl"
                />
                <p className="text-xs text-gray-400 mt-1">
                  변수: {'{{blog_name}}'}, {'{{blog_nickname}}'}, {'{{sender_name}}'}, {'{{company_name}}'}
                </p>
              </div>
              <div>
                <Label className="text-sm text-gray-600">본문</Label>
                <Textarea
                  value={editingTemplate.body}
                  onChange={(e) => setEditingTemplate({...editingTemplate, body: e.target.value})}
                  placeholder="이메일 본문 내용..."
                  rows={8}
                  className="mt-1 rounded-xl"
                />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingTemplate(null)} className="rounded-xl">
                  취소
                </Button>
                <Button onClick={handleUpdateTemplate} className="rounded-xl bg-gray-900 hover:bg-gray-800">
                  저장
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
