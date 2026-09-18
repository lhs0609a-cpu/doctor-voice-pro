'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  ArrowLeft,
  Play,
  Pause,
  RefreshCw,
  Send,
  Trash2,
  Mail,
  Eye,
  MousePointerClick,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  Calendar,
} from 'lucide-react'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
import { outreachAPI, type OutreachCampaign, type OutreachEmailLog } from '@/lib/api'
import { toast } from 'sonner'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const STATUS_CONFIG: Record<string, { label: string; tone: Tone }> = {
  draft: { label: '초안', tone: 'muted' },
  active: { label: '진행중', tone: 'ok' },
  paused: { label: '일시정지', tone: 'warn' },
  completed: { label: '완료', tone: 'accent' },
}

const LOG_STATUS: Record<string, { label: string; tone: Tone }> = {
  sent: { label: '발송됨', tone: 'muted' },
  opened: { label: '오픈됨', tone: 'accent' },
  clicked: { label: '클릭됨', tone: 'accent' },
  replied: { label: '회신', tone: 'ok' },
  bounced: { label: '반송', tone: 'danger' },
  unsubscribed: { label: '수신거부', tone: 'warn' },
}

const TH = 'h-10 text-[12px] font-medium uppercase tracking-wide text-muted-foreground'
const TD = 'py-2.5'

export default function CampaignDetailPage() {
  const params = useParams()
  const router = useRouter()
  const campaignId = params.id as string

  const [campaign, setCampaign] = useState<OutreachCampaign | null>(null)
  const [emailLogs, setEmailLogs] = useState<OutreachEmailLog[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  // Send batch dialog
  const [sendDialogOpen, setSendDialogOpen] = useState(false)
  const [batchSize, setBatchSize] = useState(10)

  useEffect(() => {
    loadCampaignDetail()
  }, [campaignId])

  const loadCampaignDetail = async () => {
    setLoading(true)
    try {
      const [campaignData, logsData] = await Promise.all([
        outreachAPI.getCampaign(campaignId),
        outreachAPI.getEmailLogs({ campaign_id: campaignId, limit: 100 })
      ])
      setCampaign(campaignData)
      setEmailLogs(logsData.logs || [])
    } catch (error) {
      toast.error('캠페인 로딩 실패')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleStart = async () => {
    setActionLoading(true)
    try {
      const result = await outreachAPI.startCampaign(campaignId)
      toast.success(result.message || '캠페인이 시작되었습니다')
      loadCampaignDetail()
    } catch (error) {
      toast.error('캠페인 시작 실패')
    } finally {
      setActionLoading(false)
    }
  }

  const handlePause = async () => {
    setActionLoading(true)
    try {
      const result = await outreachAPI.pauseCampaign(campaignId)
      toast.success(result.message || '캠페인이 일시정지되었습니다')
      loadCampaignDetail()
    } catch (error) {
      toast.error('캠페인 일시정지 실패')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSendBatch = async () => {
    setActionLoading(true)
    try {
      const result = await outreachAPI.sendCampaignBatch(campaignId, batchSize)
      if (result.success) {
        const sent = result.results?.sent || 0
        toast.success(`${sent}건 발송 완료`)
        setSendDialogOpen(false)
        loadCampaignDetail()
      } else {
        toast.error('발송 실패')
      }
    } catch (error) {
      toast.error('배치 발송 실패')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('이 캠페인을 삭제하시겠습니까? 발송 기록은 유지됩니다.')) return

    try {
      await outreachAPI.deleteCampaign(campaignId)
      toast.success('캠페인이 삭제되었습니다')
      router.push('/dashboard/outreach?tab=campaigns')
    } catch (error) {
      toast.error('삭제 실패')
    }
  }

  const handleMarkReplied = async (logId: string) => {
    try {
      await outreachAPI.markEmailReplied(logId)
      toast.success('회신으로 표시되었습니다')
      loadCampaignDetail()
    } catch (error) {
      toast.error('업데이트 실패')
    }
  }

  const backLink = (
    <Button variant="ghost" size="sm" className="-ml-2 tracking-normal" asChild>
      <Link href="/dashboard/outreach?tab=campaigns">
        <ArrowLeft className="h-4 w-4" />
        캠페인 목록
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

  if (!campaign) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon={<AlertCircle className="h-8 w-8" />}
          title="캠페인을 찾을 수 없습니다"
          description="삭제되었거나 잘못된 주소일 수 있어요."
          action={
            <Button variant="outline" asChild>
              <Link href="/dashboard/outreach?tab=campaigns">
                <ArrowLeft className="h-4 w-4" />
                목록으로
              </Link>
            </Button>
          }
        />
      </div>
    )
  }

  const statusConfig = STATUS_CONFIG[campaign.status] || STATUS_CONFIG.draft
  const totalSent = campaign.total_sent || 0
  const totalOpened = campaign.total_opened || 0
  const totalClicked = campaign.total_clicked || 0
  const totalReplied = campaign.total_replied || 0
  const openRate = totalSent > 0 ? ((totalOpened / totalSent) * 100).toFixed(1) : '0'
  const clickRate = totalSent > 0 ? ((totalClicked / totalSent) * 100).toFixed(1) : '0'
  const replyRate = totalSent > 0 ? ((totalReplied / totalSent) * 100).toFixed(1) : '0'

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={backLink}
        title={
          <span className="inline-flex items-center gap-2">
            {campaign.name}
            <Pill tone={statusConfig.tone}>{statusConfig.label}</Pill>
          </span>
        }
        description={campaign.description || undefined}
        actions={
          <>
            <Button
              variant="outline"
              onClick={handleDelete}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
              삭제
            </Button>
            {campaign.status === 'active' ? (
              <Button variant="outline" onClick={handlePause} disabled={actionLoading}>
                <Pause className="h-4 w-4" />
                일시정지
              </Button>
            ) : campaign.status !== 'completed' ? (
              <Button onClick={handleStart} disabled={actionLoading}>
                <Play className="h-4 w-4" />
                시작
              </Button>
            ) : null}
            {campaign.status === 'active' && (
              <Button onClick={() => setSendDialogOpen(true)} disabled={actionLoading}>
                <Send className="h-4 w-4" />
                배치 발송
              </Button>
            )}
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="발송" value={totalSent.toLocaleString()} icon={<Mail className="h-4 w-4" />} />
        <StatTile label="오픈" value={totalOpened.toLocaleString()} hint={`오픈율 ${openRate}%`} icon={<Eye className="h-4 w-4" />} />
        <StatTile label="클릭" value={totalClicked.toLocaleString()} hint={`클릭율 ${clickRate}%`} icon={<MousePointerClick className="h-4 w-4" />} />
        <StatTile label="회신" value={totalReplied.toLocaleString()} hint={`회신율 ${replyRate}%`} tone="ok" icon={<MessageSquare className="h-4 w-4" />} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Main Content */}
        <div className="space-y-4 lg:col-span-2">
          {/* Email Logs */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>발송 내역</CardTitle>
                <Button variant="ghost" size="sm" onClick={loadCampaignDetail}>
                  <RefreshCw className="h-4 w-4" />
                  새로고침
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {emailLogs.length === 0 ? (
                <EmptyState
                  icon={<Mail className="h-8 w-8" />}
                  title="아직 보낸 이메일이 없어요"
                  description={
                    campaign.status === 'active'
                      ? '배치 발송으로 타겟 블로그에 첫 이메일을 보내보세요.'
                      : '캠페인을 시작하면 발송 내역이 여기에 쌓여요.'
                  }
                  action={
                    campaign.status === 'active' ? (
                      <Button variant="outline" size="sm" onClick={() => setSendDialogOpen(true)} disabled={actionLoading}>
                        <Send className="h-4 w-4" />
                        배치 발송
                      </Button>
                    ) : campaign.status !== 'completed' ? (
                      <Button variant="outline" size="sm" onClick={handleStart} disabled={actionLoading}>
                        <Play className="h-4 w-4" />
                        캠페인 시작
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className={TH}>받는 사람</TableHead>
                        <TableHead className={TH}>제목</TableHead>
                        <TableHead className={TH}>상태</TableHead>
                        <TableHead className={TH}>발송일</TableHead>
                        <TableHead className={TH}></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emailLogs.map((log) => {
                        const status = LOG_STATUS[log.status]
                        return (
                          <TableRow key={log.id} className="hover:bg-muted/40">
                            <TableCell className={TD}>
                              <div>
                                <p className="font-medium">{log.to_name || '-'}</p>
                                <p className="text-xs text-muted-foreground">{log.to_email}</p>
                              </div>
                            </TableCell>
                            <TableCell className={`${TD} max-w-xs truncate`}>
                              {log.subject}
                            </TableCell>
                            <TableCell className={TD}>
                              <Pill tone={status?.tone || 'muted'}>{status?.label || log.status}</Pill>
                            </TableCell>
                            <TableCell className={`${TD} text-muted-foreground tabular-nums`}>
                              {log.sent_at ? new Date(log.sent_at).toLocaleDateString() : '-'}
                            </TableCell>
                            <TableCell className={`${TD} text-right`}>
                              {log.status !== 'replied' && log.status !== 'bounced' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleMarkReplied(log.id)}
                                >
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                  회신
                                </Button>
                              )}
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

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Campaign Settings */}
          <Card>
            <CardHeader>
              <CardTitle>캠페인 설정</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-[13px] font-medium text-muted-foreground">타겟 등급</Label>
                <div className="mt-1 flex flex-wrap gap-1">
                  {(campaign.target_grades || []).map((grade) => (
                    <Pill key={grade} tone="accent">{grade}등급</Pill>
                  ))}
                </div>
              </div>

              {campaign.target_categories && campaign.target_categories.length > 0 && (
                <div>
                  <Label className="text-[13px] font-medium text-muted-foreground">카테고리</Label>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {campaign.target_categories.map((cat) => (
                      <Pill key={cat} tone="muted">{cat}</Pill>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-[13px] font-medium text-muted-foreground">최소 점수</Label>
                  <p className="text-sm font-medium tabular-nums">{campaign.min_score || 0}점</p>
                </div>
                <div>
                  <Label className="text-[13px] font-medium text-muted-foreground">일일 한도</Label>
                  <p className="text-sm font-medium tabular-nums">{campaign.daily_limit || 50}건</p>
                </div>
              </div>

              <div>
                <Label className="text-[13px] font-medium text-muted-foreground">발송 시간</Label>
                <p className="text-sm font-medium tabular-nums">
                  {campaign.sending_hours_start || 9}시 ~ {campaign.sending_hours_end || 18}시
                </p>
              </div>

              <div>
                <Label className="text-[13px] font-medium text-muted-foreground">발송 요일</Label>
                <p className="text-sm font-medium">
                  {(campaign.sending_days || [1,2,3,4,5]).map(d =>
                    ['', '월', '화', '수', '목', '금', '토', '일'][d]
                  ).join(', ')}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Template Sequence */}
          <Card>
            <CardHeader>
              <CardTitle>이메일 시퀀스</CardTitle>
            </CardHeader>
            <CardContent>
              {(campaign.templates || []).length === 0 ? (
                <p className="text-sm text-muted-foreground">템플릿 없음</p>
              ) : (
                <div className="space-y-2">
                  {(campaign.templates || []).map((t: any, idx: number) => (
                    <div key={idx} className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-xs font-medium text-primary tabular-nums">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">템플릿 #{idx + 1}</p>
                        {idx > 0 && (
                          <p className="text-xs text-muted-foreground">+{t.delay_days || 3}일 후</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>타임라인</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-3">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-[13px] text-muted-foreground">생성일</p>
                    <p className="font-medium tabular-nums">
                      {campaign.created_at ? new Date(campaign.created_at).toLocaleDateString() : '-'}
                    </p>
                  </div>
                </div>
                {campaign.started_at && (
                  <div className="flex items-center gap-3">
                    <Play className="h-4 w-4 text-success" />
                    <div>
                      <p className="text-[13px] text-muted-foreground">시작일</p>
                      <p className="font-medium tabular-nums">
                        {new Date(campaign.started_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                )}
                {campaign.completed_at && (
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                    <div>
                      <p className="text-[13px] text-muted-foreground">완료일</p>
                      <p className="font-medium tabular-nums">
                        {new Date(campaign.completed_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Send Batch Dialog */}
      <Dialog open={sendDialogOpen} onOpenChange={setSendDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>배치 발송</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label>발송 건수</Label>
            <Input
              type="number"
              min={1}
              max={50}
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value) || 10)}
              className="mt-2"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              타겟 조건에 맞는 블로그에 즉시 이메일을 발송합니다.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={handleSendBatch} disabled={actionLoading}>
              {actionLoading ? '발송 중...' : '발송'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
