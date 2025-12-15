'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import {
  MapPin,
  Star,
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Users,
  Search,
  Loader2,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Sparkles,
  Copy,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Trophy,
  Target,
  Calendar,
  QrCode,
  Gift,
  Eye
} from 'lucide-react'
import {
  placeAPI,
  reviewsAPI,
  competitorsAPI,
  rankingsAPI,
  campaignsAPI,
  NaverPlace,
  OptimizationCheck,
  PlaceReview,
  Competitor,
  PlaceKeyword,
  ReviewCampaign,
  ReviewAnalytics,
  RewardType
} from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'


export default function PlacePage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [isLoading, setIsLoading] = useState(true)
  const [places, setPlaces] = useState<NaverPlace[]>([])
  const [selectedPlace, setSelectedPlace] = useState<NaverPlace | null>(null)
  const [optimization, setOptimization] = useState<{ optimization_score: number; checks: OptimizationCheck[] } | null>(null)
  const [reviews, setReviews] = useState<PlaceReview[]>([])
  const [reviewAnalytics, setReviewAnalytics] = useState<ReviewAnalytics | null>(null)
  const [competitors, setCompetitors] = useState<Competitor[]>([])
  const [keywords, setKeywords] = useState<PlaceKeyword[]>([])
  const [campaigns, setCampaigns] = useState<ReviewCampaign[]>([])

  // Dialog states
  const [isConnectDialogOpen, setIsConnectDialogOpen] = useState(false)
  const [isReplyDialogOpen, setIsReplyDialogOpen] = useState(false)
  const [isKeywordDialogOpen, setIsKeywordDialogOpen] = useState(false)
  const [isCampaignDialogOpen, setIsCampaignDialogOpen] = useState(false)
  const [selectedReview, setSelectedReview] = useState<PlaceReview | null>(null)
  const [generatedReply, setGeneratedReply] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)

  // Form states
  const [connectForm, setConnectForm] = useState({ place_id: '', place_name: '', place_url: '' })
  const [keywordForm, setKeywordForm] = useState({ keyword: '', category: '' })
  const [campaignForm, setCampaignForm] = useState<{
    name: string
    reward_type: RewardType
    reward_description: string
    start_date: string
    end_date: string
    target_count: number
  }>({
    name: '',
    reward_type: 'discount',
    reward_description: '',
    start_date: '',
    end_date: '',
    target_count: 10,
  })

  useEffect(() => {
    loadPlaces()
  }, [])

  useEffect(() => {
    if (selectedPlace) {
      loadPlaceData()
    }
  }, [selectedPlace, activeTab])

  const loadPlaces = async () => {
    setIsLoading(true)
    try {
      const data = await placeAPI.getList()
      setPlaces(data || [])
      if (data && data.length > 0) {
        setSelectedPlace(data[0])
      }
    } catch (error) {
      console.error('Failed to load places:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadPlaceData = async () => {
    if (!selectedPlace) return

    try {
      switch (activeTab) {
        case 'overview':
          const opt = await placeAPI.getOptimization(selectedPlace.id)
          setOptimization(opt)
          break
        case 'reviews':
          const [reviewsData, analyticsData] = await Promise.all([
            reviewsAPI.getList(selectedPlace.id),
            reviewsAPI.getAnalytics(selectedPlace.id),
          ])
          setReviews(reviewsData || [])
          setReviewAnalytics(analyticsData)
          break
        case 'competitors':
          const comps = await competitorsAPI.getList()
          setCompetitors(comps || [])
          break
        case 'rankings':
          const kws = await rankingsAPI.getKeywords(selectedPlace.id)
          setKeywords(kws || [])
          break
        case 'campaigns':
          const camps = await campaignsAPI.getList(undefined, selectedPlace.id)
          setCampaigns(camps || [])
          break
      }
    } catch (error) {
      console.error('Failed to load place data:', error)
    }
  }

  const handleConnectPlace = async () => {
    if (!connectForm.place_id || !connectForm.place_name) {
      toast.error('플레이스 ID와 이름을 입력해주세요')
      return
    }

    try {
      await placeAPI.connect({
        place_id: connectForm.place_id,
        place_name: connectForm.place_name,
        place_url: connectForm.place_url || undefined,
      })
      toast.success('플레이스 연동 성공')
      setIsConnectDialogOpen(false)
      setConnectForm({ place_id: '', place_name: '', place_url: '' })
      loadPlaces()
    } catch (error: any) {
      toast.error('연동 실패', {
        description: error.response?.data?.detail || '플레이스 연동에 실패했습니다.',
      })
    }
  }

  const handleGenerateReply = async () => {
    if (!selectedReview) return

    setIsGenerating(true)
    try {
      const result = await reviewsAPI.generateReply(selectedReview.id, 'professional')
      setGeneratedReply(result.reply)
    } catch (error) {
      toast.error('AI 답변 생성 실패')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSubmitReply = async () => {
    if (!selectedReview || !generatedReply) return

    try {
      await reviewsAPI.reply(selectedReview.id, generatedReply)
      toast.success('답변이 등록되었습니다')
      setIsReplyDialogOpen(false)
      setSelectedReview(null)
      setGeneratedReply('')
      loadPlaceData()
    } catch (error) {
      toast.error('답변 등록 실패')
    }
  }

  const handleAddKeyword = async () => {
    if (!keywordForm.keyword || !selectedPlace) {
      toast.error('키워드를 입력해주세요')
      return
    }

    try {
      await rankingsAPI.addKeyword({
        place_db_id: selectedPlace.id,
        keyword: keywordForm.keyword,
        category: keywordForm.category || undefined,
      })
      toast.success('키워드가 추가되었습니다')
      setIsKeywordDialogOpen(false)
      setKeywordForm({ keyword: '', category: '' })
      loadPlaceData()
    } catch (error) {
      toast.error('키워드 추가 실패')
    }
  }

  const handleCreateCampaign = async () => {
    if (!campaignForm.name || !selectedPlace) {
      toast.error('캠페인 이름을 입력해주세요')
      return
    }

    try {
      await campaignsAPI.create({
        ...campaignForm,
        place_db_id: selectedPlace.id,
      })
      toast.success('캠페인이 생성되었습니다')
      setIsCampaignDialogOpen(false)
      setCampaignForm({
        name: '',
        reward_type: 'discount',
        reward_description: '',
        start_date: '',
        end_date: '',
        target_count: 10,
      })
      loadPlaceData()
    } catch (error) {
      toast.error('캠페인 생성 실패')
    }
  }

  const handleAutoDetectCompetitors = async () => {
    if (!selectedPlace) return

    try {
      const detected = await competitorsAPI.autoDetect(selectedPlace.id, 3, 10)
      toast.success(`${detected.length}개의 경쟁사가 탐지되었습니다`)
      loadPlaceData()
    } catch (error) {
      toast.error('경쟁사 탐지 실패')
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      case 'fail':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return null
    }
  }

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'positive':
        return <ThumbsUp className="h-4 w-4 text-green-500" />
      case 'negative':
        return <ThumbsDown className="h-4 w-4 text-red-500" />
      default:
        return <Minus className="h-4 w-4 text-gray-400" />
    }
  }

  const getTrendIcon = (trend: string, change: number) => {
    if (change > 0) {
      return <TrendingUp className="h-4 w-4 text-green-500" />
    } else if (change < 0) {
      return <TrendingDown className="h-4 w-4 text-red-500" />
    }
    return <Minus className="h-4 w-4 text-gray-400" />
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
              <MapPin className="h-8 w-8 text-green-600" />
              플레이스 관리
            </h1>
            <p className="text-gray-600 mt-1">
              네이버 플레이스를 통합 관리하고 최적화하세요
            </p>
          </div>

          <div className="flex gap-2">
            {selectedPlace && (
              <Select
                value={selectedPlace.id}
                onValueChange={(value) => {
                  const place = places.find((p) => p.id === value)
                  if (place) setSelectedPlace(place)
                }}
              >
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="플레이스 선택" />
                </SelectTrigger>
                <SelectContent>
                  {places.map((place) => (
                    <SelectItem key={place.id} value={place.id}>
                      {place.place_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Dialog open={isConnectDialogOpen} onOpenChange={setIsConnectDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  플레이스 연동
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>플레이스 연동</DialogTitle>
                  <DialogDescription>
                    네이버 플레이스 정보를 입력하여 연동하세요
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label>플레이스 ID *</Label>
                    <Input
                      placeholder="네이버 플레이스 ID"
                      value={connectForm.place_id}
                      onChange={(e) =>
                        setConnectForm({ ...connectForm, place_id: e.target.value })
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>병원명 *</Label>
                    <Input
                      placeholder="예: 서울피부과의원"
                      value={connectForm.place_name}
                      onChange={(e) =>
                        setConnectForm({ ...connectForm, place_name: e.target.value })
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>플레이스 URL (선택)</Label>
                    <Input
                      placeholder="https://map.naver.com/..."
                      value={connectForm.place_url}
                      onChange={(e) =>
                        setConnectForm({ ...connectForm, place_url: e.target.value })
                      }
                    />
                    <p className="text-xs text-gray-500">
                      네이버 지도에서 플레이스 페이지의 URL을 복사해 붙여넣으세요
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsConnectDialogOpen(false)}>
                    취소
                  </Button>
                  <Button onClick={handleConnectPlace}>연동하기</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {places.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <MapPin className="h-16 w-16 mx-auto text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                연동된 플레이스가 없습니다
              </h3>
              <p className="text-gray-500 mb-6">
                네이버 플레이스를 연동하여 리뷰 관리, 경쟁 분석, 순위 추적을 시작하세요
              </p>
              <Button onClick={() => setIsConnectDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                첫 플레이스 연동하기
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-6">
              <TabsTrigger value="overview">개요</TabsTrigger>
              <TabsTrigger value="reviews">리뷰</TabsTrigger>
              <TabsTrigger value="competitors">경쟁분석</TabsTrigger>
              <TabsTrigger value="rankings">순위추적</TabsTrigger>
              <TabsTrigger value="campaigns">캠페인</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview">
              <div className="grid gap-6 md:grid-cols-2">
                {/* Place Info Card */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <MapPin className="h-5 w-5" />
                      플레이스 정보
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {selectedPlace && (
                      <div className="space-y-4">
                        <div>
                          <div className="text-sm text-gray-500">상호명</div>
                          <div className="font-medium">{selectedPlace.place_name}</div>
                        </div>
                        <div>
                          <div className="text-sm text-gray-500">카테고리</div>
                          <div className="font-medium">{selectedPlace.category || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm text-gray-500">주소</div>
                          <div className="font-medium">{selectedPlace.address || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm text-gray-500">전화번호</div>
                          <div className="font-medium">{selectedPlace.phone || '-'}</div>
                        </div>
                        {selectedPlace.place_url && (
                          <div className="pt-4 border-t">
                            <Button variant="outline" size="sm" asChild>
                              <a
                                href={selectedPlace.place_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <ExternalLink className="h-4 w-4 mr-2" />
                                플레이스 바로가기
                              </a>
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Optimization Score Card */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Target className="h-5 w-5" />
                      최적화 점수
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-4">
                      <div className="text-5xl font-bold text-blue-600 mb-2">
                        {optimization?.optimization_score || 0}
                      </div>
                      <div className="text-gray-500 mb-4">/ 100점</div>
                      <Progress value={optimization?.optimization_score || 0} className="h-3" />
                    </div>
                    {optimization?.checks && (
                      <div className="mt-6 space-y-3">
                        {optimization.checks.map((check, index) => (
                          <div
                            key={index}
                            className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                          >
                            {getStatusIcon(check.status)}
                            <div className="flex-1">
                              <div className="font-medium text-sm">{check.message}</div>
                              {check.suggestion && (
                                <div className="text-xs text-gray-500 mt-1">
                                  {check.suggestion}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Reviews Tab */}
            <TabsContent value="reviews">
              <div className="grid gap-6">
                {/* Review Analytics */}
                {reviewAnalytics && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-500">총 리뷰</p>
                            <p className="text-2xl font-bold">
                              {reviewAnalytics.summary?.total_reviews || 0}
                            </p>
                          </div>
                          <MessageSquare className="h-8 w-8 text-blue-200" />
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-500">평균 별점</p>
                            <p className="text-2xl font-bold flex items-center">
                              {reviewAnalytics.summary?.avg_rating?.toFixed(1) || '-'}
                              <Star className="h-5 w-5 text-yellow-400 ml-1" />
                            </p>
                          </div>
                          <Star className="h-8 w-8 text-yellow-200" />
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-500">긍정 리뷰</p>
                            <p className="text-2xl font-bold text-green-600">
                              {reviewAnalytics.sentiment_breakdown?.positive || 0}
                            </p>
                          </div>
                          <ThumbsUp className="h-8 w-8 text-green-200" />
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-500">부정 리뷰</p>
                            <p className="text-2xl font-bold text-red-600">
                              {reviewAnalytics.sentiment_breakdown?.negative || 0}
                            </p>
                          </div>
                          <ThumbsDown className="h-8 w-8 text-red-200" />
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Reviews List */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <MessageSquare className="h-5 w-5" />
                        리뷰 목록
                      </span>
                      <Button variant="outline" size="sm" onClick={loadPlaceData}>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        새로고침
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {reviews.length === 0 ? (
                      <div className="text-center py-12">
                        <MessageSquare className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                        <p className="text-gray-500">리뷰가 없습니다</p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {reviews.map((review) => (
                          <div
                            key={review.id}
                            className="p-4 border rounded-lg hover:bg-gray-50"
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex items-center gap-3">
                                <div className="flex items-center">
                                  {Array.from({ length: 5 }).map((_, i) => (
                                    <Star
                                      key={i}
                                      className={`h-4 w-4 ${
                                        i < (review.rating || 0)
                                          ? 'text-yellow-400 fill-yellow-400'
                                          : 'text-gray-200'
                                      }`}
                                    />
                                  ))}
                                </div>
                                {getSentimentIcon(review.sentiment || 'neutral')}
                                <span className="font-medium">{review.author_name || '익명'}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                {review.is_replied ? (
                                  <Badge className="bg-green-100 text-green-700">
                                    답변완료
                                  </Badge>
                                ) : (
                                  <Badge variant="outline">미답변</Badge>
                                )}
                              </div>
                            </div>
                            <p className="mt-2 text-gray-700">{review.content}</p>
                            <div className="mt-3 flex items-center justify-between">
                              <span className="text-sm text-gray-500">
                                {review.written_at
                                  ? format(new Date(review.written_at), 'yyyy.MM.dd', {
                                      locale: ko,
                                    })
                                  : '-'}
                              </span>
                              {!review.is_replied && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setSelectedReview(review)
                                    setIsReplyDialogOpen(true)
                                  }}
                                >
                                  <Sparkles className="h-4 w-4 mr-1" />
                                  AI 답변
                                </Button>
                              )}
                            </div>
                            {review.is_replied && review.reply_content && (
                              <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                                <div className="text-sm font-medium text-blue-700 mb-1">
                                  답변
                                </div>
                                <p className="text-sm text-gray-700">{review.reply_content}</p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Reply Dialog */}
              <Dialog open={isReplyDialogOpen} onOpenChange={setIsReplyDialogOpen}>
                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>AI 리뷰 답변 생성</DialogTitle>
                    <DialogDescription>
                      AI가 리뷰에 맞는 답변을 생성합니다
                    </DialogDescription>
                  </DialogHeader>
                  {selectedReview && (
                    <div className="space-y-4">
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="font-medium">{selectedReview.author_name || '익명'}</span>
                          <div className="flex">
                            {Array.from({ length: selectedReview.rating || 0 }).map((_, i) => (
                              <Star
                                key={i}
                                className="h-3 w-3 text-yellow-400 fill-yellow-400"
                              />
                            ))}
                          </div>
                        </div>
                        <p className="text-sm text-gray-700">{selectedReview.content}</p>
                      </div>
                      <div className="space-y-2">
                        <Label>생성된 답변</Label>
                        <Textarea
                          value={generatedReply}
                          onChange={(e) => setGeneratedReply(e.target.value)}
                          rows={5}
                          placeholder="AI 답변을 생성하거나 직접 작성하세요"
                        />
                      </div>
                    </div>
                  )}
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={handleGenerateReply}
                      disabled={isGenerating}
                    >
                      {isGenerating ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4 mr-2" />
                      )}
                      AI 생성
                    </Button>
                    <Button onClick={handleSubmitReply} disabled={!generatedReply}>
                      답변 등록
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </TabsContent>

            {/* Competitors Tab */}
            <TabsContent value="competitors">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Trophy className="h-5 w-5" />
                      경쟁사 분석
                    </span>
                    <Button size="sm" onClick={handleAutoDetectCompetitors}>
                      <Search className="h-4 w-4 mr-2" />
                      자동 탐지
                    </Button>
                  </CardTitle>
                  <CardDescription>
                    주변 경쟁 병원의 플레이스 정보를 분석합니다
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {competitors.length === 0 ? (
                    <div className="text-center py-12">
                      <Users className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                      <p className="text-gray-500">경쟁사가 등록되지 않았습니다</p>
                      <p className="text-sm text-gray-400 mt-1">
                        자동 탐지 버튼을 클릭하여 주변 경쟁사를 찾아보세요
                      </p>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>병원명</TableHead>
                          <TableHead>거리</TableHead>
                          <TableHead className="text-right">리뷰수</TableHead>
                          <TableHead className="text-right">별점</TableHead>
                          <TableHead>강점</TableHead>
                          <TableHead>약점</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {competitors.map((comp) => (
                          <TableRow key={comp.id}>
                            <TableCell className="font-medium">
                              {comp.place_name}
                            </TableCell>
                            <TableCell>{comp.distance_km?.toFixed(1)}km</TableCell>
                            <TableCell className="text-right">
                              {comp.review_count.toLocaleString()}
                            </TableCell>
                            <TableCell className="text-right">
                              <span className="flex items-center justify-end gap-1">
                                {comp.avg_rating?.toFixed(1)}
                                <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                              </span>
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-1">
                                {comp.strengths?.slice(0, 2).map((s, i) => (
                                  <Badge
                                    key={i}
                                    variant="outline"
                                    className="text-green-600 border-green-200"
                                  >
                                    {s}
                                  </Badge>
                                ))}
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-1">
                                {comp.weaknesses?.slice(0, 2).map((w, i) => (
                                  <Badge
                                    key={i}
                                    variant="outline"
                                    className="text-red-600 border-red-200"
                                  >
                                    {w}
                                  </Badge>
                                ))}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Rankings Tab */}
            <TabsContent value="rankings">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <TrendingUp className="h-5 w-5" />
                      순위 추적
                    </span>
                    <Dialog open={isKeywordDialogOpen} onOpenChange={setIsKeywordDialogOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="h-4 w-4 mr-2" />
                          키워드 추가
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>추적 키워드 추가</DialogTitle>
                          <DialogDescription>
                            플레이스 검색 순위를 추적할 키워드를 추가하세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>키워드</Label>
                            <Input
                              placeholder="예: 강남역 피부과"
                              value={keywordForm.keyword}
                              onChange={(e) =>
                                setKeywordForm({ ...keywordForm, keyword: e.target.value })
                              }
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>카테고리 (선택)</Label>
                            <Input
                              placeholder="예: 피부과"
                              value={keywordForm.category}
                              onChange={(e) =>
                                setKeywordForm({ ...keywordForm, category: e.target.value })
                              }
                            />
                          </div>
                        </div>
                        <DialogFooter>
                          <Button
                            variant="outline"
                            onClick={() => setIsKeywordDialogOpen(false)}
                          >
                            취소
                          </Button>
                          <Button onClick={handleAddKeyword}>추가</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </CardTitle>
                  <CardDescription>
                    주요 키워드의 플레이스 검색 순위를 모니터링합니다
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {keywords.length === 0 ? (
                    <div className="text-center py-12">
                      <Search className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                      <p className="text-gray-500">추적 중인 키워드가 없습니다</p>
                      <p className="text-sm text-gray-400 mt-1">
                        키워드를 추가하여 순위 변동을 모니터링하세요
                      </p>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>키워드</TableHead>
                          <TableHead className="text-center">현재 순위</TableHead>
                          <TableHead className="text-center">변동</TableHead>
                          <TableHead className="text-center">최고</TableHead>
                          <TableHead className="text-center">최저</TableHead>
                          <TableHead>마지막 체크</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {keywords.map((kw) => (
                          <TableRow key={kw.id}>
                            <TableCell className="font-medium">{kw.keyword}</TableCell>
                            <TableCell className="text-center">
                              <span className="text-lg font-bold">
                                {kw.current_rank || '-'}
                              </span>
                              <span className="text-gray-400 text-sm">위</span>
                            </TableCell>
                            <TableCell className="text-center">
                              <div className="flex items-center justify-center gap-1">
                                {getTrendIcon(kw.trend, kw.rank_change)}
                                <span
                                  className={
                                    kw.rank_change > 0
                                      ? 'text-green-600'
                                      : kw.rank_change < 0
                                      ? 'text-red-600'
                                      : 'text-gray-400'
                                  }
                                >
                                  {kw.rank_change > 0 ? '+' : ''}
                                  {kw.rank_change || 0}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell className="text-center text-green-600">
                              {kw.best_rank || '-'}
                            </TableCell>
                            <TableCell className="text-center text-red-600">
                              {kw.worst_rank || '-'}
                            </TableCell>
                            <TableCell className="text-gray-500 text-sm">
                              {kw.last_checked_at
                                ? format(new Date(kw.last_checked_at), 'MM.dd HH:mm')
                                : '-'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Campaigns Tab */}
            <TabsContent value="campaigns">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Gift className="h-5 w-5" />
                      리뷰 캠페인
                    </span>
                    <Dialog
                      open={isCampaignDialogOpen}
                      onOpenChange={setIsCampaignDialogOpen}
                    >
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="h-4 w-4 mr-2" />
                          캠페인 만들기
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>리뷰 캠페인 만들기</DialogTitle>
                          <DialogDescription>
                            리뷰 작성 고객에게 혜택을 제공하는 캠페인을 만드세요
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>캠페인명</Label>
                            <Input
                              placeholder="예: 12월 리뷰 이벤트"
                              value={campaignForm.name}
                              onChange={(e) =>
                                setCampaignForm({ ...campaignForm, name: e.target.value })
                              }
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label>보상 유형</Label>
                            <Select
                              value={campaignForm.reward_type}
                              onValueChange={(value) =>
                                setCampaignForm({ ...campaignForm, reward_type: value as RewardType })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="discount">할인</SelectItem>
                                <SelectItem value="gift">사은품</SelectItem>
                                <SelectItem value="point">포인트</SelectItem>
                                <SelectItem value="coupon">쿠폰</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2">
                            <Label>보상 내용</Label>
                            <Input
                              placeholder="예: 10% 할인 쿠폰"
                              value={campaignForm.reward_description}
                              onChange={(e) =>
                                setCampaignForm({
                                  ...campaignForm,
                                  reward_description: e.target.value,
                                })
                              }
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                              <Label>시작일</Label>
                              <Input
                                type="date"
                                value={campaignForm.start_date}
                                onChange={(e) =>
                                  setCampaignForm({
                                    ...campaignForm,
                                    start_date: e.target.value,
                                  })
                                }
                              />
                            </div>
                            <div className="grid gap-2">
                              <Label>종료일</Label>
                              <Input
                                type="date"
                                value={campaignForm.end_date}
                                onChange={(e) =>
                                  setCampaignForm({
                                    ...campaignForm,
                                    end_date: e.target.value,
                                  })
                                }
                              />
                            </div>
                          </div>
                          <div className="grid gap-2">
                            <Label>목표 리뷰 수</Label>
                            <Input
                              type="number"
                              value={campaignForm.target_count}
                              onChange={(e) =>
                                setCampaignForm({
                                  ...campaignForm,
                                  target_count: parseInt(e.target.value) || 0,
                                })
                              }
                            />
                          </div>
                        </div>
                        <DialogFooter>
                          <Button
                            variant="outline"
                            onClick={() => setIsCampaignDialogOpen(false)}
                          >
                            취소
                          </Button>
                          <Button onClick={handleCreateCampaign}>생성</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </CardTitle>
                  <CardDescription>
                    리뷰 작성 유도 캠페인을 관리하고 QR 코드를 생성합니다
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {campaigns.length === 0 ? (
                    <div className="text-center py-12">
                      <QrCode className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                      <p className="text-gray-500">진행 중인 캠페인이 없습니다</p>
                      <p className="text-sm text-gray-400 mt-1">
                        캠페인을 만들어 리뷰 작성을 유도해보세요
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {campaigns.map((campaign) => (
                        <div
                          key={campaign.id}
                          className="p-4 border rounded-lg hover:bg-gray-50"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{campaign.name}</span>
                                <Badge
                                  variant={
                                    campaign.status === 'active' ? 'default' : 'secondary'
                                  }
                                  className={
                                    campaign.status === 'active'
                                      ? 'bg-green-100 text-green-700'
                                      : ''
                                  }
                                >
                                  {campaign.status === 'active'
                                    ? '진행중'
                                    : campaign.status === 'ended'
                                    ? '종료'
                                    : '준비중'}
                                </Badge>
                              </div>
                              <p className="text-sm text-gray-500 mt-1">
                                {campaign.reward_description}
                              </p>
                            </div>
                            <div className="text-right">
                              <div className="text-2xl font-bold text-blue-600">
                                {campaign.current_count}
                                <span className="text-gray-400 text-base">
                                  /{campaign.target_count}
                                </span>
                              </div>
                              <div className="text-xs text-gray-500">리뷰</div>
                            </div>
                          </div>
                          <Progress
                            value={(campaign.current_count / campaign.target_count) * 100}
                            className="h-2 mt-3"
                          />
                          <div className="flex items-center justify-between mt-3">
                            <span className="text-sm text-gray-500">
                              {format(new Date(campaign.start_date), 'yyyy.MM.dd')} -{' '}
                              {format(new Date(campaign.end_date), 'yyyy.MM.dd')}
                            </span>
                            <div className="flex gap-2">
                              <Button variant="outline" size="sm">
                                <QrCode className="h-4 w-4 mr-1" />
                                QR코드
                              </Button>
                              <Button variant="outline" size="sm">
                                <Copy className="h-4 w-4 mr-1" />
                                링크복사
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
          </Tabs>
        )}
      </main>
    </div>
  )
}
