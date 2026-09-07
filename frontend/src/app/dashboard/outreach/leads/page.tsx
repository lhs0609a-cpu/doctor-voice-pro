'use client'

import { useState, useEffect } from 'react'
import { publicLeadsAPI, type PublicLead, type RegionData, type LeadStats } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, StatTile, EmptyState } from '@/components/app-shell/ui-kit'
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import {
  Search,
  Download,
  Save,
  Phone,
  Mail,
  MapPin,
  Building2,
  Users,
  TrendingUp,
  RefreshCw,
  Send,
  Trash2,
  ExternalLink,
  Filter,
  Database,
  Zap,
  Loader2,
} from 'lucide-react'

export default function PublicLeadsPage() {
  // 지역/업종 데이터
  const [regionData, setRegionData] = useState<RegionData | null>(null)

  // 검색 조건
  const [searchSido, setSearchSido] = useState('')
  const [searchSigungu, setSearchSigungu] = useState('')
  const [searchCategory, setSearchCategory] = useState('')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchLimit, setSearchLimit] = useState(100)

  // 검색 결과
  const [searchResults, setSearchResults] = useState<PublicLead[]>([])
  const [isSearching, setIsSearching] = useState(false)

  // 저장된 리드
  const [savedLeads, setSavedLeads] = useState<PublicLead[]>([])
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null)
  const [isLoadingLeads, setIsLoadingLeads] = useState(false)

  // 필터
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [filterCategory, setFilterCategory] = useState<string>('')
  const [filterSearch, setFilterSearch] = useState('')

  // 선택된 리드
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set())

  // 상세 다이얼로그
  const [detailLead, setDetailLead] = useState<PublicLead | null>(null)

  // 탭 상태
  const [activeTab, setActiveTab] = useState('search')

  // 이메일 추출 상태
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractingLeadId, setExtractingLeadId] = useState<string | null>(null)

  // 초기 데이터 로드
  useEffect(() => {
    loadRegionData()
    loadSavedLeads()
    loadStats()
  }, [])

  const loadRegionData = async () => {
    try {
      const data = await publicLeadsAPI.getRegions()
      setRegionData(data)
    } catch (error) {
      console.error('지역 데이터 로드 실패:', error)
    }
  }

  const loadSavedLeads = async () => {
    setIsLoadingLeads(true)
    try {
      const result = await publicLeadsAPI.getList({
        status: filterStatus || undefined,
        category: filterCategory || undefined,
        search: filterSearch || undefined,
        limit: 100,
      })
      setSavedLeads(result.leads)
    } catch (error) {
      console.error('리드 로드 실패:', error)
    } finally {
      setIsLoadingLeads(false)
    }
  }

  const loadStats = async () => {
    try {
      const stats = await publicLeadsAPI.getStats()
      setLeadStats(stats)
    } catch (error) {
      console.error('통계 로드 실패:', error)
    }
  }

  // 리드 검색
  const handleSearch = async () => {
    if (!searchSido) {
      toast.error('시도를 선택해주세요')
      return
    }

    setIsSearching(true)
    try {
      const result = await publicLeadsAPI.search({
        sido: searchSido,
        sigungu: searchSigungu || undefined,
        category: searchCategory || undefined,
        keyword: searchKeyword || undefined,
        limit: searchLimit,
      })

      setSearchResults(result.leads)
      toast.success(result.message || `${result.total}개의 리드를 수집했습니다`)
    } catch (error) {
      toast.error('검색 중 오류가 발생했습니다')
    } finally {
      setIsSearching(false)
    }
  }

  // 검색 결과 저장
  const handleSaveResults = async () => {
    if (searchResults.length === 0) {
      toast.error('저장할 리드가 없습니다')
      return
    }

    try {
      const result = await publicLeadsAPI.save(searchResults)
      toast.success(result.message)
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('저장 중 오류가 발생했습니다')
    }
  }

  // 선택된 리드 저장
  const handleSaveSelected = async () => {
    const selectedItems = searchResults.filter((lead) => selectedLeads.has(lead.id))
    if (selectedItems.length === 0) {
      toast.error('선택된 리드가 없습니다')
      return
    }

    try {
      const result = await publicLeadsAPI.save(selectedItems)
      toast.success(result.message)
      setSelectedLeads(new Set())
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('저장 중 오류가 발생했습니다')
    }
  }

  // 이메일 영업으로 내보내기
  const handleExportToOutreach = async () => {
    const leadsWithEmail = savedLeads.filter(
      (lead) => selectedLeads.has(lead.id) && lead.email
    )

    if (leadsWithEmail.length === 0) {
      toast.error('이메일이 있는 선택된 리드가 없습니다')
      return
    }

    try {
      const result = await publicLeadsAPI.exportToOutreach(
        leadsWithEmail.map((l) => l.id)
      )
      toast.success(result.message)
      setSelectedLeads(new Set())
      loadSavedLeads()
    } catch (error) {
      toast.error('내보내기 중 오류가 발생했습니다')
    }
  }

  // 단일 리드 이메일 추출
  const handleExtractEmail = async (leadId: string) => {
    setExtractingLeadId(leadId)
    try {
      const result = await publicLeadsAPI.extractEmail(leadId)
      if (result.email) {
        toast.success(`이메일 추출 성공: ${result.email}`)
      } else {
        toast.info('이메일을 찾을 수 없습니다')
      }
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('이메일 추출 중 오류가 발생했습니다')
    } finally {
      setExtractingLeadId(null)
    }
  }

  // 선택된 리드 이메일 일괄 추출
  const handleBatchExtractEmails = async () => {
    const leadsToExtract = savedLeads.filter(
      (lead) => selectedLeads.has(lead.id) && !lead.email
    )

    if (leadsToExtract.length === 0) {
      toast.error('이메일이 없는 선택된 리드가 없습니다')
      return
    }

    setIsExtracting(true)
    try {
      const result = await publicLeadsAPI.batchExtractEmails(
        leadsToExtract.map((l) => l.id)
      )
      toast.success(result.message)
      setSelectedLeads(new Set())
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('이메일 추출 중 오류가 발생했습니다')
    } finally {
      setIsExtracting(false)
    }
  }

  // 리드 삭제
  const handleDeleteLead = async (leadId: string) => {
    try {
      await publicLeadsAPI.delete(leadId)
      toast.success('리드가 삭제되었습니다')
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('삭제 중 오류가 발생했습니다')
    }
  }

  // 리드 상태 업데이트
  const handleUpdateStatus = async (leadId: string, status: string) => {
    try {
      await publicLeadsAPI.update(leadId, { status: status as PublicLead['status'] })
      toast.success('상태가 업데이트되었습니다')
      loadSavedLeads()
      loadStats()
    } catch (error) {
      toast.error('업데이트 중 오류가 발생했습니다')
    }
  }

  // 전체 선택/해제
  const handleSelectAll = (leads: PublicLead[], checked: boolean) => {
    if (checked) {
      setSelectedLeads(new Set(leads.map((l) => l.id)))
    } else {
      setSelectedLeads(new Set())
    }
  }

  // 개별 선택
  const handleSelectLead = (leadId: string, checked: boolean) => {
    const newSelected = new Set(selectedLeads)
    if (checked) {
      newSelected.add(leadId)
    } else {
      newSelected.delete(leadId)
    }
    setSelectedLeads(newSelected)
  }

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; tone: 'ok' | 'warn' | 'danger' | 'accent' | 'muted' }> = {
      new: { label: '신규', tone: 'accent' },
      contacted: { label: '연락함', tone: 'muted' },
      interested: { label: '관심있음', tone: 'ok' },
      not_interested: { label: '관심없음', tone: 'danger' },
      converted: { label: '전환됨', tone: 'ok' },
    }
    const config = statusMap[status] || { label: status, tone: 'muted' as const }
    return <Pill tone={config.tone}>{config.label}</Pill>
  }

  const getScorePill = (score: number) => (
    <Pill tone={score >= 70 ? 'ok' : score >= 40 ? 'accent' : 'muted'}>
      <span className="tabular-nums">{score}</span>점
    </Pill>
  )

  const thCls = 'text-[12px] font-medium uppercase tracking-wide text-muted-foreground'

  return (
    <div className="space-y-6">
      <PageHeader
        title="공공데이터 리드 수집"
        description="공공데이터 API로 자영업자 정보를 모아 리드로 저장합니다."
      />

      {/* 통계 카드 */}
      {leadStats && (
        <div className="grid gap-4 md:grid-cols-4">
          <StatTile label="총 리드" value={leadStats.total} icon={<Database className="h-4 w-4" />} />
          <StatTile label="오늘 수집" value={leadStats.recent_collected} icon={<TrendingUp className="h-4 w-4" />} />
          <StatTile label="연락 완료" value={leadStats.by_status?.contacted || 0} icon={<Phone className="h-4 w-4" />} />
          <StatTile label="전환됨" value={leadStats.by_status?.converted || 0} tone="ok" icon={<Users className="h-4 w-4" />} />
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="search">리드 수집</TabsTrigger>
          <TabsTrigger value="saved">저장된 리드 ({savedLeads.length})</TabsTrigger>
        </TabsList>

        {/* 리드 수집 탭 */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>검색 조건</CardTitle>
              <CardDescription>
                지역과 업종을 선택하여 자영업자 정보를 수집합니다
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-4">
                <div className="space-y-2">
                  <Label>시도 *</Label>
                  <Select value={searchSido} onValueChange={(v) => { setSearchSido(v); setSearchSigungu('') }}>
                    <SelectTrigger>
                      <SelectValue placeholder="시도 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {regionData?.sido_list.map((sido) => (
                        <SelectItem key={sido} value={sido}>{sido}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>시군구</Label>
                  <Select value={searchSigungu} onValueChange={setSearchSigungu} disabled={!searchSido}>
                    <SelectTrigger>
                      <SelectValue placeholder="시군구 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {searchSido && regionData?.sigungu_map[searchSido]?.map((sigungu) => (
                        <SelectItem key={sigungu} value={sigungu}>{sigungu}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>업종</Label>
                  <Select value={searchCategory} onValueChange={setSearchCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="업종 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {regionData?.categories.map((cat) => (
                        <SelectItem key={cat.code} value={cat.name}>{cat.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>키워드</Label>
                  <Input
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    placeholder="상호명 키워드"
                  />
                </div>
              </div>

              <div className="flex items-end gap-4">
                <div className="space-y-2">
                  <Label>수집 개수</Label>
                  <Select value={String(searchLimit)} onValueChange={(v) => setSearchLimit(Number(v))}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="50">50개</SelectItem>
                      <SelectItem value="100">100개</SelectItem>
                      <SelectItem value="200">200개</SelectItem>
                      <SelectItem value="500">500개</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button onClick={handleSearch} disabled={isSearching}>
                  {isSearching ? (
                    <RefreshCw className="animate-spin" />
                  ) : (
                    <Search />
                  )}
                  검색
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 검색 결과 */}
          {searchResults.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>검색 결과</CardTitle>
                    <CardDescription><span className="tabular-nums">{searchResults.length}</span>개의 리드를 찾았습니다</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleSaveSelected} disabled={selectedLeads.size === 0}>
                      <Save />
                      선택 저장 (<span className="tabular-nums">{selectedLeads.size}</span>)
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleSaveResults}>
                      <Download />
                      전체 저장
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table className="text-sm">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          <Checkbox
                            checked={selectedLeads.size === searchResults.length}
                            onCheckedChange={(checked) => handleSelectAll(searchResults, checked as boolean)}
                          />
                        </TableHead>
                        <TableHead className={thCls}>상호명</TableHead>
                        <TableHead className={thCls}>업종</TableHead>
                        <TableHead className={thCls}>주소</TableHead>
                        <TableHead className={thCls}>전화번호</TableHead>
                        <TableHead className={`${thCls} text-right`}>스코어</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {searchResults.map((lead) => (
                        <TableRow key={lead.id} className="cursor-pointer hover:bg-muted/40" onClick={() => setDetailLead(lead)}>
                          <TableCell className="py-2.5" onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={selectedLeads.has(lead.id)}
                              onCheckedChange={(checked) => handleSelectLead(lead.id, checked as boolean)}
                            />
                          </TableCell>
                          <TableCell className="py-2.5 font-medium">{lead.business_name}</TableCell>
                          <TableCell className="py-2.5">{lead.category}</TableCell>
                          <TableCell className="max-w-[200px] truncate py-2.5">{lead.address}</TableCell>
                          <TableCell className="py-2.5 tabular-nums">{lead.phone || '-'}</TableCell>
                          <TableCell className="py-2.5 text-right">{getScorePill(lead.score)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* 저장된 리드 탭 */}
        <TabsContent value="saved" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>저장된 리드</CardTitle>
                  <CardDescription>수집해 저장한 리드를 관리합니다</CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    onClick={handleBatchExtractEmails}
                    disabled={selectedLeads.size === 0 || isExtracting}
                  >
                    {isExtracting ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Zap />
                    )}
                    이메일 추출
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleExportToOutreach}
                    disabled={selectedLeads.size === 0}
                  >
                    <Send />
                    이메일 영업으로 내보내기
                  </Button>
                  <Button variant="ghost" size="sm" onClick={loadSavedLeads}>
                    <RefreshCw />
                    새로고침
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 필터 */}
              <div className="flex flex-wrap gap-3">
                <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); loadSavedLeads() }}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="상태 필터" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">전체</SelectItem>
                    <SelectItem value="new">신규</SelectItem>
                    <SelectItem value="contacted">연락함</SelectItem>
                    <SelectItem value="interested">관심있음</SelectItem>
                    <SelectItem value="not_interested">관심없음</SelectItem>
                    <SelectItem value="converted">전환됨</SelectItem>
                  </SelectContent>
                </Select>

                <Select value={filterCategory} onValueChange={(v) => { setFilterCategory(v); loadSavedLeads() }}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="업종 필터" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">전체</SelectItem>
                    {regionData?.categories.map((cat) => (
                      <SelectItem key={cat.code} value={cat.name}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="min-w-[200px] flex-1">
                  <Input
                    value={filterSearch}
                    onChange={(e) => setFilterSearch(e.target.value)}
                    placeholder="상호명, 주소, 전화번호 검색..."
                    onKeyDown={(e) => e.key === 'Enter' && loadSavedLeads()}
                  />
                </div>
                <Button variant="outline" size="icon" onClick={loadSavedLeads} title="필터 적용">
                  <Filter className="h-4 w-4" />
                </Button>
              </div>

              {/* 리드 테이블 */}
              {isLoadingLeads ? (
                <div className="flex justify-center py-16">
                  <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                </div>
              ) : savedLeads.length === 0 ? (
                <EmptyState
                  icon={<Database className="h-8 w-8" />}
                  title="저장된 리드가 없습니다"
                  description="리드 수집 탭에서 지역과 업종을 골라 검색한 뒤 저장하세요."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setActiveTab('search')}>
                      <Search />
                      리드 수집하기
                    </Button>
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table className="text-sm">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          <Checkbox
                            checked={selectedLeads.size === savedLeads.length && savedLeads.length > 0}
                            onCheckedChange={(checked) => handleSelectAll(savedLeads, checked as boolean)}
                          />
                        </TableHead>
                        <TableHead className={thCls}>상호명</TableHead>
                        <TableHead className={thCls}>업종</TableHead>
                        <TableHead className={thCls}>지역</TableHead>
                        <TableHead className={thCls}>연락처</TableHead>
                        <TableHead className={thCls}>상태</TableHead>
                        <TableHead className={`${thCls} text-right`}>스코어</TableHead>
                        <TableHead className={`${thCls} text-right`}>작업</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {savedLeads.map((lead) => (
                        <TableRow key={lead.id} className="hover:bg-muted/40">
                          <TableCell className="py-2.5">
                            <Checkbox
                              checked={selectedLeads.has(lead.id)}
                              onCheckedChange={(checked) => handleSelectLead(lead.id, checked as boolean)}
                            />
                          </TableCell>
                          <TableCell className="py-2.5 font-medium">
                            <button
                              className="text-left hover:underline"
                              onClick={() => setDetailLead(lead)}
                            >
                              {lead.business_name}
                            </button>
                          </TableCell>
                          <TableCell className="py-2.5">{lead.category}</TableCell>
                          <TableCell className="py-2.5">{lead.sigungu}</TableCell>
                          <TableCell className="py-2.5">
                            <div className="space-y-1">
                              {lead.phone && (
                                <a href={`tel:${lead.phone}`} className="flex items-center gap-1 tabular-nums hover:underline">
                                  <Phone className="h-3 w-3 text-muted-foreground" /> {lead.phone}
                                </a>
                              )}
                              {lead.email && (
                                <a href={`mailto:${lead.email}`} className="flex items-center gap-1 hover:underline">
                                  <Mail className="h-3 w-3 text-muted-foreground" /> {lead.email}
                                </a>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="py-2.5">
                            <Select
                              value={lead.status}
                              onValueChange={(v) => handleUpdateStatus(lead.id, v)}
                            >
                              <SelectTrigger className="h-8 w-28">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="new">신규</SelectItem>
                                <SelectItem value="contacted">연락함</SelectItem>
                                <SelectItem value="interested">관심있음</SelectItem>
                                <SelectItem value="not_interested">관심없음</SelectItem>
                                <SelectItem value="converted">전환됨</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className="py-2.5 text-right">{getScorePill(lead.score)}</TableCell>
                          <TableCell className="py-2.5 text-right">
                            <div className="flex justify-end gap-1">
                              {!lead.email && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleExtractEmail(lead.id)}
                                  disabled={extractingLeadId === lead.id}
                                  title="이메일 추출"
                                >
                                  {extractingLeadId === lead.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                  ) : (
                                    <Zap className="h-4 w-4 text-primary" />
                                  )}
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeleteLead(lead.id)}
                                title="삭제"
                              >
                                <Trash2 className="h-4 w-4 text-danger" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 상세 다이얼로그 */}
      <Dialog open={!!detailLead} onOpenChange={(open) => !open && setDetailLead(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{detailLead?.business_name}</DialogTitle>
            <DialogDescription>{detailLead?.category}</DialogDescription>
          </DialogHeader>

          {detailLead && (
            <div className="space-y-4 text-sm">
              <div className="grid gap-3">
                <div className="flex items-start gap-2">
                  <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-[13px] font-medium text-muted-foreground">주소</p>
                    <p>{detailLead.road_address || detailLead.address}</p>
                  </div>
                </div>

                {detailLead.phone && (
                  <div className="flex items-start gap-2">
                    <Phone className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-[13px] font-medium text-muted-foreground">전화번호</p>
                      <a href={`tel:${detailLead.phone}`} className="tabular-nums text-primary hover:underline">
                        {detailLead.phone}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.email && (
                  <div className="flex items-start gap-2">
                    <Mail className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-[13px] font-medium text-muted-foreground">이메일</p>
                      <a href={`mailto:${detailLead.email}`} className="text-primary hover:underline">
                        {detailLead.email}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.website && (
                  <div className="flex items-start gap-2">
                    <ExternalLink className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-[13px] font-medium text-muted-foreground">웹사이트</p>
                      <a
                        href={detailLead.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="break-all text-primary hover:underline"
                      >
                        {detailLead.website}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.owner_name && (
                  <div className="flex items-start gap-2">
                    <Building2 className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-[13px] font-medium text-muted-foreground">대표자</p>
                      <p>{detailLead.owner_name}</p>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between border-t pt-3">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">리드 스코어</span>
                    {getScorePill(detailLead.score)}
                  </div>
                  <div>
                    {getStatusBadge(detailLead.status)}
                  </div>
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                출처: {detailLead.source}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="ghost" onClick={() => setDetailLead(null)}>
              닫기
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
