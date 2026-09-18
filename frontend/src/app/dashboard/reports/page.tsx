'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import {
  FileBarChart,
  FileSpreadsheet,
  Calendar,
  TrendingUp,
  Loader2,
  Plus,
  Settings,
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Trash2
} from 'lucide-react'
import { reportAPI, Report } from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'

interface ReportSubscription {
  id: string
  is_active: boolean
  report_type: string
  day_of_month: number
  day_of_week: number | null
  include_pdf: boolean
  include_excel: boolean
  email_enabled: boolean
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [subscription, setSubscription] = useState<ReportSubscription | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState('reports')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [reportsData, subscriptionData] = await Promise.all([
        reportAPI.getList(),
        reportAPI.getSubscription()
      ])
      setReports(reportsData || [])
      setSubscription(subscriptionData as any)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenerateMonthly = async () => {
    setIsGenerating(true)
    try {
      const now = new Date()
      const year = now.getFullYear()
      const month = now.getMonth() // 이전 달

      await reportAPI.generateMonthly(year, month === 0 ? 12 : month)
      toast.success('리포트 생성 시작', {
        description: '월간 리포트가 생성되고 있습니다. 잠시 후 확인해주세요.'
      })

      setTimeout(() => loadData(), 3000)
    } catch (error: any) {
      toast.error('리포트 생성 실패', {
        description: error.response?.data?.detail || '리포트 생성 중 오류가 발생했습니다.'
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleGenerateWeekly = async () => {
    setIsGenerating(true)
    try {
      await reportAPI.generateWeekly()
      toast.success('리포트 생성 시작', {
        description: '주간 리포트가 생성되고 있습니다. 잠시 후 확인해주세요.'
      })

      setTimeout(() => loadData(), 3000)
    } catch (error: any) {
      toast.error('리포트 생성 실패', {
        description: error.response?.data?.detail || '리포트 생성 중 오류가 발생했습니다.'
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDownloadExcel = async (reportId: string) => {
    try {
      const blob = await reportAPI.downloadExcel(reportId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `report_${reportId}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error: any) {
      toast.error('다운로드 실패', {
        description: '파일 다운로드 중 오류가 발생했습니다.'
      })
    }
  }

  const handleDeleteReport = async (reportId: string) => {
    if (!confirm('이 리포트를 삭제하시겠습니까?')) return

    try {
      await reportAPI.delete(reportId)
      toast.success('리포트 삭제됨', {
        description: '리포트가 삭제되었습니다.'
      })
      loadData()
    } catch (error: any) {
      toast.error('삭제 실패', {
        description: error.response?.data?.detail || '삭제 중 오류가 발생했습니다.'
      })
    }
  }

  const handleUpdateSubscription = async (updates: Partial<ReportSubscription>) => {
    try {
      await reportAPI.updateSubscription(updates)
      toast.success('설정 저장됨', {
        description: '자동 리포트 설정이 저장되었습니다.'
      })
      loadData()
    } catch (error: any) {
      toast.error('설정 저장 실패', {
        description: error.response?.data?.detail || '설정 저장 중 오류가 발생했습니다.'
      })
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Pill tone="ok"><CheckCircle2 className="mr-1 h-3 w-3" />완료</Pill>
      case 'generating':
        return <Pill tone="accent"><Loader2 className="mr-1 h-3 w-3 animate-spin" />생성중</Pill>
      case 'failed':
        return <Pill tone="danger"><AlertCircle className="mr-1 h-3 w-3" />실패</Pill>
      default:
        return <Pill tone="muted">{status}</Pill>
    }
  }

  const getReportTypeBadge = (type: string) => {
    switch (type) {
      case 'monthly':
        return <Pill tone="muted"><Calendar className="mr-1 h-3 w-3" />월간</Pill>
      case 'weekly':
        return <Pill tone="muted"><Clock className="mr-1 h-3 w-3" />주간</Pill>
      case 'custom':
        return <Pill tone="muted"><FileText className="mr-1 h-3 w-3" />커스텀</Pill>
      default:
        return <Pill tone="muted">{type}</Pill>
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="마케팅 리포트"
        description="블로그 마케팅 성과를 분석하고 리포트로 받아보세요"
        actions={
          <>
            <Button variant="outline" onClick={handleGenerateWeekly} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              주간 리포트
            </Button>
            <Button onClick={handleGenerateMonthly} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              월간 리포트
            </Button>
          </>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="reports">리포트 목록</TabsTrigger>
          <TabsTrigger value="settings">자동 리포트 설정</TabsTrigger>
        </TabsList>

        <TabsContent value="reports">
          {reports.length === 0 ? (
            <EmptyState
              icon={<FileBarChart className="h-8 w-8" />}
              title="생성된 리포트가 없습니다"
              description="월간 또는 주간 리포트를 만들어 마케팅 성과를 확인해보세요"
              action={
                <Button onClick={handleGenerateMonthly} disabled={isGenerating}>
                  {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  첫 리포트 만들기
                </Button>
              }
            />
          ) : (
            <div className="grid gap-4">
              {reports.map((report) => (
                <Card key={report.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          {getReportTypeBadge(report.report_type)}
                          {getStatusBadge(report.status)}
                        </div>
                        <CardTitle>{report.title}</CardTitle>
                        <CardDescription className="tabular-nums">
                          {format(new Date(report.period_start), 'yyyy.MM.dd', { locale: ko })} - {format(new Date(report.period_end), 'yyyy.MM.dd', { locale: ko })}
                        </CardDescription>
                      </div>
                      <div className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {format(new Date(report.created_at), 'yyyy.MM.dd HH:mm', { locale: ko })}
                      </div>
                    </div>
                  </CardHeader>

                  {report.status === 'completed' && (
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                        <div className="rounded-lg border bg-muted/40 p-4">
                          <div className="text-[13px] font-medium text-muted-foreground">총 발행 글</div>
                          <div className="kpi mt-1">{report.total_posts}</div>
                        </div>
                        <div className="rounded-lg border bg-muted/40 p-4">
                          <div className="text-[13px] font-medium text-muted-foreground">평균 설득력</div>
                          <div className="kpi mt-1 flex items-center gap-1">
                            {report.avg_persuasion_score?.toFixed(1) || '-'}
                            {report.avg_persuasion_score && report.avg_persuasion_score >= 80 && (
                              <TrendingUp className="h-4 w-4 text-success" />
                            )}
                          </div>
                        </div>
                        <div className="rounded-lg border bg-muted/40 p-4">
                          <div className="text-[13px] font-medium text-muted-foreground">총 조회수</div>
                          <div className="kpi mt-1">
                            {report.total_views?.toLocaleString() || '-'}
                          </div>
                        </div>
                        <div className="rounded-lg border bg-muted/40 p-4">
                          <div className="text-[13px] font-medium text-muted-foreground">주요 키워드</div>
                          <div className="kpi mt-1">
                            {report.top_keywords?.length || 0}
                          </div>
                        </div>
                      </div>

                      {report.top_keywords && report.top_keywords.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-[13px] font-medium text-muted-foreground">상위 키워드</h4>
                          <div className="flex flex-wrap gap-2">
                            {report.top_keywords.slice(0, 10).map((keyword, i) => (
                              <Badge key={i} variant="secondary">{keyword}</Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {report.recommendations && report.recommendations.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-[13px] font-medium text-muted-foreground">AI 추천사항</h4>
                          <ul className="space-y-1">
                            {report.recommendations.slice(0, 3).map((rec, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm">
                                <span className="text-primary">•</span>
                                {rec}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </CardContent>
                  )}

                  <CardFooter className="flex justify-between">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-danger hover:text-danger"
                      onClick={() => handleDeleteReport(report.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                      삭제
                    </Button>

                    {report.status === 'completed' && (
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownloadExcel(report.id)}
                        >
                          <FileSpreadsheet className="h-4 w-4" />
                          Excel
                        </Button>
                      </div>
                    )}
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-4 w-4 text-muted-foreground" />
                자동 리포트 설정
              </CardTitle>
              <CardDescription>
                매월 자동으로 리포트를 만들고 이메일로 받아보세요
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <Label>자동 리포트 생성</Label>
                  <p className="text-sm text-muted-foreground">매월 설정된 날짜에 자동으로 리포트를 생성합니다</p>
                </div>
                <Switch
                  checked={subscription?.is_active || false}
                  onCheckedChange={(checked: boolean) => handleUpdateSubscription({ is_active: checked })}
                />
              </div>

              <div className="space-y-2">
                <Label>리포트 유형</Label>
                <Select
                  value={subscription?.report_type || 'monthly'}
                  onValueChange={(value) => handleUpdateSubscription({ report_type: value })}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">월간 리포트</SelectItem>
                    <SelectItem value="weekly">주간 리포트</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>생성일 (매월)</Label>
                <Select
                  value={String(subscription?.day_of_month || 1)}
                  onValueChange={(value) => handleUpdateSubscription({ day_of_month: parseInt(value) })}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                      <SelectItem key={day} value={String(day)}>
                        매월 {day}일
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <Label>Excel 파일 포함</Label>
                  <p className="text-sm text-muted-foreground">리포트에 Excel 파일을 함께 생성합니다</p>
                </div>
                <Switch
                  checked={subscription?.include_excel || false}
                  onCheckedChange={(checked: boolean) => handleUpdateSubscription({ include_excel: checked })}
                />
              </div>

              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <Label>이메일 알림</Label>
                  <p className="text-sm text-muted-foreground">리포트 생성 시 이메일로 알림을 받습니다</p>
                </div>
                <Switch
                  checked={subscription?.email_enabled || false}
                  onCheckedChange={(checked: boolean) => handleUpdateSubscription({ email_enabled: checked })}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
