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
  Share2,
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
  <div>${post.generated_content.replace(/\n/g, '<br>')}</div>
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
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-2" />
          <p className="text-muted-foreground">로딩 중...</p>
        </div>
      </div>
    )
  }

  if (!post) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/posts">
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              목록으로
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold">
              {isEditing ? '포스팅 편집' : '포스팅 상세'}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              작성일: {formatDate(post.created_at)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isEditing ? (
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
                <X className="h-4 w-4 mr-2" />
                취소
              </Button>
              <Button onClick={handleSave} disabled={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? '저장 중...' : '저장'}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={handleCopy}
                className="gap-2"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
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
                  <Button variant="outline" className="gap-2">
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

              <Button
                variant="default"
                onClick={handleOpenNaverDialog}
                className="gap-2 bg-green-600 hover:bg-green-700"
              >
                <Send className="h-4 w-4" />
                네이버 블로그 발행
              </Button>

              <Button onClick={() => setIsEditing(true)} className="gap-2">
                <Edit className="h-4 w-4" />
                편집
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => router.push(`/dashboard/create?rewrite=${post.id}`)}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    다시 작성
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleDelete} className="text-red-600">
                    <Trash2 className="h-4 w-4 mr-2" />
                    삭제
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </div>

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
                  <Label htmlFor="title">제목</Label>
                  <Input
                    id="title"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    placeholder="포스팅 제목"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="content">내용</Label>
                  <Textarea
                    id="content"
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    placeholder="포스팅 내용"
                    rows={20}
                    className="font-mono"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="status">상태</Label>
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
              {/* Post Header Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-2xl mb-2">
                        {post.title || '제목 없음'}
                      </CardTitle>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(post.created_at)}
                        </span>
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${
                            post.status === 'published'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {post.status === 'published' ? '발행됨' : '임시저장'}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {/* Post Content */}
              <Card>
                <CardHeader>
                  <CardTitle>생성된 콘텐츠</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="prose max-w-none">
                    <div className="whitespace-pre-wrap text-base leading-relaxed">
                      {post.generated_content}
                    </div>
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
                    <div className="prose max-w-none">
                      <div className="whitespace-pre-wrap text-base leading-relaxed text-muted-foreground">
                        {post.original_content}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Analysis Tab */}
        <TabsContent value="analysis" className="space-y-4">
          <div className="grid md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">설득력 점수</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {Math.round(post.persuasion_score)}점
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  100점 만점
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">의료법 검토</CardTitle>
                <Shield className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600">
                  {post.law_check?.compliant ? '통과' : '검토 필요'}
                </div>
                {post.law_check?.issues?.length > 0 && (
                  <p className="text-xs text-red-600 mt-1">
                    {post.law_check.issues.length}개 이슈 발견
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">SEO 점수</CardTitle>
                <SearchIcon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {post.seo_keywords?.length || 0}개
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  키워드 최적화
                </p>
              </CardContent>
            </Card>
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
                    <span
                      key={index}
                      className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Law Check Issues */}
          {post.law_check?.issues && post.law_check.issues.length > 0 && (
            <Card className="border-orange-200">
              <CardHeader>
                <CardTitle className="text-orange-600">의료법 검토 사항</CardTitle>
                <CardDescription>확인이 필요한 항목들</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {post.law_check.issues.map((issue, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <span className="text-orange-600 mt-0.5">•</span>
                      <span>{issue}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Versions Tab */}
        <TabsContent value="versions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>버전 이력</CardTitle>
              <CardDescription>
                이 포스팅의 모든 수정 이력을 확인할 수 있습니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                <p>버전 이력 기능은 곧 추가됩니다</p>
                <p className="text-sm mt-2">
                  향후 버전 비교 및 복원 기능이 제공될 예정입니다
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
