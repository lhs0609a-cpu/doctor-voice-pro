'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { postsAPI, postsAPIExtended, tagsAPI } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import { toast } from 'sonner'
import {
  FileText,
  Star,
  StarOff,
  Search,
  Filter,
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
      setTags(data)
    } catch (error) {
      console.error('Failed to load tags:', error)
    }
  }

  const loadPosts = async () => {
    try {
      setLoading(true)

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
      setPosts(data.posts)
      setTotalPages(data.total_pages || 1)
    } catch (error) {
      toast.error('포스팅 로드 실패')
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
    <div className="container mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">포스팅 관리</h1>
          <p className="text-muted-foreground">모든 포스팅을 관리하고 검색하세요</p>
        </div>
        <Button onClick={() => router.push('/dashboard/create')}>
          <FileText className="mr-2 h-4 w-4" />
          새 포스팅
        </Button>
      </div>

      {/* Search & Filters */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Search className="h-5 w-5 text-muted-foreground" />
            <span className="font-semibold">검색 및 필터</span>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="ml-auto"
              >
                <X className="h-4 w-4 mr-1" />
                초기화
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Search */}
            <Input
              placeholder="제목 또는 내용 검색..."
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
              variant={favoriteFilter ? 'default' : 'outline'}
              onClick={() =>
                setFavoriteFilter(favoriteFilter === true ? undefined : true)
              }
              className="gap-2"
            >
              <Star className="h-4 w-4" />
              즐겨찾기만
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {selectedPosts.size > 0 && (
        <Card className="mb-4 bg-blue-50 dark:bg-blue-950">
          <CardContent className="py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                {selectedPosts.size}개 선택됨
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setSelectedPosts(new Set())}>
                  선택 취소
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleBulkDelete}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  삭제
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Posts List */}
      {loading ? (
        <PostListSkeleton count={5} />
      ) : posts.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-6">
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>검색 결과가 없습니다</p>
              <p className="text-sm mt-2">다른 조건으로 검색해보세요</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {posts.map((post) => (
            <Card
              key={post.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => router.push(`/dashboard/posts/${post.id}`)}
            >
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <Checkbox
                    checked={selectedPosts.has(post.id)}
                    onCheckedChange={() => toggleSelectPost(post.id)}
                    onClick={(e) => e.stopPropagation()}
                  />

                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-lg">{post.title}</h3>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => handleToggleFavorite(post.id, e)}
                        >
                          {post.is_favorited ? (
                            <Star className="h-5 w-5 fill-yellow-400 text-yellow-400" />
                          ) : (
                            <StarOff className="h-5 w-5" />
                          )}
                        </Button>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreVertical className="h-5 w-5" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={(e) => handleDuplicate(post.id, e)}>
                              <Copy className="h-4 w-4 mr-2" />
                              복제
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => handleDelete(post.id, e)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              삭제
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={post.status === 'published' ? 'default' : 'secondary'}>
                        {post.status === 'draft' && '작성중'}
                        {post.status === 'published' && '발행됨'}
                        {post.status === 'scheduled' && '예약됨'}
                        {post.status === 'archived' && '보관됨'}
                      </Badge>
                      <Badge variant="outline">
                        설득력 {Math.round(post.persuasion_score)}점
                      </Badge>
                      {post.tags &&
                        post.tags.map((tag) => (
                          <Badge
                            key={tag.id}
                            style={{ backgroundColor: tag.color, color: 'white' }}
                          >
                            {tag.name}
                          </Badge>
                        ))}
                    </div>

                    <p className="text-sm text-muted-foreground mt-2">
                      {new Date(post.created_at).toLocaleDateString('ko-KR')}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            이전
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
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
