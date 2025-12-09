'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { postsAPI } from '@/lib/api'
import type { Post } from '@/types'
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
} from 'lucide-react'

export default function CreatePostPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [originalContent, setOriginalContent] = useState('')
  const [generatedPost, setGeneratedPost] = useState<Post | null>(null)
  const [config, setConfig] = useState({
    persuasion_level: 4,
    framework: '관심유도형',
    target_length: 1500,
    writing_perspective: '1인칭',
  })

  // Auto-save hook
  const { lastSaved, loadSaved, clearSaved } = useAutoSave({
    key: 'draft-post-create',
    data: { originalContent, config },
    delay: 3000,
    enabled: !generatedPost, // Only auto-save before generation
  })

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

    setLoading(true)
    const loadingToast = toast.loading('AI가 블로그를 생성하고 있습니다...', {
      description: '약 30초 정도 소요됩니다'
    })

    try {
      const post = await postsAPI.create({
        original_content: originalContent,
        ...config,
      })
      setGeneratedPost(post)
      // Clear auto-saved draft after successful generation
      clearSaved()
      toast.success('블로그 생성 완료!', {
        id: loadingToast,
        description: `설득력 점수: ${Math.round(post.persuasion_score)}점`
      })
    } catch (error: any) {
      toast.error('포스팅 생성 실패', {
        id: loadingToast,
        description: error.response?.data?.detail || '오류가 발생했습니다'
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
          <h1 className="text-3xl font-bold mb-2">AI 블로그 작성</h1>
          <p className="text-muted-foreground">
            의료 정보를 입력하면 AI가 설득력 있는 블로그 글로 변환합니다
          </p>
        </div>
        {lastSaved && !generatedPost && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>마지막 저장: {formatLastSaved(lastSaved)}</span>
          </div>
        )}
      </div>

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

              <div className="space-y-2">
                <Label>목표 길이</Label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: '짧게', value: 1000 },
                    { label: '보통', value: 1500 },
                    { label: '길게', value: 2500 },
                  ].map((option) => (
                    <Button
                      key={option.value}
                      variant={config.target_length === option.value ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setConfig({ ...config, target_length: option.value })}
                    >
                      {option.label}
                    </Button>
                  ))}
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
                <CardContent className="space-y-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">제목</Label>
                    <h3 className="text-lg font-semibold mt-1">{generatedPost.title}</h3>
                  </div>

                  <div>
                    <Label className="text-xs text-muted-foreground">본문</Label>
                    <div className="mt-2 prose prose-sm max-w-none">
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {generatedPost.generated_content}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">분석 결과</CardTitle>
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

                  <Button className="w-full" onClick={handleSave}>
                    저장하고 상세보기
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
