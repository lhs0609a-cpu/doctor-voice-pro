'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Pill } from '@/components/app-shell/ui-kit'
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
    if (confidence >= 0.7) return 'text-success'
    if (confidence >= 0.4) return 'text-warning'
    return 'text-danger'
  }

  const getQualityTone = (quality: string): 'ok' | 'warn' | 'muted' => {
    if (quality === 'high') return 'ok'
    if (quality === 'medium') return 'warn'
    return 'muted'
  }

  const ruleCards = writingGuide
    ? [
        {
          icon: Type,
          label: '제목',
          lines: [
            `길이: ${writingGuide.rules.title.length.min}~${writingGuide.rules.title.length.max}자`,
            `최적: ${writingGuide.rules.title.length.optimal}자`,
            `키워드 위치: ${getPositionLabel(writingGuide.rules.title.keyword_placement.best_position)}`,
          ],
        },
        {
          icon: FileText,
          label: '본문',
          lines: [
            `길이: ${writingGuide.rules.content.length.min.toLocaleString()}~${writingGuide.rules.content.length.max.toLocaleString()}자`,
            `소제목: ${writingGuide.rules.content.structure.heading_count.min}~${writingGuide.rules.content.structure.heading_count.max}개`,
            `키워드: ${writingGuide.rules.content.structure.keyword_count.min}~${writingGuide.rules.content.structure.keyword_count.max}회`,
          ],
        },
        {
          icon: Image,
          label: '이미지',
          lines: [
            `개수: ${writingGuide.rules.media.images.min}~${writingGuide.rules.media.images.max}장`,
            `최적: ${writingGuide.rules.media.images.optimal}장`,
            `동영상: ${writingGuide.rules.media.videos.recommended ? '권장' : '선택'}`,
          ],
        },
        {
          icon: Target,
          label: '키워드 밀도',
          lines: [
            `밀도: ${writingGuide.rules.content.structure.keyword_density.min}~${writingGuide.rules.content.structure.keyword_density.max}/1000자`,
            `최적: ${writingGuide.rules.content.structure.keyword_density.optimal}/1000자`,
            `카테고리: ${writingGuide.category_name}`,
          ],
        },
      ]
    : []

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            네이버 상위노출 분석
          </CardTitle>
          <CardDescription className="mt-1">
            상위 1~3위 글을 분석해 최적의 글쓰기 규칙을 찾습니다
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => setExpanded(!expanded)}
          aria-label={expanded ? '접기' : '펼치기'}
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
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
                  <TrendingUp className="h-4 w-4" />
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
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-warning" />
                  )}
                  <span>
                    {writingGuide.status === 'data_driven' ? '데이터 기반 분석' : '기본값 적용'}
                  </span>
                </div>
                <div className={`font-medium tabular-nums ${getConfidenceColor(writingGuide.confidence)}`}>
                  신뢰도: {Math.round(writingGuide.confidence * 100)}% ({writingGuide.sample_count}개 샘플)
                </div>
              </div>

              {/* 핵심 규칙 요약 */}
              <div className="grid grid-cols-2 gap-4">
                {ruleCards.map((rule) => {
                  const Icon = rule.icon
                  return (
                    <div key={rule.label} className="rounded-lg border bg-muted/40 p-3">
                      <div className="mb-2 flex items-center gap-2">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">{rule.label}</span>
                      </div>
                      <div className="space-y-1 text-xs tabular-nums text-muted-foreground">
                        {rule.lines.map((line) => (
                          <p key={line}>{line}</p>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* 상세 보기 토글 */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                className="w-full text-xs"
              >
                {showDetails ? '상세 정보 숨기기' : '상위 글 상세 정보 보기'}
                {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </Button>

              {/* 상세 정보 */}
              {showDetails && analysisResult.results.length > 0 && (
                <div className="space-y-2">
                  {analysisResult.results.map((result, idx) => (
                    <div key={idx} className="rounded-lg border bg-muted/40 p-3 text-xs">
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Pill tone="accent">{result.rank}위</Pill>
                          <Pill tone={getQualityTone(result.data_quality)}>{result.data_quality}</Pill>
                        </div>
                        <a
                          href={result.post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-primary hover:underline"
                        >
                          보기 <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                      <p className="mb-2 line-clamp-1 font-medium">{result.title}</p>
                      <div className="grid grid-cols-4 gap-2 tabular-nums text-muted-foreground">
                        <div>
                          <span className="text-muted-foreground/70">본문:</span> {result.content_length.toLocaleString()}자
                        </div>
                        <div>
                          <span className="text-muted-foreground/70">이미지:</span> {result.image_count}장
                        </div>
                        <div>
                          <span className="text-muted-foreground/70">소제목:</span> {result.heading_count}개
                        </div>
                        <div>
                          <span className="text-muted-foreground/70">키워드:</span> {result.keyword_count}회
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
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                다시 분석하기
              </Button>
            </div>
          )}

          {/* 분석 전 안내 */}
          {!analysisResult && !loading && (
            <div className="py-4 text-center text-sm text-muted-foreground">
              <Search className="mx-auto mb-2 h-8 w-8 text-muted-foreground/50" />
              <p>키워드를 입력하고 분석 버튼을 클릭하세요</p>
              <p className="mt-1 text-xs">상위 1~3위 글의 패턴을 분석합니다</p>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}
