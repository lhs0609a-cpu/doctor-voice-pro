'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  ArrowLeft,
  ExternalLink,
  Mail,
  Phone,
  Instagram,
  Youtube,
  Star,
  TrendingUp,
  Zap,
  Target,
  Send,
  CheckCircle2,
  Clock,
  AlertCircle,
  Edit,
  Trash2,
  RefreshCw,
  MessageSquare,
  Eye,
  MousePointerClick,
  Users,
  Calendar,
} from 'lucide-react'
import { outreachAPI, type NaverBlogLead, type OutreachEmailLog, type OutreachEmailTemplate } from '@/lib/api'
import { toast } from 'sonner'

const BLOG_STATUSES = [
  { value: 'new', label: '신규', color: 'bg-sky-100 text-sky-700' },
  { value: 'contact_found', label: '연락처 발견', color: 'bg-emerald-100 text-emerald-700' },
  { value: 'contacted', label: '연락함', color: 'bg-violet-100 text-violet-700' },
  { value: 'responded', label: '회신받음', color: 'bg-fuchsia-100 text-fuchsia-700' },
  { value: 'converted', label: '전환됨', color: 'bg-green-100 text-green-700' },
  { value: 'not_interested', label: '관심없음', color: 'bg-gray-100 text-gray-600' },
  { value: 'invalid', label: '유효하지 않음', color: 'bg-red-100 text-red-700' },
]

const GRADE_STYLES: Record<string, { bg: string; text: string }> = {
  A: { bg: 'bg-emerald-100', text: 'text-emerald-700' },
  B: { bg: 'bg-blue-100', text: 'text-blue-700' },
  C: { bg: 'bg-amber-100', text: 'text-amber-700' },
  D: { bg: 'bg-gray-100', text: 'text-gray-600' },
}

export default function BlogDetailPage() {
  const params = useParams()
  const router = useRouter()
  const blogId = params.id as string

  const [blog, setBlog] = useState<NaverBlogLead | null>(null)
  const [emailHistory, setEmailHistory] = useState<OutreachEmailLog[]>([])
  const [templates, setTemplates] = useState<OutreachEmailTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)

  // 이메일 발송 다이얼로그
  const [sendDialogOpen, setSendDialogOpen] = useState(false)
  const [selectedTemplateId, setSelectedTemplateId] = useState('')

  // 메모 수정
  const [notes, setNotes] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)

  useEffect(() => {
    loadBlogDetail()
    loadTemplates()
  }, [blogId])

  const loadBlogDetail = async () => {
    setLoading(true)
    try {
      const data = await outreachAPI.getBlog(blogId)
      setBlog(data)
      setEmailHistory(data.email_history || [])
      setNotes(data.notes || '')
    } catch (error) {
      toast.error('블로그 정보 로딩 실패')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const loadTemplates = async () => {
    try {
      const data = await outreachAPI.getTemplates()
      setTemplates(data.templates)
    } catch (error) {
      console.error('Templates load error:', error)
    }
  }

  const handleStatusChange = async (newStatus: string) => {
    try {
      await outreachAPI.updateBlogStatus(blogId, newStatus)
      toast.success('상태가 변경되었습니다')
      loadBlogDetail()
    } catch (error) {
      toast.error('상태 변경 실패')
    }
  }

  const handleSendEmail = async () => {
    if (!selectedTemplateId) {
      toast.error('템플릿을 선택하세요')
      return
    }

    setSending(true)
    try {
      const result = await outreachAPI.sendEmail({
        blog_id: blogId,
        template_id: selectedTemplateId,
      })
      if (result.success) {
        toast.success('이메일이 발송되었습니다')
        setSendDialogOpen(false)
        setSelectedTemplateId('')
        loadBlogDetail()
      } else {
        toast.error(result.message || '발송 실패')
      }
    } catch (error) {
      toast.error('이메일 발송 실패')
    } finally {
      setSending(false)
    }
  }

  const handleSaveNotes = async () => {
    setSavingNotes(true)
    try {
      await outreachAPI.updateBlogNotes(blogId, notes)
      toast.success('메모가 저장되었습니다')
    } catch (error) {
      toast.error('메모 저장 실패')
    } finally {
      setSavingNotes(false)
    }
  }

  const handleExtractContact = async () => {
    try {
      const result = await outreachAPI.extractContacts(blogId)
      if (result.success) {
        toast.success(`연락처 추출 완료: ${result.contacts_found || 0}개 발견`)
        loadBlogDetail()
      } else {
        toast.error(result.message || '연락처 추출 실패')
      }
    } catch (error) {
      toast.error('연락처 추출 실패')
    }
  }

  const handleRescore = async () => {
    try {
      const result = await outreachAPI.scoreBlog(blogId)
      if (result.success) {
        toast.success('스코어링 완료')
        loadBlogDetail()
      }
    } catch (error) {
      toast.error('스코어링 실패')
    }
  }

  const handleDelete = async () => {
    if (!confirm('이 블로그를 삭제하시겠습니까?')) return

    try {
      await outreachAPI.deleteBlog(blogId)
      toast.success('삭제되었습니다')
      router.push('/dashboard/outreach')
    } catch (error) {
      toast.error('삭제 실패')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!blog) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p className="text-gray-500">블로그를 찾을 수 없습니다</p>
          <Link href="/dashboard/outreach">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              목록으로
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const gradeStyle = GRADE_STYLES[blog.lead_grade || 'D'] || GRADE_STYLES.D
  const statusInfo = BLOG_STATUSES.find(s => s.value === blog.status)

  return (
    <div className="min-h-screen bg-gray-50/50">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Link href="/dashboard/outreach">
              <Button variant="ghost" size="icon" className="rounded-full">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {blog.blog_name || blog.owner_nickname || blog.blog_id}
              </h1>
              <a
                href={blog.blog_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-500 hover:text-violet-600 flex items-center gap-1"
              >
                {blog.blog_url}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleDelete} className="text-red-600 hover:text-red-700">
              <Trash2 className="w-4 h-4 mr-2" />
              삭제
            </Button>
            <Button onClick={() => setSendDialogOpen(true)} disabled={!blog.has_contact}>
              <Send className="w-4 h-4 mr-2" />
              이메일 발송
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Blog Info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Score Card */}
            <Card>
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <CardTitle>리드 스코어</CardTitle>
                  <Button variant="ghost" size="sm" onClick={handleRescore}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    재계산
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6 mb-6">
                  <div className="text-center">
                    <div className={`w-20 h-20 rounded-2xl ${gradeStyle.bg} flex items-center justify-center mb-2`}>
                      <span className={`text-3xl font-bold ${gradeStyle.text}`}>
                        {blog.lead_grade || 'D'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500">등급</p>
                  </div>
                  <div className="flex-1">
                    <div className="text-4xl font-bold text-gray-900 mb-1">
                      {blog.lead_score?.toFixed(1) || 0}
                      <span className="text-lg text-gray-400 font-normal">/100</span>
                    </div>
                    <p className="text-sm text-gray-500">종합 점수</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: '영향력', value: blog.influence_score, icon: TrendingUp, color: 'text-blue-500' },
                    { label: '활동성', value: blog.activity_score, icon: Zap, color: 'text-emerald-500' },
                    { label: '관련성', value: blog.relevance_score, icon: Target, color: 'text-violet-500' },
                  ].map((score) => (
                    <div key={score.label} className="bg-gray-50 rounded-xl p-4 text-center">
                      <score.icon className={`w-5 h-5 mx-auto mb-2 ${score.color}`} />
                      <p className="text-xl font-bold text-gray-900">{score.value?.toFixed(0) || 0}</p>
                      <p className="text-xs text-gray-500">{score.label}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Metrics Card */}
            <Card>
              <CardHeader>
                <CardTitle>블로그 지표</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: '일일 방문자', value: blog.visitor_daily?.toLocaleString() || 0, icon: Eye },
                    { label: '총 방문자', value: blog.visitor_total?.toLocaleString() || 0, icon: Users },
                    { label: '이웃 수', value: blog.neighbor_count?.toLocaleString() || 0, icon: Users },
                    { label: '포스팅 수', value: blog.post_count?.toLocaleString() || 0, icon: MessageSquare },
                  ].map((metric) => (
                    <div key={metric.label} className="bg-gray-50 rounded-xl p-4">
                      <metric.icon className="w-4 h-4 text-gray-400 mb-2" />
                      <p className="text-xl font-bold text-gray-900">{metric.value}</p>
                      <p className="text-xs text-gray-500">{metric.label}</p>
                    </div>
                  ))}
                </div>

                {blog.last_post_date && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Calendar className="w-4 h-4" />
                      <span>최근 포스팅: {new Date(blog.last_post_date).toLocaleDateString()}</span>
                    </div>
                    {blog.last_post_title && (
                      <p className="mt-1 text-sm text-gray-700 truncate">{blog.last_post_title}</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Email History */}
            <Card>
              <CardHeader>
                <CardTitle>이메일 발송 내역</CardTitle>
                <CardDescription>이 블로그로 발송한 이메일 기록</CardDescription>
              </CardHeader>
              <CardContent>
                {emailHistory.length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <Mail className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>발송 내역이 없습니다</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>제목</TableHead>
                        <TableHead>상태</TableHead>
                        <TableHead>발송일</TableHead>
                        <TableHead>오픈/클릭</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emailHistory.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell className="font-medium">{log.subject}</TableCell>
                          <TableCell>
                            <Badge variant={
                              log.status === 'replied' ? 'default' :
                              log.status === 'opened' || log.status === 'clicked' ? 'secondary' :
                              log.status === 'bounced' ? 'destructive' : 'outline'
                            }>
                              {log.status === 'sent' ? '발송됨' :
                               log.status === 'opened' ? '오픈됨' :
                               log.status === 'clicked' ? '클릭됨' :
                               log.status === 'replied' ? '회신받음' :
                               log.status === 'bounced' ? '반송' : log.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-gray-500">
                            {log.sent_at ? new Date(log.sent_at).toLocaleString() : '-'}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              {log.opened_at && (
                                <span className="flex items-center gap-1">
                                  <Eye className="w-3 h-3" />
                                  {new Date(log.opened_at).toLocaleDateString()}
                                </span>
                              )}
                              {log.clicked_at && (
                                <span className="flex items-center gap-1">
                                  <MousePointerClick className="w-3 h-3" />
                                  {new Date(log.clicked_at).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Contacts & Status */}
          <div className="space-y-6">
            {/* Status Card */}
            <Card>
              <CardHeader>
                <CardTitle>상태</CardTitle>
              </CardHeader>
              <CardContent>
                <Select value={blog.status} onValueChange={handleStatusChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BLOG_STATUSES.map((status) => (
                      <SelectItem key={status.value} value={status.value}>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${status.color}`}>
                          {status.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="mt-4 flex flex-wrap gap-2">
                  {blog.is_influencer && (
                    <Badge variant="secondary" className="bg-amber-50 text-amber-700">
                      <Star className="w-3 h-3 mr-1" />
                      인플루언서
                    </Badge>
                  )}
                  {blog.has_contact && (
                    <Badge variant="secondary" className="bg-emerald-50 text-emerald-700">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      연락처 보유
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Contacts Card */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>연락처</CardTitle>
                  <Button variant="ghost" size="sm" onClick={handleExtractContact}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    추출
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {!blog.contacts || blog.contacts.length === 0 ? (
                  <div className="text-center py-6 text-gray-400">
                    <Mail className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">연락처 없음</p>
                    <Button variant="outline" size="sm" className="mt-3" onClick={handleExtractContact}>
                      연락처 추출하기
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {blog.contacts.map((contact: any, idx: number) => (
                      <div key={idx} className="space-y-2">
                        {contact.email && (
                          <div className="flex items-center gap-2 text-sm">
                            <Mail className="w-4 h-4 text-gray-400" />
                            <a href={`mailto:${contact.email}`} className="text-blue-600 hover:underline">
                              {contact.email}
                            </a>
                          </div>
                        )}
                        {contact.phone && (
                          <div className="flex items-center gap-2 text-sm">
                            <Phone className="w-4 h-4 text-gray-400" />
                            <span>{contact.phone}</span>
                          </div>
                        )}
                        {contact.instagram && (
                          <div className="flex items-center gap-2 text-sm">
                            <Instagram className="w-4 h-4 text-gray-400" />
                            <a
                              href={`https://instagram.com/${contact.instagram}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              @{contact.instagram}
                            </a>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Notes Card */}
            <Card>
              <CardHeader>
                <CardTitle>메모</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="메모 입력..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={4}
                  className="resize-none"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 w-full"
                  onClick={handleSaveNotes}
                  disabled={savingNotes}
                >
                  {savingNotes ? '저장 중...' : '메모 저장'}
                </Button>
              </CardContent>
            </Card>

            {/* Category & Tags */}
            <Card>
              <CardHeader>
                <CardTitle>분류</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs text-gray-500">카테고리</Label>
                    <p className="font-medium">{blog.category || '미분류'}</p>
                  </div>
                  {blog.keywords && blog.keywords.length > 0 && (
                    <div>
                      <Label className="text-xs text-gray-500">키워드</Label>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {blog.keywords.map((kw: string, idx: number) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {kw}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Send Email Dialog */}
      <Dialog open={sendDialogOpen} onOpenChange={setSendDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>이메일 발송</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>받는 사람</Label>
              <Input
                value={blog.contacts?.[0]?.email || '연락처 없음'}
                disabled
                className="mt-1"
              />
            </div>
            <div>
              <Label>템플릿 선택</Label>
              <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="템플릿을 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((template) => (
                    <SelectItem key={template.id} value={template.id}>
                      {template.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={handleSendEmail} disabled={sending || !selectedTemplateId}>
              {sending ? '발송 중...' : '발송'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
