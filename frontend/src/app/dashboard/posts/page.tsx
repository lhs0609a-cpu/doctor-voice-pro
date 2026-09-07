'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { postsAPI, postsAPIExtended, tagsAPI } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PostListSkeleton } from '@/components/post-skeleton'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
import { toast } from 'sonner'
import {
  FileText,
  Star,
  StarOff,
  Search,
  Copy,
  Trash2,
  MoreVertical,
  X,
} from 'lucide-react'

interface Post {
  id: string
  title: string
  status: string
  persuasion_score: number
  is_favorited: boolean
  created_at: string
  seo_keywords?: string[]
  tags?: Array<{ id: string; name: string; color: string }>
}

interface Tag {
  id: string
  name: string
  color: string
  post_count: number
}

const STATUS_LABEL: Record<string, string> = {
  draft: '작성중',
  published: '발행됨',
  scheduled: '예약됨',
  archived: '보관됨',
}

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'danger' | 'accent' | 'muted'> = {
  draft: 'muted',
  published: 'ok',
  scheduled: 'accent',
  archived: 'muted',
}

export default function PostsPageEnhanced() {
  const router = useRouter()
  const [posts, setPosts] = useState<Post[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPosts, setSelectedPosts] = useState<Set<string>>(new Set())

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | undefined>()
  const [tagFilter, setTagFilter] = useState<string>('')
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100])

  // Pagination
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  useEffect(() => {
    loadTags()
  }, [])

  useEffect(() => {
    loadPosts()
  }, [page, searchQuery, statusFilter, favoriteFilter, tagFilter, scoreRange])

  const loadTags = async () => {
    try {
      const data = await tagsAPI.getAll()
      setTags(data || [])
    } catch (error) {
      console.error('Failed to load tags:', error)
      setTags([])
    }
  }

  const loadPosts = async () => {
    try {
      setLoading(true)

      // 필터가 적용되어 있으면 search API 사용, 아니면 기본 list API 사용
      const hasFilters = searchQuery ||
        (statusFilter && statusFilter !== 'all') ||
        favoriteFilter !== undefined ||
        tagFilter ||
        scoreRange[0] > 0 ||
        scoreRange[1] < 100

      if (hasFilters) {
        // search API 시도
        try {
          const params: any = {
            page,
            page_size: 10,
          }

          if (searchQuery) params.q = searchQuery
          if (statusFilter && statusFilter !== 'all') params.status = statusFilter
          if (favoriteFilter !== undefined) params.is_favorited = favoriteFilter
          if (tagFilter) params.tag_id = tagFilter
          if (scoreRange[0] > 0) params.min_score = scoreRange[0]
          if (scoreRange[1] < 100) params.max_score = scoreRange[1]

          const data = await postsAPIExtended.search(params)
          setPosts(data.posts || [])
          setTotalPages(data.total_pages || 1)
        } catch (searchError) {
          console.error('Search API failed, falling back to list:', searchError)
          // search 실패 시 기본 list API로 fallback
          const data = await postsAPI.list(page, 10)
          setPosts((data.posts || []) as unknown as Post[])
          setTotalPages(data.total_pages || 1)
          toast.error('검색 기능을 사용할 수 없습니다. 전체 목록을 표시합니다.')
        }
      } else {
        // 필터 없으면 기본 list API 사용
        const data = await postsAPI.list(page, 10)
        setPosts((data.posts || []) as unknown as Post[])
        setTotalPages(data.total_pages || 1)
      }
    } catch (error) {
      console.error('Failed to load posts:', error)
      setPosts([])
      setTotalPages(1)
    } finally {
      setLoading(false)
    }
  }

  const handleToggleFavorite = async (postId: string, event: React.MouseEvent) => {
    event.stopPropagation()
    try {
      await postsAPIExtended.toggleFavorite(postId)
      loadPosts()
      toast.success('즐겨찾기 업데이트')
    } catch (error) {
      toast.error('오류가 발생했습니다')
    }
  }

  const handleDuplicate = async (postId: string, event: React.MouseEvent) => {
    event.stopPropagation()
    try {
      const duplicated = await postsAPIExtended.duplicate(postId)
      toast.success('포스팅이 복제되었습니다')
      router.push(`/dashboard/posts/${duplicated.id}`)
    } catch (error) {
      toast.error('복제 실패')
    }
  }

  const handleDelete = async (postId: string, event: React.MouseEvent) => {
    event.stopPropagation()
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      await postsAPI.delete(postId)
      toast.success('포스팅이 삭제되었습니다')
      loadPosts()
    } catch (error) {
      toast.error('삭제 실패')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedPosts.size === 0) return
    if (!confirm(`${selectedPosts.size}개의 포스팅을 삭제하시겠습니까?`)) return

    try {
      await Promise.all(Array.from(selectedPosts).map((id) => postsAPI.delete(id)))
      toast.success('선택한 포스팅이 삭제되었습니다')
      setSelectedPosts(new Set())
      loadPosts()
    } catch (error) {
      toast.error('일부 포스팅 삭제 실패')
    }
  }

  const toggleSelectPost = (postId: string) => {
    const newSelected = new Set(selectedPosts)
    if (newSelected.has(postId)) {
      newSelected.delete(postId)
    } else {
      newSelected.add(postId)
    }
    setSelectedPosts(newSelected)
  }

  const toggleSelectAll = () => {
    if (selectedPosts.size === posts.length) {
      setSelectedPosts(new Set())
    } else {
      setSelectedPosts(new Set(posts.map((p) => p.id)))
    }
  }

  const clearFilters = () => {
    setSearchQuery('')
    setStatusFilter('all')
    setFavoriteFilter(undefined)
    setTagFilter('')
    setScoreRange([0, 100])
    setPage(1)
  }

  const hasActiveFilters =
    searchQuery ||
    (statusFilter && statusFilter !== 'all') ||
    favoriteFilter !== undefined ||
    tagFilter ||
    scoreRange[0] > 0 ||
    scoreRange[1] < 100

  return (
    <div className="space-y-6">
      <PageHeader
        title="포스팅 관리"
        description="작성한 글을 검색하고 상태를 관리하세요"
        actions={
          <Button onClick={() => router.push('/dashboard/create')}>
            <FileText className="h-4 w-4" />
            새 글 만들기
          </Button>
        }
      />

      {/* Search & Filters */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            검색 및 필터
          </CardTitle>
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X className="h-4 w-4" />
              초기화
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Search */}
            <Input
              placeholder="제목 또는 내용 검색"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="상태" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">모든 상태</SelectItem>
                <SelectItem value="draft">작성중</SelectItem>
                <SelectItem value="published">발행됨</SelectItem>
                <SelectItem value="scheduled">예약됨</SelectItem>
                <SelectItem value="archived">보관됨</SelectItem>
              </SelectContent>
            </Select>

            {/* Tag Filter */}
            <Select value={tagFilter} onValueChange={setTagFilter}>
              <SelectTrigger>
                <SelectValue placeholder="태그" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">모든 태그</SelectItem>
                {tags.map((tag) => (
                  <SelectItem key={tag.id} value={tag.id}>
                    {tag.name} ({tag.post_count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Favorite Filter */}
            <Button
              variant={favoriteFilter ? 'secondary' : 'outline'}
              onClick={() =>
                setFavoriteFilter(favoriteFilter === true ? undefined : true)
              }
            >
              <Star className={`h-4 w-4 ${favoriteFilter ? 'fill-current text-warning' : ''}`} />
              즐겨찾기만
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {selectedPosts.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border bg-accent px-4 py-2.5 text-sm">
          <span className="font-medium text-accent-foreground">
            {selectedPosts.size}개 선택됨
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setSelectedPosts(new Set())}>
              선택 취소
            </Button>
            <Button variant="destructive" size="sm" onClick={handleBulkDelete}>
              <Trash2 className="h-4 w-4" />
              삭제
            </Button>
          </div>
        </div>
      )}

      {/* Posts List */}
      {loading ? (
        <PostListSkeleton count={5} />
      ) : posts.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          title={hasActiveFilters ? '검색 결과가 없습니다' : '아직 작성한 글이 없습니다'}
          description={
            hasActiveFilters
              ? '다른 조건으로 다시 검색해보세요'
              : '첫 글을 만들어 블로그 포스팅을 시작하세요'
          }
          action={
            hasActiveFilters ? (
              <Button variant="outline" onClick={clearFilters}>
                <X className="h-4 w-4" />
                필터 초기화
              </Button>
            ) : (
              <Button onClick={() => router.push('/dashboard/create')}>
                <FileText className="h-4 w-4" />
                새 글 만들기
              </Button>
            )
          }
        />
      ) : (
        <div className="surface overflow-hidden">
          <div className="flex items-center gap-3 border-b bg-muted/40 px-4 py-2 text-[12px] font-medium uppercase tracking-wide text-muted-foreground">
            <Checkbox
              checked={posts.length > 0 && selectedPosts.size === posts.length}
              onCheckedChange={toggleSelectAll}
              aria-label="전체 선택"
            />
            <span className="flex-1">제목</span>
            <span className="hidden w-20 text-right sm:block">설득력</span>
            <span className="hidden w-24 text-right md:block">작성일</span>
            <span className="w-[72px]" />
          </div>
          {posts.map((post) => (
            <ListRow key={post.id} className="p-0">
              <div
                role="link"
                tabIndex={0}
                className="flex flex-1 cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                onClick={() => router.push(`/dashboard/posts/${post.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') router.push(`/dashboard/posts/${post.id}`)
                }}
              >
              <Checkbox
                checked={selectedPosts.has(post.id)}
                onCheckedChange={() => toggleSelectPost(post.id)}
                onClick={(e) => e.stopPropagation()}
                aria-label="선택"
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{post.title || '제목 없음'}</span>
                  <Pill tone={STATUS_TONE[post.status] ?? 'muted'}>
                    {STATUS_LABEL[post.status] ?? post.status}
                  </Pill>
                </div>
                {post.tags && post.tags.length > 0 && (
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {post.tags.map((tag) => (
                      <Badge
                        key={tag.id}
                        className="border-transparent text-[11px] font-medium"
                        style={{ backgroundColor: tag.color, color: 'white' }}
                      >
                        {tag.name}
                      </Badge>
                    ))}
                  </div>
                )}
                <p className="mt-0.5 text-xs text-muted-foreground md:hidden">
                  {new Date(post.created_at).toLocaleDateString('ko-KR')}
                </p>
              </div>

              <span className="hidden w-20 text-right tabular-nums text-muted-foreground sm:block">
                {Math.round(post.persuasion_score)}점
              </span>
              <span className="hidden w-24 text-right tabular-nums text-muted-foreground md:block">
                {new Date(post.created_at).toLocaleDateString('ko-KR')}
              </span>

              <div className="flex w-[72px] items-center justify-end gap-0.5">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={(e) => handleToggleFavorite(post.id, e)}
                  aria-label={post.is_favorited ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                >
                  {post.is_favorited ? (
                    <Star className="h-4 w-4 fill-current text-warning" />
                  ) : (
                    <StarOff className="h-4 w-4 text-muted-foreground" />
                  )}
                </Button>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={(e) => e.stopPropagation()}
                      aria-label="더 보기"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={(e) => handleDuplicate(post.id, e)}>
                      <Copy className="mr-2 h-4 w-4" />
                      복제
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => handleDelete(post.id, e)}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      삭제
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              </div>
            </ListRow>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            이전
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === totalPages}
            onClick={() => setPage(page + 1)}
          >
            다음
          </Button>
        </div>
      )}
    </div>
  )
}
