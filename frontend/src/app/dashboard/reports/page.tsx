'use client'

import { useState, useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  FileBarChart,
  Download,
  FileSpreadsheet,
  Calendar,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart,
  Loader2,
  Plus,
  Settings,
  RefreshCw,
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Trash2
} from 'lucide-react'
import { reportAPI } from '@/lib/api'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'

interface Report {
  id: string
  report_type: string
  title: string
  period_start: string
  period_end: string
  status: string
  total_posts: number
  avg_persuasion_score: number | null
  total_views: number | null
  top_keywords: string[] | null
  recommendations: string[] | null
  file_path: string | null
  created_at: string
}

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
        return <Badge className="bg-green-100 text-green-700"><CheckCircle2 className="h-3 w-3 mr-1" />완료</Badge>
      case 'generating':
        return <Badge className="bg-blue-100 text-blue-700"><Loader2 className="h-3 w-3 mr-1 animate-spin" />생성중</Badge>
      case 'failed':
        return <Badge className="bg-red-100 text-red-700"><AlertCircle className="h-3 w-3 mr-1" />실패</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const getReportTypeBadge = (type: string) => {
    switch (type) {
      case 'monthly':
        return <Badge variant="outline"><Calendar className="h-3 w-3 mr-1" />월간</Badge>
      case 'weekly':
        return <Badge variant="outline"><Clock className="h-3 w-3 mr-1" />주간</Badge>
      case 'custom':
        return <Badge variant="outline"><FileText className="h-3 w-3 mr-1" />커스텀</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
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
              <FileBarChart className="h-8 w-8 text-blue-600" />
              마케팅 리포트
            </h1>
            <p className="text-gray-600 mt-1">
              블로그 마케팅 성과를 분석하고 리포트를 생성하세요
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleGenerateWeekly} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              주간 리포트
            </Button>
            <Button onClick={handleGenerateMonthly} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              월간 리포트
            </Button>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="reports">리포트 목록</TabsTrigger>
            <TabsTrigger value="settings">자동 리포트 설정</TabsTrigger>
          </TabsList>

          <TabsContent value="reports">
            {reports.length === 0 ? (
              <Card>
                <CardContent className="py-16 text-center">
                  <FileBarChart className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">생성된 리포트가 없습니다</h3>
                  <p className="text-gray-500 mb-6">
                    월간 또는 주간 리포트를 생성하여 마케팅 성과를 분석해보세요
                  </p>
                  <Button onClick={handleGenerateMonthly} disabled={isGenerating}>
                    {isGenerating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                    첫 리포트 생성하기
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
                {reports.map((report) => (
                  <Card key={report.id} className="hover:shadow-md transition-shadow">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            {getReportTypeBadge(report.report_type)}
                            {getStatusBadge(report.status)}
                          </div>
                          <CardTitle className="text-xl">{report.title}</CardTitle>
                          <CardDescription>
                            {format(new Date(report.period_start), 'yyyy.MM.dd', { locale: ko })} - {format(new Date(report.period_end), 'yyyy.MM.dd', { locale: ko })}
                          </CardDescription>
                        </div>
                        <div className="text-sm text-gray-500">
                          {format(new Date(report.created_at), 'yyyy.MM.dd HH:mm', { locale: ko })}
                        </div>
                      </div>
                    </CardHeader>

                    {report.status === 'completed' && (
                      <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div className="bg-blue-50 rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-blue-700">{report.total_posts}</div>
                            <div className="text-sm text-blue-600">총 발행 글</div>
                          </div>
                          <div className="bg-green-50 rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-green-700 flex items-center justify-center">
                              {report.avg_persuasion_score?.toFixed(1) || '-'}
                              {report.avg_persuasion_score && report.avg_persuasion_score >= 80 && (
                                <TrendingUp className="h-4 w-4 ml-1" />
                              )}
                            </div>
                            <div className="text-sm text-green-600">평균 설득력</div>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-purple-700">
                              {report.total_views?.toLocaleString() || '-'}
                            </div>
                            <div className="text-sm text-purple-600">총 조회수</div>
                          </div>
                          <div className="bg-orange-50 rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-orange-700">
                              {report.top_keywords?.length || 0}
                            </div>
                            <div className="text-sm text-orange-600">주요 키워드</div>
                          </div>
                        </div>

                        {report.top_keywords && report.top_keywords.length > 0 && (
                          <div className="mb-4">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">상위 키워드</h4>
                            <div className="flex flex-wrap gap-2">
                              {report.top_keywords.slice(0, 10).map((keyword, i) => (
                                <Badge key={i} variant="secondary">{keyword}</Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {report.recommendations && report.recommendations.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-gray-700 mb-2">AI 추천사항</h4>
                            <ul className="space-y-1">
                              {report.recommendations.slice(0, 3).map((rec, i) => (
                                <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                                  <span className="text-blue-500">•</span>
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
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleDeleteReport(report.id)}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        삭제
                      </Button>

                      {report.status === 'completed' && (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDownloadExcel(report.id)}
                          >
                            <FileSpreadsheet className="h-4 w-4 mr-1" />
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
                  <Settings className="h-5 w-5" />
                  자동 리포트 설정
                </CardTitle>
                <CardDescription>
                  매월 자동으로 리포트를 생성하고 이메일로 받아보세요
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>자동 리포트 생성</Label>
                    <p className="text-sm text-gray-500">매월 설정된 날짜에 자동으로 리포트를 생성합니다</p>
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

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Excel 파일 포함</Label>
                    <p className="text-sm text-gray-500">리포트에 Excel 파일을 함께 생성합니다</p>
                  </div>
                  <Switch
                    checked={subscription?.include_excel || false}
                    onCheckedChange={(checked: boolean) => handleUpdateSubscription({ include_excel: checked })}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>이메일 알림</Label>
                    <p className="text-sm text-gray-500">리포트 생성 시 이메일로 알림을 받습니다</p>
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
      </main>
    </div>
  )
}
