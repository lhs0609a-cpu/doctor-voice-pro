'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
  Star,
  TrendingUp,
  Zap,
  Target,
  Send,
  CheckCircle2,
  AlertCircle,
  Trash2,
  RefreshCw,
  MessageSquare,
  Eye,
  MousePointerClick,
  Users,
  Calendar,
} from 'lucide-react'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { outreachAPI, type NaverBlogLead, type BlogContact, type OutreachEmailLog, type OutreachEmailTemplate } from '@/lib/api'
import { toast } from 'sonner'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const BLOG_STATUSES: { value: string; label: string; tone: Tone }[] = [
  { value: 'new', label: '신규', tone: 'accent' },
  { value: 'contact_found', label: '연락처 발견', tone: 'ok' },
  { value: 'contacted', label: '연락함', tone: 'accent' },
  { value: 'responded', label: '회신받음', tone: 'accent' },
  { value: 'converted', label: '전환됨', tone: 'ok' },
  { value: 'not_interested', label: '관심없음', tone: 'muted' },
  { value: 'invalid', label: '유효하지 않음', tone: 'danger' },
]

const GRADE_STYLES: Record<string, string> = {
  A: 'bg-success-soft text-success',
  B: 'bg-accent text-primary',
  C: 'bg-warning-soft text-warning',
  D: 'bg-muted text-muted-foreground',
}

const EMAIL_STATUS: Record<string, { label: string; tone: Tone }> = {
  sent: { label: '발송됨', tone: 'muted' },
  opened: { label: '오픈됨', tone: 'accent' },
  clicked: { label: '클릭됨', tone: 'accent' },
  replied: { label: '회신받음', tone: 'ok' },
  bounced: { label: '반송', tone: 'danger' },
}

const TH = 'h-10 text-[12px] font-medium uppercase tracking-wide text-muted-foreground'
const TD = 'py-2.5'

export default function BlogDetailPage() {
  const params = useParams()
  const router = useRouter()
  const blogId = params.id as string

  const [blog, setBlog] = useState<(NaverBlogLead & { contacts?: BlogContact[] }) | null>(null)
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
        toast.error(result.error || '발송 실패')
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

  const backLink = (
    <Button variant="ghost" size="sm" className="-ml-2 tracking-normal" asChild>
      <Link href="/dashboard/outreach">
        <ArrowLeft className="h-4 w-4" />
        블로그 목록
      </Link>
    </Button>
  )

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  if (!blog) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon={<AlertCircle className="h-8 w-8" />}
          title="블로그를 찾을 수 없습니다"
          description="삭제되었거나 잘못된 주소일 수 있어요."
          action={
            <Button variant="outline" asChild>
              <Link href="/dashboard/outreach">
                <ArrowLeft className="h-4 w-4" />
                목록으로
              </Link>
            </Button>
          }
        />
      </div>
    )
  }

  const gradeStyle = GRADE_STYLES[blog.lead_grade || 'D'] || GRADE_STYLES.D

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={backLink}
        title={blog.blog_name || blog.owner_nickname || blog.blog_id}
        description={
          <a
            href={blog.blog_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 hover:text-primary hover:underline"
          >
            {blog.blog_url}
            <ExternalLink className="h-3 w-3" />
          </a>
        }
        actions={
          <>
            <Button variant="outline" onClick={handleDelete} className="text-destructive hover:text-destructive">
              <Trash2 className="h-4 w-4" />
              삭제
            </Button>
            <Button onClick={() => setSendDialogOpen(true)} disabled={!blog.has_contact}>
              <Send className="h-4 w-4" />
              이메일 발송
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Left Column - Blog Info */}
        <div className="space-y-4 lg:col-span-2">
          {/* Score Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>리드 스코어</CardTitle>
                <Button variant="ghost" size="sm" onClick={handleRescore}>
                  <RefreshCw className="h-4 w-4" />
                  다시 계산
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-6">
                <div className="text-center">
                  <div className={`mb-2 flex h-16 w-16 items-center justify-center rounded-xl ${gradeStyle}`}>
                    <span className="text-2xl font-bold">{blog.lead_grade || 'D'}</span>
                  </div>
                  <p className="text-[13px] font-medium text-muted-foreground">등급</p>
                </div>
                <div className="flex-1">
                  <div className="kpi">
                    {blog.lead_score?.toFixed(1) || 0}
                    <span className="text-base font-normal text-muted-foreground">/100</span>
                  </div>
                  <p className="mt-1 text-[13px] font-medium text-muted-foreground">종합 점수</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: '영향력', value: blog.influence_score, icon: TrendingUp },
                  { label: '활동성', value: blog.activity_score, icon: Zap },
                  { label: '관련성', value: blog.relevance_score, icon: Target },
                ].map((score) => (
                  <div key={score.label} className="rounded-lg border bg-muted/40 p-4 text-center">
                    <score.icon className="mx-auto mb-2 h-4 w-4 text-muted-foreground" />
                    <p className="text-lg font-semibold tabular-nums">{score.value?.toFixed(0) || 0}</p>
                    <p className="text-xs text-muted-foreground">{score.label}</p>
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
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                {[
                  { label: '일일 방문자', value: blog.visitor_daily?.toLocaleString() || 0, icon: Eye },
                  { label: '총 방문자', value: blog.visitor_total?.toLocaleString() || 0, icon: Users },
                  { label: '이웃 수', value: blog.neighbor_count?.toLocaleString() || 0, icon: Users },
                  { label: '포스팅 수', value: blog.post_count?.toLocaleString() || 0, icon: MessageSquare },
                ].map((metric) => (
                  <div key={metric.label} className="rounded-lg border bg-muted/40 p-4">
                    <metric.icon className="mb-2 h-4 w-4 text-muted-foreground" />
                    <p className="text-lg font-semibold tabular-nums">{metric.value}</p>
                    <p className="text-xs text-muted-foreground">{metric.label}</p>
                  </div>
                ))}
              </div>

              {blog.last_post_date && (
                <div className="border-t pt-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Calendar className="h-4 w-4" />
                    <span>최근 포스팅: {new Date(blog.last_post_date).toLocaleDateString()}</span>
                  </div>
                  {blog.last_post_title && (
                    <p className="mt-1 truncate text-sm">{blog.last_post_title}</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Email History */}
          <Card>
            <CardHeader>
              <CardTitle>이메일 발송 내역</CardTitle>
              <CardDescription>이 블로그로 보낸 이메일 기록</CardDescription>
            </CardHeader>
            <CardContent>
              {emailHistory.length === 0 ? (
                <EmptyState
                  icon={<Mail className="h-8 w-8" />}
                  title="아직 보낸 이메일이 없어요"
                  description="연락처가 있으면 템플릿을 골라 바로 보낼 수 있어요."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setSendDialogOpen(true)} disabled={!blog.has_contact}>
                      <Send className="h-4 w-4" />
                      이메일 보내기
                    </Button>
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className={TH}>제목</TableHead>
                        <TableHead className={TH}>상태</TableHead>
                        <TableHead className={TH}>발송일</TableHead>
                        <TableHead className={TH}>오픈/클릭</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emailHistory.map((log) => {
                        const status = EMAIL_STATUS[log.status]
                        return (
                          <TableRow key={log.id} className="hover:bg-muted/40">
                            <TableCell className={`${TD} font-medium`}>{log.subject}</TableCell>
                            <TableCell className={TD}>
                              <Pill tone={status?.tone || 'muted'}>{status?.label || log.status}</Pill>
                            </TableCell>
                            <TableCell className={`${TD} text-muted-foreground tabular-nums`}>
                              {log.sent_at ? new Date(log.sent_at).toLocaleString() : '-'}
                            </TableCell>
                            <TableCell className={TD}>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground tabular-nums">
                                {log.opened_at && (
                                  <span className="flex items-center gap-1">
                                    <Eye className="h-3 w-3" />
                                    {new Date(log.opened_at).toLocaleDateString()}
                                  </span>
                                )}
                                {log.clicked_at && (
                                  <span className="flex items-center gap-1">
                                    <MousePointerClick className="h-3 w-3" />
                                    {new Date(log.clicked_at).toLocaleDateString()}
                                  </span>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Contacts & Status */}
        <div className="space-y-4">
          {/* Status Card */}
          <Card>
            <CardHeader>
              <CardTitle>상태</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select value={blog.status} onValueChange={handleStatusChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {BLOG_STATUSES.map((status) => (
                    <SelectItem key={status.value} value={status.value}>
                      <Pill tone={status.tone}>{status.label}</Pill>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {(blog.is_influencer || blog.has_contact) && (
                <div className="flex flex-wrap gap-2">
                  {blog.is_influencer && (
                    <Pill tone="warn" className="gap-1">
                      <Star className="h-3 w-3" />
                      인플루언서
                    </Pill>
                  )}
                  {blog.has_contact && (
                    <Pill tone="ok" className="gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      연락처 보유
                    </Pill>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Contacts Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>연락처</CardTitle>
                <Button variant="ghost" size="sm" onClick={handleExtractContact}>
                  <RefreshCw className="h-4 w-4" />
                  추출
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!blog.contacts || blog.contacts.length === 0 ? (
                <EmptyState
                  icon={<Mail className="h-6 w-6" />}
                  title="연락처가 없어요"
                  description="블로그에서 이메일·전화번호를 찾아볼게요."
                  className="py-8"
                  action={
                    <Button variant="outline" size="sm" onClick={handleExtractContact}>
                      연락처 추출하기
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {blog.contacts.map((contact: any, idx: number) => (
                    <div key={idx} className="space-y-2">
                      {contact.email && (
                        <div className="flex items-center gap-2 text-sm">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <a href={`mailto:${contact.email}`} className="text-primary hover:underline">
                            {contact.email}
                          </a>
                        </div>
                      )}
                      {contact.phone && (
                        <div className="flex items-center gap-2 text-sm">
                          <Phone className="h-4 w-4 text-muted-foreground" />
                          <span className="tabular-nums">{contact.phone}</span>
                        </div>
                      )}
                      {contact.instagram && (
                        <div className="flex items-center gap-2 text-sm">
                          <Instagram className="h-4 w-4 text-muted-foreground" />
                          <a
                            href={`https://instagram.com/${contact.instagram}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
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
                  <Label className="text-[13px] font-medium text-muted-foreground">카테고리</Label>
                  <p className="text-sm font-medium">{blog.category || '미분류'}</p>
                </div>
                {blog.keywords && blog.keywords.length > 0 && (
                  <div>
                    <Label className="text-[13px] font-medium text-muted-foreground">키워드</Label>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {blog.keywords.map((kw: string, idx: number) => (
                        <Pill key={idx} tone="muted">{kw}</Pill>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
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
