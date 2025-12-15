'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Share2,
  Instagram,
  Facebook,
  Link2,
  Unlink,
  Plus,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Copy,
  Wand2,
  Video,
  Image as ImageIcon,
  FileText,
  Hash,
  ExternalLink,
  Trash2,
  Send,
  Clock,
  RefreshCw
} from 'lucide-react'
import { snsAPI, postsAPI, type SNSPlatform, type SNSContentType } from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'

interface SNSConnection {
  id: string
  platform: string
  platform_username: string | null
  profile_image_url: string | null
  page_name: string | null
  is_active: boolean
  connection_status: string
  created_at: string
}

interface SNSPost {
  id: string
  platform: string
  content_type: string
  caption: string | null
  hashtags: string[] | null
  media_urls: string[] | null
  script: string | null
  script_duration: number | null
  status: string
  scheduled_at: string | null
  published_at: string | null
  platform_post_url: string | null
  error_message: string | null
  original_post_id: string | null
  created_at: string
}

interface BlogPost {
  id: string
  title: string
  created_at: string
}

export default function SNSPage() {
  const [connections, setConnections] = useState<SNSConnection[]>([])
  const [snsPosts, setSNSPosts] = useState<SNSPost[]>([])
  const [blogPosts, setBlogPosts] = useState<BlogPost[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('posts')
  const [convertDialogOpen, setConvertDialogOpen] = useState(false)
  const [scriptDialogOpen, setScriptDialogOpen] = useState(false)
  const [selectedBlogPost, setSelectedBlogPost] = useState<string>('')
  const [selectedPlatform, setSelectedPlatform] = useState<string>('instagram')
  const [selectedContentType, setSelectedContentType] = useState<string>('post')
  const [scriptDuration, setScriptDuration] = useState<number>(30)
  const [convertedContent, setConvertedContent] = useState<any>(null)
  const [generatedScript, setGeneratedScript] = useState<any>(null)
  const [isConverting, setIsConverting] = useState(false)
  const [isGeneratingScript, setIsGeneratingScript] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [connectionsData, postsData, blogPostsData] = await Promise.all([
        snsAPI.getConnections(),
        snsAPI.getPosts(),
        postsAPI.list()
      ])
      setConnections(connectionsData || [])
      setSNSPosts(postsData || [])
      setBlogPosts(blogPostsData?.posts || [])
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleConnect = async (platform: string) => {
    try {
      const redirectUri = `${window.location.origin}/dashboard/sns/callback/${platform}`
      const response = await snsAPI.getAuthUrl(platform as SNSPlatform, redirectUri)
      window.location.href = response.auth_url
    } catch (error: any) {
      toast.error('연동 실패', {
        description: error.response?.data?.detail || 'OAuth URL 생성에 실패했습니다.'
      })
    }
  }

  const handleDisconnect = async (platform: string) => {
    if (!confirm(`${platform} 연동을 해제하시겠습니까?`)) return

    try {
      await snsAPI.disconnect(platform as SNSPlatform)
      toast.success('연동 해제됨', {
        description: `${platform} 연동이 해제되었습니다.`
      })
      loadData()
    } catch (error: any) {
      toast.error('연동 해제 실패', {
        description: error.response?.data?.detail || '연동 해제에 실패했습니다.'
      })
    }
  }

  const handleConvert = async () => {
    if (!selectedBlogPost) {
      toast.error('글 선택 필요', {
        description: '변환할 블로그 글을 선택해주세요.'
      })
      return
    }

    setIsConverting(true)
    try {
      const result = await snsAPI.convert({
        post_id: selectedBlogPost,
        platform: selectedPlatform as SNSPlatform,
        content_type: selectedContentType as SNSContentType
      })
      setConvertedContent(result)
      toast.success('변환 완료', {
        description: 'SNS 콘텐츠로 변환되었습니다.'
      })
    } catch (error: any) {
      toast.error('변환 실패', {
        description: error.response?.data?.detail || '콘텐츠 변환에 실패했습니다.'
      })
    } finally {
      setIsConverting(false)
    }
  }

  const handleGenerateScript = async () => {
    if (!selectedBlogPost) {
      toast.error('글 선택 필요', {
        description: '스크립트를 생성할 블로그 글을 선택해주세요.'
      })
      return
    }

    setIsGeneratingScript(true)
    try {
      const result = await snsAPI.generateScript({
        post_id: selectedBlogPost,
        duration: scriptDuration
      })
      setGeneratedScript(result)
      toast.success('스크립트 생성 완료', {
        description: '숏폼 스크립트가 생성되었습니다.'
      })
    } catch (error: any) {
      toast.error('스크립트 생성 실패', {
        description: error.response?.data?.detail || '스크립트 생성에 실패했습니다.'
      })
    } finally {
      setIsGeneratingScript(false)
    }
  }

  const handleCreatePost = async () => {
    if (!convertedContent) return

    try {
      await snsAPI.createPost({
        platform: convertedContent.platform,
        caption: convertedContent.caption,
        content_type: convertedContent.content_type,
        hashtags: convertedContent.hashtags,
        original_post_id: convertedContent.original_post_id
      })
      toast.success('SNS 포스트 생성됨', {
        description: '포스트가 초안으로 저장되었습니다.'
      })
      setConvertDialogOpen(false)
      setConvertedContent(null)
      loadData()
    } catch (error: any) {
      toast.error('포스트 생성 실패', {
        description: error.response?.data?.detail || '포스트 생성에 실패했습니다.'
      })
    }
  }

  const handlePublish = async (postId: string) => {
    try {
      await snsAPI.publishPost(postId)
      toast.success('발행 완료', {
        description: 'SNS에 포스트가 발행되었습니다.'
      })
      loadData()
    } catch (error: any) {
      toast.error('발행 실패', {
        description: error.response?.data?.detail || '포스트 발행에 실패했습니다.'
      })
    }
  }

  const handleDeletePost = async (postId: string) => {
    if (!confirm('이 포스트를 삭제하시겠습니까?')) return

    try {
      await snsAPI.deletePost(postId)
      toast.success('삭제됨', {
        description: '포스트가 삭제되었습니다.'
      })
      loadData()
    } catch (error: any) {
      toast.error('삭제 실패', {
        description: error.response?.data?.detail || '삭제에 실패했습니다.'
      })
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('복사됨', {
      description: '클립보드에 복사되었습니다.'
    })
  }

  const getPlatformIcon = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'instagram':
        return <Instagram className="h-5 w-5" />
      case 'facebook':
        return <Facebook className="h-5 w-5" />
      default:
        return <Share2 className="h-5 w-5" />
    }
  }

  const getPlatformColor = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'instagram':
        return 'bg-gradient-to-r from-purple-500 to-pink-500'
      case 'facebook':
        return 'bg-blue-600'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return <Badge variant="secondary"><FileText className="h-3 w-3 mr-1" />초안</Badge>
      case 'scheduled':
        return <Badge className="bg-blue-100 text-blue-700"><Clock className="h-3 w-3 mr-1" />예약됨</Badge>
      case 'published':
        return <Badge className="bg-green-100 text-green-700"><CheckCircle2 className="h-3 w-3 mr-1" />발행됨</Badge>
      case 'failed':
        return <Badge className="bg-red-100 text-red-700"><AlertCircle className="h-3 w-3 mr-1" />실패</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const getContentTypeBadge = (type: string) => {
    switch (type) {
      case 'post':
        return <Badge variant="outline"><ImageIcon className="h-3 w-3 mr-1" />이미지</Badge>
      case 'story':
        return <Badge variant="outline"><FileText className="h-3 w-3 mr-1" />스토리</Badge>
      case 'reel':
      case 'short':
        return <Badge variant="outline"><Video className="h-3 w-3 mr-1" />숏폼</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
  }

  const isConnected = (platform: string) => {
    return connections.some(c => c.platform.toLowerCase() === platform.toLowerCase() && c.is_active)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
        <DashboardNav />
        <main className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <DashboardNav />

      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Share2 className="h-8 w-8 text-blue-600" />
              SNS 멀티 포스팅
            </h1>
            <p className="text-gray-600 mt-1">
              블로그 글을 SNS 콘텐츠로 변환하고 발행하세요
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setScriptDialogOpen(true)}>
              <Video className="h-4 w-4 mr-2" />
              숏폼 스크립트
            </Button>
            <Button onClick={() => setConvertDialogOpen(true)}>
              <Wand2 className="h-4 w-4 mr-2" />
              콘텐츠 변환
            </Button>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="posts">SNS 포스트</TabsTrigger>
            <TabsTrigger value="connections">계정 연동</TabsTrigger>
          </TabsList>

          <TabsContent value="posts">
            {snsPosts.length === 0 ? (
              <Card>
                <CardContent className="py-16 text-center">
                  <Share2 className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">SNS 포스트가 없습니다</h3>
                  <p className="text-gray-500 mb-6">
                    블로그 글을 SNS 콘텐츠로 변환하여 발행해보세요
                  </p>
                  <Button onClick={() => setConvertDialogOpen(true)}>
                    <Wand2 className="h-4 w-4 mr-2" />
                    콘텐츠 변환하기
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
                {snsPosts.map((post) => (
                  <Card key={post.id} className="hover:shadow-md transition-shadow">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white ${getPlatformColor(post.platform)}`}>
                            {getPlatformIcon(post.platform)}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              {getStatusBadge(post.status)}
                              {getContentTypeBadge(post.content_type)}
                            </div>
                            <CardDescription className="mt-1">
                              {format(new Date(post.created_at), 'yyyy.MM.dd HH:mm', { locale: ko })}
                              {post.published_at && (
                                <span className="ml-2 text-green-600">
                                  (발행: {format(new Date(post.published_at), 'yyyy.MM.dd HH:mm', { locale: ko })})
                                </span>
                              )}
                            </CardDescription>
                          </div>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent>
                      {post.caption && (
                        <div className="mb-4">
                          <p className="text-gray-700 whitespace-pre-wrap line-clamp-3">{post.caption}</p>
                        </div>
                      )}

                      {post.hashtags && post.hashtags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-4">
                          {post.hashtags.map((tag, i) => (
                            <span key={i} className="text-blue-600 text-sm">#{tag}</span>
                          ))}
                        </div>
                      )}

                      {post.script && (
                        <div className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Video className="h-4 w-4 text-purple-600" />
                            <span className="text-sm font-medium">숏폼 스크립트</span>
                            {post.script_duration && (
                              <Badge variant="secondary">{post.script_duration}초</Badge>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 whitespace-pre-wrap line-clamp-3">{post.script}</p>
                        </div>
                      )}

                      {post.error_message && (
                        <div className="bg-red-50 text-red-700 rounded-lg p-3 text-sm">
                          <AlertCircle className="h-4 w-4 inline mr-1" />
                          {post.error_message}
                        </div>
                      )}
                    </CardContent>

                    <CardFooter className="flex justify-between">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleDeletePost(post.id)}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        삭제
                      </Button>

                      <div className="flex gap-2">
                        {post.caption && (
                          <Button variant="outline" size="sm" onClick={() => copyToClipboard(post.caption!)}>
                            <Copy className="h-4 w-4 mr-1" />
                            복사
                          </Button>
                        )}
                        {post.platform_post_url && (
                          <Button variant="outline" size="sm" asChild>
                            <a href={post.platform_post_url} target="_blank" rel="noopener noreferrer">
                              <ExternalLink className="h-4 w-4 mr-1" />
                              보기
                            </a>
                          </Button>
                        )}
                        {post.status === 'draft' && isConnected(post.platform) && (
                          <Button size="sm" onClick={() => handlePublish(post.id)}>
                            <Send className="h-4 w-4 mr-1" />
                            발행
                          </Button>
                        )}
                      </div>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="connections">
            <div className="grid md:grid-cols-2 gap-4">
              {/* Instagram */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center text-white">
                      <Instagram className="h-6 w-6" />
                    </div>
                    <div>
                      <CardTitle>Instagram</CardTitle>
                      <CardDescription>비즈니스 계정 연동</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {isConnected('instagram') ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                        <span className="text-sm">연동됨</span>
                      </div>
                      {connections.find(c => c.platform === 'instagram')?.platform_username && (
                        <p className="text-sm text-gray-600">
                          @{connections.find(c => c.platform === 'instagram')?.platform_username}
                        </p>
                      )}
                      <Button variant="outline" className="w-full" onClick={() => handleDisconnect('instagram')}>
                        <Unlink className="h-4 w-4 mr-2" />
                        연동 해제
                      </Button>
                    </div>
                  ) : (
                    <Button className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600" onClick={() => handleConnect('instagram')}>
                      <Link2 className="h-4 w-4 mr-2" />
                      Instagram 연동
                    </Button>
                  )}
                </CardContent>
              </Card>

              {/* Facebook */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-blue-600 flex items-center justify-center text-white">
                      <Facebook className="h-6 w-6" />
                    </div>
                    <div>
                      <CardTitle>Facebook</CardTitle>
                      <CardDescription>페이지 연동</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {isConnected('facebook') ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                        <span className="text-sm">연동됨</span>
                      </div>
                      {connections.find(c => c.platform === 'facebook')?.page_name && (
                        <p className="text-sm text-gray-600">
                          {connections.find(c => c.platform === 'facebook')?.page_name}
                        </p>
                      )}
                      <Button variant="outline" className="w-full" onClick={() => handleDisconnect('facebook')}>
                        <Unlink className="h-4 w-4 mr-2" />
                        연동 해제
                      </Button>
                    </div>
                  ) : (
                    <Button className="w-full bg-blue-600 hover:bg-blue-700" onClick={() => handleConnect('facebook')}>
                      <Link2 className="h-4 w-4 mr-2" />
                      Facebook 연동
                    </Button>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-lg">연동 안내</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-gray-600 space-y-2">
                <p>• Instagram은 비즈니스 또는 크리에이터 계정이 필요합니다.</p>
                <p>• Facebook은 관리하는 페이지가 있어야 합니다.</p>
                <p>• Instagram 연동 시 Facebook 페이지와 연결되어 있어야 합니다.</p>
                <p>• 연동 후 포스트를 직접 발행하거나 예약 발행할 수 있습니다.</p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* Convert Dialog */}
      <Dialog open={convertDialogOpen} onOpenChange={setConvertDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>블로그 글 변환</DialogTitle>
            <DialogDescription>
              블로그 글을 SNS 콘텐츠로 변환합니다
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>블로그 글 선택</Label>
              <Select value={selectedBlogPost} onValueChange={setSelectedBlogPost}>
                <SelectTrigger>
                  <SelectValue placeholder="변환할 글을 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  {blogPosts.map((post) => (
                    <SelectItem key={post.id} value={post.id}>
                      {post.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>플랫폼</Label>
                <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instagram">Instagram</SelectItem>
                    <SelectItem value="facebook">Facebook</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>콘텐츠 타입</Label>
                <Select value={selectedContentType} onValueChange={setSelectedContentType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="post">이미지 포스트</SelectItem>
                    <SelectItem value="story">스토리</SelectItem>
                    <SelectItem value="reel">릴스/숏츠</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {!convertedContent && (
              <Button onClick={handleConvert} disabled={isConverting || !selectedBlogPost} className="w-full">
                {isConverting ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />변환 중...</>
                ) : (
                  <><Wand2 className="h-4 w-4 mr-2" />AI로 변환하기</>
                )}
              </Button>
            )}

            {convertedContent && (
              <div className="space-y-4 border rounded-lg p-4 bg-gray-50">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">변환 결과</h4>
                  <Button variant="ghost" size="sm" onClick={() => copyToClipboard(convertedContent.caption)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label>캡션</Label>
                  <Textarea
                    value={convertedContent.caption}
                    onChange={(e) => setConvertedContent({ ...convertedContent, caption: e.target.value })}
                    rows={5}
                  />
                </div>

                <div className="space-y-2">
                  <Label>해시태그</Label>
                  <div className="flex flex-wrap gap-1">
                    {convertedContent.hashtags?.map((tag: string, i: number) => (
                      <Badge key={i} variant="secondary">#{tag}</Badge>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setConvertDialogOpen(false)
              setConvertedContent(null)
            }}>
              닫기
            </Button>
            {convertedContent && (
              <Button onClick={handleCreatePost}>
                <Plus className="h-4 w-4 mr-2" />
                포스트 저장
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Script Dialog */}
      <Dialog open={scriptDialogOpen} onOpenChange={setScriptDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>숏폼 스크립트 생성</DialogTitle>
            <DialogDescription>
              블로그 글을 릴스/숏츠용 스크립트로 변환합니다
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>블로그 글 선택</Label>
              <Select value={selectedBlogPost} onValueChange={setSelectedBlogPost}>
                <SelectTrigger>
                  <SelectValue placeholder="스크립트를 생성할 글을 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  {blogPosts.map((post) => (
                    <SelectItem key={post.id} value={post.id}>
                      {post.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>영상 길이</Label>
              <Select value={String(scriptDuration)} onValueChange={(v) => setScriptDuration(parseInt(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15초</SelectItem>
                  <SelectItem value="30">30초</SelectItem>
                  <SelectItem value="45">45초</SelectItem>
                  <SelectItem value="60">60초</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {!generatedScript && (
              <Button onClick={handleGenerateScript} disabled={isGeneratingScript || !selectedBlogPost} className="w-full">
                {isGeneratingScript ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />생성 중...</>
                ) : (
                  <><Video className="h-4 w-4 mr-2" />스크립트 생성</>
                )}
              </Button>
            )}

            {generatedScript && (
              <div className="space-y-4 border rounded-lg p-4 bg-gray-50">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2">
                    <Video className="h-4 w-4 text-purple-600" />
                    생성된 스크립트
                    <Badge variant="secondary">{generatedScript.duration}초</Badge>
                  </h4>
                  <Button variant="ghost" size="sm" onClick={() => copyToClipboard(generatedScript.script)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>

                <div className="bg-white rounded-lg p-4 border">
                  <p className="whitespace-pre-wrap text-sm">{generatedScript.script}</p>
                </div>

                {generatedScript.hooks && generatedScript.hooks.length > 0 && (
                  <div>
                    <Label className="text-sm">후킹 멘트 제안</Label>
                    <ul className="mt-1 space-y-1">
                      {generatedScript.hooks.map((hook: string, i: number) => (
                        <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                          <span className="text-purple-500">•</span>
                          {hook}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {generatedScript.cta && generatedScript.cta.length > 0 && (
                  <div>
                    <Label className="text-sm">CTA 제안</Label>
                    <ul className="mt-1 space-y-1">
                      {generatedScript.cta.map((cta: string, i: number) => (
                        <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                          <span className="text-blue-500">•</span>
                          {cta}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setScriptDialogOpen(false)
              setGeneratedScript(null)
            }}>
              닫기
            </Button>
            {generatedScript && (
              <Button onClick={() => {
                copyToClipboard(generatedScript.script)
                setScriptDialogOpen(false)
                setGeneratedScript(null)
              }}>
                <Copy className="h-4 w-4 mr-2" />
                복사하고 닫기
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
