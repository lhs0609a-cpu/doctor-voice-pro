'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
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
import { PLATFORM_LABELS, SENTIMENT_LABELS } from '@/types/reputation'
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
      case 'critical': return <Pill tone="danger">긴급</Pill>
      case 'warning': return <Pill tone="warn">주의</Pill>
      case 'positive': return <Pill tone="ok">긍정</Pill>
      default: return <Pill tone="muted">일반</Pill>
    }
  }

  const getSentimentIcon = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive': return <ThumbsUp className="h-4 w-4 text-success" />
      case 'negative': return <ThumbsDown className="h-4 w-4 text-danger" />
      case 'mixed': return <Minus className="h-4 w-4 text-warning" />
      default: return <Minus className="h-4 w-4 text-muted-foreground" />
    }
  }

  const totalPages = Math.ceil(total / limit)

  const STYLE_LABELS: Record<string, string> = {
    apologetic: '사과형',
    explanatory: '설명형',
    compensatory: '보상형',
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="멘션 관리"
        description="수집된 리뷰와 멘션을 확인하고 AI로 대응합니다."
        actions={
          <>
            {profiles.length > 1 && (
              <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
                <SelectTrigger className="h-9 w-[180px]">
                  <SelectValue placeholder="사업장 선택" />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map(p => (
                    <SelectItem key={p.id} value={p.id}>{p.business_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button variant="outline" size="sm" onClick={() => router.push('/dashboard/reputation')}>
              <ArrowLeft className="h-4 w-4" />
              평판 홈
            </Button>
          </>
        }
      />

      {/* 필터 */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex min-w-[200px] flex-1 items-center gap-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="멘션 내용 검색"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                className="h-9"
              />
            </div>

            <Select value={platformFilter} onValueChange={v => { setPlatformFilter(v); setPage(0) }}>
              <SelectTrigger className="h-9 w-[140px]">
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
              <SelectTrigger className="h-9 w-[120px]">
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
              <SelectTrigger className="h-9 w-[120px]">
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

            <Button size="sm" onClick={handleSearch}>
              <Filter className="h-4 w-4" />
              검색
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 결과 카운트 */}
      <div className="flex items-center justify-between">
        <p className="text-sm tabular-nums text-muted-foreground">총 {total}건</p>
      </div>

      {/* 멘션 목록 */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
        </div>
      ) : mentions.length === 0 ? (
        <EmptyState
          icon={<MessageSquare className="h-8 w-8" />}
          title="멘션이 없습니다"
          description="수집을 실행하거나 필터를 조정해 보세요."
          action={
            <Button variant="outline" size="sm" onClick={() => router.push('/dashboard/reputation')}>
              평판 홈으로 이동
            </Button>
          }
        />
      ) : (
        <div className="space-y-2">
          {mentions.map(mention => (
            <Card
              key={mention.id}
              className={`cursor-pointer transition-colors hover:bg-muted/40 ${
                mention.status === 'new' ? 'border-l-2 border-l-primary' : ''
              }`}
              onClick={() => openMentionDetail(mention.id)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex-shrink-0">
                    {getSentimentIcon(mention.sentiment)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Pill tone="muted">
                        {PLATFORM_LABELS[mention.platform as keyof typeof PLATFORM_LABELS] || mention.platform}
                      </Pill>
                      {getRiskBadge(mention.risk_level)}
                      {mention.rating && (
                        <span className="flex items-center gap-0.5 text-xs tabular-nums text-muted-foreground">
                          <Star className="h-3 w-3 fill-current text-warning" />
                          {mention.rating}
                        </span>
                      )}
                      {mention.status === 'new' && (
                        <Pill tone="accent">NEW</Pill>
                      )}
                      {mention.is_defamation && (
                        <Pill tone="danger">
                          <AlertTriangle className="mr-0.5 inline h-3 w-3" />
                          명예훼손
                        </Pill>
                      )}
                    </div>

                    {mention.title && (
                      <h3 className="mb-0.5 text-sm font-medium">{mention.title}</h3>
                    )}
                    <p className="line-clamp-2 text-sm text-foreground/80">{mention.content}</p>

                    <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{mention.author_name || '익명'}</span>
                      {mention.created_at && (
                        <span>{new Date(mention.created_at).toLocaleDateString('ko-KR')}</span>
                      )}
                      {mention.ai_summary && (
                        <span className="max-w-[200px] truncate text-primary">AI: {mention.ai_summary}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-shrink-0 flex-col items-center gap-1">
                    <button
                      onClick={e => { e.stopPropagation(); handleBookmark(mention.id, mention.is_bookmarked) }}
                      className="rounded-md p-1 transition-colors hover:bg-muted"
                    >
                      {mention.is_bookmarked
                        ? <BookmarkCheck className="h-4 w-4 text-primary" />
                        : <Bookmark className="h-4 w-4 text-muted-foreground/60" />
                      }
                    </button>
                    {mention.source_url && (
                      <a
                        href={mention.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="rounded-md p-1 transition-colors hover:bg-muted"
                      >
                        <ExternalLink className="h-4 w-4 text-muted-foreground" />
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
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground">
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
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
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
                  <h3 className="text-sm font-semibold">{selectedMention.title}</h3>
                )}

                <div className="whitespace-pre-wrap rounded-lg border bg-muted/40 p-4 text-sm">
                  {selectedMention.content}
                </div>

                {/* AI 분석 결과 */}
                {selectedMention.analyzed_at && (
                  <div className="space-y-2 rounded-lg bg-accent p-4">
                    <h4 className="flex items-center gap-1 text-sm font-medium text-primary">
                      <Sparkles className="h-4 w-4" />
                      AI 분석 결과
                    </h4>
                    {selectedMention.ai_summary && (
                      <p className="text-sm text-accent-foreground">{selectedMention.ai_summary}</p>
                    )}
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="rounded-md bg-card px-2 py-1">
                        감성: {SENTIMENT_LABELS[selectedMention.sentiment as keyof typeof SENTIMENT_LABELS] || '-'}
                      </span>
                      <span className="rounded-md bg-card px-2 py-1 tabular-nums">
                        위험도: {selectedMention.risk_score || 0}/100
                      </span>
                      <span className="rounded-md bg-card px-2 py-1 tabular-nums">
                        확산가능성: {Math.round(selectedMention.spread_potential || 0)}%
                      </span>
                      {selectedMention.is_defamation && (
                        <Pill tone="danger">명예훼손 가능성</Pill>
                      )}
                    </div>
                    {selectedMention.issues && selectedMention.issues.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {selectedMention.issues.map((issue, i) => (
                          <Pill key={i} tone="muted">{issue}</Pill>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* 별점 + 원문 */}
                <div className="flex items-center gap-4">
                  {selectedMention.rating && (
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map(i => (
                        <Star
                          key={i}
                          className={`h-4 w-4 ${i <= selectedMention.rating! ? 'fill-current text-warning' : 'text-muted-foreground/30'}`}
                        />
                      ))}
                      <span className="ml-1 text-sm tabular-nums">{selectedMention.rating}</span>
                    </div>
                  )}
                  {selectedMention.source_url && (
                    <a
                      href={selectedMention.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <ExternalLink className="h-3 w-3" />
                      원문 보기
                    </a>
                  )}
                </div>

                {/* AI 대응 답변 */}
                <div className="border-t pt-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-medium">AI 대응 답변</h4>
                    <Button
                      size="sm"
                      onClick={handleGenerateResponse}
                      disabled={isGenerating}
                    >
                      {isGenerating
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <Sparkles className="h-4 w-4" />
                      }
                      {generatedResponses.length > 0 ? '다시 생성' : 'AI 답변 생성'}
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
                          <div className="relative whitespace-pre-wrap rounded-lg border bg-muted/40 p-4 pr-12 text-sm">
                            {resp.content}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="absolute right-2 top-2"
                              onClick={() => handleCopy(resp.content, resp.id)}
                            >
                              {copiedId === resp.id
                                ? <Check className="h-4 w-4 text-success" />
                                : <Copy className="h-4 w-4" />
                              }
                            </Button>
                          </div>
                        </TabsContent>
                      ))}
                    </Tabs>
                  ) : (
                    <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                      AI 답변 생성을 누르면<br />
                      사과형/설명형/보상형 3가지 답변이 생성됩니다.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
