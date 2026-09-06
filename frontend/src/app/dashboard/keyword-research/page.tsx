'use client'

import { useState, useMemo, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Search,
  Loader2,
  Copy,
  Download,
  ChevronDown,
  ChevronRight,
  Network,
  ListTree,
  Layers,
  Clock,
  Sparkles,
  CheckSquare,
  Square,
  Save,
} from 'lucide-react'
import { toast } from 'sonner'
import { topPostsAPI } from '@/lib/api'
import type { KeywordResearchResult, ResearchKeyword } from '@/lib/api'

// 수집 개수 옵션 - 체크한 개수만큼 가져온다
const COUNT_OPTIONS = [
  { value: 100, label: '100개', hint: '빠름 · 약 15초' },
  { value: 200, label: '200개', hint: '약 25초' },
  { value: 300, label: '300개', hint: '기본 · 약 40초' },
  { value: 400, label: '400개', hint: '약 55초' },
  { value: 500, label: '500개', hint: '약 70초' },
  { value: 700, label: '700개', hint: '약 100초' },
  { value: 1000, label: '1000개', hint: '최대 · 약 150초' },
]

const TYPE_COLORS: Record<string, string> = {
  상업형: 'bg-amber-100 text-amber-800 border-amber-200',
  정보형: 'bg-blue-100 text-blue-800 border-blue-200',
  지역형: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  장소형: 'bg-violet-100 text-violet-800 border-violet-200',
  일반: 'bg-gray-100 text-gray-700 border-gray-200',
}

const TYPE_ORDER = ['상업형', '정보형', '지역형', '장소형', '일반']

const CATEGORY_OPTIONS = [
  { value: 'hospital', label: '병원/의료' },
  { value: 'restaurant', label: '맛집/음식점' },
  { value: 'beauty', label: '뷰티/화장품' },
  { value: 'parenting', label: '육아/교육' },
  { value: 'travel', label: '여행/숙소' },
  { value: 'tech', label: 'IT/리뷰' },
  { value: 'fitness', label: '운동/헬스' },
  { value: 'general', label: '일반' },
]

export default function KeywordResearchPage() {
  const [keyword, setKeyword] = useState('')
  const [targetCount, setTargetCount] = useState(300)
  const [maxDepth, setMaxDepth] = useState(2)
  const [useRegions, setUseRegions] = useState(true)
  const [useGoogle, setUseGoogle] = useState(true)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<KeywordResearchResult | null>(null)

  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [filterType, setFilterType] = useState<string>('all')
  const [listQuery, setListQuery] = useState('')
  const [saveCategory, setSaveCategory] = useState('hospital')
  const [saving, setSaving] = useState(false)

  // 키워드 수집 실행
  const handleSearch = useCallback(async () => {
    const seed = keyword.trim()
    if (!seed) {
      toast.error('검색할 키워드를 입력해주세요')
      return
    }

    setLoading(true)
    setResult(null)
    setSelected(new Set())
    setExpandedGroups(new Set())

    const loadingToast = toast.loading(
      `"${seed}" 연관검색어를 ${targetCount}개까지 수집 중입니다...`
    )

    try {
      const data = await topPostsAPI.researchKeywords({
        keyword: seed,
        target_count: targetCount,
        max_depth: maxDepth,
        use_google: useGoogle,
        use_regions: useRegions,
      })
      setResult(data)
      // 상위 5개 그룹은 기본으로 펼쳐둔다
      setExpandedGroups(new Set(data.groups.slice(0, 5).map((g) => g.hub)))
      toast.success(
        `${data.collected_count}개 수집 완료 (${data.stats.group_count}개 그룹, ${data.elapsed_seconds}초)`,
        { id: loadingToast }
      )
    } catch (error: any) {
      const message =
        error?.response?.data?.detail || error?.message || '키워드 수집에 실패했습니다'
      toast.error(message, { id: loadingToast })
    } finally {
      setLoading(false)
    }
  }, [keyword, targetCount, maxDepth, useGoogle, useRegions])

  const toggleGroup = (hub: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(hub)) next.delete(hub)
      else next.add(hub)
      return next
    })
  }

  const toggleSelected = (kw: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(kw)) next.delete(kw)
      else next.add(kw)
      return next
    })
  }

  const selectGroup = (keywords: string[], select: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      keywords.forEach((k) => (select ? next.add(k) : next.delete(k)))
      return next
    })
  }

  // 전체 목록 필터링
  const filteredKeywords = useMemo(() => {
    if (!result) return []
    const query = listQuery.trim().toLowerCase()
    return result.keywords.filter((k) => {
      if (filterType !== 'all' && k.type !== filterType) return false
      if (query && !k.keyword.toLowerCase().includes(query)) return false
      return true
    })
  }, [result, filterType, listQuery])

  const copyKeywords = (keywords: string[], label: string) => {
    if (keywords.length === 0) {
      toast.error('복사할 키워드가 없습니다')
      return
    }
    navigator.clipboard.writeText(keywords.join('\n'))
    toast.success(`${label} ${keywords.length}개를 복사했습니다`)
  }

  const downloadCsv = () => {
    if (!result) return
    const rows = [
      ['키워드', '유형', '단계', '상위키워드', '수집출처'],
      ...result.keywords.map((k) => [
        k.keyword,
        k.type,
        String(k.depth),
        k.parent || '',
        k.source,
      ]),
    ]
    const csv = '﻿' + rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `연관검색어_${result.seed}_${result.collected_count}개.csv`
    link.click()
    URL.revokeObjectURL(url)
    toast.success('CSV 파일을 다운로드했습니다')
  }

  const handleSaveSelected = async () => {
    if (selected.size === 0) {
      toast.error('저장할 키워드를 선택해주세요')
      return
    }
    setSaving(true)
    try {
      const res = await topPostsAPI.saveResearchKeywords(saveCategory, Array.from(selected))
      toast.success(`${res.saved}개 저장 완료 (중복 ${res.skipped}개 제외)`)
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || '저장에 실패했습니다')
    } finally {
      setSaving(false)
    }
  }

  const progressPercent = result
    ? Math.min(100, Math.round((result.collected_count / result.target_count) * 100))
    : 0

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Network className="h-6 w-6 text-indigo-600" />
          연관 키워드 대량 수집
        </h1>
        <p className="text-muted-foreground mt-1">
          키워드 하나를 넣으면 서브로 연결된 연관검색어까지 원하는 개수만큼 캐냅니다
        </p>
      </div>

      {/* 검색 설정 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            키워드 검색
          </CardTitle>
          <CardDescription>
            예를 들어 &quot;임플란트&quot;를 넣으면 임플란트 후기 / 임플란트 가격 / 강남 임플란트 처럼
            하위로 연결된 연관검색어를 묶어서 보여줍니다
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-col md:flex-row gap-3">
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !loading) handleSearch()
              }}
              placeholder="검색할 키워드 (예: 임플란트)"
              className="md:flex-1 h-11 text-base"
              disabled={loading}
            />
            <Button onClick={handleSearch} disabled={loading} className="h-11 md:w-40">
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  수집 중...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  연관검색어 수집
                </>
              )}
            </Button>
          </div>

          {/* 수집 개수 선택 */}
          <div>
            <label className="text-sm font-medium mb-2 block">
              수집 개수{' '}
              <span className="text-muted-foreground font-normal">
                — 체크한 개수만큼 가져옵니다
              </span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {COUNT_OPTIONS.map((option) => {
                const isSelected = targetCount === option.value
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setTargetCount(option.value)}
                    disabled={loading}
                    className={`p-3 rounded-lg border-2 text-left transition-all ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center gap-1.5">
                      {isSelected ? (
                        <CheckSquare className="h-4 w-4 text-indigo-600" />
                      ) : (
                        <Square className="h-4 w-4 text-gray-400" />
                      )}
                      <span className="font-semibold text-sm">{option.label}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-1">{option.hint}</p>
                  </button>
                )
              })}
            </div>
          </div>

          {/* 확장 옵션 */}
          <div className="flex flex-wrap items-center gap-6 pt-1">
            <div className="flex items-center gap-2">
              <Checkbox
                id="use-regions"
                checked={useRegions}
                onCheckedChange={(v) => setUseRegions(Boolean(v))}
                disabled={loading}
              />
              <label htmlFor="use-regions" className="text-sm cursor-pointer">
                지역명 조합 포함 <span className="text-muted-foreground">(강남 임플란트)</span>
              </label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="use-google"
                checked={useGoogle}
                onCheckedChange={(v) => setUseGoogle(Boolean(v))}
                disabled={loading}
              />
              <label htmlFor="use-google" className="text-sm cursor-pointer">
                구글 자동완성 병행 <span className="text-muted-foreground">(질문형 보완)</span>
              </label>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm">확장 깊이</span>
              <Select
                value={String(maxDepth)}
                onValueChange={(v) => setMaxDepth(Number(v))}
                disabled={loading}
              >
                <SelectTrigger className="w-36 h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1단계 (빠름)</SelectItem>
                  <SelectItem value="2">2단계 (기본)</SelectItem>
                  <SelectItem value="3">3단계 (깊게)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {loading && (
            <div className="p-4 bg-blue-50 rounded-lg space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-blue-900">
                <Loader2 className="h-4 w-4 animate-spin" />
                네이버 자동완성 · 연관검색어를 훑는 중입니다 (최대 2~3분)
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
                <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-500" />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 결과 */}
      {result && (
        <>
          {/* 요약 통계 */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">수집된 키워드</p>
                <p className="text-2xl font-bold">
                  {result.collected_count}
                  <span className="text-base font-normal text-muted-foreground">
                    {' '}
                    / {result.target_count}
                  </span>
                </p>
                <Progress value={progressPercent} className="h-1.5 mt-2" />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">연관 그룹</p>
                    <p className="text-2xl font-bold">{result.stats.group_count}</p>
                  </div>
                  <Layers className="h-7 w-7 text-purple-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">선택됨</p>
                    <p className="text-2xl font-bold">{selected.size}</p>
                  </div>
                  <CheckSquare className="h-7 w-7 text-emerald-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">소요 시간</p>
                    <p className="text-2xl font-bold">{result.elapsed_seconds}초</p>
                  </div>
                  <Clock className="h-7 w-7 text-blue-500" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 유형 분포 */}
          <Card>
            <CardContent className="pt-6 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium mr-1">유형 분포</span>
              {TYPE_ORDER.filter((t) => result.stats.by_type[t]).map((type) => (
                <Badge key={type} variant="outline" className={TYPE_COLORS[type]}>
                  {type} {result.stats.by_type[type]}개
                </Badge>
              ))}
              {result.collected_count < result.target_count && (
                <span className="text-xs text-muted-foreground ml-auto">
                  네이버에 존재하는 연관검색어를 모두 긁어와 {result.collected_count}개에서
                  멈췄습니다. 더 필요하면 확장 깊이를 올려보세요.
                </span>
              )}
            </CardContent>
          </Card>

          {/* 액션 바 */}
          <Card>
            <CardContent className="pt-6 flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyKeywords(result.keywords.map((k) => k.keyword), '전체 키워드')}
              >
                <Copy className="h-4 w-4 mr-2" />
                전체 복사
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyKeywords(Array.from(selected), '선택 키워드')}
                disabled={selected.size === 0}
              >
                <Copy className="h-4 w-4 mr-2" />
                선택 복사 ({selected.size})
              </Button>
              <Button variant="outline" size="sm" onClick={downloadCsv}>
                <Download className="h-4 w-4 mr-2" />
                CSV 다운로드
              </Button>

              <div className="flex items-center gap-2 ml-auto">
                <Select value={saveCategory} onValueChange={setSaveCategory}>
                  <SelectTrigger className="w-40 h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  onClick={handleSaveSelected}
                  disabled={selected.size === 0 || saving}
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  선택 키워드 분석풀에 저장
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 허브 키워드 (직접 연관검색어) */}
          {result.hubs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5 text-amber-500" />
                  &quot;{result.seed}&quot; 직접 연관검색어
                </CardTitle>
                <CardDescription>
                  각 키워드 아래에 하위 연관검색어가 몇 개씩 붙어 있는지 함께 보여줍니다
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {result.hubs.map((hub) => (
                  <button
                    key={hub.keyword}
                    onClick={() => {
                      toggleGroup(hub.keyword)
                      document
                        .getElementById(`group-${hub.keyword}`)
                        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    }}
                    className={`px-3 py-1.5 rounded-full border text-sm transition-colors hover:brightness-95 ${
                      TYPE_COLORS[hub.type] || TYPE_COLORS['일반']
                    }`}
                  >
                    {hub.keyword}
                    <span className="ml-1.5 opacity-70">+{hub.count - 1}</span>
                  </button>
                ))}
              </CardContent>
            </Card>
          )}

          {/* 그룹 / 전체목록 탭 */}
          <Tabs defaultValue="groups" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2 max-w-md">
              <TabsTrigger value="groups" className="flex items-center gap-2">
                <ListTree className="h-4 w-4" />
                연관 그룹 ({result.groups.length})
              </TabsTrigger>
              <TabsTrigger value="all" className="flex items-center gap-2">
                <Layers className="h-4 w-4" />
                전체 목록 ({result.collected_count})
              </TabsTrigger>
            </TabsList>

            {/* 그룹 트리 */}
            <TabsContent value="groups" className="space-y-3">
              {result.groups.map((group) => {
                const isOpen = expandedGroups.has(group.hub)
                const groupKeywords = [group.hub, ...group.children.map((c) => c.keyword)]
                const allSelected = groupKeywords.every((k) => selected.has(k))
                return (
                  <Card key={group.hub} id={`group-${group.hub}`}>
                    <CardContent className="pt-5">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => toggleGroup(group.hub)}
                          className="flex items-center gap-2 flex-1 text-left"
                        >
                          {isOpen ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                          )}
                          <span className="font-semibold">{group.hub}</span>
                          <Badge variant="outline" className={TYPE_COLORS[group.type]}>
                            {group.type}
                          </Badge>
                          <Badge variant="secondary">{group.count}개</Badge>
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => selectGroup(groupKeywords, !allSelected)}
                        >
                          {allSelected ? '그룹 해제' : '그룹 선택'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyKeywords(groupKeywords, group.hub)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>

                      {isOpen && (
                        <div className="mt-3 pl-6 border-l-2 border-gray-100 space-y-1">
                          {group.children.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-1">
                              하위 연관검색어가 없습니다
                            </p>
                          ) : (
                            group.children.map((child) => (
                              <KeywordRow
                                key={child.keyword}
                                item={child}
                                checked={selected.has(child.keyword)}
                                onToggle={toggleSelected}
                              />
                            ))
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </TabsContent>

            {/* 전체 목록 */}
            <TabsContent value="all" className="space-y-4">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex flex-col sm:flex-row gap-3">
                    <Input
                      value={listQuery}
                      onChange={(e) => setListQuery(e.target.value)}
                      placeholder="목록 안에서 검색"
                      className="sm:flex-1"
                    />
                    <Select value={filterType} onValueChange={setFilterType}>
                      <SelectTrigger className="sm:w-44">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">전체 유형</SelectItem>
                        {TYPE_ORDER.filter((t) => result.stats.by_type[t]).map((type) => (
                          <SelectItem key={type} value={type}>
                            {type} ({result.stats.by_type[type]})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      onClick={() =>
                        selectGroup(
                          filteredKeywords.map((k) => k.keyword),
                          !filteredKeywords.every((k) => selected.has(k.keyword))
                        )
                      }
                    >
                      화면 전체 선택/해제
                    </Button>
                  </div>

                  <p className="text-sm text-muted-foreground">
                    {filteredKeywords.length}개 표시 중
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-6 gap-y-1 max-h-[600px] overflow-y-auto pr-2">
                    {filteredKeywords.map((item) => (
                      <KeywordRow
                        key={item.keyword}
                        item={item}
                        checked={selected.has(item.keyword)}
                        onToggle={toggleSelected}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}

function KeywordRow({
  item,
  checked,
  onToggle,
}: {
  item: ResearchKeyword
  checked: boolean
  onToggle: (keyword: string) => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onToggle(item.keyword)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onToggle(item.keyword)
        }
      }}
      className="flex items-center gap-2 py-1 cursor-pointer group select-none"
    >
      <Checkbox checked={checked} className="pointer-events-none" tabIndex={-1} />
      <span className="text-sm group-hover:text-indigo-600 truncate">{item.keyword}</span>
      <Badge
        variant="outline"
        className={`ml-auto shrink-0 text-[10px] px-1.5 py-0 ${TYPE_COLORS[item.type] || TYPE_COLORS['일반']}`}
      >
        {item.type}
      </Badge>
    </div>
  )
}
