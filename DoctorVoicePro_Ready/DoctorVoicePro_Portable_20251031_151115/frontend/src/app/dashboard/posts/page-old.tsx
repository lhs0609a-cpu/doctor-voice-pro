'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { postsAPI } from '@/lib/api'
import type { Post } from '@/types'
import {
  Search,
  Filter,
  Trash2,
  Edit,
  Eye,
  Calendar,
  TrendingUp,
  PenTool,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
  FileText,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPosts, setSelectedPosts] = useState<number[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('newest')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const itemsPerPage = 10

  useEffect(() => {
    loadPosts()
  }, [currentPage, statusFilter, sortBy, searchQuery])

  const loadPosts = async () => {
    setLoading(true)
    try {
      const response = await postsAPI.list(currentPage, itemsPerPage)
      let filteredPosts = response.posts

      // Filter by status
      if (statusFilter !== 'all') {
        filteredPosts = filteredPosts.filter((post) => post.status === statusFilter)
      }

      // Search filter
      if (searchQuery) {
        filteredPosts = filteredPosts.filter(
          (post) =>
            post.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            post.generated_content?.toLowerCase().includes(searchQuery.toLowerCase())
        )
      }

      // Sort
      switch (sortBy) {
        case 'newest':
          filteredPosts.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          break
        case 'oldest':
          filteredPosts.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
          break
        case 'score':
          filteredPosts.sort((a, b) => b.persuasion_score - a.persuasion_score)
          break
        case 'title':
          filteredPosts.sort((a, b) => (a.title || '').localeCompare(b.title || ''))
          break
      }

      setPosts(filteredPosts)
      setTotal(response.total)
      setTotalPages(Math.ceil(response.total / itemsPerPage))
    } catch (error) {
      console.error('Failed to load posts:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedPosts(posts.map((post) => post.id))
    } else {
      setSelectedPosts([])
    }
  }

  const handleSelectPost = (postId: number, checked: boolean) => {
    if (checked) {
      setSelectedPosts([...selectedPosts, postId])
    } else {
      setSelectedPosts(selectedPosts.filter((id) => id !== postId))
    }
  }

  const handleDeleteSelected = async () => {
    if (!confirm(`${selectedPosts.length}개의 포스팅을 삭제하시겠습니까?`)) {
      return
    }

    try {
      await Promise.all(selectedPosts.map((id) => postsAPI.delete(id)))
      setSelectedPosts([])
      loadPosts()
    } catch (error) {
      console.error('Failed to delete posts:', error)
      alert('포스팅 삭제 중 오류가 발생했습니다.')
    }
  }

  const handleDeletePost = async (postId: number) => {
    if (!confirm('이 포스팅을 삭제하시겠습니까?')) {
      return
    }

    try {
      await postsAPI.delete(postId)
      loadPosts()
    } catch (error) {
      console.error('Failed to delete post:', error)
      alert('포스팅 삭제 중 오류가 발생했습니다.')
    }
  }

  const handleUpdateStatus = async (postId: number, newStatus: string) => {
    try {
      await postsAPI.update(postId, { status: newStatus })
      loadPosts()
    } catch (error) {
      console.error('Failed to update post status:', error)
      alert('포스팅 상태 변경 중 오류가 발생했습니다.')
    }
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">포스팅 관리</h1>
          <p className="text-muted-foreground">
            총 {total}개의 포스팅이 있습니다
          </p>
        </div>
        <Link href="/dashboard/create">
          <Button size="lg" className="gap-2">
            <PenTool className="h-4 w-4" />
            새 포스팅 작성
          </Button>
        </Link>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="md:col-span-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="제목이나 내용으로 검색..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="상태 필터" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="draft">임시저장</SelectItem>
                <SelectItem value="published">발행됨</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort */}
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger>
                <SelectValue placeholder="정렬" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">최신순</SelectItem>
                <SelectItem value="oldest">오래된순</SelectItem>
                <SelectItem value="score">설득력 높은순</SelectItem>
                <SelectItem value="title">제목순</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {selectedPosts.length > 0 && (
        <Card className="border-2 border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                {selectedPosts.length}개 선택됨
              </span>
              <div className="flex gap-2">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDeleteSelected}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  선택 삭제
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Posts List */}
      <Card>
        <CardHeader>
          <CardTitle>포스팅 목록</CardTitle>
          <CardDescription>작성한 모든 포스팅을 관리합니다</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">
              로딩 중...
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground mb-4">
                포스팅이 없습니다
              </p>
              <Link href="/dashboard/create">
                <Button>첫 포스팅 작성하기</Button>
              </Link>
            </div>
          ) : (
            <>
              {/* Table Header */}
              <div className="border-b">
                <div className="flex items-center gap-4 p-4 font-medium text-sm text-muted-foreground">
                  <div className="w-8">
                    <Checkbox
                      checked={
                        selectedPosts.length === posts.length &&
                        posts.length > 0
                      }
                      onCheckedChange={handleSelectAll}
                    />
                  </div>
                  <div className="flex-1">제목</div>
                  <div className="w-24 text-center">설득력</div>
                  <div className="w-24 text-center">상태</div>
                  <div className="w-40">작성일</div>
                  <div className="w-20"></div>
                </div>
              </div>

              {/* Table Body */}
              <div className="divide-y">
                {posts.map((post) => (
                  <div
                    key={post.id}
                    className="flex items-center gap-4 p-4 hover:bg-accent transition-colors"
                  >
                    <div className="w-8">
                      <Checkbox
                        checked={selectedPosts.includes(post.id)}
                        onCheckedChange={(checked) =>
                          handleSelectPost(post.id, checked as boolean)
                        }
                      />
                    </div>
                    <Link
                      href={`/dashboard/posts/${post.id}`}
                      className="flex-1 min-w-0"
                    >
                      <h4 className="font-medium truncate hover:text-blue-600 transition-colors">
                        {post.title || '제목 없음'}
                      </h4>
                      <p className="text-sm text-muted-foreground truncate">
                        {post.generated_content?.substring(0, 100)}...
                      </p>
                    </Link>
                    <div className="w-24 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <TrendingUp className="h-3 w-3 text-muted-foreground" />
                        <span className="font-semibold">
                          {Math.round(post.persuasion_score)}
                        </span>
                      </div>
                    </div>
                    <div className="w-24 text-center">
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
                    <div className="w-40 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(post.created_at)}
                      </div>
                    </div>
                    <div className="w-20 flex justify-end">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <Link href={`/dashboard/posts/${post.id}`}>
                            <DropdownMenuItem>
                              <Eye className="h-4 w-4 mr-2" />
                              상세보기
                            </DropdownMenuItem>
                          </Link>
                          <DropdownMenuSeparator />
                          {post.status === 'draft' ? (
                            <DropdownMenuItem
                              onClick={() =>
                                handleUpdateStatus(post.id, 'published')
                              }
                            >
                              발행하기
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() =>
                                handleUpdateStatus(post.id, 'draft')
                              }
                            >
                              임시저장으로 변경
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => handleDeletePost(post.id)}
                            className="text-red-600"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            삭제
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 mt-4 border-t">
                  <div className="text-sm text-muted-foreground">
                    페이지 {currentPage} / {totalPages}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      이전
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      다음
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
