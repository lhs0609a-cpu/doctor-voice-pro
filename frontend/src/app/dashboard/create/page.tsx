'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { postsAPI } from '@/lib/api'
import type { Post, WritingStyle, RequestRequirements } from '@/types'
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
} from 'lucide-react'
import { Document, Paragraph, TextRun, Packer } from 'docx'
import { saveAs } from 'file-saver'
import { CharacterCount } from '@/components/post/character-count'
import { KeywordTags } from '@/components/post/keyword-tags'
import { TitleSelector } from '@/components/post/title-selector'
import { SubtitlePreview } from '@/components/post/subtitle-preview'
import { ForbiddenWordsAlert } from '@/components/post/forbidden-words-alert'
import { WritingStyleConfig } from '@/components/post/writing-style-config'
import { RequestRequirementsInput } from '@/components/post/request-requirements-input'
import { Slider } from '@/components/ui/slider'
import { Input } from '@/components/ui/input'
import { CafeReviewCreator } from '@/components/cafe-review/cafe-review-creator'

export default function CreatePostPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  const [generatedPost, setGeneratedPost] = useState<Post | null>(null)
  const [generatedPosts, setGeneratedPosts] = useState<Post[]>([])
  const [claudeApiStatus, setClaudeApiStatus] = useState<any>(null)
  const [checkingApi, setCheckingApi] = useState(true)
  const [config, setConfig] = useState({
    persuasion_level: 4,
    framework: '관심유도형',
    target_length: 1500,
    writing_perspective: '1인칭',
    count: 1, // 생성할 원고 개수
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
  const [selectedPostIndex, setSelectedPostIndex] = useState(0)
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
      description: `병렬 처리 시작...`
    })

    try {
      // 주제 변환 처리
      let processedContent = originalContent
      if (topicConversion.enabled) {
        const regex = new RegExp(topicConversion.from, 'gi')
        processedContent = originalContent.replace(regex, topicConversion.to)
      }

      // Rate Limit 방지를 위한 배치 처리
      // 한 번에 3개씩 처리하여 API 제한 회피
      const BATCH_SIZE = 3
      const results: Array<{ success: boolean; post?: Post; error?: string; index: number }> = []

      for (let batchStart = 0; batchStart < count; batchStart += BATCH_SIZE) {
        const batchEnd = Math.min(batchStart + BATCH_SIZE, count)
        const batchSize = batchEnd - batchStart

        toast.loading(`AI가 블로그를 생성하고 있습니다... (${batchStart}/${count})`, {
          id: loadingToast,
          description: `배치 ${Math.floor(batchStart / BATCH_SIZE) + 1} 처리 중... (${batchSize}개)`
        })

        // 현재 배치의 요청들을 병렬로 실행
        const batchPromises = Array.from({ length: batchSize }, (_, i) => {
          const globalIndex = batchStart + i
          return postsAPI.create({
            original_content: processedContent,
            ...config,
            writing_style: writingStyle,
            requirements: requirements,
          })
          .then(post => {
            // 성공 시
            setGenerationProgress(prev => {
              const newCompleted = prev.completed + 1
              toast.loading(`AI가 블로그를 생성하고 있습니다... (${newCompleted}/${count})`, {
                id: loadingToast,
                description: `✅ ${newCompleted}개 완료 | ⏳ ${count - newCompleted}개 진행중`
              })
              return { ...prev, completed: newCompleted }
            })
            return { success: true, post, index: globalIndex }
          })
          .catch(error => {
            // 실패 시 - 개별 원고 실패해도 다른 원고는 계속 진행
            const errorMsg = error.response?.data?.detail || error.message || '생성 실패'
            setGenerationProgress(prev => {
              const newFailed = prev.failed + 1
              const newCompleted = prev.completed + 1
              toast.loading(`AI가 블로그를 생성하고 있습니다... (${newCompleted}/${count})`, {
                id: loadingToast,
                description: `✅ ${prev.completed}개 완료 | ❌ ${newFailed}개 실패 | ⏳ ${count - newCompleted}개 진행중`
              })
              return {
                ...prev,
                completed: newCompleted,
                failed: newFailed,
                errors: [...prev.errors, `원고 ${globalIndex + 1}: ${errorMsg}`]
              }
            })
            return { success: false, error: errorMsg, index: globalIndex }
          })
        })

        // 현재 배치 완료 대기
        const batchResults = await Promise.all(batchPromises)
        results.push(...batchResults)

        // 다음 배치 전에 짧은 딜레이 (Rate Limit 방지)
        if (batchEnd < count) {
          await new Promise(resolve => setTimeout(resolve, 1000))
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
    if (generatedPost) {
      router.push(`/dashboard/posts/${generatedPost.id}`)
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

      {/* Claude API Status */}
      {checkingApi ? (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <div>
              <p className="font-medium text-blue-900">Claude AI 연결 확인 중...</p>
              <p className="text-sm text-blue-700">잠시만 기다려주세요</p>
            </div>
          </CardContent>
        </Card>
      ) : claudeApiStatus?.connected ? (
        <Card className="bg-green-50 border-green-200">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div className="flex-1">
              <p className="font-medium text-green-900">Claude AI 연결됨</p>
              <p className="text-sm text-green-700">
                API 키: {claudeApiStatus.api_key_prefix} | 모델: {claudeApiStatus.model}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div className="flex-1">
              <p className="font-medium text-red-900">Claude AI 연결 실패</p>
              <p className="text-sm text-red-700">
                {claudeApiStatus?.error || 'API 키를 확인해주세요'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>원본 의료 정보</CardTitle>
              <CardDescription>변환할 의료 정보를 입력하세요 (최소 50자)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
                      max={5000}
                      step={100}
                      value={config.target_length}
                      onChange={(e) => {
                        const value = parseInt(e.target.value) || 500
                        const clampedValue = Math.max(500, Math.min(5000, value))
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
                  max={5000}
                  step={100}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>500자 (짧게)</span>
                  <span>2,750자 (보통)</span>
                  <span>5,000자 (길게)</span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <Button
                    variant={config.target_length === 1000 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 1000 })}
                  >
                    짧게 (1000)
                  </Button>
                  <Button
                    variant={config.target_length === 1500 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 1500 })}
                  >
                    보통 (1500)
                  </Button>
                  <Button
                    variant={config.target_length === 2000 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setConfig({ ...config, target_length: 2000 })}
                  >
                    길게 (2000)
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
                <Label>생성 개수 (병렬 처리로 빠르게!)</Label>
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
                  배치 처리로 안정적 생성 (3개씩 묶음 처리, Rate Limit 방지)
                </p>
              </div>

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
                    <Button className="w-full" onClick={handleSave}>
                      저장하고 상세보기
                    </Button>
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
