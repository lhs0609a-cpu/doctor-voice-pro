'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
  Search,
  Filter,
  ExternalLink,
  Clock,
  XCircle,
} from 'lucide-react'
import { outreachAPI, type OutreachEmailLog, type OutreachCampaign } from '@/lib/api'
import { toast } from 'sonner'

const EMAIL_STATUSES = [
  { value: 'sent', label: '발송됨', icon: Mail, color: 'bg-blue-100 text-blue-700' },
  { value: 'opened', label: '오픈됨', icon: Eye, color: 'bg-emerald-100 text-emerald-700' },
  { value: 'clicked', label: '클릭됨', icon: MousePointerClick, color: 'bg-violet-100 text-violet-700' },
  { value: 'replied', label: '회신', icon: MessageSquare, color: 'bg-green-100 text-green-700' },
  { value: 'bounced', label: '반송', icon: AlertCircle, color: 'bg-red-100 text-red-700' },
  { value: 'unsubscribed', label: '수신거부', icon: XCircle, color: 'bg-gray-100 text-gray-600' },
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
              <h1 className="text-2xl font-bold text-gray-900">이메일 발송 로그</h1>
              <p className="text-sm text-gray-500">전체 {total}건의 발송 기록</p>
            </div>
          </div>
          <Button variant="outline" onClick={loadLogs}>
            <RefreshCw className="w-4 h-4 mr-2" />
            새로고침
          </Button>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <Filter className="w-4 h-4 text-gray-400" />
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
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Mail className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>발송 기록이 없습니다</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>받는 사람</TableHead>
                    <TableHead>제목</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>발송일</TableHead>
                    <TableHead>추적</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => {
                    const statusInfo = getStatusInfo(log.status)
                    return (
                      <TableRow key={log.id} className="cursor-pointer hover:bg-gray-50" onClick={() => openDetail(log)}>
                        <TableCell>
                          <div>
                            <p className="font-medium text-sm">{log.to_name || '-'}</p>
                            <p className="text-xs text-gray-500">{log.to_email}</p>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-xs">
                          <p className="truncate text-sm">{log.subject}</p>
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${statusInfo.color}`}>
                            <statusInfo.icon className="w-3 h-3" />
                            {statusInfo.label}
                          </span>
                        </TableCell>
                        <TableCell className="text-sm text-gray-500">
                          {log.sent_at ? new Date(log.sent_at).toLocaleString() : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {log.opened_at && (
                              <span className="flex items-center gap-0.5" title={`오픈: ${new Date(log.opened_at).toLocaleString()}`}>
                                <Eye className="w-3 h-3 text-emerald-500" />
                              </span>
                            )}
                            {log.clicked_at && (
                              <span className="flex items-center gap-0.5" title={`클릭: ${new Date(log.clicked_at).toLocaleString()}`}>
                                <MousePointerClick className="w-3 h-3 text-violet-500" />
                              </span>
                            )}
                            {log.replied_at && (
                              <span className="flex items-center gap-0.5" title={`회신: ${new Date(log.replied_at).toLocaleString()}`}>
                                <MessageSquare className="w-3 h-3 text-green-500" />
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {log.status !== 'replied' && log.status !== 'bounced' && log.status !== 'unsubscribed' && (
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
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              이전
            </Button>
            <span className="text-sm text-gray-500">
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
      </div>

      {/* Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>이메일 상세</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500">받는 사람</p>
                  <p className="font-medium">{selectedLog.to_name || '-'}</p>
                  <p className="text-sm text-gray-500">{selectedLog.to_email}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">상태</p>
                  <Badge className={getStatusInfo(selectedLog.status).color}>
                    {getStatusInfo(selectedLog.status).label}
                  </Badge>
                </div>
              </div>

              <div>
                <p className="text-xs text-gray-500">제목</p>
                <p className="font-medium">{selectedLog.subject}</p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">발송</p>
                  <p className="text-sm">
                    {selectedLog.sent_at ? new Date(selectedLog.sent_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">오픈</p>
                  <p className="text-sm">
                    {selectedLog.opened_at ? new Date(selectedLog.opened_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">클릭</p>
                  <p className="text-sm">
                    {selectedLog.clicked_at ? new Date(selectedLog.clicked_at).toLocaleString() : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">회신</p>
                  <p className="text-sm">
                    {selectedLog.replied_at ? new Date(selectedLog.replied_at).toLocaleString() : '-'}
                  </p>
                </div>
              </div>

              {selectedLog.error_message && (
                <div className="p-4 bg-red-50 border border-red-100 rounded-lg">
                  <p className="text-xs text-red-600 font-medium mb-1">오류 메시지</p>
                  <p className="text-sm text-red-700">{selectedLog.error_message}</p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-4 border-t">
                {selectedLog.status !== 'replied' && selectedLog.status !== 'bounced' && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleMarkReplied(selectedLog.id)
                      setDetailDialogOpen(false)
                    }}
                  >
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    회신으로 표시
                  </Button>
                )}
                <Button variant="outline" onClick={() => setDetailDialogOpen(false)}>
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
