'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
} from '@/components/ui/dialog'
import {
  ArrowLeft,
  RefreshCw,
  Mail,
  Eye,
  MousePointerClick,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  Filter,
  XCircle,
} from 'lucide-react'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { outreachAPI, type OutreachEmailLog, type OutreachCampaign } from '@/lib/api'
import { toast } from 'sonner'

type PillTone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const EMAIL_STATUSES: { value: string; label: string; icon: typeof Mail; tone: PillTone }[] = [
  { value: 'sent', label: '발송됨', icon: Mail, tone: 'accent' },
  { value: 'opened', label: '오픈됨', icon: Eye, tone: 'ok' },
  { value: 'clicked', label: '클릭됨', icon: MousePointerClick, tone: 'accent' },
  { value: 'replied', label: '회신', icon: MessageSquare, tone: 'ok' },
  { value: 'bounced', label: '반송', icon: AlertCircle, tone: 'danger' },
  { value: 'unsubscribed', label: '수신거부', icon: XCircle, tone: 'muted' },
]

export default function EmailLogsPage() {
  const [logs, setLogs] = useState<OutreachEmailLog[]>([])
  const [campaigns, setCampaigns] = useState<OutreachCampaign[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [campaignFilter, setCampaignFilter] = useState('')

  // Detail dialog
  const [selectedLog, setSelectedLog] = useState<OutreachEmailLog | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)

  // Pagination
  const [page, setPage] = useState(0)
  const pageSize = 20

  useEffect(() => {
    loadCampaigns()
  }, [])

  useEffect(() => {
    loadLogs()
  }, [statusFilter, campaignFilter, page])

  const loadCampaigns = async () => {
    try {
      const data = await outreachAPI.getCampaigns()
      setCampaigns(data.campaigns)
    } catch (error) {
      console.error('Campaigns load error:', error)
    }
  }

  const loadLogs = async () => {
    setLoading(true)
    try {
      const params: any = {
        skip: page * pageSize,
        limit: pageSize,
      }
      if (statusFilter) params.status = statusFilter
      if (campaignFilter) params.campaign_id = campaignFilter

      const data = await outreachAPI.getEmailLogs(params)
      setLogs(data.logs)
      setTotal(data.total)
    } catch (error) {
      toast.error('로그 로딩 실패')
    } finally {
      setLoading(false)
    }
  }

  const handleMarkReplied = async (logId: string) => {
    try {
      await outreachAPI.markEmailReplied(logId)
      toast.success('회신으로 표시되었습니다')
      loadLogs()
    } catch (error) {
      toast.error('업데이트 실패')
    }
  }

  const openDetail = (log: OutreachEmailLog) => {
    setSelectedLog(log)
    setDetailDialogOpen(true)
  }

  const getStatusInfo = (status: string) => {
    return EMAIL_STATUSES.find(s => s.value === status) || EMAIL_STATUSES[0]
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <PageHeader
        title="이메일 발송 로그"
        description={<>전체 <span className="tabular-nums">{total}</span>건의 발송 기록</>}
        actions={
          <>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/outreach">
                <ArrowLeft />
                아웃리치로
              </Link>
            </Button>
            <Button variant="outline" size="sm" onClick={loadLogs}>
              <RefreshCw />
              새로고침
            </Button>
          </>
        }
      />

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="상태" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">전체 상태</SelectItem>
                {EMAIL_STATUSES.map((status) => (
                  <SelectItem key={status.value} value={status.value}>
                    {status.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={campaignFilter} onValueChange={setCampaignFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="캠페인" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">전체 캠페인</SelectItem>
                {campaigns.map((campaign) => (
                  <SelectItem key={campaign.id} value={campaign.id}>
                    {campaign.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {(statusFilter || campaignFilter) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatusFilter('')
                  setCampaignFilter('')
                }}
              >
                필터 초기화
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
            </div>
          ) : logs.length === 0 ? (
            <EmptyState
              className="m-4"
              icon={<Mail className="h-8 w-8" />}
              title="발송 기록이 없습니다"
              description="캠페인을 발송하면 이곳에 기록이 쌓입니다."
              action={
                <Button variant="outline" size="sm" asChild>
                  <Link href="/dashboard/outreach">캠페인 보러 가기</Link>
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table className="text-sm">
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">받는 사람</TableHead>
                    <TableHead className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">제목</TableHead>
                    <TableHead className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">상태</TableHead>
                    <TableHead className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">발송일</TableHead>
                    <TableHead className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">추적</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => {
                    const statusInfo = getStatusInfo(log.status)
                    return (
                      <TableRow key={log.id} className="cursor-pointer hover:bg-muted/40" onClick={() => openDetail(log)}>
                        <TableCell className="py-2.5">
                          <div>
                            <p className="font-medium">{log.to_name || '-'}</p>
                            <p className="text-xs text-muted-foreground">{log.to_email}</p>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-xs py-2.5">
                          <p className="truncate">{log.subject}</p>
                        </TableCell>
                        <TableCell className="py-2.5">
                          <Pill tone={statusInfo.tone}>
                            <statusInfo.icon className="mr-1 inline h-3 w-3" />
                            {statusInfo.label}
                          </Pill>
                        </TableCell>
                        <TableCell className="py-2.5 tabular-nums text-muted-foreground">
                          {log.sent_at ? new Date(log.sent_at).toLocaleString() : '-'}
                        </TableCell>
                        <TableCell className="py-2.5">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            {log.opened_at && (
                              <span className="flex items-center gap-0.5" title={`오픈: ${new Date(log.opened_at).toLocaleString()}`}>
                                <Eye className="h-3 w-3 text-success" />
                              </span>
                            )}
                            {log.clicked_at && (
                              <span className="flex items-center gap-0.5" title={`클릭: ${new Date(log.clicked_at).toLocaleString()}`}>
                                <MousePointerClick className="h-3 w-3 text-primary" />
                              </span>
                            )}
                            {log.replied_at && (
                              <span className="flex items-center gap-0.5" title={`회신: ${new Date(log.replied_at).toLocaleString()}`}>
                                <MessageSquare className="h-3 w-3 text-success" />
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                          {log.status !== 'replied' && log.status !== 'bounced' && log.status !== 'unsubscribed' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleMarkReplied(log.id)}
                            >
                              <CheckCircle2 />
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            이전
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground">
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            다음
          </Button>
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>이메일 상세</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 pt-2 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[13px] font-medium text-muted-foreground">받는 사람</p>
                  <p className="font-medium">{selectedLog.to_name || '-'}</p>
                  <p className="text-muted-foreground">{selectedLog.to_email}</p>
                </div>
                <div>
                  <p className="mb-1 text-[13px] font-medium text-muted-foreground">상태</p>
                  <Pill tone={getStatusInfo(selectedLog.status).tone}>
                    {getStatusInfo(selectedLog.status).label}
                  </Pill>
                </div>
              </div>

              <div>
                <p className="text-[13px] font-medium text-muted-foreground">제목</p>
                <p className="font-medium">{selectedLog.subject}</p>
              </div>

              <div className="grid grid-cols-2 gap-4 rounded-lg border bg-muted/40 p-4 md:grid-cols-4">
                <div>
                  <p className="text-[13px] font-medium text-muted-foreground">발송</p>
                  <p className="tabular-nums">
                    {selectedLog.sent_at ? new Date(selectedLog.sent_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-[13px] font-medium text-muted-foreground">오픈</p>
                  <p className="tabular-nums">
                    {selectedLog.opened_at ? new Date(selectedLog.opened_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-[13px] font-medium text-muted-foreground">클릭</p>
                  <p className="tabular-nums">
                    {selectedLog.clicked_at ? new Date(selectedLog.clicked_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-[13px] font-medium text-muted-foreground">회신</p>
                  <p className="tabular-nums">
                    {selectedLog.replied_at ? new Date(selectedLog.replied_at).toLocaleString() : '-'}
                  </p>
                </div>
              </div>

              {selectedLog.error_message && (
                <div className="rounded-lg border bg-danger-soft p-4">
                  <p className="mb-1 text-[13px] font-medium text-danger">오류 메시지</p>
                  <p className="text-danger">{selectedLog.error_message}</p>
                </div>
              )}

              <div className="flex justify-end gap-2 border-t pt-4">
                {selectedLog.status !== 'replied' && selectedLog.status !== 'bounced' && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleMarkReplied(selectedLog.id)
                      setDetailDialogOpen(false)
                    }}
                  >
                    <CheckCircle2 />
                    회신으로 표시
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setDetailDialogOpen(false)}>
                  닫기
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
