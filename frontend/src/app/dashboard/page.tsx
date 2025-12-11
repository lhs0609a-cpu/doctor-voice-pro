'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { postsAPI, systemAPI } from '@/lib/api'
import type { Post } from '@/types'
import {
  FileText,
  TrendingUp,
  Eye,
  PenTool,
  ArrowRight,
  Calendar,
  Sparkles,
  CheckCircle2,
  XCircle,
  Server,
  Send,
} from 'lucide-react'
import { toast } from 'sonner'

export default function DashboardPage() {
  const router = useRouter()
  const [posts, setPosts] = useState<Post[]>([])
  const [stats, setStats] = useState({
    total: 0,
    thisMonth: 0,
    avgScore: 0,
  })
  const [loading, setLoading] = useState(true)
  const [systemInfo, setSystemInfo] = useState<{
    version: string
    status: string
    aiConnected: boolean
  } | null>(null)

  useEffect(() => {
    loadPosts()
    loadSystemInfo()
  }, [])

  // Post를 SavedPost 형식으로 변환하여 localStorage에 저장하고 발행 페이지로 이동
  const handlePublish = (post: Post) => {
    // SavedPost 형식으로 변환
    const savedPost = {
      id: `db-post-${post.id}`,
      savedAt: new Date().toISOString(),
      suggested_titles: post.suggested_titles || (post.title ? [post.title] : []),
      generated_content: post.generated_content || '',
      seo_keywords: post.seo_keywords || [],
      original_content: post.original_content || '',
      title: post.title || '',
      content: post.generated_content || '',
      // DB Post 식별을 위한 추가 필드
      sourcePostId: post.id,
      sourceType: 'database',
    }

    try {
      // 기존 저장된 글 로드
      const existing = localStorage.getItem('saved-posts')
      const posts = existing ? JSON.parse(existing) : []

      // 이미 같은 Post가 저장되어 있는지 확인
      const existingIndex = posts.findIndex((p: any) => p.sourcePostId === post.id)

      if (existingIndex >= 0) {
        // 기존 항목 업데이트
        posts[existingIndex] = savedPost
      } else {
        // 새로 추가 (맨 앞에)
        posts.unshift(savedPost)
      }

      localStorage.setItem('saved-posts', JSON.stringify(posts))

      // 선택할 글 ID를 저장 (저장된 글 페이지에서 자동 선택용)
      localStorage.setItem('saved-posts-select', savedPost.id)

      toast.success('발행 준비 완료', {
        description: '저장된 글 페이지로 이동합니다',
      })

      // 저장된 글 페이지로 이동
      router.push('/dashboard/saved')
    } catch (error) {
      console.error('발행 준비 실패:', error)
      toast.error('발행 준비에 실패했습니다')
    }
  }

  const loadSystemInfo = async () => {
    try {
      const [info, health] = await Promise.all([
        systemAPI.getInfo(),
        systemAPI.healthCheck(),
      ])
      setSystemInfo({
        version: info.version,
        status: health.status,
        aiConnected: health.ai?.connected || false,
      })
    } catch (error) {
      console.error('Failed to load system info:', error)
      setSystemInfo({
        version: '-',
        status: 'offline',
        aiConnected: false,
      })
    }
  }

  const loadPosts = async () => {
    try {
      const response = await postsAPI.list(1, 5)
      setPosts(response.posts)

      // Calculate stats
      const thisMonth = response.posts.filter((post) => {
        const postDate = new Date(post.created_at)
        const now = new Date()
        return (
          postDate.getMonth() === now.getMonth() &&
          postDate.getFullYear() === now.getFullYear()
        )
      }).length

      const avgScore =
        response.posts.length > 0
          ? response.posts.reduce((sum, p) => sum + p.persuasion_score, 0) /
            response.posts.length
          : 0

      setStats({
        total: response.total,
        thisMonth,
        avgScore: Math.round(avgScore),
      })
    } catch (error) {
      console.error('Failed to load posts:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Welcome Section */}
      <div className="pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold mb-3 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">대시보드</h1>
          <p className="text-lg text-gray-600">AI 블로그 각색 현황을 한눈에 확인하세요</p>
        </div>
        {/* System Status */}
        <div className="flex items-center gap-4 bg-white rounded-xl px-5 py-3 shadow-md border border-gray-100">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-600">v{systemInfo?.version || '...'}</span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          <div className="flex items-center gap-2">
            {systemInfo?.status === 'healthy' ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : systemInfo?.status === 'offline' ? (
              <XCircle className="h-4 w-4 text-red-500" />
            ) : (
              <div className="h-4 w-4 rounded-full border-2 border-gray-300 border-t-transparent animate-spin" />
            )}
            <span className={`text-sm font-medium ${
              systemInfo?.status === 'healthy' ? 'text-green-600' :
              systemInfo?.status === 'offline' ? 'text-red-600' : 'text-gray-500'
            }`}>
              {systemInfo?.status === 'healthy' ? '서버 정상' :
               systemInfo?.status === 'offline' ? '서버 오프라인' : '확인 중...'}
            </span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          <div className="flex items-center gap-2">
            {systemInfo?.aiConnected ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <span className={`text-sm font-medium ${
              systemInfo?.aiConnected ? 'text-green-600' : 'text-red-600'
            }`}>
              AI {systemInfo?.aiConnected ? '연결됨' : '미연결'}
            </span>
          </div>
        </div>
      </div>

      {/* Quick Action */}
      <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50 via-purple-50 to-white shadow-lg hover:shadow-xl transition-all duration-300 animate-fade-in-up animation-delay-200">
        <CardContent className="pt-8 pb-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <PenTool className="h-6 w-6 text-blue-600" />
                <h3 className="text-2xl font-bold text-gray-800">새 포스팅 작성</h3>
              </div>
              <p className="text-base text-gray-600">
                AI가 5분 만에 설득력 있는 블로그 글을 만들어드립니다
              </p>
            </div>
            <Link href="/dashboard/create">
              <Button size="lg" className="gap-2 px-8 py-6 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all">
                <Sparkles className="h-5 w-5" />
                글 작성하기
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      <div className="grid md:grid-cols-3 gap-6 animate-fade-in-up animation-delay-400">
        <Card className="border-2 border-transparent hover:border-blue-200 shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 bg-gradient-to-br from-blue-50 to-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-semibold text-gray-700">총 포스팅</CardTitle>
            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-blue-600 mb-1">{stats.total}개</div>
            <p className="text-sm text-gray-600 font-medium">
              이번 달 {stats.thisMonth}개 작성
            </p>
          </CardContent>
        </Card>

        <Card className="border-2 border-transparent hover:border-purple-200 shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 bg-gradient-to-br from-purple-50 to-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-semibold text-gray-700">평균 설득력</CardTitle>
            <div className="h-10 w-10 rounded-full bg-purple-100 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-purple-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-purple-600 mb-1">{stats.avgScore}점</div>
            <p className="text-sm text-gray-600 font-medium">100점 만점</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-transparent hover:border-green-200 shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 bg-gradient-to-br from-green-50 to-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-semibold text-gray-700">시간 절약</CardTitle>
            <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
              <Eye className="h-5 w-5 text-green-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-green-600 mb-1">{stats.thisMonth * 55}분</div>
            <p className="text-sm text-gray-600 font-medium">이번 달 기준</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Posts */}
      <Card className="shadow-lg border-2 animate-fade-in-up animation-delay-600">
        <CardHeader className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl font-bold text-gray-800">최근 포스팅</CardTitle>
              <CardDescription className="text-base text-gray-600">최근 작성한 블로그 글 목록</CardDescription>
            </div>
            <Link href="/dashboard/posts">
              <Button variant="ghost" size="sm" className="gap-2 hover:bg-white transition-all">
                전체 보기
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="text-gray-600 mt-4 font-medium">로딩 중...</p>
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-12">
              <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 flex items-center justify-center mx-auto mb-4">
                <FileText className="h-10 w-10 text-blue-600" />
              </div>
              <p className="text-gray-600 mb-6 text-lg">아직 작성한 포스팅이 없습니다</p>
              <Link href="/dashboard/create">
                <Button size="lg" className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all">
                  <Sparkles className="h-5 w-5 mr-2" />
                  첫 포스팅 작성하기
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((post, index) => (
                <div
                  key={post.id}
                  className="flex flex-col md:flex-row items-start md:items-center justify-between p-5 rounded-xl border-2 border-gray-100 hover:border-blue-200 hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 transition-all duration-300 shadow-sm hover:shadow-md"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="flex-1 mb-3 md:mb-0">
                    <h4 className="font-bold text-lg mb-2 text-gray-800">
                      {post.title || '제목 없음'}
                    </h4>
                    <div className="flex flex-wrap items-center gap-4 text-sm">
                      <span className="flex items-center gap-1.5 text-gray-600 font-medium">
                        <Calendar className="h-4 w-4 text-blue-600" />
                        {formatDate(post.created_at)}
                      </span>
                      <span className="flex items-center gap-1.5 text-gray-600 font-medium">
                        <TrendingUp className="h-4 w-4 text-purple-600" />
                        설득력 {Math.round(post.persuasion_score)}점
                      </span>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold ${
                          post.status === 'published'
                            ? 'bg-green-100 text-green-700 border border-green-300'
                            : 'bg-gray-100 text-gray-700 border border-gray-300'
                        }`}
                      >
                        {post.status === 'published' ? '발행됨' : '임시저장'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 text-white font-medium gap-1.5"
                      onClick={() => handlePublish(post)}
                    >
                      <Send className="h-3.5 w-3.5" />
                      발행하기
                    </Button>
                    <Link href={`/dashboard/posts/${post.id}`}>
                      <Button variant="ghost" size="sm" className="hover:bg-blue-100 transition-all font-medium">
                        상세보기
                        <ArrowRight className="h-4 w-4 ml-1" />
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
