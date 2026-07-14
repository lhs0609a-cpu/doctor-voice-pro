'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ArrowLeft,
  Search,
  Loader2,
  Star,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  MessageSquare,
  Sparkles,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Minus,
  AlertTriangle,
  Filter,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { reputationAPI } from '@/lib/api'
import type { MonitorProfile, Mention, GeneratedResponse } from '@/types/reputation'
import { PLATFORM_LABELS, SENTIMENT_LABELS, RISK_LABELS, STATUS_LABELS } from '@/types/reputation'
import { toast } from 'sonner'


export default function MentionsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [isLoading, setIsLoading] = useState(true)
  const [profiles, setProfiles] = useState<MonitorProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [mentions, setMentions] = useState<Mention[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const limit = 20

  // Filters
  const [platformFilter, setPlatformFilter] = useState<string>('all')
  const [sentimentFilter, setSentimentFilter] = useState<string>('all')
  const [riskFilter, setRiskFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Detail view
  const [selectedMention, setSelectedMention] = useState<Mention | null>(null)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedResponses, setGeneratedResponses] = useState<GeneratedResponse[]>([])
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    loadProfiles()
  }, [])

  useEffect(() => {
    if (selectedProfileId) {
      loadMentions()
    }
  }, [selectedProfileId, platformFilter, sentimentFilter, riskFilter, page])

  // URL에서 mention ID가 있으면 상세 열기
  useEffect(() => {
    const mentionId = searchParams.get('id')
    if (mentionId && selectedProfileId) {
      openMentionDetail(mentionId)
    }
  }, [searchParams, selectedProfileId])

  const loadProfiles = async () => {
    try {
      const data = await reputationAPI.getProfiles()
      setProfiles(data)
      if (data.length > 0) {
        setSelectedProfileId(data[0].id)
      }
    } catch (error) {
      console.error('프로필 로드 실패:', error)
      setIsLoading(false)
    }
  }

  const loadMentions = async () => {
    setIsLoading(true)
    try {
      const params: any = {
        profile_id: selectedProfileId,
        skip: page * limit,
        limit,
      }
      if (platformFilter !== 'all') params.platform = platformFilter
      if (sentimentFilter !== 'all') params.sentiment = sentimentFilter
      if (riskFilter !== 'all') params.risk_level = riskFilter
      if (searchQuery) params.search = searchQuery

      const data = await reputationAPI.getMentions(params)
      setMentions(data.mentions)
      setTotal(data.total)
    } catch (error) {
      console.error('멘션 로드 실패:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const openMentionDetail = async (mentionId: string) => {
    try {
      const data = await reputationAPI.getMention(mentionId)
      setSelectedMention(data)
      setGeneratedResponses(data.responses || [])
      setIsDetailOpen(true)

      // 읽음 처리
      if (data.status === 'new') {
        await reputationAPI.updateMention(mentionId, { status: 'read' })
      }
    } catch (error) {
      toast.error('멘션 상세 로드에 실패했습니다.')
    }
  }

  const handleBookmark = async (mentionId: string, current: boolean) => {
    try {
      await reputationAPI.updateMention(mentionId, { is_bookmarked: !current })
      setMentions(prev =>
        prev.map(m => m.id === mentionId ? { ...m, is_bookmarked: !current } : m)
      )
      if (selectedMention?.id === mentionId) {
        setSelectedMention(prev => prev ? { ...prev, is_bookmarked: !current } : prev)
      }
    } catch (error) {
      toast.error('북마크 처리에 실패했습니다.')
    }
  }

  const handleGenerateResponse = async () => {
    if (!selectedMention) return
    setIsGenerating(true)
    try {
      const result = await reputationAPI.generateResponse(selectedMention.id)
      setGeneratedResponses(result.responses)
      toast.success('AI 대응 답변이 생성되었습니다.')
    } catch (error) {
      toast.error('답변 생성에 실패했습니다.')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    toast.success('클립보드에 복사되었습니다.')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleSearch = () => {
    setPage(0)
    loadMentions()
  }

  const getRiskBadge = (level: string | null) => {
    switch (level) {
      case 'critical': return <Badge variant="destructive" className="text-xs">긴급</Badge>
      case 'warning': return <Badge className="text-xs bg-yellow-500">주의</Badge>
      case 'positive': return <Badge className="text-xs bg-green-500">긍정</Badge>
      default: return <Badge variant="secondary" className="text-xs">일반</Badge>
    }
  }

  const getSentimentIcon = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive': return <ThumbsUp className="h-4 w-4 text-green-500" />
      case 'negative': return <ThumbsDown className="h-4 w-4 text-red-500" />
      case 'mixed': return <Minus className="h-4 w-4 text-yellow-500" />
      default: return <Minus className="h-4 w-4 text-gray-400" />
    }
  }

  const totalPages = Math.ceil(total / limit)

  const STYLE_LABELS: Record<string, string> = {
    apologetic: '사과형',
    explanatory: '설명형',
    compensatory: '보상형',
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardNav />
      <main className="container mx-auto px-4 py-6">
        {/* 헤더 */}
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" onClick={() => router.push('/dashboard/reputation')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="h-6 w-6 text-blue-600" />
              멘션 관리
            </h1>
            <p className="text-sm text-gray-500 mt-1">수집된 리뷰/멘션 확인 및 AI 대응</p>
          </div>

          {profiles.length > 1 && (
            <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="사업장 선택" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.business_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* 필터 */}
        <Card className="mb-4">
          <CardContent className="pt-4 pb-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                <Search className="h-4 w-4 text-gray-400" />
                <Input
                  placeholder="멘션 내용 검색..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  className="h-9"
                />
              </div>

              <Select value={platformFilter} onValueChange={v => { setPlatformFilter(v); setPage(0) }}>
                <SelectTrigger className="w-[140px] h-9">
                  <SelectValue placeholder="플랫폼" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 플랫폼</SelectItem>
                  <SelectItem value="naver_place">네이버 플레이스</SelectItem>
                  <SelectItem value="google_maps">구글 지도</SelectItem>
                  <SelectItem value="kakao_map">카카오맵</SelectItem>
                  <SelectItem value="naver_blog">네이버 블로그</SelectItem>
                  <SelectItem value="naver_cafe">네이버 카페</SelectItem>
                  <SelectItem value="dcinside">DC인사이드</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sentimentFilter} onValueChange={v => { setSentimentFilter(v); setPage(0) }}>
                <SelectTrigger className="w-[120px] h-9">
                  <SelectValue placeholder="감성" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 감성</SelectItem>
                  <SelectItem value="positive">긍정</SelectItem>
                  <SelectItem value="neutral">중립</SelectItem>
                  <SelectItem value="negative">부정</SelectItem>
                  <SelectItem value="mixed">혼합</SelectItem>
                </SelectContent>
              </Select>

              <Select value={riskFilter} onValueChange={v => { setRiskFilter(v); setPage(0) }}>
                <SelectTrigger className="w-[120px] h-9">
                  <SelectValue placeholder="위험도" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 위험도</SelectItem>
                  <SelectItem value="critical">긴급</SelectItem>
                  <SelectItem value="warning">주의</SelectItem>
                  <SelectItem value="normal">일반</SelectItem>
                  <SelectItem value="positive">긍정</SelectItem>
                </SelectContent>
              </Select>

              <Button size="sm" variant="outline" onClick={handleSearch}>
                <Filter className="h-4 w-4 mr-1" />
                검색
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 결과 카운트 */}
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-gray-500">총 {total}건</p>
        </div>

        {/* 멘션 목록 */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        ) : mentions.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <MessageSquare className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">멘션이 없습니다.</p>
              <p className="text-xs text-gray-400 mt-1">크롤링을 실행하거나 필터를 조정해보세요.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {mentions.map(mention => (
              <Card
                key={mention.id}
                className={`cursor-pointer hover:shadow-sm transition-shadow ${
                  mention.status === 'new' ? 'border-l-4 border-l-blue-500' : ''
                }`}
                onClick={() => openMentionDetail(mention.id)}
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {getSentimentIcon(mention.sentiment)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <Badge variant="outline" className="text-xs">
                          {PLATFORM_LABELS[mention.platform as keyof typeof PLATFORM_LABELS] || mention.platform}
                        </Badge>
                        {getRiskBadge(mention.risk_level)}
                        {mention.rating && (
                          <span className="flex items-center gap-0.5 text-xs text-yellow-600">
                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                            {mention.rating}
                          </span>
                        )}
                        {mention.status === 'new' && (
                          <Badge className="text-xs bg-blue-500">NEW</Badge>
                        )}
                        {mention.is_defamation && (
                          <Badge variant="destructive" className="text-xs">
                            <AlertTriangle className="h-3 w-3 mr-0.5" />
                            명예훼손
                          </Badge>
                        )}
                      </div>

                      {mention.title && (
                        <h3 className="font-medium text-sm mb-0.5">{mention.title}</h3>
                      )}
                      <p className="text-sm text-gray-700 line-clamp-2">{mention.content}</p>

                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                        <span>{mention.author_name || '익명'}</span>
                        {mention.created_at && (
                          <span>{new Date(mention.created_at).toLocaleDateString('ko-KR')}</span>
                        )}
                        {mention.ai_summary && (
                          <span className="text-blue-500 truncate max-w-[200px]">AI: {mention.ai_summary}</span>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-center gap-1 flex-shrink-0">
                      <button
                        onClick={e => { e.stopPropagation(); handleBookmark(mention.id, mention.is_bookmarked) }}
                        className="p-1 hover:bg-gray-100 rounded"
                      >
                        {mention.is_bookmarked
                          ? <BookmarkCheck className="h-4 w-4 text-blue-500" />
                          : <Bookmark className="h-4 w-4 text-gray-300" />
                        }
                      </button>
                      {mention.source_url && (
                        <a
                          href={mention.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          <ExternalLink className="h-4 w-4 text-gray-400" />
                        </a>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-gray-500">
              {page + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* 멘션 상세 다이얼로그 */}
        <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            {selectedMention && (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    {getSentimentIcon(selectedMention.sentiment)}
                    멘션 상세
                    {getRiskBadge(selectedMention.risk_level)}
                  </DialogTitle>
                  <DialogDescription>
                    {PLATFORM_LABELS[selectedMention.platform as keyof typeof PLATFORM_LABELS]} |
                    {' '}{selectedMention.author_name || '익명'} |
                    {' '}{selectedMention.created_at ? new Date(selectedMention.created_at).toLocaleString('ko-KR') : ''}
                  </DialogDescription>
                </DialogHeader>

                {/* 본문 */}
                <div className="space-y-4">
                  {selectedMention.title && (
                    <h3 className="font-semibold">{selectedMention.title}</h3>
                  )}

                  <div className="bg-gray-50 rounded-lg p-4 text-sm whitespace-pre-wrap">
                    {selectedMention.content}
                  </div>

                  {/* AI 분석 결과 */}
                  {selectedMention.analyzed_at && (
                    <div className="bg-blue-50 rounded-lg p-4 space-y-2">
                      <h4 className="font-medium text-sm text-blue-800 flex items-center gap-1">
                        <Sparkles className="h-4 w-4" />
                        AI 분석 결과
                      </h4>
                      {selectedMention.ai_summary && (
                        <p className="text-sm text-blue-700">{selectedMention.ai_summary}</p>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="bg-white px-2 py-1 rounded">
                          감성: {SENTIMENT_LABELS[selectedMention.sentiment as keyof typeof SENTIMENT_LABELS] || '-'}
                        </span>
                        <span className="bg-white px-2 py-1 rounded">
                          위험도: {selectedMention.risk_score || 0}/100
                        </span>
                        <span className="bg-white px-2 py-1 rounded">
                          확산가능성: {Math.round(selectedMention.spread_potential || 0)}%
                        </span>
                        {selectedMention.is_defamation && (
                          <span className="bg-red-100 text-red-700 px-2 py-1 rounded">
                            명예훼손 가능성
                          </span>
                        )}
                      </div>
                      {selectedMention.issues && selectedMention.issues.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedMention.issues.map((issue, i) => (
                            <Badge key={i} variant="outline" className="text-xs">{issue}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 별점 + 이미지 */}
                  <div className="flex items-center gap-4">
                    {selectedMention.rating && (
                      <div className="flex items-center gap-1">
                        {[1, 2, 3, 4, 5].map(i => (
                          <Star
                            key={i}
                            className={`h-4 w-4 ${i <= selectedMention.rating! ? 'text-yellow-400 fill-yellow-400' : 'text-gray-200'}`}
                          />
                        ))}
                        <span className="text-sm ml-1">{selectedMention.rating}</span>
                      </div>
                    )}
                    {selectedMention.source_url && (
                      <a
                        href={selectedMention.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                      >
                        <ExternalLink className="h-3 w-3" />
                        원문 보기
                      </a>
                    )}
                  </div>

                  {/* AI 대응 답변 */}
                  <div className="border-t pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-medium">AI 대응 답변</h4>
                      <Button
                        size="sm"
                        onClick={handleGenerateResponse}
                        disabled={isGenerating}
                      >
                        {isGenerating
                          ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          : <Sparkles className="h-4 w-4 mr-1" />
                        }
                        {generatedResponses.length > 0 ? '재생성' : 'AI 답변 생성'}
                      </Button>
                    </div>

                    {generatedResponses.length > 0 ? (
                      <Tabs defaultValue={generatedResponses[0]?.style || 'apologetic'}>
                        <TabsList className="w-full">
                          {generatedResponses.map(resp => (
                            <TabsTrigger key={resp.style} value={resp.style} className="flex-1">
                              {STYLE_LABELS[resp.style] || resp.style}
                            </TabsTrigger>
                          ))}
                        </TabsList>
                        {generatedResponses.map(resp => (
                          <TabsContent key={resp.style} value={resp.style}>
                            <div className="bg-gray-50 rounded-lg p-4 text-sm whitespace-pre-wrap relative">
                              {resp.content}
                              <Button
                                variant="ghost"
                                size="sm"
                                className="absolute top-2 right-2"
                                onClick={() => handleCopy(resp.content, resp.id)}
                              >
                                {copiedId === resp.id
                                  ? <Check className="h-4 w-4 text-green-500" />
                                  : <Copy className="h-4 w-4" />
                                }
                              </Button>
                            </div>
                          </TabsContent>
                        ))}
                      </Tabs>
                    ) : (
                      <div className="text-center py-6 text-gray-400 text-sm">
                        AI 답변 생성 버튼을 클릭하면<br />
                        사과형/설명형/보상형 3가지 답변이 생성됩니다.
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  )
}
