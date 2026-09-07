'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { postsAPI, naverAPI } from '@/lib/api'
import type { Post } from '@/types'
import {
  ArrowLeft,
  Edit,
  Save,
  X,
  Copy,
  Download,
  Trash2,
  RefreshCw,
  Clock,
  TrendingUp,
  Shield,
  Search as SearchIcon,
  FileText,
  MoreVertical,
  Check,
  Send,
} from 'lucide-react'
import { CharacterCount } from '@/components/post/character-count'
import { KeywordTags } from '@/components/post/keyword-tags'
import { TitleSelector } from '@/components/post/title-selector'
import { SubtitlePreview } from '@/components/post/subtitle-preview'
import { ForbiddenWordsAlert } from '@/components/post/forbidden-words-alert'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface PageProps {
  params: {
    id: string
  }
}

export default function PostDetailPage({ params }: PageProps) {
  const router = useRouter()
  const [post, setPost] = useState<Post | null>(null)
  const [loading, setLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')
  const [editedContent, setEditedContent] = useState('')
  const [editedStatus, setEditedStatus] = useState<string>('draft')
  const [copied, setCopied] = useState(false)

  // Naver Blog Publishing
  const [showNaverDialog, setShowNaverDialog] = useState(false)
  const [naverCategories, setNaverCategories] = useState<any[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [naverOpenType, setNaverOpenType] = useState<string>('0')
  const [isPublishing, setIsPublishing] = useState(false)
  const [naverConnected, setNaverConnected] = useState(false)

  useEffect(() => {
    loadPost()
    checkNaverConnection()
  }, [params.id])

  const loadPost = async () => {
    try {
      const data = await postsAPI.getById(parseInt(params.id))
      setPost(data)
      setEditedTitle(data.title || '')
      setEditedContent(data.generated_content || '')
      setEditedStatus(data.status)
    } catch (error) {
      console.error('Failed to load post:', error)
      alert('포스팅을 불러올 수 없습니다.')
      router.push('/dashboard/posts')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!post) return

    setIsSaving(true)
    try {
      await postsAPI.update(post.id, {
        title: editedTitle,
        generated_content: editedContent,
        status: editedStatus,
      })

      await loadPost()
      setIsEditing(false)
      alert('저장되었습니다.')
    } catch (error) {
      console.error('Failed to save post:', error)
      alert('저장 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!post) return
    if (!confirm('이 포스팅을 삭제하시겠습니까?')) return

    try {
      await postsAPI.delete(post.id)
      alert('삭제되었습니다.')
      router.push('/dashboard/posts')
    } catch (error) {
      console.error('Failed to delete post:', error)
      alert('삭제 중 오류가 발생했습니다.')
    }
  }

  const handleCopy = async () => {
    if (!post?.generated_content) return

    try {
      await navigator.clipboard.writeText(post.generated_content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
      alert('복사 중 오류가 발생했습니다.')
    }
  }

  const handleExport = (format: string) => {
    if (!post) return

    let content = ''
    let filename = ''

    switch (format) {
      case 'txt':
        content = `${post.title}\n\n${post.generated_content}`
        filename = `${post.title || 'post'}.txt`
        break
      case 'md':
        content = `# ${post.title}\n\n${post.generated_content}`
        filename = `${post.title || 'post'}.md`
        break
      case 'html':
        content = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${post.title}</title>
</head>
<body>
  <h1>${post.title}</h1>
  <div>${(post.generated_content || '').replace(/\n/g, '<br>')}</div>
</body>
</html>`
        filename = `${post.title || 'post'}.html`
        break
    }

    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const checkNaverConnection = async () => {
    try {
      await naverAPI.getConnection()
      setNaverConnected(true)
    } catch (error) {
      setNaverConnected(false)
    }
  }

  const loadNaverCategories = async () => {
    try {
      const categories = await naverAPI.getCategories()
      setNaverCategories(categories)
    } catch (error) {
      console.error('Failed to load Naver categories:', error)
      alert('네이버 블로그 카테고리를 불러올 수 없습니다.')
    }
  }

  const handleOpenNaverDialog = async () => {
    if (!naverConnected) {
      const confirm_connect = confirm(
        '네이버 블로그 연동이 필요합니다. 설정 페이지로 이동하시겠습니까?'
      )
      if (confirm_connect) {
        router.push('/dashboard/settings')
      }
      return
    }

    await loadNaverCategories()
    setShowNaverDialog(true)
  }

  const handlePublishToNaver = async () => {
    if (!post) return

    setIsPublishing(true)
    try {
      const result = await naverAPI.publishPost({
        post_id: post.id.toString(),
        category_no: selectedCategory || undefined,
        open_type: naverOpenType,
        tags: post.seo_keywords || undefined,
      })

      if (result.success) {
        alert('네이버 블로그에 성공적으로 발행되었습니다!')
        setShowNaverDialog(false)
        await loadPost()

        // Open Naver blog post in new tab
        if (result.naver_post_url) {
          window.open(result.naver_post_url, '_blank')
        }
      } else {
        alert(result.message || '발행에 실패했습니다.')
      }
    } catch (error) {
      console.error('Failed to publish to Naver:', error)
      alert('네이버 블로그 발행 중 오류가 발생했습니다.')
    } finally {
      setIsPublishing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  if (!post) {
    return null
  }

  const isCompliant = post.medical_law_check?.is_compliant
  const totalIssues = post.medical_law_check?.total_issues ?? 0

  const renderIssueList = (
    items: any[],
    kind: 'violation' | 'warning',
  ) =>
    items.map((item: any, index: number) => (
      <div
        key={`${kind}-${index}`}
        className={`rounded-lg border p-3 ${
          kind === 'violation'
            ? 'border-danger/20 bg-danger-soft'
            : 'border-warning/20 bg-warning-soft'
        }`}
      >
        <div className="flex flex-wrap items-start gap-2 text-sm">
          <span
            className={`font-medium ${
              kind === 'violation' ? 'text-danger line-through' : 'text-warning'
            }`}
          >
            {typeof item === 'string' ? item : item.text}
          </span>
          {typeof item === 'object' && item.suggestion && (
            <>
              <span className="text-muted-foreground">→</span>
              <span className="font-medium text-success">{item.suggestion}</span>
            </>
          )}
        </div>
        {typeof item === 'object' && item.category && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            분류: {item.category.replace(/_/g, ' ')}
          </p>
        )}
      </div>
    ))

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/posts"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        목록으로
      </Link>

      <PageHeader
        eyebrow={`작성일 ${formatDate(post.created_at)}`}
        title={isEditing ? '포스팅 편집' : '포스팅 상세'}
        actions={
          isEditing ? (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditing(false)
                  setEditedTitle(post.title || '')
                  setEditedContent(post.generated_content || '')
                  setEditedStatus(post.status)
                }}
                disabled={isSaving}
              >
                <X className="h-4 w-4" />
                취소
              </Button>
              <Button onClick={handleSave} disabled={isSaving}>
                <Save className="h-4 w-4" />
                {isSaving ? '저장 중...' : '저장'}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={handleCopy}>
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-success" />
                    복사됨
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    복사
                  </>
                )}
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    <Download className="h-4 w-4" />
                    내보내기
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={() => handleExport('txt')}>
                    텍스트 파일 (.txt)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport('md')}>
                    마크다운 (.md)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport('html')}>
                    HTML (.html)
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Edit className="h-4 w-4" />
                편집
              </Button>

              <Button onClick={handleOpenNaverDialog}>
                <Send className="h-4 w-4" />
                네이버 블로그 발행
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="더 보기">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => router.push(`/dashboard/create?rewrite=${post.id}`)}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    다시 작성
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleDelete} className="text-destructive focus:text-destructive">
                    <Trash2 className="mr-2 h-4 w-4" />
                    삭제
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )
        }
      />

      <Tabs defaultValue="content" className="space-y-4">
        <TabsList>
          <TabsTrigger value="content">내용</TabsTrigger>
          <TabsTrigger value="analysis">분석</TabsTrigger>
          <TabsTrigger value="versions">버전 이력</TabsTrigger>
        </TabsList>

        {/* Content Tab */}
        <TabsContent value="content" className="space-y-4">
          {isEditing ? (
            <Card>
              <CardHeader>
                <CardTitle>포스팅 편집</CardTitle>
                <CardDescription>
                  제목과 내용을 수정하고 저장하세요
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="title" className="text-[13px] font-medium text-muted-foreground">제목</Label>
                  <Input
                    id="title"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    placeholder="포스팅 제목"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="content" className="text-[13px] font-medium text-muted-foreground">내용</Label>
                  <Textarea
                    id="content"
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    placeholder="포스팅 내용"
                    rows={20}
                    className="font-mono text-sm"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="status" className="text-[13px] font-medium text-muted-foreground">상태</Label>
                  <Select
                    value={editedStatus}
                    onValueChange={setEditedStatus}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">임시저장</SelectItem>
                      <SelectItem value="published">발행됨</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Post Content */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{post.title || '제목 없음'}</CardTitle>
                  <div className="flex flex-wrap items-center gap-3 pt-1 text-[13px] font-medium text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {formatDate(post.created_at)}
                    </span>
                    <Pill tone={post.status === 'published' ? 'ok' : 'muted'}>
                      {post.status === 'published' ? '발행됨' : '임시저장'}
                    </Pill>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
                    {post.generated_content}
                  </div>
                </CardContent>
              </Card>

              {/* Original Content */}
              {post.original_content && (
                <Card>
                  <CardHeader>
                    <CardTitle>원본 콘텐츠</CardTitle>
                    <CardDescription>AI가 각색하기 전의 원본 내용</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                      {post.original_content}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Analysis Tab */}
        <TabsContent value="analysis" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <StatTile
              label="설득력 점수"
              value={`${Math.round(post.persuasion_score)}점`}
              hint="100점 만점"
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatTile
              label="의료법 검토"
              value={isCompliant ? '통과' : '검토 필요'}
              tone={isCompliant ? 'ok' : 'warn'}
              hint={totalIssues > 0 ? `${totalIssues}개 이슈 발견` : undefined}
              icon={<Shield className="h-4 w-4" />}
            />
            <StatTile
              label="SEO 키워드"
              value={`${post.seo_keywords?.length || 0}개`}
              hint="키워드 최적화"
              icon={<SearchIcon className="h-4 w-4" />}
            />
          </div>

          {/* SEO Keywords */}
          {post.seo_keywords && post.seo_keywords.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>SEO 키워드</CardTitle>
                <CardDescription>검색 엔진 최적화를 위한 키워드</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {post.seo_keywords.map((keyword, index) => (
                    <Pill key={index} tone="accent">
                      {keyword}
                    </Pill>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* P2 Fix: Law Check Issues - 수정 제안과 함께 표시 */}
          {post.medical_law_check && (post.medical_law_check.violations.length > 0 || post.medical_law_check.warnings.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-warning">의료법 검토 사항</CardTitle>
                <CardDescription>아래 표현을 수정하면 의료법 위반 위험을 줄일 수 있습니다</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {post.medical_law_check.violations.length > 0 && (
                  <div className="space-y-2">
                    <p className="flex items-center gap-1.5 text-[13px] font-medium text-danger">
                      <span className="h-2 w-2 rounded-full bg-danger" />
                      위반 의심 표현 ({post.medical_law_check.violations.length}건)
                    </p>
                    <div className="space-y-2">
                      {renderIssueList(post.medical_law_check.violations, 'violation')}
                    </div>
                  </div>
                )}
                {post.medical_law_check.warnings.length > 0 && (
                  <div className="space-y-2">
                    <p className="flex items-center gap-1.5 text-[13px] font-medium text-warning">
                      <span className="h-2 w-2 rounded-full bg-warning" />
                      주의 표현 ({post.medical_law_check.warnings.length}건)
                    </p>
                    <div className="space-y-2">
                      {renderIssueList(post.medical_law_check.warnings, 'warning')}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Content Analysis */}
          {post.content_analysis && (
            <CharacterCount analysis={post.content_analysis} />
          )}

          {/* Keywords */}
          {post.content_analysis?.keywords && post.content_analysis.keywords.length > 0 && (
            <KeywordTags keywords={post.content_analysis.keywords} />
          )}

          {/* Suggested Titles */}
          {post.suggested_titles && post.suggested_titles.length > 0 && (
            <TitleSelector
              titles={post.suggested_titles}
              currentTitle={post.title || ''}
              onSelect={(title) => {
                setEditedTitle(title)
                setPost({ ...post, title })
              }}
            />
          )}

          {/* Suggested Subtitles */}
          {post.suggested_subtitles && post.suggested_subtitles.length > 0 && (
            <SubtitlePreview subtitles={post.suggested_subtitles} />
          )}

          {/* Forbidden Words Check */}
          {post.forbidden_words_check && (
            <ForbiddenWordsAlert forbiddenCheck={post.forbidden_words_check} />
          )}
        </TabsContent>

        {/* Versions Tab */}
        <TabsContent value="versions" className="space-y-4">
          <EmptyState
            icon={<FileText className="h-8 w-8" />}
            title="버전 이력은 곧 추가됩니다"
            description="수정 이력을 비교하고 이전 버전으로 되돌리는 기능이 제공될 예정입니다"
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
