'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import {
  MessageCircleQuestion,
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
  Award,
  Trash2,
  Edit,
  Copy
} from 'lucide-react'
import {
  knowledgeAPI,
  KnowledgeKeyword,
  KnowledgeQuestion,
  KnowledgeAnswer,
  KnowledgeTemplate,
  KnowledgeDashboard,
  QuestionStatus,
  AnswerStatus,
  AnswerTone
} from '@/lib/api'
import { toast } from 'sonner'

const TONE_OPTIONS = [
  { value: 'professional', label: '전문적' },
  { value: 'friendly', label: '친근한' },
  { value: 'empathetic', label: '공감하는' },
  { value: 'formal', label: '격식있는' },
]

const CATEGORY_OPTIONS = [
  { value: '의료', label: '의료/건강' },
  { value: '뷰티', label: '뷰티/미용' },
  { value: '피부과', label: '피부과' },
  { value: '성형외과', label: '성형외과' },
  { value: '치과', label: '치과' },
  { value: '한의원', label: '한의원' },
]

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [isLoading, setIsLoading] = useState(true)

  // Data states
  const [dashboard, setDashboard] = useState<KnowledgeDashboard | null>(null)
  const [keywords, setKeywords] = useState<KnowledgeKeyword[]>([])
  const [questions, setQuestions] = useState<KnowledgeQuestion[]>([])
  const [answers, setAnswers] = useState<KnowledgeAnswer[]>([])
  const [templates, setTemplates] = useState<KnowledgeTemplate[]>([])
  const [topQuestions, setTopQuestions] = useState<KnowledgeQuestion[]>([])

  // UI states
  const [isCollecting, setIsCollecting] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedQuestion, setSelectedQuestion] = useState<KnowledgeQuestion | null>(null)
  const [selectedAnswer, setSelectedAnswer] = useState<KnowledgeAnswer | null>(null)

  // Dialog states
  const [isKeywordDialogOpen, setIsKeywordDialogOpen] = useState(false)
  const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false)
  const [isAnswerDialogOpen, setIsAnswerDialogOpen] = useState(false)

  // Form states
  const [newKeyword, setNewKeyword] = useState({ keyword: '', category: '', priority: 1 })
  const [newTemplate, setNewTemplate] = useState({ name: '', template_content: '', category: '', tone: 'professional' as AnswerTone })
  const [answerSettings, setAnswerSettings] = useState({
    tone: 'professional' as AnswerTone,
    include_promotion: true,
    blog_link: '',
    place_link: ''
  })

  // Filters
  const [questionFilter, setQuestionFilter] = useState<QuestionStatus | ''>('')
  const [answerFilter, setAnswerFilter] = useState<AnswerStatus | ''>('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [dashboardData, keywordsData, topQuestionsData] = await Promise.all([
        knowledgeAPI.getDashboard(),
        knowledgeAPI.getKeywords(),
        knowledgeAPI.getTopQuestions(5)
      ])
      setDashboard(dashboardData)
      setKeywords(keywordsData)
      setTopQuestions(topQuestionsData)
    } catch (error) {
      console.error('Failed to load data:', error)
      toast.error('데이터 로딩 실패')
    } finally {
      setIsLoading(false)
    }
  }

  const loadQuestions = async () => {
    try {
      const data = await knowledgeAPI.getQuestions({
        status: questionFilter || undefined,
        limit: 50
      })
      setQuestions(data)
    } catch (error) {
      toast.error('질문 로딩 실패')
    }
  }

  const loadAnswers = async () => {
    try {
      const data = await knowledgeAPI.getAnswers({
        status: answerFilter || undefined,
        limit: 50
      })
      setAnswers(data)
    } catch (error) {
      toast.error('답변 로딩 실패')
    }
  }

  const loadTemplates = async () => {
    try {
      const data = await knowledgeAPI.getTemplates()
      setTemplates(data)
    } catch (error) {
      toast.error('템플릿 로딩 실패')
    }
  }

  useEffect(() => {
    if (activeTab === 'questions') loadQuestions()
    if (activeTab === 'answers') loadAnswers()
    if (activeTab === 'templates') loadTemplates()
  }, [activeTab, questionFilter, answerFilter])

  // 질문 수집
  const handleCollect = async () => {
    setIsCollecting(true)
    try {
      const result = await knowledgeAPI.collectQuestions()
      toast.success(result.message)
      loadData()
      if (activeTab === 'questions') loadQuestions()
    } catch (error) {
      toast.error('질문 수집 실패')
    } finally {
      setIsCollecting(false)
    }
  }

  // 답변 생성
  const handleGenerateAnswer = async (questionId: string) => {
    setIsGenerating(true)
    try {
      const answer = await knowledgeAPI.generateAnswer({
        question_id: questionId,
        tone: answerSettings.tone,
        include_promotion: answerSettings.include_promotion,
        blog_link: answerSettings.blog_link || undefined,
        place_link: answerSettings.place_link || undefined
      })
      toast.success('답변이 생성되었습니다')
      setSelectedAnswer(answer)
      setIsAnswerDialogOpen(true)
      loadQuestions()
    } catch (error) {
      toast.error('답변 생성 실패')
    } finally {
      setIsGenerating(false)
    }
  }

  // 키워드 추가
  const handleAddKeyword = async () => {
    if (!newKeyword.keyword) {
      toast.error('키워드를 입력해주세요')
      return
    }
    try {
      await knowledgeAPI.createKeyword({
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
      await knowledgeAPI.deleteKeyword(keywordId)
      toast.success('키워드가 삭제되었습니다')
      loadData()
    } catch (error) {
      toast.error('키워드 삭제 실패')
    }
  }

  // 답변 승인
  const handleApproveAnswer = async (answerId: string) => {
    try {
      await knowledgeAPI.approveAnswer(answerId)
      toast.success('답변이 승인되었습니다')
      loadAnswers()
    } catch (error) {
      toast.error('승인 실패')
    }
  }

  // 답변 등록 완료
  const handleMarkPosted = async (answerId: string) => {
    try {
      await knowledgeAPI.markAsPosted(answerId)
      toast.success('등록 완료 처리되었습니다')
      loadAnswers()
      loadData()
    } catch (error) {
      toast.error('처리 실패')
    }
  }

  // 템플릿 추가
  const handleAddTemplate = async () => {
    if (!newTemplate.name || !newTemplate.template_content) {
      toast.error('이름과 내용을 입력해주세요')
      return
    }
    try {
      await knowledgeAPI.createTemplate({
        name: newTemplate.name,
        template_content: newTemplate.template_content,
        category: newTemplate.category || undefined,
        tone: newTemplate.tone
      })
      toast.success('템플릿이 추가되었습니다')
      setIsTemplateDialogOpen(false)
      setNewTemplate({ name: '', template_content: '', category: '', tone: 'professional' })
      loadTemplates()
    } catch (error) {
      toast.error('템플릿 추가 실패')
    }
  }

  // 클립보드 복사
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('클립보드에 복사되었습니다')
  }

  const getStatusBadge = (status: QuestionStatus | AnswerStatus) => {
    const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      new: { label: '신규', variant: 'default' },
      reviewing: { label: '검토중', variant: 'secondary' },
      answered: { label: '답변완료', variant: 'outline' },
      skipped: { label: '건너뜀', variant: 'destructive' },
      draft: { label: '초안', variant: 'secondary' },
      approved: { label: '승인됨', variant: 'default' },
      posted: { label: '등록됨', variant: 'outline' },
      rejected: { label: '반려됨', variant: 'destructive' },
    }
    const config = statusConfig[status] || { label: status, variant: 'secondary' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
  }

  const getUrgencyBadge = (urgency: string) => {
    if (urgency === 'high') return <Badge variant="destructive">긴급</Badge>
    if (urgency === 'medium') return <Badge variant="secondary">보통</Badge>
    return <Badge variant="outline">낮음</Badge>
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
        <DashboardNav />
        <main className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <DashboardNav />

      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <MessageCircleQuestion className="h-8 w-8 text-green-600" />
              지식인 답변 도우미
            </h1>
            <p className="text-gray-600 mt-1">
              네이버 지식인 질문을 모니터링하고 AI로 답변을 생성하세요
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
              질문 수집
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">오늘 수집</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {dashboard?.today_collected || 0}
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
                  <p className="text-sm font-medium text-gray-500">답변 대기</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {dashboard?.pending_questions || 0}
                  </p>
                </div>
                <Clock className="h-8 w-8 text-orange-200" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">초안 답변</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {dashboard?.draft_answers || 0}
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
                  <p className="text-sm font-medium text-gray-500">이번 주 답변</p>
                  <p className="text-2xl font-bold text-green-600">
                    {dashboard?.week_answered || 0}
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
            <TabsTrigger value="questions">질문 모니터링</TabsTrigger>
            <TabsTrigger value="answers">답변 관리</TabsTrigger>
            <TabsTrigger value="templates">템플릿</TabsTrigger>
            <TabsTrigger value="settings">설정</TabsTrigger>
          </TabsList>

          {/* 개요 탭 */}
          <TabsContent value="overview">
            <div className="grid md:grid-cols-2 gap-6">
              {/* 모니터링 키워드 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Search className="h-5 w-5" />
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
                              placeholder="예: 보톡스 효과"
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
                              {kw.question_count}개 발견
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

              {/* 추천 질문 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Star className="h-5 w-5 text-yellow-500" />
                    고관련성 질문 TOP 5
                  </CardTitle>
                  <CardDescription>
                    답변하면 효과적인 질문들입니다
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {topQuestions.length === 0 ? (
                    <p className="text-center text-gray-500 py-8">
                      수집된 질문이 없습니다
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {topQuestions.map((q) => (
                        <div
                          key={q.id}
                          className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer"
                          onClick={() => {
                            setSelectedQuestion(q)
                            setActiveTab('questions')
                          }}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm truncate">{q.title}</p>
                              <div className="flex items-center gap-2 mt-1">
                                <Badge variant="outline" className="text-xs">
                                  관련성 {q.relevance_score}%
                                </Badge>
                                {q.reward_points > 0 && (
                                  <Badge variant="secondary" className="text-xs">
                                    내공 {q.reward_points}
                                  </Badge>
                                )}
                                {getUrgencyBadge(q.urgency)}
                              </div>
                            </div>
                            <Button
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleGenerateAnswer(q.id)
                              }}
                              disabled={isGenerating}
                            >
                              <Sparkles className="h-3 w-3 mr-1" />
                              답변
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* 질문 모니터링 탭 */}
          <TabsContent value="questions">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>수집된 질문</CardTitle>
                  <Select
                    value={questionFilter}
                    onValueChange={(v) => setQuestionFilter(v as QuestionStatus | '')}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="상태 필터" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">전체</SelectItem>
                      <SelectItem value="new">신규</SelectItem>
                      <SelectItem value="reviewing">검토중</SelectItem>
                      <SelectItem value="answered">답변완료</SelectItem>
                      <SelectItem value="skipped">건너뜀</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {questions.length === 0 ? (
                  <div className="text-center py-12">
                    <MessageCircleQuestion className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">수집된 질문이 없습니다</p>
                    <Button className="mt-4" onClick={handleCollect} disabled={isCollecting}>
                      질문 수집하기
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {questions.map((q) => (
                      <div
                        key={q.id}
                        className="p-4 border rounded-lg hover:border-blue-300 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {getStatusBadge(q.status)}
                              {getUrgencyBadge(q.urgency)}
                              <Badge variant="outline">관련성 {q.relevance_score}%</Badge>
                              {q.reward_points > 0 && (
                                <Badge variant="secondary">내공 {q.reward_points}</Badge>
                              )}
                            </div>
                            <h3 className="font-semibold mb-1">{q.title}</h3>
                            {q.content && (
                              <p className="text-sm text-gray-600 line-clamp-2">{q.content}</p>
                            )}
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span>조회 {q.view_count}</span>
                              <span>답변 {q.answer_count}개</span>
                              {q.matched_keywords && q.matched_keywords.length > 0 && (
                                <span>키워드: {q.matched_keywords.join(', ')}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col gap-2">
                            {q.url && (
                              <Button variant="outline" size="sm" asChild>
                                <a href={q.url} target="_blank" rel="noopener noreferrer">
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              </Button>
                            )}
                            <Button
                              size="sm"
                              onClick={() => handleGenerateAnswer(q.id)}
                              disabled={isGenerating || q.status === 'answered'}
                            >
                              {isGenerating ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <Sparkles className="h-4 w-4 mr-1" />
                                  답변 생성
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

          {/* 답변 관리 탭 */}
          <TabsContent value="answers">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>생성된 답변</CardTitle>
                  <Select
                    value={answerFilter}
                    onValueChange={(v) => setAnswerFilter(v as AnswerStatus | '')}
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
                {answers.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">생성된 답변이 없습니다</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {answers.map((answer) => (
                      <div
                        key={answer.id}
                        className="p-4 border rounded-lg"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {getStatusBadge(answer.status)}
                              {answer.quality_score && (
                                <Badge variant="outline">
                                  품질 {answer.quality_score.toFixed(0)}점
                                </Badge>
                              )}
                              {answer.is_chosen && (
                                <Badge className="bg-yellow-100 text-yellow-800">
                                  <Award className="h-3 w-3 mr-1" />
                                  채택됨
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-4">
                              {answer.final_content || answer.content}
                            </p>
                            {answer.blog_link && (
                              <p className="text-xs text-blue-600 mt-2">
                                블로그: {answer.blog_link}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => copyToClipboard(answer.final_content || answer.content)}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                            {answer.status === 'draft' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => handleApproveAnswer(answer.id)}
                                >
                                  <CheckCircle className="h-4 w-4" />
                                </Button>
                              </>
                            )}
                            {answer.status === 'approved' && (
                              <Button
                                size="sm"
                                onClick={() => handleMarkPosted(answer.id)}
                              >
                                등록완료
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

          {/* 템플릿 탭 */}
          <TabsContent value="templates">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>답변 템플릿</CardTitle>
                  <Dialog open={isTemplateDialogOpen} onOpenChange={setIsTemplateDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        템플릿 추가
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                      <DialogHeader>
                        <DialogTitle>템플릿 추가</DialogTitle>
                        <DialogDescription>
                          자주 사용하는 답변 형식을 템플릿으로 저장하세요
                        </DialogDescription>
                      </DialogHeader>
                      <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                          <Label>템플릿 이름</Label>
                          <Input
                            placeholder="예: 시술 문의 기본 답변"
                            value={newTemplate.name}
                            onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="grid gap-2">
                            <Label>카테고리</Label>
                            <Select
                              value={newTemplate.category}
                              onValueChange={(v) => setNewTemplate({ ...newTemplate, category: v })}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="선택" />
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
                            <Label>답변 톤</Label>
                            <Select
                              value={newTemplate.tone}
                              onValueChange={(v) => setNewTemplate({ ...newTemplate, tone: v as AnswerTone })}
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
                        </div>
                        <div className="grid gap-2">
                          <Label>템플릿 내용</Label>
                          <Textarea
                            placeholder="답변 템플릿을 작성하세요. {병원명}, {시술명} 등의 변수를 사용할 수 있습니다."
                            rows={8}
                            value={newTemplate.template_content}
                            onChange={(e) => setNewTemplate({ ...newTemplate, template_content: e.target.value })}
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setIsTemplateDialogOpen(false)}>
                          취소
                        </Button>
                        <Button onClick={handleAddTemplate}>저장</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                {templates.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">등록된 템플릿이 없습니다</p>
                  </div>
                ) : (
                  <div className="grid md:grid-cols-2 gap-4">
                    {templates.map((template) => (
                      <div
                        key={template.id}
                        className="p-4 border rounded-lg"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h3 className="font-semibold">{template.name}</h3>
                            <div className="flex items-center gap-2 mt-1">
                              {template.category && (
                                <Badge variant="secondary">{template.category}</Badge>
                              )}
                              <Badge variant="outline">
                                {TONE_OPTIONS.find((t) => t.value === template.tone)?.label}
                              </Badge>
                              <span className="text-xs text-gray-500">
                                {template.usage_count}회 사용
                              </span>
                            </div>
                          </div>
                        </div>
                        <p className="text-sm text-gray-600 line-clamp-3">
                          {template.template_content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 설정 탭 */}
          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  답변 생성 설정
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h3 className="font-semibold">기본 답변 스타일</h3>
                    <div className="grid gap-4">
                      <div className="grid gap-2">
                        <Label>답변 톤</Label>
                        <Select
                          value={answerSettings.tone}
                          onValueChange={(v) => setAnswerSettings({ ...answerSettings, tone: v as AnswerTone })}
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
                          checked={answerSettings.include_promotion}
                          onCheckedChange={(v) => setAnswerSettings({ ...answerSettings, include_promotion: v })}
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
                          value={answerSettings.blog_link}
                          onChange={(e) => setAnswerSettings({ ...answerSettings, blog_link: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>플레이스 링크</Label>
                        <Input
                          placeholder="https://place.naver.com/..."
                          value={answerSettings.place_link}
                          onChange={(e) => setAnswerSettings({ ...answerSettings, place_link: e.target.value })}
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

      {/* 답변 확인 다이얼로그 */}
      <Dialog open={isAnswerDialogOpen} onOpenChange={setIsAnswerDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>생성된 답변</DialogTitle>
          </DialogHeader>
          {selectedAnswer && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                {selectedAnswer.quality_score && (
                  <Badge variant="outline">
                    품질 점수: {selectedAnswer.quality_score.toFixed(0)}
                  </Badge>
                )}
                <Badge variant="secondary">
                  {TONE_OPTIONS.find((t) => t.value === selectedAnswer.tone)?.label}
                </Badge>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="whitespace-pre-wrap text-sm">
                  {selectedAnswer.content}
                </p>
              </div>
              {selectedAnswer.promotion_text && (
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm text-blue-800">{selectedAnswer.promotion_text}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => selectedAnswer && copyToClipboard(selectedAnswer.content)}
            >
              <Copy className="h-4 w-4 mr-2" />
              복사
            </Button>
            <Button
              onClick={() => {
                if (selectedAnswer) handleApproveAnswer(selectedAnswer.id)
                setIsAnswerDialogOpen(false)
              }}
            >
              승인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
