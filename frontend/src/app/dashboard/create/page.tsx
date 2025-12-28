'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { postsAPI, authAPI, crawlAPI, type CrawlImage, type OneClickResponse } from '@/lib/api'
import type { Post, WritingStyle, RequestRequirements, User } from '@/types'
import { useAutoSave } from '@/hooks/useAutoSave'
import { toast } from 'sonner'
import {
  Sparkles,
  Loader2,
  TrendingUp,
  Hash,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Save,
  Clock,
  FileDown,
  FileText,
  PenTool,
  Coffee,
  Link,
  Download,
  Image as ImageIcon,
  X,
  Zap,
  ExternalLink,
} from 'lucide-react'
import { Document, Paragraph, TextRun, Packer } from 'docx'
import { saveAs } from 'file-saver'
import { CharacterCount } from '@/components/post/character-count'
import { KeywordTags } from '@/components/post/keyword-tags'
import { TitleSelector } from '@/components/post/title-selector'
import { SubtitlePreview } from '@/components/post/subtitle-preview'
import { ForbiddenWordsAlert } from '@/components/post/forbidden-words-alert'
import { DIACRANKScore } from '@/components/post/dia-crank-score'
import { WritingStyleConfig } from '@/components/post/writing-style-config'
import { RequestRequirementsInput } from '@/components/post/request-requirements-input'
import { Slider } from '@/components/ui/slider'
import { Input } from '@/components/ui/input'
import { CafeReviewCreator } from '@/components/cafe-review/cafe-review-creator'
import { OneClickPublish } from '@/components/naver-publish/one-click-publish'
import { TopPostAnalyzer } from '@/components/post/top-post-analyzer'

export default function CreatePostPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  const [generatedPost, setGeneratedPost] = useState<Post | null>(null)
  const [generatedPosts, setGeneratedPosts] = useState<Post[]>([])
  const [claudeApiStatus, setClaudeApiStatus] = useState<any>(null)
  const [gptApiStatus, setGptApiStatus] = useState<any>(null)
  const [geminiApiStatus, setGeminiApiStatus] = useState<any>(null)
  const [checkingApi, setCheckingApi] = useState(true)
  const [checkingGptApi, setCheckingGptApi] = useState(true)
  const [checkingGeminiApi, setCheckingGeminiApi] = useState(true)
  const [aiPricing, setAiPricing] = useState<any>(null)
  const [aiUsageStats, setAiUsageStats] = useState<any>(null)
  const [config, setConfig] = useState({
    persuasion_level: 4,
    framework: '관심유도형',
    target_length: 1800,
    writing_perspective: '1인칭',
    count: 1, // 생성할 원고 개수
    ai_provider: 'gpt', // AI 제공자: 'claude' or 'gpt'
    ai_model: 'gpt-4o-mini', // AI 모델 (기본: GPT-4o Mini - 빠름/저렴)
  })
  const [seoOptimization, setSeoOptimization] = useState({
    enabled: false,
    // 기존 DIA/CRANK 옵션
    experience_focus: true,      // 실제 경험 중심 작성 (DIA: 경험 정보)
    expertise: true,              // 전문성과 깊이 강화 (C-Rank: Content 품질)
    originality: true,            // 독창성 강조 (DIA: 독창성)
    timeliness: true,             // 적시성 반영 (DIA: 적시성)
    topic_concentration: true,    // 주제 집중도 향상 (C-Rank: Context)
    // 2025년 9월 네이버 AI 검색 업데이트 반영
    trustworthiness: true,        // 신뢰성 강화 (출처 명시, 의학적 근거)
    source_authority: true,       // 출처 권위성 (공공기관, 학술기관 인용)
    multi_perspective: true,      // 다각도 정보 제공 (편향 방지)
    search_intent_match: true,    // 검색 의도 정확 충족 (뉴럴 매칭)
  })
  const [writingStyle, setWritingStyle] = useState<WritingStyle>({
    formality: 5,
    friendliness: 7,
    technical_depth: 5,
    storytelling: 6,
    emotion: 6,
    humor: 5,
    question_usage: 6,
    metaphor_usage: 5,
    sentence_length: 5,
  })
  const [requirements, setRequirements] = useState<RequestRequirements>({
    common: [],
    individual: '',
  })
  const [topicConversion, setTopicConversion] = useState({
    enabled: false,
    from: '',
    to: '',
  })
  const [topPostRules, setTopPostRules] = useState<any>(null)
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [selectedPostIndex, setSelectedPostIndex] = useState(0)
  const [blogUrl, setBlogUrl] = useState('')
  const [crawling, setCrawling] = useState(false)
  const [crawledImages, setCrawledImages] = useState<CrawlImage[]>([])
  const [oneClickProcessing, setOneClickProcessing] = useState(false)
  const [oneClickResult, setOneClickResult] = useState<OneClickResponse | null>(null)
  const [generationProgress, setGenerationProgress] = useState<{
    total: number
    completed: number
    failed: number
    errors: string[]
  }>({ total: 0, completed: 0, failed: 0, errors: [] })

  // Auto-save hook
  const { lastSaved, loadSaved, clearSaved } = useAutoSave({
    key: 'draft-post-create',
    data: { originalContent, config },
    delay: 3000,
    enabled: !generatedPost, // Only auto-save before generation
  })

  // Fetch current user
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await authAPI.getMe()
        setCurrentUser(user)
      } catch (error) {
        console.error('Failed to fetch user:', error)
      }
    }
    fetchUser()
  }, [])

  // Check Claude API status
  useEffect(() => {
    const checkClaudeApiStatus = async () => {
      setCheckingApi(true)
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/system/claude-api-status`)
        const data = await response.json()
        setClaudeApiStatus(data)
      } catch (error) {
        console.error('Failed to check Claude API status:', error)
        setClaudeApiStatus({ connected: false, error: '연결 확인 실패' })
      } finally {
        setCheckingApi(false)
      }
    }

    checkClaudeApiStatus()
  }, [])

  // Check GPT API status
  useEffect(() => {
    const checkGptApiStatus = async () => {
      setCheckingGptApi(true)
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/system/gpt-api-status`)
        const data = await response.json()
        setGptApiStatus(data)
      } catch (error) {
        console.error('Failed to check GPT API status:', error)
        setGptApiStatus({ connected: false, error: '연결 확인 실패' })
      } finally {
        setCheckingGptApi(false)
      }
    }

    checkGptApiStatus()
  }, [])

  // Check Gemini API status
  useEffect(() => {
    const checkGeminiApiStatus = async () => {
      setCheckingGeminiApi(true)
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/system/gemini-api-status`)
        const data = await response.json()
        setGeminiApiStatus(data)
      } catch (error) {
        console.error('Failed to check Gemini API status:', error)
        setGeminiApiStatus({ connected: false, error: '연결 확인 실패' })
      } finally {
        setCheckingGeminiApi(false)
      }
    }

    checkGeminiApiStatus()
  }, [])

  // Fetch AI pricing and usage stats
  useEffect(() => {
    const fetchAiData = async () => {
      try {
        // 가격 정보 가져오기
        const pricingResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/system/ai-pricing`)
        const pricingData = await pricingResponse.json()
        setAiPricing(pricingData)

        // 사용량 통계 가져오기
        const usageResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/system/ai-usage-stats`)
        const usageData = await usageResponse.json()
        setAiUsageStats(usageData)
      } catch (error) {
        console.error('Failed to fetch AI data:', error)
      }
    }

    fetchAiData()
  }, [])

  // Load saved draft on mount
  useEffect(() => {
    const saved = loadSaved()
    if (saved && saved.originalContent) {
      setOriginalContent(saved.originalContent)
      if (saved.config) {
        setConfig(saved.config)
      }
    }
  }, [loadSaved])

  const handleGenerate = async () => {
    if (!originalContent.trim() || originalContent.length < 50) {
      toast.error('원본 내용을 최소 50자 이상 입력해주세요')
      return
    }

    // 주제 변환 검증
    if (topicConversion.enabled && (!topicConversion.from || !topicConversion.to)) {
      toast.error('주제 변환을 위해 변환 전/후 주제를 모두 입력해주세요')
      return
    }

    setLoading(true)
    const count = config.count || 1

    // 진행률 초기화
    setGenerationProgress({ total: count, completed: 0, failed: 0, errors: [] })

    const loadingToast = toast.loading(`AI가 블로그를 생성하고 있습니다... (0/${count})`, {
      description: `순차 처리로 안정적 생성 중...`
    })

    try {
      // 주제 변환 처리
      let processedContent = originalContent
      if (topicConversion.enabled) {
        const regex = new RegExp(topicConversion.from, 'gi')
        processedContent = originalContent.replace(regex, topicConversion.to)
      }

      // 안정적인 순차 처리 (서버 과부하 방지)
      const results: Array<{ success: boolean; post?: Post; error?: string; index: number }> = []
      let retryCount = 0
      const MAX_RETRIES = 2

      for (let i = 0; i < count; i++) {
        toast.loading(`AI가 블로그를 생성하고 있습니다... (${i}/${count})`, {
          id: loadingToast,
          description: `${i + 1}번째 원고 생성 중... (약 30초 소요)`
        })

        try {
          const post = await postsAPI.create({
            original_content: processedContent,
            persuasion_level: config.persuasion_level,
            framework: config.framework,
            target_length: config.target_length,
            writing_perspective: config.writing_perspective,
            ai_provider: config.ai_provider,
            ai_model: config.ai_model,
            writing_style: writingStyle,
            requirements: requirements,
            seo_optimization: seoOptimization.enabled ? seoOptimization : undefined,
            top_post_rules: topPostRules || undefined,
          })

          // 성공 시
          setGenerationProgress(prev => {
            const newCompleted = prev.completed + 1
            toast.loading(`AI가 블로그를 생성하고 있습니다... (${newCompleted}/${count})`, {
              id: loadingToast,
              description: `✅ ${newCompleted}개 완료 | ⏳ ${count - newCompleted}개 남음`
            })
            return { ...prev, completed: newCompleted }
          })
          results.push({ success: true, post, index: i })
          retryCount = 0 // 성공하면 재시도 카운트 리셋

          // 다음 요청 전 잠시 대기 (서버 안정화)
          if (i < count - 1) {
            await new Promise(resolve => setTimeout(resolve, 2000))
          }
        } catch (error: any) {
          const errorMsg = error.response?.data?.detail || error.message || '생성 실패'
          const isServerError = error.response?.status >= 500 || errorMsg.includes('timeout') || errorMsg.includes('network')

          // 서버 오류인 경우 재시도
          if (isServerError && retryCount < MAX_RETRIES) {
            retryCount++
            toast.loading(`서버 오류 발생, ${retryCount}번째 재시도 중...`, {
              id: loadingToast,
              description: `5초 후 다시 시도합니다`
            })
            await new Promise(resolve => setTimeout(resolve, 5000))
            i-- // 같은 인덱스 재시도
            continue
          }

          // 실패 기록
          setGenerationProgress(prev => {
            const newFailed = prev.failed + 1
            return {
              ...prev,
              failed: newFailed,
              errors: [...prev.errors, `원고 ${i + 1}: ${errorMsg}`]
            }
          })
          results.push({ success: false, error: errorMsg, index: i })
          retryCount = 0

          // 실패해도 다음 원고 진행 (잠시 대기 후)
          if (i < count - 1) {
            await new Promise(resolve => setTimeout(resolve, 3000))
          }
        }
      }

      // 성공한 원고들만 필터링
      const successfulPosts = results
        .filter((r): r is { success: true; post: Post; index: number } => r.success)
        .map(r => r.post)

      if (successfulPosts.length === 0) {
        throw new Error('모든 원고 생성에 실패했습니다')
      }

      setGeneratedPosts(successfulPosts)
      setGeneratedPost(successfulPosts[0])
      setSelectedPostIndex(0)

      // Clear auto-saved draft after successful generation
      clearSaved()

      const failedCount = results.filter(r => !r.success).length

      if (failedCount > 0) {
        // 일부 실패
        toast.warning(`블로그 생성 완료 (일부 실패)`, {
          id: loadingToast,
          description: `✅ ${successfulPosts.length}개 성공 | ❌ ${failedCount}개 실패`
        })
      } else {
        // 모두 성공
        toast.success(`블로그 ${count}개 생성 완료!`, {
          id: loadingToast,
          description: `평균 설득력 점수: ${Math.round(successfulPosts.reduce((sum, p) => sum + p.persuasion_score, 0) / successfulPosts.length)}점`
        })
      }
    } catch (error: any) {
      console.error('Generation error:', error)
      toast.error('포스팅 생성 실패', {
        id: loadingToast,
        description: error.message || error.response?.data?.detail || '오류가 발생했습니다'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = () => {
    if (!generatedPost) return

    // 로컬 스토리지에 저장
    try {
      const savedPost = {
        ...generatedPost,
        id: `post-${Date.now()}`,
        savedAt: new Date().toISOString(),
      }

      const existing = localStorage.getItem('saved-posts')
      const posts = existing ? JSON.parse(existing) : []
      const updated = [savedPost, ...posts]
      localStorage.setItem('saved-posts', JSON.stringify(updated))

      toast.success('글이 저장되었습니다', {
        description: '저장된 글 탭에서 확인하세요',
      })

      // 저장된 글 페이지로 이동
      router.push('/dashboard/saved')
    } catch (error) {
      console.error('저장 실패:', error)
      toast.error('글 저장에 실패했습니다')
    }
  }

  const handleDownloadWord = async () => {
    if (!generatedPost) return

    try {
      // Create document sections
      const sections = []

      // Add title
      sections.push(
        new Paragraph({
          children: [
            new TextRun({
              text: generatedPost.title || '제목 없음',
              bold: true,
              size: 32, // 16pt
            }),
          ],
          spacing: { after: 400 },
        })
      )

      // Add metadata
      if (generatedPost.persuasion_score) {
        sections.push(
          new Paragraph({
            children: [
              new TextRun({
                text: `설득력 점수: ${Math.round(generatedPost.persuasion_score)}점`,
                italics: true,
                size: 20, // 10pt
              }),
            ],
            spacing: { after: 200 },
          })
        )
      }

      // Add a separator
      sections.push(
        new Paragraph({
          children: [new TextRun({ text: '―――――――――――――――――――――――――――――' })],
          spacing: { after: 400 },
        })
      )

      // Split content by paragraphs and add them
      const contentParagraphs = (generatedPost.generated_content || '').split('\n')
      contentParagraphs.forEach((para) => {
        sections.push(
          new Paragraph({
            children: [
              new TextRun({
                text: para || ' ',
                size: 22, // 11pt
              }),
            ],
            spacing: { after: 200 },
          })
        )
      })

      // Add hashtags if available
      if (generatedPost.hashtags && generatedPost.hashtags.length > 0) {
        sections.push(
          new Paragraph({
            children: [new TextRun({ text: '' })],
            spacing: { after: 400 },
          })
        )
        sections.push(
          new Paragraph({
            children: [
              new TextRun({
                text: '추천 해시태그',
                bold: true,
                size: 24, // 12pt
              }),
            ],
            spacing: { after: 200 },
          })
        )
        sections.push(
          new Paragraph({
            children: [
              new TextRun({
                text: generatedPost.hashtags.slice(0, 10).join(' '),
                size: 20,
              }),
            ],
          })
        )
      }

      // Create document
      const doc = new Document({
        sections: [
          {
            properties: {},
            children: sections,
          },
        ],
      })

      // Generate and download
      const blob = await Packer.toBlob(doc)
      const fileName = `${generatedPost.title || '블로그'}_${new Date().toISOString().slice(0, 10)}.docx`
      saveAs(blob, fileName)

      toast.success('Word 파일 다운로드 완료')
    } catch (error) {
      console.error('Word 파일 생성 실패:', error)
      toast.error('Word 파일 다운로드 실패')
    }
  }

  const handleDownloadText = () => {
    if (!generatedPost) return

    try {
      // Create text content
      let textContent = `${generatedPost.title || '제목 없음'}\n\n`

      if (generatedPost.persuasion_score) {
        textContent += `설득력 점수: ${Math.round(generatedPost.persuasion_score)}점\n\n`
      }

      textContent += `${'='.repeat(50)}\n\n`
      textContent += `${generatedPost.generated_content || ''}\n\n`

      if (generatedPost.hashtags && generatedPost.hashtags.length > 0) {
        textContent += `\n추천 해시태그\n`
        textContent += generatedPost.hashtags.slice(0, 10).join(' ')
      }

      // Create blob and download
      const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' })
      const fileName = `${generatedPost.title || '블로그'}_${new Date().toISOString().slice(0, 10)}.txt`
      saveAs(blob, fileName)

      toast.success('텍스트 파일 다운로드 완료')
    } catch (error) {
      console.error('텍스트 파일 생성 실패:', error)
      toast.error('텍스트 파일 다운로드 실패')
    }
  }

  const handleTitleSelect = (title: string) => {
    if (generatedPost) {
      setGeneratedPost({
        ...generatedPost,
        title,
      })
    }
  }

  const formatLastSaved = (date: Date | null) => {
    if (!date) return null
    const now = new Date()
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
    if (diff < 10) return '방금 전'
    if (diff < 60) return `${diff}초 전`
    if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
    return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
  }

  // 블로그 URL에서 글 가져오기
  const handleCrawlBlog = async () => {
    if (!blogUrl.trim()) {
      toast.error('블로그 URL을 입력해주세요')
      return
    }

    setCrawling(true)
    const loadingToast = toast.loading('블로그 글을 가져오는 중...', {
      description: '잠시만 기다려주세요'
    })

    try {
      const result = await crawlAPI.crawlBlog(blogUrl)

      if (result.success && result.content) {
        setOriginalContent(result.content)

        // 이미지 저장
        if (result.images && result.images.length > 0) {
          setCrawledImages(result.images)
          toast.success('블로그 글을 가져왔습니다', {
            id: loadingToast,
            description: `${result.platform} | ${result.content.length}자 | 이미지 ${result.images.length}개`
          })
        } else {
          setCrawledImages([])
          toast.success('블로그 글을 가져왔습니다', {
            id: loadingToast,
            description: `${result.platform} | ${result.content.length}자`
          })
        }

        // 제목이 있으면 알려줌
        if (result.title) {
          toast.info(`제목: ${result.title}`, {
            duration: 5000
          })
        }

        // URL 초기화
        setBlogUrl('')
      } else {
        throw new Error(result.error || '블로그 글을 가져오지 못했습니다')
      }
    } catch (error: any) {
      console.error('Crawl error:', error)
      toast.error('블로그 글 가져오기 실패', {
        id: loadingToast,
        description: error.response?.data?.detail || error.message || '알 수 없는 오류'
      })
    } finally {
      setCrawling(false)
    }
  }

  // 이미지 다운로드
  const handleDownloadImage = async (imageUrl: string, index: number) => {
    try {
      const response = await fetch(imageUrl)
      const blob = await response.blob()
      const extension = imageUrl.split('.').pop()?.split('?')[0] || 'jpg'
      const filename = `image_${index + 1}.${extension}`
      saveAs(blob, filename)
      toast.success(`이미지 ${index + 1} 다운로드 완료`)
    } catch (error) {
      toast.error('이미지 다운로드 실패')
    }
  }

  // 모든 이미지 다운로드
  const handleDownloadAllImages = async () => {
    toast.loading('이미지 다운로드 중...')
    for (let i = 0; i < crawledImages.length; i++) {
      await handleDownloadImage(crawledImages[i].url, i)
      // 연속 다운로드 시 딜레이
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    toast.success(`${crawledImages.length}개 이미지 다운로드 완료`)
  }

  // 원클릭 자동화: URL → 크롤링 → AI 리라이트 → 네이버 임시저장
  const handleOneClickAutomation = async () => {
    if (!blogUrl.trim()) {
      toast.error('블로그 URL을 입력해주세요')
      return
    }

    setOneClickProcessing(true)
    setOneClickResult(null)

    const loadingToast = toast.loading('원클릭 자동화 진행 중...', {
      description: '1/3 블로그 글 크롤링 중...'
    })

    try {
      // 진행 상태 업데이트
      setTimeout(() => {
        toast.loading('원클릭 자동화 진행 중...', {
          id: loadingToast,
          description: '2/3 AI 리라이트 중...'
        })
      }, 3000)

      setTimeout(() => {
        toast.loading('원클릭 자동화 진행 중...', {
          id: loadingToast,
          description: '3/3 네이버 블로그 임시저장 중...'
        })
      }, 8000)

      const result = await crawlAPI.oneClick({
        url: blogUrl,
        ai_provider: 'gpt',
        ai_model: 'gpt-4o-mini',
        target_length: 1800,
        framework: '관심유도형',
        persuasion_level: 4
      })

      setOneClickResult(result)

      if (result.success) {
        toast.success('원클릭 자동화 완료!', {
          id: loadingToast,
          description: '네이버 블로그에 임시저장되었습니다'
        })

        // 이미지가 있으면 표시
        if (result.images && result.images.length > 0) {
          setCrawledImages(result.images)
        }

        // URL 초기화
        setBlogUrl('')
      } else {
        toast.error('원클릭 자동화 실패', {
          id: loadingToast,
          description: result.error || '알 수 없는 오류'
        })
      }
    } catch (error: any) {
      console.error('One-click error:', error)
      toast.error('원클릭 자동화 실패', {
        id: loadingToast,
        description: error.response?.data?.detail || error.message || '알 수 없는 오류'
      })
    } finally {
      setOneClickProcessing(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">AI 글 작성</h1>
          <p className="text-muted-foreground">
            블로그 글과 카페 바이럴 후기를 AI로 쉽게 작성하세요
          </p>
        </div>
        {lastSaved && !generatedPost && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>마지막 저장: {formatLastSaved(lastSaved)}</span>
          </div>
        )}
      </div>

      <Tabs defaultValue="blog" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="blog" className="gap-2">
            <PenTool className="h-4 w-4" />
            블로그 작성
          </TabsTrigger>
          <TabsTrigger value="cafe-review" className="gap-2">
            <Coffee className="h-4 w-4" />
            카페 바이럴 후기
          </TabsTrigger>
        </TabsList>

        <TabsContent value="blog" className="space-y-6 mt-6">{/* Blog content starts here */}

      {/* GPT API Status - 관리자만 표시 */}
      {currentUser?.is_admin && (checkingGptApi ? (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <div>
              <p className="font-medium text-blue-900">GPT API 연결 확인 중...</p>
              <p className="text-sm text-blue-700">잠시만 기다려주세요</p>
            </div>
          </CardContent>
        </Card>
      ) : gptApiStatus?.connected ? (
        <Card className="bg-green-50 border-green-200">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div className="flex-1">
              <p className="font-medium text-green-900">GPT API 연결됨</p>
              <p className="text-sm text-green-700">
                API 키: {gptApiStatus.api_key_prefix} | 모델: {gptApiStatus.model}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div className="flex-1">
              <p className="font-medium text-red-900">GPT API 연결 실패</p>
              <p className="text-sm text-red-700">
                {gptApiStatus?.error || 'API 키를 확인해주세요'}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Gemini API Status - 관리자만 표시 */}
      {currentUser?.is_admin && (checkingGeminiApi ? (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <div>
              <p className="font-medium text-blue-900">Gemini API 연결 확인 중...</p>
              <p className="text-sm text-blue-700">잠시만 기다려주세요</p>
            </div>
          </CardContent>
        </Card>
      ) : geminiApiStatus?.connected ? (
        <Card className="bg-green-50 border-green-200">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div className="flex-1">
              <p className="font-medium text-green-900">Gemini API 연결됨</p>
              <p className="text-sm text-green-700">
                API 키: {geminiApiStatus.api_key_prefix} | 모델: {geminiApiStatus.model}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-yellow-50 border-yellow-200">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-yellow-600" />
            <div className="flex-1">
              <p className="font-medium text-yellow-900">Gemini API 미연결</p>
              <p className="text-sm text-yellow-700">
                {geminiApiStatus?.error || 'GEMINI_API_KEY를 설정하면 사용 가능'}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}

      {/* AI 사용량 및 비용 현황 - 관리자만 표시 */}
      {currentUser?.is_admin && aiUsageStats && (
        <Card className="bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
          <CardContent className="py-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-xs text-gray-500">오늘 사용</p>
                  <p className="text-lg font-bold text-purple-700">
                    {aiUsageStats.today?.requests || 0}건 / ₩{(aiUsageStats.today?.cost_krw || 0).toLocaleString()}
                  </p>
                </div>
                <div className="h-8 w-px bg-gray-300" />
                <div>
                  <p className="text-xs text-gray-500">이번달 누적</p>
                  <p className="text-lg font-bold text-blue-700">
                    {aiUsageStats.this_month?.requests || 0}건 / ₩{(aiUsageStats.this_month?.cost_krw || 0).toLocaleString()}
                  </p>
                </div>
                <div className="h-8 w-px bg-gray-300" />
                <div>
                  <p className="text-xs text-gray-500">전체 누적</p>
                  <p className="text-lg font-bold text-gray-700">
                    {aiUsageStats.total?.requests || 0}건 / ₩{(aiUsageStats.total?.cost_krw || 0).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">선택한 모델 예상 비용</p>
                <p className="text-lg font-bold text-green-700">
                  {(() => {
                    const modelPricing = aiPricing?.pricing?.find((p: any) => p.model_id === config.ai_model)
                    return modelPricing
                      ? `₩${Math.round(modelPricing.estimated_cost_per_post_krw * config.count).toLocaleString()}`
                      : '계산 중...'
                  })()}
                  <span className="text-xs font-normal text-gray-500"> / {config.count}건</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* AI 제공자 선택 */}
      <Card>
        <CardHeader>
          <CardTitle>AI 제공자 선택</CardTitle>
          <CardDescription>사용할 AI를 선택하고 모델을 선택하세요</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>AI 제공자</Label>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant={config.ai_provider === 'gpt' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setConfig({
                    ...config,
                    ai_provider: 'gpt',
                    ai_model: 'gpt-4o-mini'
                  })
                }}
              >
                GPT (OpenAI)
              </Button>
              <Button
                variant={config.ai_provider === 'gemini' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setConfig({
                    ...config,
                    ai_provider: 'gemini',
                    ai_model: 'gemini-2.0-flash'
                  })
                }}
                disabled={!geminiApiStatus?.connected}
              >
                Gemini (Google) {!geminiApiStatus?.connected && '(미연결)'}
              </Button>
            </div>
          </div>

          {/* GPT 모델 선택 */}
          {config.ai_provider === 'gpt' && (
            <div className="space-y-2">
              <Label>GPT 모델</Label>
              <div className="grid grid-cols-1 gap-2">
                <Button
                  variant={config.ai_model === 'gpt-4o-mini' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setConfig({ ...config, ai_model: 'gpt-4o-mini' })}
                >
                  GPT-4o Mini (빠름)
                </Button>
              </div>
            </div>
          )}

          {/* Gemini 모델 선택 */}
          {config.ai_provider === 'gemini' && (
            <div className="space-y-2">
              <Label>Gemini 모델</Label>
              <div className="grid grid-cols-1 gap-2">
                <Button
                  variant={config.ai_model === 'gemini-2.0-flash' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setConfig({ ...config, ai_model: 'gemini-2.0-flash' })}
                >
                  Gemini 2.0 Flash (추천)
                </Button>
                <Button
                  variant={config.ai_model === 'gemini-1.5-pro' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setConfig({ ...config, ai_model: 'gemini-1.5-pro' })}
                >
                  Gemini 1.5 Pro (고성능)
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>원본 의료 정보</CardTitle>
              <CardDescription>변환할 의료 정보를 입력하거나 블로그 URL에서 가져오세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 블로그 URL 가져오기 */}
              <div className="space-y-2 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2 text-sm font-medium text-blue-900">
                  <Link className="h-4 w-4" />
                  블로그 글 가져오기
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="블로그 URL 입력 (네이버, 티스토리 등)"
                    value={blogUrl}
                    onChange={(e) => setBlogUrl(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !crawling) {
                        handleCrawlBlog()
                      }
                    }}
                    disabled={crawling}
                    className="flex-1"
                  />
                  <Button
                    onClick={handleCrawlBlog}
                    disabled={crawling || !blogUrl.trim()}
                    variant="default"
                    size="default"
                  >
                    {crawling ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        가져오는 중...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4 mr-2" />
                        가져오기
                      </>
                    )}
                  </Button>
                </div>
                <div className="flex gap-2 pt-2">
                  <Button
                    onClick={handleOneClickAutomation}
                    disabled={oneClickProcessing || crawling || !blogUrl.trim()}
                    className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700"
                  >
                    {oneClickProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        처리 중...
                      </>
                    ) : (
                      <>
                        <Zap className="h-4 w-4 mr-2" />
                        원클릭 자동화
                      </>
                    )}
                  </Button>
                </div>
                <p className="text-xs text-blue-700">
                  <strong>원클릭 자동화:</strong> URL 입력 → 글+이미지 크롤링 → AI 리라이트 → 네이버 블로그 임시저장까지 한번에!
                </p>
              </div>

              {/* 원클릭 결과 표시 */}
              {oneClickResult && oneClickResult.success && (
                <div className="space-y-3 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-purple-900">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      원클릭 자동화 완료
                    </div>
                    <Button
                      onClick={() => setOneClickResult(null)}
                      variant="ghost"
                      size="sm"
                      className="text-gray-500 hover:text-gray-700"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-white p-2 rounded border">
                      <div className="text-gray-500 text-xs">원본</div>
                      <div className="font-medium truncate">{oneClickResult.original_title}</div>
                      <div className="text-xs text-gray-400">{oneClickResult.original_content_length}자</div>
                    </div>
                    <div className="bg-white p-2 rounded border">
                      <div className="text-gray-500 text-xs">리라이트</div>
                      <div className="font-medium truncate">{oneClickResult.rewritten_title}</div>
                      <div className="text-xs text-gray-400">{oneClickResult.rewritten_content_length}자</div>
                    </div>
                  </div>

                  {oneClickResult.naver_post_url && (
                    <a
                      href={oneClickResult.naver_post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 p-3 bg-green-100 text-green-800 rounded-lg hover:bg-green-200 transition-colors"
                    >
                      <ExternalLink className="h-4 w-4" />
                      <span className="font-medium">네이버 블로그에서 확인하기 (임시저장됨)</span>
                    </a>
                  )}

                  {oneClickResult.images_count && oneClickResult.images_count > 0 && (
                    <p className="text-xs text-purple-700">
                      이미지 {oneClickResult.images_count}개가 추출되었습니다. 아래에서 다운로드 후 블로그에 수동 첨부해주세요.
                    </p>
                  )}
                </div>
              )}

              {/* 가져온 이미지 표시 */}
              {crawledImages.length > 0 && (
                <div className="space-y-3 p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-green-900">
                      <ImageIcon className="h-4 w-4" />
                      가져온 이미지 ({crawledImages.length}개)
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={handleDownloadAllImages}
                        variant="outline"
                        size="sm"
                        className="text-green-700 border-green-300 hover:bg-green-100"
                      >
                        <Download className="h-3 w-3 mr-1" />
                        전체 다운로드
                      </Button>
                      <Button
                        onClick={() => setCrawledImages([])}
                        variant="ghost"
                        size="sm"
                        className="text-gray-500 hover:text-gray-700"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto">
                    {crawledImages.map((img, index) => (
                      <div
                        key={index}
                        className="relative group cursor-pointer rounded-lg overflow-hidden border border-green-200 bg-white"
                        onClick={() => handleDownloadImage(img.url, index)}
                      >
                        <img
                          src={img.url}
                          alt={img.alt || `이미지 ${index + 1}`}
                          className="w-full h-20 object-cover"
                          onError={(e) => {
                            // 이미지 로드 실패 시 플레이스홀더
                            (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="%23f3f4f6" width="100" height="100"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="12">No Image</text></svg>'
                          }}
                        />
                        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-all flex items-center justify-center">
                          <Download className="h-5 w-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                        <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 text-center truncate">
                          {img.caption || `이미지 ${index + 1}`}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-green-700">
                    이미지를 클릭하면 개별 다운로드됩니다. 이미지는 블로그 발행 시 별도로 첨부해주세요.
                  </p>
                </div>
              )}

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-muted-foreground">또는 직접 입력</span>
                </div>
              </div>

              <Textarea
                placeholder="예시: 퇴행성 관절염은 관절 연골의 손상으로 발생합니다. 주요 증상은 통증, 부종, 관절 운동 제한입니다..."
                className="min-h-[300px] resize-none"
                value={originalContent}
                onChange={(e) => setOriginalContent(e.target.value)}
              />
              <div className="text-sm text-muted-foreground">
                {originalContent.length}자 / 최소 50자
              </div>

              {/* 주제 변환 옵션 */}
              <div className="space-y-3 pt-4 border-t">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="topicConversion"
                    checked={topicConversion.enabled}
                    onChange={(e) => setTopicConversion({ ...topicConversion, enabled: e.target.checked })}
                    className="rounded"
                  />
                  <Label htmlFor="topicConversion" className="cursor-pointer">
                    주제 변환 (예: 아토피 → 건선)
                  </Label>
                </div>

                {topicConversion.enabled && (
                  <div className="grid grid-cols-2 gap-2 pl-6">
                    <Input
                      placeholder="변환 전 (예: 아토피)"
                      value={topicConversion.from}
                      onChange={(e) => setTopicConversion({ ...topicConversion, from: e.target.value })}
                    />
                    <Input
                      placeholder="변환 후 (예: 건선)"
                      value={topicConversion.to}
                      onChange={(e) => setTopicConversion({ ...topicConversion, to: e.target.value })}
                    />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>각색 설정</CardTitle>
              <CardDescription>원하는 스타일을 선택하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>각색 레벨</Label>
                <div className="grid grid-cols-5 gap-2">
                  {[1, 2, 3, 4, 5].map((level) => (
                    <Button
                      key={level}
                      variant={config.persuasion_level === level ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, persuasion_level: level })}
                    >
                      {level}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  1: 정보전달 | 3: 공감유도 | 5: 스토리 극대화
                </p>
              </div>

              <div className="space-y-2">
                <Label>설득 프레임워크</Label>
                <div className="grid grid-cols-2 gap-2">
                  {['관심유도형', '공감해결형', '스토리형', '질문답변형', '정보전달형', '경험공유형'].map((framework) => (
                    <Button
                      key={framework}
                      variant={config.framework === framework ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, framework })}
                    >
                      {framework}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>목표 글자수</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      min={500}
                      max={2800}
                      step={100}
                      value={config.target_length}
                      onChange={(e) => {
                        const value = parseInt(e.target.value) || 500
                        const clampedValue = Math.max(500, Math.min(2800, value))
                        setConfig({ ...config, target_length: clampedValue })
                      }}
                      className="w-24 h-8 text-sm"
                    />
                    <span className="text-sm text-muted-foreground">자</span>
                  </div>
                </div>
                <Slider
                  value={[config.target_length]}
                  onValueChange={(value) => setConfig({ ...config, target_length: value[0] })}
                  min={500}
                  max={2800}
                  step={100}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>500자 (짧게)</span>
                  <span>1,650자 (보통)</span>
                  <span>2,800자 (길게)</span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <Button
                    variant={config.target_length === 1200 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 1200 })}
                  >
                    짧게 (1200)
                  </Button>
                  <Button
                    variant={config.target_length === 1800 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 1800 })}
                  >
                    보통 (1800)
                  </Button>
                  <Button
                    variant={config.target_length === 2400 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 2400 })}
                  >
                    길게 (2400)
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>작성 시점</Label>
                <div className="grid grid-cols-3 gap-2">
                  {['1인칭', '3인칭', '대화형'].map((perspective) => (
                    <Button
                      key={perspective}
                      variant={config.writing_perspective === perspective ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, writing_perspective: perspective })}
                    >
                      {perspective}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  1인칭: 원장이 직접 | 3인칭: 객관적 전문가 | 대화형: 친근한 대화
                </p>
              </div>

              <div className="space-y-2">
                <Label>생성 개수</Label>
                <div className="grid grid-cols-5 gap-2">
                  {[1, 2, 3, 4, 5].map((count) => (
                    <Button
                      key={count}
                      variant={config.count === count ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, count })}
                    >
                      {count}개
                    </Button>
                  ))}
                </div>
                <div className="grid grid-cols-5 gap-2">
                  {[6, 7, 8, 9, 10].map((count) => (
                    <Button
                      key={count}
                      variant={config.count === count ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, count })}
                    >
                      {count}개
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  순차 처리로 안정적 생성 (1개당 약 30초, 오류 시 자동 재시도)
                </p>
              </div>

              {/* 검색 최적화 (DIA/CRANK) */}
              <div className="space-y-3 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="seoOptimization"
                      checked={seoOptimization.enabled}
                      onChange={(e) => setSeoOptimization({ ...seoOptimization, enabled: e.target.checked })}
                      className="rounded"
                    />
                    <Label htmlFor="seoOptimization" className="cursor-pointer font-semibold">
                      🔍 검색 최적화 (DIA/CRANK)
                    </Label>
                  </div>
                  <span className="text-xs text-muted-foreground">네이버 상위노출</span>
                </div>

                {seoOptimization.enabled && (
                  <div className="pl-6 space-y-2">
                    <p className="text-xs text-muted-foreground mb-3">
                      네이버 검색 알고리즘(DIA/CRANK)에 최적화된 콘텐츠로 작성합니다
                    </p>

                    <div className="grid grid-cols-1 gap-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="experience_focus"
                          checked={seoOptimization.experience_focus}
                          onChange={(e) => setSeoOptimization({ ...seoOptimization, experience_focus: e.target.checked })}
                          className="rounded"
                        />
                        <Label htmlFor="experience_focus" className="cursor-pointer text-sm">
                          실제 경험 중심 작성 <span className="text-xs text-muted-foreground">(DIA: 경험 정보)</span>
                        </Label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="expertise"
                          checked={seoOptimization.expertise}
                          onChange={(e) => setSeoOptimization({ ...seoOptimization, expertise: e.target.checked })}
                          className="rounded"
                        />
                        <Label htmlFor="expertise" className="cursor-pointer text-sm">
                          전문성과 깊이 강화 <span className="text-xs text-muted-foreground">(C-Rank: Content)</span>
                        </Label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="originality"
                          checked={seoOptimization.originality}
                          onChange={(e) => setSeoOptimization({ ...seoOptimization, originality: e.target.checked })}
                          className="rounded"
                        />
                        <Label htmlFor="originality" className="cursor-pointer text-sm">
                          독창성 강조 <span className="text-xs text-muted-foreground">(DIA: 독창성)</span>
                        </Label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="timeliness"
                          checked={seoOptimization.timeliness}
                          onChange={(e) => setSeoOptimization({ ...seoOptimization, timeliness: e.target.checked })}
                          className="rounded"
                        />
                        <Label htmlFor="timeliness" className="cursor-pointer text-sm">
                          적시성 반영 <span className="text-xs text-muted-foreground">(DIA: 적시성)</span>
                        </Label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="topic_concentration"
                          checked={seoOptimization.topic_concentration}
                          onChange={(e) => setSeoOptimization({ ...seoOptimization, topic_concentration: e.target.checked })}
                          className="rounded"
                        />
                        <Label htmlFor="topic_concentration" className="cursor-pointer text-sm">
                          주제 집중도 향상 <span className="text-xs text-muted-foreground">(C-Rank: Context)</span>
                        </Label>
                      </div>
                    </div>

                    {/* 2025년 9월 네이버 AI 검색 업데이트 반영 */}
                    <div className="mt-4 pt-4 border-t border-dashed">
                      <p className="text-xs font-semibold text-blue-700 mb-3 flex items-center gap-1">
                        🆕 2025 네이버 AI 검색 업데이트 반영 (HyperClova X 기반)
                      </p>

                      <div className="grid grid-cols-1 gap-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="trustworthiness"
                            checked={seoOptimization.trustworthiness}
                            onChange={(e) => setSeoOptimization({ ...seoOptimization, trustworthiness: e.target.checked })}
                            className="rounded"
                          />
                          <Label htmlFor="trustworthiness" className="cursor-pointer text-sm">
                            신뢰성 강화 <span className="text-xs text-muted-foreground">(출처 명시, 의학적 근거)</span>
                          </Label>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="source_authority"
                            checked={seoOptimization.source_authority}
                            onChange={(e) => setSeoOptimization({ ...seoOptimization, source_authority: e.target.checked })}
                            className="rounded"
                          />
                          <Label htmlFor="source_authority" className="cursor-pointer text-sm">
                            출처 권위성 <span className="text-xs text-muted-foreground">(공공기관 77%↑, 학술기관 30%↑)</span>
                          </Label>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="multi_perspective"
                            checked={seoOptimization.multi_perspective}
                            onChange={(e) => setSeoOptimization({ ...seoOptimization, multi_perspective: e.target.checked })}
                            className="rounded"
                          />
                          <Label htmlFor="multi_perspective" className="cursor-pointer text-sm">
                            다각도 정보 제공 <span className="text-xs text-muted-foreground">(AI 편향/환각 방지)</span>
                          </Label>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="search_intent_match"
                            checked={seoOptimization.search_intent_match}
                            onChange={(e) => setSeoOptimization({ ...seoOptimization, search_intent_match: e.target.checked })}
                            className="rounded"
                          />
                          <Label htmlFor="search_intent_match" className="cursor-pointer text-sm">
                            검색 의도 충족 <span className="text-xs text-muted-foreground">(뉴럴 매칭 최적화)</span>
                          </Label>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 네이버 상위노출 분석 */}
              {seoOptimization.enabled && (
                <div className="pt-2">
                  <TopPostAnalyzer
                    onRulesGenerated={(rules) => {
                      setTopPostRules(rules)
                      if (rules) {
                        // 규칙이 생성되면 target_length를 자동 조정
                        setConfig(prev => ({
                          ...prev,
                          target_length: Math.min(2800, Math.max(500, rules.content.length.optimal))
                        }))
                      }
                    }}
                  />
                </div>
              )}

              <Button
                className="w-full gap-2"
                size="lg"
                onClick={handleGenerate}
                disabled={loading || originalContent.length < 50}
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    AI 생성 중... (30초 소요)
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    블로그 생성하기
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          <WritingStyleConfig value={writingStyle} onChange={setWritingStyle} />

          <RequestRequirementsInput value={requirements} onChange={setRequirements} />

          {/* 진행률 표시 */}
          {loading && generationProgress.total > 0 && (
            <Card className="border-blue-200 bg-blue-50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  생성 진행 중
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>완료: {generationProgress.completed - generationProgress.failed}/{generationProgress.total}</span>
                    <span>{Math.round(((generationProgress.completed - generationProgress.failed) / generationProgress.total) * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${((generationProgress.completed - generationProgress.failed) / generationProgress.total) * 100}%` }}
                    />
                  </div>
                </div>

                {generationProgress.failed > 0 && (
                  <div className="text-sm text-red-600">
                    <p className="font-medium">❌ 실패: {generationProgress.failed}개</p>
                  </div>
                )}

                {generationProgress.errors.length > 0 && (
                  <div className="text-xs space-y-1">
                    <p className="font-medium text-red-700">오류 내역:</p>
                    {generationProgress.errors.map((error, idx) => (
                      <p key={idx} className="text-red-600 pl-2">• {error}</p>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Output Section */}
        <div className="space-y-6">
          {!generatedPost ? (
            <Card className="border-dashed">
              <CardContent className="pt-6">
                <div className="text-center py-12 text-muted-foreground">
                  <Sparkles className="h-12 w-12 mx-auto mb-3 text-blue-300" />
                  <p>원본 내용을 입력하고 생성하기를 눌러주세요</p>
                  <p className="text-sm mt-2">AI가 자동으로 각색합니다</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* 에러 요약 */}
              {generationProgress.errors.length > 0 && !loading && (
                <Card className="border-red-200 bg-red-50">
                  <CardHeader>
                    <CardTitle className="text-base text-red-900">⚠️ 생성 중 발생한 오류</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-sm text-red-700">
                      {generationProgress.failed}개 원고 생성 실패 ({generatedPosts.length}개는 성공)
                    </p>
                    <div className="text-xs space-y-1 max-h-32 overflow-y-auto">
                      {generationProgress.errors.map((error, idx) => (
                        <p key={idx} className="text-red-600">• {error}</p>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 여러 개 생성된 경우 선택 탭 */}
              {generatedPosts.length > 1 && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Label className="text-sm font-medium">생성된 버전 선택</Label>
                      <span className="text-xs text-muted-foreground">({generatedPosts.length}개)</span>
                    </div>
                    <div className="space-y-2">
                      <div className="grid grid-cols-5 gap-2">
                        {generatedPosts.slice(0, 5).map((post, index) => (
                          <Button
                            key={index}
                            variant={selectedPostIndex === index ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => {
                              setSelectedPostIndex(index)
                              setGeneratedPost(post)
                            }}
                          >
                            버전 {index + 1}
                          </Button>
                        ))}
                      </div>
                      {generatedPosts.length > 5 && (
                        <div className="grid grid-cols-5 gap-2">
                          {generatedPosts.slice(5, 10).map((post, index) => (
                            <Button
                              key={index + 5}
                              variant={selectedPostIndex === index + 5 ? 'default' : 'outline'}
                              size="sm"
                              onClick={() => {
                                setSelectedPostIndex(index + 5)
                                setGeneratedPost(post)
                              }}
                            >
                              버전 {index + 6}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    생성된 포스팅
                    <div className="flex items-center gap-2 text-sm font-normal">
                      <TrendingUp className="h-4 w-4 text-blue-600" />
                      <span className="text-blue-600 font-medium">
                        설득력 {Math.round(generatedPost.persuasion_score)}점
                      </span>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <Label className="text-xs text-muted-foreground">제목</Label>
                    <h3 className="text-lg font-semibold mt-1">{generatedPost.title}</h3>
                  </div>

                  <div>
                    <Label className="text-xs text-muted-foreground">본문</Label>
                    <div className="mt-2 prose prose-sm max-w-none">
                      <div className="whitespace-pre-wrap text-sm leading-relaxed max-h-[400px] overflow-y-auto border rounded-md p-4 bg-gray-50">
                        {generatedPost.generated_content}
                      </div>
                    </div>
                  </div>

                  {/* 분석 결과 섹션 */}
                  <div className="pt-4 border-t">
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                      <Lightbulb className="h-5 w-5 text-yellow-600" />
                      분석 결과
                    </h3>

                    <div className="space-y-4">
                      {/* 1. 글자수 분석 */}
                      {generatedPost.content_analysis && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-blue-600">1️⃣</span> 글자수 분석
                          </h4>
                          <CharacterCount analysis={generatedPost.content_analysis} />
                        </div>
                      )}

                      {/* 2. 키워드 분석 */}
                      {generatedPost.content_analysis?.keywords && generatedPost.content_analysis.keywords.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-green-600">2️⃣</span> 키워드 분석
                          </h4>
                          <KeywordTags keywords={generatedPost.content_analysis.keywords} />
                        </div>
                      )}

                      {/* 3. 제목 제안 */}
                      {generatedPost.suggested_titles && generatedPost.suggested_titles.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-purple-600">3️⃣</span> 제목 제안
                          </h4>
                          <TitleSelector
                            titles={generatedPost.suggested_titles}
                            currentTitle={generatedPost.title || ''}
                            onSelect={handleTitleSelect}
                          />
                        </div>
                      )}

                      {/* 4. 소제목 미리보기 */}
                      {generatedPost.suggested_subtitles && generatedPost.suggested_subtitles.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-orange-600">4️⃣</span> 소제목 미리보기
                          </h4>
                          <SubtitlePreview subtitles={generatedPost.suggested_subtitles} />
                        </div>
                      )}

                      {/* 5. 금칙어 검사 */}
                      {generatedPost.forbidden_words_check && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-red-600">5️⃣</span> 금칙어 검사
                          </h4>
                          <ForbiddenWordsAlert forbiddenCheck={generatedPost.forbidden_words_check} />
                        </div>
                      )}

                      {/* 6. DIA/CRANK 점수 */}
                      {generatedPost.dia_crank_analysis && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                            <span className="text-indigo-600">6️⃣</span> DIA/CRANK 점수
                          </h4>
                          <DIACRANKScore analysis={generatedPost.dia_crank_analysis} />
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">추가 정보</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      {generatedPost.medical_law_check?.is_compliant ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-red-600" />
                      )}
                      <Label className="text-sm">의료법 준수</Label>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {generatedPost.medical_law_check?.is_compliant
                        ? '위반 표현이 없습니다'
                        : `${generatedPost.medical_law_check?.total_issues}개 이슈 발견 (자동 수정됨)`}
                    </p>
                  </div>

                  {generatedPost.hashtags && generatedPost.hashtags.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Hash className="h-4 w-4 text-blue-600" />
                        <Label className="text-sm">추천 해시태그</Label>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {generatedPost.hashtags.slice(0, 10).map((tag, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-xs"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {generatedPost.seo_keywords && generatedPost.seo_keywords.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Lightbulb className="h-4 w-4 text-yellow-600" />
                        <Label className="text-sm">SEO 키워드</Label>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {generatedPost.seo_keywords.slice(0, 5).join(', ')}
                      </p>
                    </div>
                  )}

                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        onClick={handleDownloadWord}
                        className="gap-2"
                      >
                        <FileDown className="h-4 w-4" />
                        Word 저장
                      </Button>
                      <Button
                        variant="outline"
                        onClick={handleDownloadText}
                        className="gap-2"
                      >
                        <FileText className="h-4 w-4" />
                        텍스트 저장
                      </Button>
                    </div>
                    <Button className="w-full" variant="outline" onClick={handleSave}>
                      저장하고 상세보기
                    </Button>
                    <OneClickPublish post={generatedPost} />
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
        </TabsContent>

        <TabsContent value="cafe-review" className="space-y-6 mt-6">
          <CafeReviewCreator />
        </TabsContent>
      </Tabs>
    </div>
  )
}
