'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
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
  Download,
  Filter,
  Star,
  TrendingUp,
  BarChart3,
  PlayCircle,
  PauseCircle,
  ExternalLink,
  Zap,
  Globe,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  MessageSquare,
  Pencil,
  Activity,
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

type PillTone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const LEAD_GRADES: { value: string; label: string; tone: PillTone; bar: string }[] = [
  { value: 'A', label: 'A등급', tone: 'ok', bar: 'bg-success' },
  { value: 'B', label: 'B등급', tone: 'accent', bar: 'bg-primary' },
  { value: 'C', label: 'C등급', tone: 'warn', bar: 'bg-warning' },
  { value: 'D', label: 'D등급', tone: 'muted', bar: 'bg-muted-foreground' },
]

const BLOG_STATUSES: { value: string; label: string; tone: PillTone }[] = [
  { value: 'new', label: '신규', tone: 'accent' },
  { value: 'contact_found', label: '연락처 발견', tone: 'ok' },
  { value: 'contacted', label: '연락함', tone: 'accent' },
  { value: 'responded', label: '회신받음', tone: 'ok' },
  { value: 'converted', label: '전환됨', tone: 'ok' },
  { value: 'not_interested', label: '관심없음', tone: 'muted' },
  { value: 'invalid', label: '유효하지 않음', tone: 'danger' },
]

export default function OutreachPage() {
  const router = useRouter()
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

  // 에러 메시지 포맷팅 헬퍼
  const formatApiError = (error: any, defaultMessage: string) => {
    const data = error?.response?.data
    if (data) {
      // 상세 에러 정보가 있는 경우
      if (data.user_message) {
        return {
          title: data.error || defaultMessage,
          description: data.user_message,
          action: data.action_required,
          helpUrl: data.help_url,
        }
      }
      // 기본 detail 에러
      if (data.detail) {
        return {
          title: defaultMessage,
          description: typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail),
        }
      }
    }
    return { title: defaultMessage, description: error?.message || '알 수 없는 오류가 발생했습니다' }
  }

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
    } catch (error: any) {
      const err = formatApiError(error, '블로그 수집 중 오류 발생')
      toast.error(err.title, {
        description: err.description,
        action: err.helpUrl ? {
          label: '도움말 보기',
          onClick: () => window.open(err.helpUrl, '_blank'),
        } : undefined,
      })
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
      } else {
        toast.error(result.message || '연락처 추출에 실패했습니다')
      }
    } catch (error: any) {
      const err = formatApiError(error, '연락처 추출 중 오류 발생')
      toast.error(err.title, { description: err.description })
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateNaverEmails = async () => {
    setLoading(true)
    try {
      const result = await outreachAPI.generateNaverEmails(100)
      if (result.success) {
        toast.success(result.message || `${result.generated}개 네이버 이메일 생성`)
        loadBlogs()
        loadDashboard()
      } else {
        toast.error(result.message || '네이버 이메일 생성에 실패했습니다')
      }
    } catch (error: any) {
      const err = formatApiError(error, '네이버 이메일 생성 중 오류 발생')
      toast.error(err.title, { description: err.description })
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
      } else {
        toast.error('스코어링에 실패했습니다')
      }
    } catch (error: any) {
      const err = formatApiError(error, '스코어링 중 오류 발생')
      toast.error(err.title, { description: err.description })
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateBlogStatus = async (blogId: string, status: string) => {
    try {
      await outreachAPI.updateBlogStatus(blogId, status)
      toast.success(status === 'WATCHING' ? '관심 목록에 추가되었습니다' : '상태가 변경되었습니다')
      loadBlogs()
    } catch (error: any) {
      const err = formatApiError(error, '상태 변경 실패')
      toast.error(err.title, { description: err.description })
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
      if (result.success) {
        toast.success(result.message || '캠페인이 시작되었습니다')
        loadCampaigns()
      } else {
        toast.error(result.message || '캠페인 시작 실패')
      }
    } catch (error: any) {
      const err = formatApiError(error, '캠페인 시작 실패')
      toast.error(err.title, {
        description: err.description,
        action: err.helpUrl ? {
          label: 'SMTP 설정 확인',
          onClick: () => window.location.href = err.helpUrl,
        } : undefined,
      })
    }
  }

  const handlePauseCampaign = async (campaignId: string) => {
    try {
      const result = await outreachAPI.pauseCampaign(campaignId)
      toast.success(result.message || '캠페인이 일시정지되었습니다')
      loadCampaigns()
    } catch (error: any) {
      const err = formatApiError(error, '캠페인 일시정지 실패')
      toast.error(err.title, { description: err.description })
    }
  }

  const handleStartScheduler = async () => {
    try {
      const result = await outreachAPI.startScheduler()
      if (result.success) {
        toast.success(result.message || '스케줄러가 시작되었습니다')
        loadSchedulerStatus()
      } else {
        toast.error(result.message || '스케줄러 시작 실패')
      }
    } catch (error: any) {
      const err = formatApiError(error, '스케줄러 시작 실패')
      toast.error(err.title, { description: err.description })
    }
  }

  const handleStopScheduler = async () => {
    try {
      const result = await outreachAPI.stopScheduler()
      toast.success(result.message || '스케줄러가 중지되었습니다')
      loadSchedulerStatus()
    } catch (error: any) {
      const err = formatApiError(error, '스케줄러 중지 실패')
      toast.error(err.title, { description: err.description })
    }
  }

  // Badge components
  const GradeBadge = ({ grade }: { grade: string | null }) => {
    if (!grade) return <span className="text-muted-foreground">-</span>
    const gradeInfo = LEAD_GRADES.find(g => g.value === grade)
    return <Pill tone={gradeInfo?.tone || 'muted'} className="font-semibold">{grade}</Pill>
  }

  const StatusBadge = ({ status }: { status: string }) => {
    const statusInfo = BLOG_STATUSES.find(s => s.value === status)
    return <Pill tone={statusInfo?.tone || 'muted'}>{statusInfo?.label || status}</Pill>
  }

  const thCls = 'text-[12px] font-medium uppercase tracking-wide text-muted-foreground'

  return (
    <div className="space-y-6">
      <PageHeader
        title="블로그 아웃리치"
        description="인플루언서 발굴부터 이메일 캠페인까지, 영업을 자동화합니다."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadDashboard()
              loadBlogs()
              loadScoringStats()
            }}
          >
            <RefreshCw />
            새로고침
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="h-auto flex-wrap justify-start">
          {[
            { value: 'dashboard', icon: BarChart3, label: '대시보드' },
            { value: 'blogs', icon: Users, label: '블로그' },
            { value: 'templates', icon: Mail, label: '템플릿' },
            { value: 'campaigns', icon: Target, label: '캠페인' },
            { value: 'keywords', icon: Search, label: '키워드' },
            { value: 'settings', icon: Settings, label: '설정' },
          ].map(tab => (
            <TabsTrigger key={tab.value} value={tab.value} className="gap-1.5">
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Dashboard Tab */}
        <TabsContent value="dashboard" className="space-y-6 mt-6">
          {/* Hero Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatTile
              label="수집된 블로그"
              value={dashboard?.blogs?.total || 0}
              hint={`연락처 보유 ${dashboard?.blogs?.with_contact || 0}개`}
              icon={<Globe className="h-4 w-4" />}
            />
            <StatTile
              label="활성 캠페인"
              value={dashboard?.campaigns?.active || 0}
              hint="진행 중인 이메일 캠페인"
              tone="accent"
              icon={<Zap className="h-4 w-4" />}
            />
            <StatTile
              label="오늘 발송"
              value={dashboard?.email?.today?.sent || 0}
              hint={`오픈 ${dashboard?.email?.today?.opened || 0} · 회신 ${dashboard?.email?.today?.replied || 0}`}
              icon={<Send className="h-4 w-4" />}
            />
            <StatTile
              label="전체 회신율"
              value={`${dashboard?.email?.total?.reply_rate || 0}%`}
              hint={`오픈율 ${dashboard?.email?.total?.open_rate || 0}%`}
              tone="ok"
              icon={<MessageSquare className="h-4 w-4" />}
            />
          </div>

          {/* Grade Distribution & Scores */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Grade Distribution */}
            <div className="surface p-5">
              <h3 className="section-title mb-4">등급별 분포</h3>
              <div className="space-y-3">
                {LEAD_GRADES.map(grade => {
                  const count = dashboard?.blogs?.grades?.[grade.value] || 0
                  const total = dashboard?.blogs?.total || 1
                  const percentage = Math.round((count / total) * 100)
                  return (
                    <div key={grade.value} className="flex items-center gap-4">
                      <Pill tone={grade.tone} className="w-8 justify-center font-semibold">{grade.value}</Pill>
                      <div className="flex-1">
                        <div className="flex justify-between mb-1">
                          <span className="text-sm text-muted-foreground">{grade.label}</span>
                          <span className="text-sm font-medium tabular-nums">{count}개</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${grade.bar} transition-all duration-500`}
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
            <div className="surface p-5">
              <h3 className="section-title mb-4">평균 스코어</h3>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: '리드 점수', value: scoringStats?.avg_lead_score || 0, icon: Star },
                  { label: '영향력', value: scoringStats?.avg_influence_score || 0, icon: TrendingUp },
                  { label: '활동성', value: scoringStats?.avg_activity_score || 0, icon: Zap },
                  { label: '관련성', value: scoringStats?.avg_relevance_score || 0, icon: Target },
                ].map((score, i) => (
                  <div key={i} className="rounded-lg border bg-muted/40 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <score.icon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-[13px] font-medium text-muted-foreground">{score.label}</span>
                    </div>
                    <p className="kpi">
                      {typeof score.value === 'number' ? score.value.toFixed(1) : score.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="surface p-5">
            <h3 className="section-title mb-4">빠른 실행</h3>
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-2 flex-1 min-w-[300px]">
                <Input
                  placeholder="검색할 키워드 입력..."
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                />
                <Select value={searchCategory || 'all'} onValueChange={(v) => setSearchCategory(v === 'all' ? '' : v)}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="카테고리" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">전체</SelectItem>
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
                >
                  <Search />
                  수집
                </Button>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button
                  variant="outline"
                  onClick={handleGenerateNaverEmails}
                  disabled={loading}
                >
                  <Mail />
                  네이버 이메일 생성
                </Button>
                <Button
                  variant="outline"
                  onClick={handleExtractContactsBatch}
                  disabled={loading}
                >
                  <Download />
                  연락처 추출
                </Button>
                <Button
                  variant="outline"
                  onClick={handleScoreBatch}
                  disabled={loading}
                >
                  <Star />
                  스코어링
                </Button>
              </div>
            </div>
          </div>

          {/* Scheduler Control */}
          <div className="surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                  schedulerStatus?.running ? 'bg-success-soft text-success' : 'bg-accent text-primary'
                }`}>
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="section-title">자동화 스케줄러</h3>
                  <p className="text-[13px] text-muted-foreground">블로그 수집, 연락처 추출, 캠페인 발송 자동화</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Pill tone={schedulerStatus?.running ? 'ok' : 'muted'}>
                  {schedulerStatus?.running ? (
                    <>
                      <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
                      실행 중
                    </>
                  ) : (
                    <>
                      <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                      중지됨
                    </>
                  )}
                </Pill>
                {schedulerStatus?.running ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleStopScheduler}
                    className="text-danger"
                  >
                    <StopCircle />
                    중지
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleStartScheduler}
                  >
                    <PlayCircle />
                    시작
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={loadSchedulerStatus}
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {schedulerStatus && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t">
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Globe className="h-4 w-4 text-muted-foreground" />
                    <span className="text-[13px] font-medium text-muted-foreground">블로그 수집</span>
                  </div>
                  <p className="kpi">{schedulerStatus.blogs_collected}</p>
                  {schedulerStatus.last_collection && (
                    <p className="text-xs text-muted-foreground mt-1">
                      마지막: {new Date(schedulerStatus.last_collection).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span className="text-[13px] font-medium text-muted-foreground">연락처 추출</span>
                  </div>
                  <p className="kpi">{schedulerStatus.contacts_extracted}</p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Send className="h-4 w-4 text-muted-foreground" />
                    <span className="text-[13px] font-medium text-muted-foreground">이메일 발송</span>
                  </div>
                  <p className="kpi">{schedulerStatus.emails_sent}</p>
                  {schedulerStatus.last_campaign_run && (
                    <p className="text-xs text-muted-foreground mt-1">
                      마지막: {new Date(schedulerStatus.last_campaign_run).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-[13px] font-medium text-muted-foreground">시작 시간</span>
                  </div>
                  <p className="text-sm font-medium tabular-nums">
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
          <div className="flex flex-wrap items-center gap-3 surface p-4">
            <Filter className="w-4 h-4 text-muted-foreground" />
            {[
              { value: blogFilter.category, setter: (v: string) => setBlogFilter({...blogFilter, category: v === 'all' ? '' : v}), placeholder: '카테고리', options: BLOG_CATEGORIES.map(c => ({ value: c.value, label: `${c.icon} ${c.label}` })) },
              { value: blogFilter.grade, setter: (v: string) => setBlogFilter({...blogFilter, grade: v === 'all' ? '' : v}), placeholder: '등급', options: LEAD_GRADES.map(g => ({ value: g.value, label: g.label })) },
              { value: blogFilter.status, setter: (v: string) => setBlogFilter({...blogFilter, status: v === 'all' ? '' : v}), placeholder: '상태', options: BLOG_STATUSES.map(s => ({ value: s.value, label: s.label })) },
            ].map((filter, i) => (
              <Select key={i} value={filter.value || 'all'} onValueChange={filter.setter}>
                <SelectTrigger className="w-32 text-sm">
                  <SelectValue placeholder={filter.placeholder} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체</SelectItem>
                  {filter.options.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ))}
            <Select
              value={blogFilter.has_contact === undefined ? 'all' : blogFilter.has_contact.toString()}
              onValueChange={(v) => setBlogFilter({
                ...blogFilter,
                has_contact: v === 'all' ? undefined : v === 'true'
              })}
            >
              <SelectTrigger className="w-32 text-sm">
                <SelectValue placeholder="연락처" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="true">있음</SelectItem>
                <SelectItem value="false">없음</SelectItem>
              </SelectContent>
            </Select>
            <span className="ml-auto text-sm text-muted-foreground">
              총 <span className="font-semibold tabular-nums text-foreground">{blogsTotal}</span>개
            </span>
          </div>

          {blogs.length === 0 && (
            <EmptyState
              icon={<Users className="h-8 w-8" />}
              title="수집된 블로그가 없습니다"
              description="대시보드 탭에서 키워드를 입력해 블로그를 수집하세요."
              action={
                <Button variant="outline" size="sm" onClick={() => setActiveTab('dashboard')}>
                  <Search />
                  블로그 수집하기
                </Button>
              }
            />
          )}

          {/* Blogs Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {blogs.map(blog => (
              <div
                key={blog.id}
                className="group surface p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <a
                      href={blog.blog_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1 truncate"
                    >
                      {blog.blog_name || blog.owner_nickname || blog.blog_id}
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                    <p className="text-xs text-muted-foreground truncate">@{blog.blog_id}</p>
                  </div>
                  <GradeBadge grade={blog.lead_grade} />
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <Pill tone="muted">
                    {BLOG_CATEGORIES.find(c => c.value === blog.category)?.label || '기타'}
                  </Pill>
                  <StatusBadge status={blog.status} />
                </div>

                <div className="grid grid-cols-3 gap-2 mb-3 text-center">
                  <div className="rounded-lg bg-muted/40 py-2">
                    <p className="text-xs text-muted-foreground">점수</p>
                    <p className="font-semibold tabular-nums">{blog.lead_score?.toFixed(0) || 0}</p>
                  </div>
                  <div className="rounded-lg bg-muted/40 py-2">
                    <p className="text-xs text-muted-foreground">방문자</p>
                    <p className="font-semibold tabular-nums">{(blog.visitor_daily || 0).toLocaleString()}</p>
                  </div>
                  <div className="rounded-lg bg-muted/40 py-2">
                    <p className="text-xs text-muted-foreground">이웃</p>
                    <p className="font-semibold tabular-nums">{(blog.neighbor_count || 0).toLocaleString()}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between mb-3">
                  {blog.has_contact ? (
                    <span className="text-xs text-success flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      연락처 보유
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">연락처 없음</span>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => window.open(blog.blog_url, '_blank')}
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </Button>
                </div>

                {/* 등급별 액션 가이드 */}
                <div className={`rounded-lg border p-3 text-xs ${
                  blog.lead_grade === 'A' ? 'bg-success-soft' :
                  blog.lead_grade === 'B' ? 'bg-accent' :
                  blog.lead_grade === 'C' ? 'bg-warning-soft' :
                  'bg-muted/40'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className={`font-medium ${
                      blog.lead_grade === 'A' ? 'text-success' :
                      blog.lead_grade === 'B' ? 'text-primary' :
                      blog.lead_grade === 'C' ? 'text-warning' :
                      'text-muted-foreground'
                    }`}>
                      {blog.lead_grade === 'A' ? '지금 연락 추천' :
                       blog.lead_grade === 'B' ? '관심 목록 추가' :
                       blog.lead_grade === 'C' ? '추후 검토' :
                       '관찰 대상'}
                    </span>
                    {blog.lead_grade === 'A' && blog.has_contact && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-xs"
                        onClick={() => {
                          // 이메일 발송 페이지로 이동하거나 모달 열기
                          router.push(`/dashboard/outreach/campaigns/new?blog_id=${blog.id}`)
                        }}
                      >
                        이메일 발송
                      </Button>
                    )}
                    {blog.lead_grade === 'B' && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-xs"
                        onClick={() => {
                          handleUpdateBlogStatus(blog.id, 'WATCHING')
                        }}
                      >
                        관심 등록
                      </Button>
                    )}
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {blog.lead_grade === 'A' ? '높은 영향력 + 활발한 활동. 협찬 성공률 높음!' :
                     blog.lead_grade === 'B' ? '잠재력 있음. 팔로업 알림을 설정하세요.' :
                     blog.lead_grade === 'C' ? '영향력 보통. 대량 캠페인에 적합.' :
                     '활동량 낮음. 추가 모니터링 필요.'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4 mt-6">
          <div className="flex justify-between items-center">
            <h3 className="section-title">이메일 템플릿</h3>
            <Dialog open={templateDialogOpen} onOpenChange={setTemplateDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus />
                  새 템플릿
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>새 이메일 템플릿</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>템플릿 이름</Label>
                      <Input
                        value={newTemplate.name}
                        onChange={(e) => setNewTemplate({...newTemplate, name: e.target.value})}
                        placeholder="예: 협찬 제안 초기 연락"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>유형</Label>
                      <Select
                        value={newTemplate.template_type}
                        onValueChange={(v) => setNewTemplate({...newTemplate, template_type: v})}
                      >
                        <SelectTrigger className="mt-1">
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
                    <Label>설명</Label>
                    <Input
                      value={newTemplate.description}
                      onChange={(e) => setNewTemplate({...newTemplate, description: e.target.value})}
                      placeholder="템플릿 설명 (선택)"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>제목</Label>
                    <Input
                      value={newTemplate.subject}
                      onChange={(e) => setNewTemplate({...newTemplate, subject: e.target.value})}
                      placeholder="예: [협찬 제안] {{blog_name}}님께 드리는 특별한 제안"
                      className="mt-1"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      변수: {'{{blog_name}}'}, {'{{blog_nickname}}'}, {'{{sender_name}}'}, {'{{company_name}}'}
                    </p>
                  </div>
                  <div>
                    <Label>본문</Label>
                    <Textarea
                      value={newTemplate.body}
                      onChange={(e) => setNewTemplate({...newTemplate, body: e.target.value})}
                      placeholder="이메일 본문 내용..."
                      rows={8}
                      className="mt-1"
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-4">
                    <Button variant="outline" onClick={() => setTemplateDialogOpen(false)}>
                      취소
                    </Button>
                    <Button onClick={handleCreateTemplate}>
                      저장
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map(template => (
              <div key={template.id} className="surface p-5">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="text-sm font-semibold">{template.name}</h4>
                    <Pill tone="accent" className="mt-1">
                      {template.template_type === 'introduction' ? '첫 연락' : template.template_type === 'follow_up' ? '후속' : '리마인더'}
                    </Pill>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-muted-foreground hover:text-primary"
                      onClick={() => setEditingTemplate(template)}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-muted-foreground hover:text-danger"
                      onClick={() => handleDeleteTemplate(template.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                  {template.description || template.subject}
                </p>
                <div className="flex items-center justify-between text-xs tabular-nums text-muted-foreground">
                  <span>사용 {template.usage_count}회</span>
                  {template.open_rate && <span>오픈율 {template.open_rate}%</span>}
                </div>
              </div>
            ))}
            {templates.length === 0 && (
              <EmptyState
                className="col-span-full"
                icon={<Mail className="h-8 w-8" />}
                title="아직 템플릿이 없습니다"
                description="첫 연락, 후속, 리마인더용 이메일 템플릿을 만들어 두면 캠페인에서 바로 쓸 수 있습니다."
                action={
                  <Button variant="outline" size="sm" onClick={() => setTemplateDialogOpen(true)}>
                    <Plus />
                    템플릿 만들기
                  </Button>
                }
              />
            )}
          </div>
        </TabsContent>

        {/* Campaigns Tab */}
        <TabsContent value="campaigns" className="space-y-4 mt-6">
          {campaigns.length === 0 ? (
            <EmptyState
              icon={<Target className="h-8 w-8" />}
              title="아직 캠페인이 없습니다"
              description="템플릿과 대상 블로그를 준비한 뒤 캠페인을 만들어 발송하세요."
              action={
                <Button variant="outline" size="sm" onClick={() => setActiveTab('templates')}>
                  <Mail />
                  템플릿 보러 가기
                </Button>
              }
            />
          ) : (
            <div className="surface overflow-x-auto">
              <Table className="text-sm">
                <TableHeader>
                  <TableRow>
                    <TableHead className={thCls}>캠페인</TableHead>
                    <TableHead className={thCls}>상태</TableHead>
                    <TableHead className={`${thCls} text-right`}>발송</TableHead>
                    <TableHead className={`${thCls} text-right`}>오픈</TableHead>
                    <TableHead className={`${thCls} text-right`}>회신</TableHead>
                    <TableHead className={thCls}>시작일</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.map(campaign => (
                    <TableRow key={campaign.id} className="hover:bg-muted/40">
                      <TableCell className="py-2.5">
                        <div>
                          <p className="font-medium">{campaign.name}</p>
                          <p className="text-xs text-muted-foreground">{campaign.description}</p>
                        </div>
                      </TableCell>
                      <TableCell className="py-2.5">
                        <Pill tone={
                          campaign.status === 'active' ? 'ok' :
                          campaign.status === 'paused' ? 'warn' : 'muted'
                        }>
                          {campaign.status === 'active' && <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-success" />}
                          {campaign.status === 'active' ? '활성' :
                           campaign.status === 'paused' ? '일시정지' :
                           campaign.status === 'completed' ? '완료' : '초안'}
                        </Pill>
                      </TableCell>
                      <TableCell className="py-2.5 text-right tabular-nums font-medium">{campaign.total_sent}</TableCell>
                      <TableCell className="py-2.5 text-right tabular-nums font-medium">{campaign.total_opened}</TableCell>
                      <TableCell className="py-2.5 text-right tabular-nums font-medium">{campaign.total_replied}</TableCell>
                      <TableCell className="py-2.5 tabular-nums text-muted-foreground">
                        {campaign.started_at ? new Date(campaign.started_at).toLocaleDateString() : '-'}
                      </TableCell>
                      <TableCell className="py-2.5 text-right">
                        {campaign.status === 'active' ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handlePauseCampaign(campaign.id)}
                          >
                            <PauseCircle className="w-4 h-4" />
                          </Button>
                        ) : campaign.status !== 'completed' && (
                          <Button
                            size="sm"
                            variant="ghost"
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
            </div>
          )}
        </TabsContent>

        {/* Keywords Tab */}
        <TabsContent value="keywords" className="space-y-4 mt-6">
          <div className="flex justify-between items-center">
            <h3 className="section-title">검색 키워드</h3>
            <Dialog open={keywordDialogOpen} onOpenChange={setKeywordDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus />
                  키워드 추가
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>검색 키워드 추가</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <div>
                    <Label>키워드</Label>
                    <Input
                      value={newKeyword.keyword}
                      onChange={(e) => setNewKeyword({...newKeyword, keyword: e.target.value})}
                      placeholder="예: 성형외과, 피부과, 맛집"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>카테고리</Label>
                    <Select
                      value={newKeyword.category}
                      onValueChange={(v) => setNewKeyword({...newKeyword, category: v})}
                    >
                      <SelectTrigger className="mt-1">
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
                    <Button variant="outline" onClick={() => setKeywordDialogOpen(false)}>
                      취소
                    </Button>
                    <Button onClick={handleCreateKeyword}>
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
                className="group surface flex items-center justify-between px-4 py-3 transition-colors hover:bg-muted/40"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <Search className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{keyword.keyword}</p>
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {BLOG_CATEGORIES.find(c => c.value === keyword.category)?.label ? `${BLOG_CATEGORIES.find(c => c.value === keyword.category)?.label} · ` : ''}
                      수집 {keyword.total_collected}개
                      {keyword.last_collected_at && ` · ${new Date(keyword.last_collected_at).toLocaleDateString()}`}
                    </p>
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-danger transition-all"
                  onClick={() => handleDeleteKeyword(keyword.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            {keywords.length === 0 && (
              <EmptyState
                className="col-span-full"
                icon={<Search className="h-8 w-8" />}
                title="아직 키워드가 없습니다"
                description="스케줄러가 자동으로 블로그를 수집할 검색 키워드를 추가하세요."
                action={
                  <Button variant="outline" size="sm" onClick={() => setKeywordDialogOpen(true)}>
                    <Plus />
                    키워드 추가하기
                  </Button>
                }
              />
            )}
          </div>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-6 mt-6">
          {/* Sender Info */}
          <div className="surface p-5">
            <h3 className="section-title mb-4">발신자 정보</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>발신자 이름</Label>
                <Input
                  value={settings?.sender_name || ''}
                  onChange={(e) => setSettings(s => s ? {...s, sender_name: e.target.value} : null)}
                  placeholder="홍길동"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>발신자 이메일</Label>
                <Input
                  type="email"
                  value={settings?.sender_email || ''}
                  onChange={(e) => setSettings(s => s ? {...s, sender_email: e.target.value} : null)}
                  placeholder="example@company.com"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>회사명</Label>
                <Input
                  value={settings?.company_name || ''}
                  onChange={(e) => setSettings(s => s ? {...s, company_name: e.target.value} : null)}
                  placeholder="회사명"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>서비스명</Label>
                <Input
                  value={settings?.service_name || ''}
                  onChange={(e) => setSettings(s => s ? {...s, service_name: e.target.value} : null)}
                  placeholder="서비스명"
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* SMTP Settings */}
          <div className="surface p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="section-title">SMTP 설정</h3>
              <a
                href="/dashboard/outreach/smtp-guide"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                <HelpCircle className="h-4 w-4" />
                설정 가이드 보기
              </a>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>SMTP 호스트</Label>
                <Input
                  value={settings?.smtp_host || ''}
                  onChange={(e) => setSettings(s => s ? {...s, smtp_host: e.target.value} : null)}
                  placeholder="smtp.gmail.com"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>포트</Label>
                <Input
                  type="number"
                  value={settings?.smtp_port || 587}
                  onChange={(e) => setSettings(s => s ? {...s, smtp_port: parseInt(e.target.value)} : null)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label>사용자명</Label>
                <Input
                  value={settings?.smtp_username || ''}
                  onChange={(e) => setSettings(s => s ? {...s, smtp_username: e.target.value} : null)}
                  placeholder="이메일 주소"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>비밀번호</Label>
                <Input
                  type="password"
                  placeholder={settings?.smtp_configured ? '●●●●●●●●' : '앱 비밀번호'}
                  className="mt-1"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 mt-4 pt-4 border-t">
              <Switch checked={settings?.smtp_use_tls || false} />
              <Label>TLS 암호화 사용</Label>
            </div>
          </div>

          {/* Naver API Settings */}
          <div className="surface p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="section-title">네이버 검색 API</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  블로그 수집에 사용되는 네이버 Open API 설정
                </p>
              </div>
              {settings?.naver_api_configured ? (
                <Pill tone="ok">
                  <CheckCircle2 className="mr-1 inline h-3 w-3" />
                  설정됨
                </Pill>
              ) : (
                <Pill tone="muted">미설정</Pill>
              )}
            </div>
            <div className="rounded-lg border bg-muted/40 p-4 mb-4">
              <p className="text-sm font-medium">네이버 Open API 키 발급 방법</p>
              <ol className="text-sm text-muted-foreground mt-2 space-y-1 list-decimal list-inside">
                <li><a href="https://developers.naver.com" target="_blank" rel="noopener noreferrer" className="text-primary underline">developers.naver.com</a> 접속</li>
                <li>애플리케이션 등록 → 검색 API 선택</li>
                <li>Client ID와 Client Secret 복사</li>
              </ol>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Client ID</Label>
                <Input
                  value={settings?.naver_client_id || ''}
                  onChange={(e) => setSettings(s => s ? {...s, naver_client_id: e.target.value} : null)}
                  placeholder="네이버 API Client ID"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Client Secret</Label>
                <Input
                  type="password"
                  placeholder={settings?.naver_api_configured ? '●●●●●●●●' : 'Client Secret'}
                  onChange={(e) => setSettings(s => s ? {...s, naver_client_secret: e.target.value} : null)}
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* Sending Limits */}
          <div className="surface p-5">
            <h3 className="section-title mb-4">발송 제한</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>일일 발송 한도</Label>
                <Input
                  type="number"
                  value={settings?.daily_limit || 50}
                  onChange={(e) => setSettings(s => s ? {...s, daily_limit: parseInt(e.target.value)} : null)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label>시간당 발송 한도</Label>
                <Input
                  type="number"
                  value={settings?.hourly_limit || 10}
                  onChange={(e) => setSettings(s => s ? {...s, hourly_limit: parseInt(e.target.value)} : null)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label>최소 발송 간격 (초)</Label>
                <Input
                  type="number"
                  value={settings?.min_interval_seconds || 300}
                  onChange={(e) => setSettings(s => s ? {...s, min_interval_seconds: parseInt(e.target.value)} : null)}
                  className="mt-1"
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
            >
              설정 저장
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      {/* Template Edit Dialog */}
      <Dialog open={!!editingTemplate} onOpenChange={(open) => !open && setEditingTemplate(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>템플릿 수정</DialogTitle>
          </DialogHeader>
          {editingTemplate && (
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>템플릿 이름</Label>
                  <Input
                    value={editingTemplate.name}
                    onChange={(e) => setEditingTemplate({...editingTemplate, name: e.target.value})}
                    placeholder="예: 협찬 제안 초기 연락"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>유형</Label>
                  <Select
                    value={editingTemplate.template_type}
                    onValueChange={(v) => setEditingTemplate({...editingTemplate, template_type: v})}
                  >
                    <SelectTrigger className="mt-1">
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
                <Label>설명</Label>
                <Input
                  value={editingTemplate.description || ''}
                  onChange={(e) => setEditingTemplate({...editingTemplate, description: e.target.value})}
                  placeholder="템플릿 설명 (선택)"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>제목</Label>
                <Input
                  value={editingTemplate.subject}
                  onChange={(e) => setEditingTemplate({...editingTemplate, subject: e.target.value})}
                  placeholder="예: [협찬 제안] {{blog_name}}님께 드리는 특별한 제안"
                  className="mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  변수: {'{{blog_name}}'}, {'{{blog_nickname}}'}, {'{{sender_name}}'}, {'{{company_name}}'}
                </p>
              </div>
              <div>
                <Label>본문</Label>
                <Textarea
                  value={editingTemplate.body}
                  onChange={(e) => setEditingTemplate({...editingTemplate, body: e.target.value})}
                  placeholder="이메일 본문 내용..."
                  rows={8}
                  className="mt-1"
                />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingTemplate(null)}>
                  취소
                </Button>
                <Button onClick={handleUpdateTemplate}>
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
