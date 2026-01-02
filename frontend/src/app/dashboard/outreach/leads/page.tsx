'use client'

import { useState, useEffect } from 'react'
import { publicLeadsAPI, type PublicLead, type RegionData, type LeadStats } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
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
    const statusMap: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      new: { label: '신규', variant: 'default' },
      contacted: { label: '연락함', variant: 'secondary' },
      interested: { label: '관심있음', variant: 'default' },
      not_interested: { label: '관심없음', variant: 'destructive' },
      converted: { label: '전환됨', variant: 'outline' },
    }
    const config = statusMap[status] || { label: status, variant: 'default' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">공공데이터 리드 수집</h1>
          <p className="text-muted-foreground">
            공공데이터 API를 활용하여 자영업자 정보를 수집합니다
          </p>
        </div>
      </div>

      {/* 통계 카드 */}
      {leadStats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">총 리드</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{leadStats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">오늘 수집</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{leadStats.recent_collected}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">연락 완료</CardTitle>
              <Phone className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{leadStats.by_status?.contacted || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">전환됨</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{leadStats.by_status?.converted || 0}</div>
            </CardContent>
          </Card>
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

              <div className="flex gap-4 items-end">
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
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4 mr-2" />
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
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>검색 결과</CardTitle>
                    <CardDescription>{searchResults.length}개의 리드를 찾았습니다</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={handleSaveSelected} disabled={selectedLeads.size === 0}>
                      <Save className="h-4 w-4 mr-2" />
                      선택 저장 ({selectedLeads.size})
                    </Button>
                    <Button onClick={handleSaveResults}>
                      <Download className="h-4 w-4 mr-2" />
                      전체 저장
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={selectedLeads.size === searchResults.length}
                          onCheckedChange={(checked) => handleSelectAll(searchResults, checked as boolean)}
                        />
                      </TableHead>
                      <TableHead>상호명</TableHead>
                      <TableHead>업종</TableHead>
                      <TableHead>주소</TableHead>
                      <TableHead>전화번호</TableHead>
                      <TableHead>스코어</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {searchResults.map((lead) => (
                      <TableRow key={lead.id} className="cursor-pointer" onClick={() => setDetailLead(lead)}>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={selectedLeads.has(lead.id)}
                            onCheckedChange={(checked) => handleSelectLead(lead.id, checked as boolean)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{lead.business_name}</TableCell>
                        <TableCell>{lead.category}</TableCell>
                        <TableCell className="max-w-[200px] truncate">{lead.address}</TableCell>
                        <TableCell>{lead.phone || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={lead.score >= 70 ? 'default' : lead.score >= 40 ? 'secondary' : 'outline'}>
                            {lead.score}점
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* 저장된 리드 탭 */}
        <TabsContent value="saved" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>저장된 리드</CardTitle>
                  <CardDescription>수집하여 저장한 리드를 관리합니다</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="default"
                    onClick={handleBatchExtractEmails}
                    disabled={selectedLeads.size === 0 || isExtracting}
                  >
                    {isExtracting ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4 mr-2" />
                    )}
                    이메일 추출
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleExportToOutreach}
                    disabled={selectedLeads.size === 0}
                  >
                    <Send className="h-4 w-4 mr-2" />
                    이메일 영업으로 내보내기
                  </Button>
                  <Button variant="outline" onClick={loadSavedLeads}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    새로고침
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 필터 */}
              <div className="flex gap-4">
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

                <div className="flex-1">
                  <Input
                    value={filterSearch}
                    onChange={(e) => setFilterSearch(e.target.value)}
                    placeholder="상호명, 주소, 전화번호 검색..."
                    onKeyDown={(e) => e.key === 'Enter' && loadSavedLeads()}
                  />
                </div>
                <Button variant="outline" onClick={loadSavedLeads}>
                  <Filter className="h-4 w-4" />
                </Button>
              </div>

              {/* 리드 테이블 */}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedLeads.size === savedLeads.length && savedLeads.length > 0}
                        onCheckedChange={(checked) => handleSelectAll(savedLeads, checked as boolean)}
                      />
                    </TableHead>
                    <TableHead>상호명</TableHead>
                    <TableHead>업종</TableHead>
                    <TableHead>지역</TableHead>
                    <TableHead>연락처</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>스코어</TableHead>
                    <TableHead>작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingLeads ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
                        로딩 중...
                      </TableCell>
                    </TableRow>
                  ) : savedLeads.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                        저장된 리드가 없습니다
                      </TableCell>
                    </TableRow>
                  ) : (
                    savedLeads.map((lead) => (
                      <TableRow key={lead.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedLeads.has(lead.id)}
                            onCheckedChange={(checked) => handleSelectLead(lead.id, checked as boolean)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          <button
                            className="text-left hover:underline"
                            onClick={() => setDetailLead(lead)}
                          >
                            {lead.business_name}
                          </button>
                        </TableCell>
                        <TableCell>{lead.category}</TableCell>
                        <TableCell>{lead.sigungu}</TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {lead.phone && (
                              <a href={`tel:${lead.phone}`} className="flex items-center gap-1 text-sm hover:underline">
                                <Phone className="h-3 w-3" /> {lead.phone}
                              </a>
                            )}
                            {lead.email && (
                              <a href={`mailto:${lead.email}`} className="flex items-center gap-1 text-sm hover:underline">
                                <Mail className="h-3 w-3" /> {lead.email}
                              </a>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={lead.status}
                            onValueChange={(v) => handleUpdateStatus(lead.id, v)}
                          >
                            <SelectTrigger className="w-28 h-8">
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
                        <TableCell>
                          <Badge variant={lead.score >= 70 ? 'default' : lead.score >= 40 ? 'secondary' : 'outline'}>
                            {lead.score}점
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {!lead.email && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleExtractEmail(lead.id)}
                                disabled={extractingLeadId === lead.id}
                                title="이메일 추출"
                              >
                                {extractingLeadId === lead.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                                ) : (
                                  <Zap className="h-4 w-4 text-blue-500" />
                                )}
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteLead(lead.id)}
                              title="삭제"
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
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
            <div className="space-y-4">
              <div className="grid gap-3">
                <div className="flex items-start gap-2">
                  <MapPin className="h-4 w-4 mt-1 text-muted-foreground" />
                  <div>
                    <p className="font-medium">주소</p>
                    <p className="text-sm text-muted-foreground">{detailLead.road_address || detailLead.address}</p>
                  </div>
                </div>

                {detailLead.phone && (
                  <div className="flex items-start gap-2">
                    <Phone className="h-4 w-4 mt-1 text-muted-foreground" />
                    <div>
                      <p className="font-medium">전화번호</p>
                      <a href={`tel:${detailLead.phone}`} className="text-sm text-blue-600 hover:underline">
                        {detailLead.phone}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.email && (
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 mt-1 text-muted-foreground" />
                    <div>
                      <p className="font-medium">이메일</p>
                      <a href={`mailto:${detailLead.email}`} className="text-sm text-blue-600 hover:underline">
                        {detailLead.email}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.website && (
                  <div className="flex items-start gap-2">
                    <ExternalLink className="h-4 w-4 mt-1 text-muted-foreground" />
                    <div>
                      <p className="font-medium">웹사이트</p>
                      <a
                        href={detailLead.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-600 hover:underline"
                      >
                        {detailLead.website}
                      </a>
                    </div>
                  </div>
                )}

                {detailLead.owner_name && (
                  <div className="flex items-start gap-2">
                    <Building2 className="h-4 w-4 mt-1 text-muted-foreground" />
                    <div>
                      <p className="font-medium">대표자</p>
                      <p className="text-sm text-muted-foreground">{detailLead.owner_name}</p>
                    </div>
                  </div>
                )}

                <div className="flex justify-between items-center pt-2">
                  <div>
                    <span className="text-sm text-muted-foreground">리드 스코어: </span>
                    <Badge variant={detailLead.score >= 70 ? 'default' : detailLead.score >= 40 ? 'secondary' : 'outline'}>
                      {detailLead.score}점
                    </Badge>
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
            <Button variant="outline" onClick={() => setDetailLead(null)}>
              닫기
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
