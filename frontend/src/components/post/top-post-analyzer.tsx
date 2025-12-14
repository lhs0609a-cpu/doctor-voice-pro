'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Search,
  Loader2,
  TrendingUp,
  FileText,
  Image,
  Type,
  Target,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-react'
import { toast } from 'sonner'

interface TopPostAnalyzerProps {
  onRulesGenerated?: (rules: WritingRules | null) => void
  keyword?: string
}

interface WritingRules {
  title: {
    length: { optimal: number; min: number; max: number }
    keyword_placement: {
      include_keyword: boolean
      rate: number
      best_position: string
      position_distribution: { front: number; middle: number; end: number }
    }
  }
  content: {
    length: { optimal: number; min: number; max: number }
    structure: {
      heading_count: { optimal: number; min: number; max: number }
      keyword_density: { optimal: number; min: number; max: number }
      keyword_count: { optimal: number; min: number; max: number }
    }
  }
  media: {
    images: { optimal: number; min: number; max: number }
    videos: { usage_rate: number; recommended: boolean }
  }
}

interface AnalysisResult {
  keyword: string
  category: string
  category_name: string
  analyzed_count: number
  results: Array<{
    rank: number
    title: string
    post_url: string
    title_length: number
    content_length: number
    image_count: number
    heading_count: number
    keyword_count: number
    keyword_density: number
    has_map: boolean
    has_video: boolean
    data_quality: string
  }>
  summary?: {
    avg_title_length: number
    avg_content_length: number
    avg_image_count: number
    avg_heading_count: number
    avg_keyword_count: number
    avg_keyword_density: number
    title_keyword_rate: number
    keyword_position: { front: number; middle: number; end: number }
  }
}

interface WritingGuide {
  status: string
  confidence: number
  sample_count: number
  category: string
  category_name: string
  rules: WritingRules
  message?: string
}

export function TopPostAnalyzer({ onRulesGenerated, keyword: initialKeyword }: TopPostAnalyzerProps) {
  const [keyword, setKeyword] = useState(initialKeyword || '')
  const [loading, setLoading] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [writingGuide, setWritingGuide] = useState<WritingGuide | null>(null)
  const [expanded, setExpanded] = useState(true)
  const [showDetails, setShowDetails] = useState(false)

  // 분석 실행
  const handleAnalyze = async () => {
    if (!keyword.trim()) {
      toast.error('키워드를 입력해주세요')
      return
    }

    setLoading(true)
    const loadingToast = toast.loading('상위 글 분석 중...', {
      description: '네이버 블로그 검색 결과를 수집하고 있습니다'
    })

    try {
      // 1. 상위 글 분석
      const analyzeResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/top-posts/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: keyword.trim(), top_n: 3 })
      })

      if (!analyzeResponse.ok) {
        throw new Error('분석 실패')
      }

      const analyzeData: AnalysisResult = await analyzeResponse.json()
      setAnalysisResult(analyzeData)

      // 2. 글쓰기 가이드 조회
      const guideResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/top-posts/writing-guide?keyword=${encodeURIComponent(keyword.trim())}`
      )

      if (guideResponse.ok) {
        const guideData: WritingGuide = await guideResponse.json()
        setWritingGuide(guideData)

        // 부모 컴포넌트에 규칙 전달
        if (onRulesGenerated) {
          onRulesGenerated(guideData.rules)
        }
      }

      toast.success(`${analyzeData.analyzed_count}개 글 분석 완료!`, {
        id: loadingToast,
        description: `카테고리: ${analyzeData.category_name}`
      })

    } catch (error: any) {
      console.error('Analysis error:', error)
      toast.error('분석 실패', {
        id: loadingToast,
        description: error.message || '잠시 후 다시 시도해주세요'
      })
    } finally {
      setLoading(false)
    }
  }

  const getPositionLabel = (position: string) => {
    switch (position) {
      case 'front': return '앞부분'
      case 'middle': return '중간'
      case 'end': return '끝부분'
      default: return position
    }
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'text-green-600'
    if (confidence >= 0.4) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <Card className="border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search className="h-5 w-5 text-indigo-600" />
            <CardTitle className="text-base">네이버 상위노출 분석</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
        <CardDescription className="text-xs">
          상위 1~3위 글을 분석하여 최적의 글쓰기 규칙을 도출합니다
        </CardDescription>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-4">
          {/* 키워드 입력 */}
          <div className="flex gap-2">
            <Input
              placeholder="분석할 키워드 입력 (예: 아토피 치료)"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              disabled={loading}
            />
            <Button
              onClick={handleAnalyze}
              disabled={loading || !keyword.trim()}
              className="shrink-0"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <TrendingUp className="h-4 w-4 mr-1" />
                  분석
                </>
              )}
            </Button>
          </div>

          {/* 분석 결과 */}
          {analysisResult && writingGuide && (
            <div className="space-y-4">
              {/* 신뢰도 및 상태 */}
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  {writingGuide.status === 'data_driven' ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                  )}
                  <span>
                    {writingGuide.status === 'data_driven' ? '데이터 기반 분석' : '기본값 적용'}
                  </span>
                </div>
                <div className={`font-medium ${getConfidenceColor(writingGuide.confidence)}`}>
                  신뢰도: {Math.round(writingGuide.confidence * 100)}% ({writingGuide.sample_count}개 샘플)
                </div>
              </div>

              {/* 핵심 규칙 요약 */}
              <div className="grid grid-cols-2 gap-3">
                {/* 제목 규칙 */}
                <div className="bg-white rounded-lg p-3 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <Type className="h-4 w-4 text-blue-600" />
                    <span className="font-medium text-sm">제목</span>
                  </div>
                  <div className="space-y-1 text-xs text-gray-600">
                    <p>길이: {writingGuide.rules.title.length.min}~{writingGuide.rules.title.length.max}자</p>
                    <p>최적: {writingGuide.rules.title.length.optimal}자</p>
                    <p>키워드 위치: {getPositionLabel(writingGuide.rules.title.keyword_placement.best_position)}</p>
                  </div>
                </div>

                {/* 본문 규칙 */}
                <div className="bg-white rounded-lg p-3 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-sm">본문</span>
                  </div>
                  <div className="space-y-1 text-xs text-gray-600">
                    <p>길이: {writingGuide.rules.content.length.min.toLocaleString()}~{writingGuide.rules.content.length.max.toLocaleString()}자</p>
                    <p>소제목: {writingGuide.rules.content.structure.heading_count.min}~{writingGuide.rules.content.structure.heading_count.max}개</p>
                    <p>키워드: {writingGuide.rules.content.structure.keyword_count.min}~{writingGuide.rules.content.structure.keyword_count.max}회</p>
                  </div>
                </div>

                {/* 이미지 규칙 */}
                <div className="bg-white rounded-lg p-3 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <Image className="h-4 w-4 text-purple-600" />
                    <span className="font-medium text-sm">이미지</span>
                  </div>
                  <div className="space-y-1 text-xs text-gray-600">
                    <p>개수: {writingGuide.rules.media.images.min}~{writingGuide.rules.media.images.max}장</p>
                    <p>최적: {writingGuide.rules.media.images.optimal}장</p>
                    <p>동영상: {writingGuide.rules.media.videos.recommended ? '권장' : '선택'}</p>
                  </div>
                </div>

                {/* 키워드 밀도 */}
                <div className="bg-white rounded-lg p-3 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="h-4 w-4 text-orange-600" />
                    <span className="font-medium text-sm">키워드 밀도</span>
                  </div>
                  <div className="space-y-1 text-xs text-gray-600">
                    <p>밀도: {writingGuide.rules.content.structure.keyword_density.min}~{writingGuide.rules.content.structure.keyword_density.max}/1000자</p>
                    <p>최적: {writingGuide.rules.content.structure.keyword_density.optimal}/1000자</p>
                    <p>카테고리: {writingGuide.category_name}</p>
                  </div>
                </div>
              </div>

              {/* 상세 보기 토글 */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                className="w-full text-xs"
              >
                {showDetails ? '상세 정보 숨기기' : '상위 글 상세 정보 보기'}
                {showDetails ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
              </Button>

              {/* 상세 정보 */}
              {showDetails && analysisResult.results.length > 0 && (
                <div className="space-y-2">
                  {analysisResult.results.map((result, idx) => (
                    <div key={idx} className="bg-white rounded-lg p-3 shadow-sm text-xs">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded font-medium">
                            {result.rank}위
                          </span>
                          <span className={`px-1.5 py-0.5 rounded ${
                            result.data_quality === 'high' ? 'bg-green-100 text-green-700' :
                            result.data_quality === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {result.data_quality}
                          </span>
                        </div>
                        <a
                          href={result.post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline flex items-center gap-1"
                        >
                          보기 <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                      <p className="font-medium mb-2 line-clamp-1">{result.title}</p>
                      <div className="grid grid-cols-4 gap-2 text-gray-600">
                        <div>
                          <span className="text-gray-400">본문:</span> {result.content_length.toLocaleString()}자
                        </div>
                        <div>
                          <span className="text-gray-400">이미지:</span> {result.image_count}장
                        </div>
                        <div>
                          <span className="text-gray-400">소제목:</span> {result.heading_count}개
                        </div>
                        <div>
                          <span className="text-gray-400">키워드:</span> {result.keyword_count}회
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 다시 분석 버튼 */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleAnalyze}
                disabled={loading}
                className="w-full"
              >
                <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
                다시 분석하기
              </Button>
            </div>
          )}

          {/* 분석 전 안내 */}
          {!analysisResult && !loading && (
            <div className="text-center py-4 text-sm text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 text-indigo-300" />
              <p>키워드를 입력하고 분석 버튼을 클릭하세요</p>
              <p className="text-xs mt-1">상위 1~3위 글의 패턴을 분석합니다</p>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}
