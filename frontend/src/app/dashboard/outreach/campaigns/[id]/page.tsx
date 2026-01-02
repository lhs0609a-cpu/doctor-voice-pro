'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
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
  Clock,
  Target,
  Users,
  TrendingUp,
  Calendar,
  BarChart3,
} from 'lucide-react'
import { outreachAPI, type OutreachCampaign, type OutreachEmailLog } from '@/lib/api'
import { toast } from 'sonner'

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: '초안', color: 'text-gray-600', bg: 'bg-gray-100' },
  active: { label: '진행중', color: 'text-emerald-600', bg: 'bg-emerald-100' },
  paused: { label: '일시정지', color: 'text-amber-600', bg: 'bg-amber-100' },
  completed: { label: '완료', color: 'text-blue-600', bg: 'bg-blue-100' },
}

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
        toast.error(result.error || '발송 실패')
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

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p className="text-gray-500">캠페인을 찾을 수 없습니다</p>
          <Link href="/dashboard/outreach?tab=campaigns">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              목록으로
            </Button>
          </Link>
        </div>
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
    <div className="min-h-screen bg-gray-50/50">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Link href="/dashboard/outreach?tab=campaigns">
              <Button variant="ghost" size="icon" className="rounded-full">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
                <Badge className={`${statusConfig.bg} ${statusConfig.color}`}>
                  {statusConfig.label}
                </Badge>
              </div>
              {campaign.description && (
                <p className="text-sm text-gray-500 mt-1">{campaign.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleDelete}
              className="text-red-600 hover:text-red-700"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              삭제
            </Button>
            {campaign.status === 'active' ? (
              <Button variant="outline" onClick={handlePause} disabled={actionLoading}>
                <Pause className="w-4 h-4 mr-2" />
                일시정지
              </Button>
            ) : campaign.status !== 'completed' ? (
              <Button onClick={handleStart} disabled={actionLoading}>
                <Play className="w-4 h-4 mr-2" />
                시작
              </Button>
            ) : null}
            {campaign.status === 'active' && (
              <Button onClick={() => setSendDialogOpen(true)} disabled={actionLoading}>
                <Send className="w-4 h-4 mr-2" />
                배치 발송
              </Button>
            )}
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: '발송', value: totalSent, icon: Mail, color: 'text-blue-500' },
            { label: '오픈', value: totalOpened, sub: `${openRate}%`, icon: Eye, color: 'text-emerald-500' },
            { label: '클릭', value: totalClicked, sub: `${clickRate}%`, icon: MousePointerClick, color: 'text-violet-500' },
            { label: '회신', value: totalReplied, sub: `${replyRate}%`, icon: MessageSquare, color: 'text-orange-500' },
          ].map((stat) => (
            <Card key={stat.label}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">{stat.label}</p>
                    <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
                    {stat.sub && <p className="text-sm text-gray-400">{stat.sub}</p>}
                  </div>
                  <stat.icon className={`w-8 h-8 ${stat.color} opacity-50`} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Email Logs */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>발송 내역</CardTitle>
                  <Button variant="ghost" size="sm" onClick={loadCampaignDetail}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    새로고침
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {emailLogs.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <Mail className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>아직 발송 내역이 없습니다</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>받는 사람</TableHead>
                        <TableHead>제목</TableHead>
                        <TableHead>상태</TableHead>
                        <TableHead>발송일</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emailLogs.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell>
                            <div>
                              <p className="font-medium text-sm">{log.to_name || '-'}</p>
                              <p className="text-xs text-gray-500">{log.to_email}</p>
                            </div>
                          </TableCell>
                          <TableCell className="max-w-xs truncate text-sm">
                            {log.subject}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                log.status === 'replied' ? 'default' :
                                log.status === 'clicked' ? 'secondary' :
                                log.status === 'opened' ? 'outline' :
                                log.status === 'bounced' ? 'destructive' : 'outline'
                              }
                              className="text-xs"
                            >
                              {log.status === 'sent' ? '발송됨' :
                               log.status === 'opened' ? '오픈됨' :
                               log.status === 'clicked' ? '클릭됨' :
                               log.status === 'replied' ? '회신' :
                               log.status === 'bounced' ? '반송' :
                               log.status === 'unsubscribed' ? '수신거부' : log.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-gray-500">
                            {log.sent_at ? new Date(log.sent_at).toLocaleDateString() : '-'}
                          </TableCell>
                          <TableCell>
                            {log.status !== 'replied' && log.status !== 'bounced' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleMarkReplied(log.id)}
                                className="text-xs"
                              >
                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                회신
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Campaign Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">캠페인 설정</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-xs text-gray-500">타겟 등급</Label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(campaign.target_grades || []).map((grade) => (
                      <Badge key={grade} variant="outline">
                        {grade}등급
                      </Badge>
                    ))}
                  </div>
                </div>

                {campaign.target_categories && campaign.target_categories.length > 0 && (
                  <div>
                    <Label className="text-xs text-gray-500">카테고리</Label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {campaign.target_categories.map((cat) => (
                        <Badge key={cat} variant="secondary" className="text-xs">
                          {cat}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-gray-500">최소 점수</Label>
                    <p className="font-medium">{campaign.min_score || 0}점</p>
                  </div>
                  <div>
                    <Label className="text-xs text-gray-500">일일 한도</Label>
                    <p className="font-medium">{campaign.daily_limit || 50}건</p>
                  </div>
                </div>

                <div>
                  <Label className="text-xs text-gray-500">발송 시간</Label>
                  <p className="font-medium">
                    {campaign.sending_hours_start || 9}시 ~ {campaign.sending_hours_end || 18}시
                  </p>
                </div>

                <div>
                  <Label className="text-xs text-gray-500">발송 요일</Label>
                  <p className="font-medium">
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
                <CardTitle className="text-base">이메일 시퀀스</CardTitle>
              </CardHeader>
              <CardContent>
                {(campaign.templates || []).length === 0 ? (
                  <p className="text-sm text-gray-400">템플릿 없음</p>
                ) : (
                  <div className="space-y-3">
                    {(campaign.templates || []).map((t: any, idx: number) => (
                      <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                        <div className="w-6 h-6 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-medium">
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium">템플릿 #{idx + 1}</p>
                          {idx > 0 && (
                            <p className="text-xs text-gray-500">+{t.delay_days || 3}일 후</p>
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
                <CardTitle className="text-base">타임라인</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <div>
                      <p className="text-gray-500">생성일</p>
                      <p className="font-medium">
                        {campaign.created_at ? new Date(campaign.created_at).toLocaleDateString() : '-'}
                      </p>
                    </div>
                  </div>
                  {campaign.started_at && (
                    <div className="flex items-center gap-3">
                      <Play className="w-4 h-4 text-emerald-500" />
                      <div>
                        <p className="text-gray-500">시작일</p>
                        <p className="font-medium">
                          {new Date(campaign.started_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  )}
                  {campaign.completed_at && (
                    <div className="flex items-center gap-3">
                      <CheckCircle2 className="w-4 h-4 text-blue-500" />
                      <div>
                        <p className="text-gray-500">완료일</p>
                        <p className="font-medium">
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
            <p className="text-xs text-gray-500 mt-2">
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
