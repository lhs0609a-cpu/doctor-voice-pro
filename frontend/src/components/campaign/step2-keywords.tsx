'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, BarChart3, ChevronDown, ChevronUp, Loader2, Plus, Search, Target, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { keywordBatchAPI } from '@/lib/api'
import { VERDICT_LABEL, campaignAPI, type Keyword, type Task } from '@/lib/campaign-api'
import { VERDICT_LABEL as MY_VERDICT_LABEL, VERDICT_TONE as MY_VERDICT_TONE, blogIndexAPI } from '@/lib/blog-index-api'
import { Pill as KitPill } from '@/components/app-shell/ui-kit'
import { BlogIndexPanel } from '@/components/blog-index/blog-index-card'
import { ChipsInput, EmptyNote, Pill, StepFooter, TABLE_CLS, TaskProgress, errMsg, fmt, taskOutcome, type StepProps } from './common'
import { KeywordSerpDialog } from './keyword-serp-dialog'

const SOURCE_LABEL: Record<string, string> = { combo: '조합', related: '연관', manual: '직접', seed: '제안' }
const COMP_LABEL: Record<string, { label: string; tone: 'ok' | 'warn' | 'crit' | 'muted' }> = {
  low: { label: '낮음', tone: 'ok' }, mid: { label: '보통', tone: 'warn' }, high: { label: '높음', tone: 'crit' },
}

export function Step2Keywords({ campaign, client, goStep }: StepProps) {
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [loading, setLoading] = useState(true)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskKind, setTaskKind] = useState<'expand' | 'analyze' | 'sheet' | 'verdict' | null>(null)
  const [volumeConfigured, setVolumeConfigured] = useState<boolean | null>(null)
  const [serpTarget, setSerpTarget] = useState<Keyword | null>(null)

  // 키워드 만들기 폼
  const [seedText, setSeedText] = useState('')
  const [regions, setRegions] = useState<string[]>(client.regions || [])
  const [diseases, setDiseases] = useState<string[]>(client.diseases || [])
  const [level, setLevel] = useState(String(client.region_expand_level ?? 1))
  const [minRegion, setMinRegion] = useState(String(client.min_volume_region ?? 0))
  const [minNational, setMinNational] = useState(String(client.min_volume_national ?? 0))
  const [includeRelated, setIncludeRelated] = useState(true)
  const [analyzeAfter, setAnalyzeAfter] = useState(true)
  const [manualText, setManualText] = useState('')
  const [adding, setAdding] = useState(false)
  const [starting, setStarting] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)

  // 필터
  const [passOnly, setPassOnly] = useState(false)
  const [verdictFilter, setVerdictFilter] = useState('all')
  const [myFilter, setMyFilter] = useState<'all' | 'good' | 'ranked'>('all')
  const [q, setQ] = useState('')

  // 내 블로그 기준 판정: 캠페인에 배정된 블로그를 앞에 둔다
  const blogOptions = useMemo(() => {
    const assigned = new Set(campaign.blog_ids || [])
    return [...(client.blogs || [])].sort((a, b) => Number(assigned.has(b.id)) - Number(assigned.has(a.id)))
  }, [client.blogs, campaign.blog_ids])
  const [myBlogId, setMyBlogId] = useState<string>('')
  const [indexOpen, setIndexOpen] = useState(false)
  useEffect(() => {
    if (myBlogId || !blogOptions.length) return
    // 이미 판정한 키워드가 있으면 그 블로그를, 없으면 배정된 첫 블로그를 고른다
    const used = keywords.find((k) => k.my_blog_id)?.my_blog_id
    setMyBlogId(used && blogOptions.some((b) => b.blog_id === used) ? used : blogOptions[0].blog_id)
  }, [blogOptions, keywords, myBlogId])
  const [expandedReason, setExpandedReason] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setKeywords(await campaignAPI.listKeywords(campaign.id))
    } catch (err: any) {
      toast.error('키워드 불러오기 실패', { description: errMsg(err) })
    } finally {
      setLoading(false)
    }
  }, [campaign.id])

  // 선택된 키워드의 경쟁 블로그를 뒤에서 미리 채점해 둔다(블로그 무관, 판정 시 캐시 히트)
  const prewarmedRef = useRef<string>('')
  useEffect(() => {
    const texts = keywords.filter((k) => k.selected).map((k) => k.keyword).slice(0, 40)
    const key = texts.join('|')
    if (!texts.length || key === prewarmedRef.current) return
    prewarmedRef.current = key
    blogIndexAPI.prewarm(texts).catch(() => { /* 실패해도 판정은 그대로 동작 */ })
  }, [keywords])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    keywordBatchAPI.getVolumeStatus().then((r) => setVolumeConfigured(!!r.configured)).catch(() => setVolumeConfigured(null))
  }, [])

  // 진행 중이던 작업 이어보기
  useEffect(() => {
    campaignAPI.listTasks({ campaign_id: campaign.id, active_only: true, limit: 5 })
      .then((ts) => {
        const t = ts.find((x) => ['keyword_expand', 'keyword_analyze', 'sheet_check', 'verdict'].some((k) => x.type.includes(k)) || x.type.includes('keyword'))
        if (t) { setTaskId(t.id); setTaskKind(t.type.includes('verdict') ? 'verdict' : t.type.includes('sheet') ? 'sheet' : t.type.includes('analy') ? 'analyze' : 'expand') }
      })
      .catch(() => { /* noop */ })
  }, [campaign.id])

  const onTaskDone = (t: Task) => {
    const o = taskOutcome(t)
    if (o.ok) toast.success(o.text); else toast.error(o.text)
    setTaskId(null); setTaskKind(null)
    load()
  }

  const startExpand = async () => {
    const seeds = seedText.split(/\n/).map((s) => s.trim()).filter(Boolean)
    if (seeds.length === 0 && diseases.length === 0) { toast.error('질환 또는 키워드를 하나 이상 넣어주세요'); return }
    setStarting(true)
    try {
      const t = await campaignAPI.expandKeywords(campaign.id, {
        seeds, regions, diseases, level: Number(level) || 0,
        min_volume_region: Number(minRegion) || 0, min_volume_national: Number(minNational) || 0,
        include_related: includeRelated, analyze_after: analyzeAfter,
      })
      setTaskKind('expand'); setTaskId(t.id)
    } catch (err: any) {
      toast.error('키워드 찾기 실패', { description: errMsg(err) })
    } finally {
      setStarting(false)
    }
  }

  const addManual = async () => {
    const list = manualText.split(/[\n,]/).map((s) => s.trim()).filter(Boolean)
    if (!list.length) return
    setAdding(true)
    try {
      await campaignAPI.addKeywords(campaign.id, list, true)
      toast.success(`${list.length}개를 추가했어요`)
      setManualText('')
      load()
    } catch (err: any) {
      toast.error('추가 실패', { description: errMsg(err) })
    } finally {
      setAdding(false)
    }
  }

  const selectedIds = useMemo(() => keywords.filter((k) => k.selected).map((k) => k.id), [keywords])

  const toggleSelect = async (ids: string[], on: boolean) => {
    if (!ids.length) return
    setKeywords((prev) => prev.map((k) => (ids.includes(k.id) ? { ...k, selected: on } : k)))
    try {
      await campaignAPI.selectKeywords(campaign.id, ids, on)
    } catch (err: any) {
      toast.error('선택 저장 실패', { description: errMsg(err) })
      load()
    }
  }

  const remove = async (k: Keyword) => {
    try {
      await campaignAPI.deleteKeyword(campaign.id, k.id)
      setKeywords((prev) => prev.filter((x) => x.id !== k.id))
    } catch (err: any) {
      toast.error('삭제 실패', { description: errMsg(err) })
    }
  }

  const analyzeSelected = async () => {
    if (!selectedIds.length) { toast.error('먼저 분석할 키워드를 선택하세요'); return }
    try {
      const t = await campaignAPI.analyzeKeywords(campaign.id, selectedIds)
      setTaskKind('analyze'); setTaskId(t.id)
    } catch (err: any) {
      toast.error('통검 분석 시작 실패', { description: errMsg(err) })
    }
  }

  const sheetCheck = async () => {
    try {
      const t = await campaignAPI.sheetCheck(campaign.id)
      setTaskKind('sheet'); setTaskId(t.id)
    } catch (err: any) {
      toast.error('시트 중복 확인 실패', { description: errMsg(err) })
    }
  }

  const runMyVerdict = async () => {
    if (!myBlogId) { toast.error('먼저 판정할 내 블로그를 고르세요'); return }
    const texts = keywords.filter((k) => k.selected).map((k) => k.keyword)
    if (!texts.length) { toast.error('먼저 판정할 키워드를 선택하세요'); return }
    try {
      const t = await blogIndexAPI.verdictBatch(myBlogId, texts, campaign.id)
      setTaskKind('verdict'); setTaskId(t.id)
    } catch (err: any) {
      toast.error('내 블로그 판정 시작 실패', { description: errMsg(err) })
    }
  }

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return keywords
      .filter((k) => (!passOnly || k.passes_filter))
      .filter((k) => verdictFilter === 'all' || (k.verdict || 'unknown') === verdictFilter)
      .filter((k) => myFilter === 'all' || (myFilter === 'good' ? (k.my_verdict === 'likely' || k.my_verdict === 'contested') : k.my_verdict === 'already_ranked'))
      .filter((k) => !needle || k.keyword.toLowerCase().includes(needle))
      .sort((a, b) => (b.monthly_mobile || 0) - (a.monthly_mobile || 0) || a.keyword.localeCompare(b.keyword))
  }, [keywords, passOnly, verdictFilter, myFilter, q])

  const myVerdictCount = useMemo(() => keywords.filter((k) => k.my_verdict).length, [keywords])
  const myBlog = blogOptions.find((b) => b.blog_id === myBlogId)

  const allVisibleSelected = filtered.length > 0 && filtered.every((k) => k.selected)
  const running = !!taskId

  return (
    <div className="space-y-6">
      {volumeConfigured === false && (
        <div className="flex items-start gap-2 rounded-lg bg-warning-soft p-3 text-sm text-warning">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>네이버 검색광고 API 키가 없어 검색량이 0으로 나옵니다 (백엔드 .env NAVER_AD_*)</span>
        </div>
      )}

      {/* 키워드 만들기 */}
      <Card className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="section-title">키워드 만들기</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">지역 × 질환 조합과 연관 검색어를 모아 검색량을 확인합니다.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setPanelOpen((v) => !v)}>
            {panelOpen ? <ChevronUp /> : <ChevronDown />}
            {panelOpen ? '접기' : '펼치기'}
          </Button>
        </div>
        {panelOpen && (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>원장님 제안·직접 입력 키워드 (줄바꿈)</Label>
                <Textarea value={seedText} onChange={(e) => setSeedText(e.target.value)} rows={5} placeholder={'무릎 연골주사\n허리디스크 비수술\n...'} />
              </div>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>지역</Label>
                  <ChipsInput value={regions} onChange={setRegions} placeholder="예: 강남, 서초" />
                </div>
                <div className="space-y-1.5">
                  <Label>질환</Label>
                  <ChipsInput value={diseases} onChange={setDiseases} placeholder="예: 무릎통증, 허리디스크" />
                </div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="space-y-1.5">
                <Label>지역 확장 범위</Label>
                <Select value={level} onValueChange={setLevel}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">입력한 지역만</SelectItem>
                    <SelectItem value="1">인접 동네까지</SelectItem>
                    <SelectItem value="2">구·시 전체</SelectItem>
                    <SelectItem value="3">광역권</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>지역 키워드 최소 검색량</Label>
                <Input type="number" min={0} value={minRegion} onChange={(e) => setMinRegion(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>전국 키워드 최소 검색량</Label>
                <Input type="number" min={0} value={minNational} onChange={(e) => setMinNational(e.target.value)} />
              </div>
              <div className="space-y-2 pt-6">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox checked={includeRelated} onCheckedChange={(v) => setIncludeRelated(v === true)} /> 연관 검색어 포함
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox checked={analyzeAfter} onCheckedChange={(v) => setAnalyzeAfter(v === true)} /> 확장 후 통검 분석까지 이어서
                </label>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={startExpand} disabled={running || starting}>
                {starting ? <Loader2 className="animate-spin" /> : <Search />} 키워드 찾기
              </Button>
              <div className="ml-auto flex items-center gap-1.5">
                <Input
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') addManual() }}
                  placeholder="직접 추가 (쉼표로 여러 개)"
                  className="w-64"
                />
                <Button variant="outline" onClick={addManual} disabled={adding || !manualText.trim()}>
                  {adding ? <Loader2 className="animate-spin" /> : <Plus />} 직접 추가
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* 내 블로그 기준 상위노출 판정 */}
      <Card className="space-y-3 p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="section-title">내 블로그 기준 상위노출 판정</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">
              선택한 키워드마다 이 블로그로 1페이지에 들어갈 확률을 잽니다. 결과는 표의 &lsquo;내 블로그&rsquo; 칸에 남습니다.
              {myVerdictCount > 0 && <span className="tabular-nums"> (판정된 키워드 {fmt(myVerdictCount)}개)</span>}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setIndexOpen(true)} disabled={!myBlogId}>
            <BarChart3 /> 블로그 지수 보기
          </Button>
        </div>
        {blogOptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">이 병원에 등록된 블로그가 없습니다. 1단계에서 블로그 계정을 먼저 추가해 주세요.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Select value={myBlogId} onValueChange={setMyBlogId} disabled={running}>
              <SelectTrigger className="w-72"><SelectValue placeholder="판정할 블로그" /></SelectTrigger>
              <SelectContent>
                {blogOptions.map((b) => (
                  <SelectItem key={b.id} value={b.blog_id}>
                    {b.label ? `${b.label} (${b.blog_id})` : b.blog_id}
                    {campaign.blog_ids?.includes(b.id) ? ' · 배정됨' : ''}
                    {b.index_score != null ? ` · 지수 ${b.index_score.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={runMyVerdict} disabled={running || !myBlogId || selectedIds.length === 0}>
              <Target /> 선택 키워드 판정 ({fmt(selectedIds.length)})
            </Button>
            {myBlog?.index_grade && (
              <span className="text-xs text-muted-foreground">
                현재 지수 <span className="font-medium tabular-nums text-foreground">{myBlog.index_score?.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}</span> · {myBlog.index_grade}
              </span>
            )}
          </div>
        )}
      </Card>

      <TaskProgress taskId={taskId} onDone={onTaskDone} onTick={(t) => { if (taskKind !== 'sheet' && t.progress > 0 && t.progress % 10 === 0) load() }} />

      {/* 키워드 표 */}
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-center gap-2">
            <h3 className="section-title">키워드 <span className="tabular-nums">{fmt(keywords.length)}</span>개</h3>
            <span className="text-xs tabular-nums text-muted-foreground">선택 {fmt(selectedIds.length)}</span>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <div className="inline-flex overflow-hidden rounded-md border text-xs">
                <button type="button" className={`px-2.5 py-1.5 ${!passOnly ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`} onClick={() => setPassOnly(false)}>전체</button>
                <button type="button" className={`px-2.5 py-1.5 ${passOnly ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`} onClick={() => setPassOnly(true)}>검색량 통과만</button>
              </div>
              <Select value={verdictFilter} onValueChange={setVerdictFilter}>
                <SelectTrigger className="h-8 w-32 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">판정 전체</SelectItem>
                  {Object.entries(VERDICT_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={myFilter} onValueChange={(v) => setMyFilter(v as typeof myFilter)}>
                <SelectTrigger className="h-8 w-44 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">내 블로그 판정: 전체</SelectItem>
                  <SelectItem value="good">가능성 높음 + 경합</SelectItem>
                  <SelectItem value="ranked">이미 노출</SelectItem>
                </SelectContent>
              </Select>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="검색" className="h-8 w-40 text-xs" />
            </div>
        </div>
        <div className="space-y-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...</div>
          ) : filtered.length === 0 ? (
            <EmptyNote>{keywords.length === 0 ? '아직 키워드가 없습니다. 위에서 키워드 찾기를 눌러 주세요.' : '조건에 맞는 키워드가 없습니다.'}</EmptyNote>
          ) : (
            <div className="overflow-x-auto">
              <Table className={TABLE_CLS}>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox checked={allVisibleSelected} onCheckedChange={(v) => toggleSelect(filtered.map((k) => k.id), v === true)} />
                    </TableHead>
                    <TableHead>키워드</TableHead>
                    <TableHead className="text-right">모바일</TableHead>
                    <TableHead className="text-right">PC</TableHead>
                    <TableHead>경쟁</TableHead>
                    <TableHead>범위</TableHead>
                    <TableHead>출처</TableHead>
                    <TableHead>판정</TableHead>
                    <TableHead>내 블로그</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((k) => {
                    const v = VERDICT_LABEL[k.verdict] || VERDICT_LABEL.unknown
                    const comp = COMP_LABEL[k.competition]
                    const s = k.serp_summary
                    const open = expandedReason === k.id
                    const myRes = k.my_verdict_result
                    const myReasons = myRes?.reasons || []
                    const myPct = k.my_probability == null ? null : Math.round(k.my_probability * 100)
                    const tooltip = [k.verdict_reason, myReasons.length ? `[내 블로그] ${myReasons.join(' / ')}` : null].filter(Boolean).join('\n') || undefined
                    const hasReason = !!k.verdict_reason || myReasons.length > 0
                    return (
                      <TableRow key={k.id} className={`cursor-pointer ${!k.passes_filter ? 'opacity-60' : ''}`} onClick={() => setSerpTarget(k)}>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox checked={k.selected} onCheckedChange={(val) => toggleSelect([k.id], val === true)} />
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="font-medium">{k.keyword}</span>
                            {k.in_sheet && <Pill tone="warn" title={k.sheet_note || undefined}>시트 중복{k.sheet_note ? ` · ${k.sheet_note}` : ''}</Pill>}
                            {k.has_draft && <Pill tone="info">원고 있음</Pill>}
                            {!k.passes_filter && <Pill tone="muted">검색량 미달</Pill>}
                          </div>
                          {s && (s.exposed_count != null || s.recommended_chars != null) && (
                            <div className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
                              노출 {fmt(s.exposed_count)} · 병원 {fmt(s.hospital_count)} · 권장 사진 {fmt(s.recommended_image_count)} · 권장 글자 {fmt(s.recommended_chars)}
                            </div>
                          )}
                          {open && k.verdict_reason && <div className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">{k.verdict_reason}</div>}
                          {open && myReasons.length > 0 && (
                            <div className="mt-1 text-xs text-muted-foreground">
                              <span className="font-medium">내 블로그 판정 근거</span>
                              {myRes?.my_score != null && <span className="tabular-nums"> · 내 점수 {myRes.my_score.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}{myRes.cut_line != null ? ` / 컷 ${myRes.cut_line.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}` : ''}</span>}
                              <ul className="mt-0.5 list-disc pl-4">{myReasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.monthly_mobile)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(k.monthly_pc)}</TableCell>
                        <TableCell>{comp ? <Pill tone={comp.tone}>{comp.label}</Pill> : <span className="text-xs text-muted-foreground">-</span>}</TableCell>
                        <TableCell className="text-xs">{k.scope === 'national' ? '전국' : '지역'}</TableCell>
                        <TableCell className="text-xs">{SOURCE_LABEL[k.source] || k.source}</TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            title={tooltip}
                            onClick={() => setExpandedReason(open ? null : k.id)}
                            className="inline-flex items-center gap-1"
                          >
                            <Pill tone={v.tone}>{v.label}</Pill>
                            {hasReason && (open ? <ChevronUp className="h-3 w-3 text-muted-foreground" /> : <ChevronDown className="h-3 w-3 text-muted-foreground" />)}
                          </button>
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {k.my_verdict ? (
                            <button type="button" title={tooltip} onClick={() => setExpandedReason(open ? null : k.id)} className="inline-flex items-center gap-1.5">
                              <KitPill tone={MY_VERDICT_TONE[k.my_verdict] || 'muted'}>{MY_VERDICT_LABEL[k.my_verdict] || k.my_verdict}</KitPill>
                              <span className="text-xs tabular-nums text-muted-foreground">{myPct == null ? '측정 불가' : `${myPct}%`}</span>
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-danger" onClick={() => remove(k)} title="삭제">
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={analyzeSelected} disabled={running || selectedIds.length === 0}>
              선택 키워드 통검 분석 ({fmt(selectedIds.length)})
            </Button>
            <Button
              variant="outline"
              onClick={sheetCheck}
              disabled={running || !client.sheet_url}
              title={!client.sheet_url ? '병원 설정에 구글 시트 주소를 넣으면 쓸 수 있어요' : undefined}
            >
              시트 중복 확인
            </Button>
            {!client.sheet_url && <span className="text-xs text-muted-foreground">시트 중복 확인은 병원 설정에 시트 주소가 있어야 해요</span>}
          </div>
        </div>
      </Card>

      <StepFooter onBack={() => goStep(1)} onNext={() => goStep(3)} nextLabel={`다음: 원고 (선택 ${fmt(selectedIds.length)}건)`} />

      <KeywordSerpDialog campaignId={campaign.id} keyword={serpTarget} onClose={() => setSerpTarget(null)} />

      <Dialog open={indexOpen} onOpenChange={setIndexOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>블로그 지수 · {myBlog?.label || myBlogId}</DialogTitle>
            <DialogDescription>공개 신호로 추정한 비공식 지수입니다. 처음 분석은 20~60초 걸립니다.</DialogDescription>
          </DialogHeader>
          {indexOpen && myBlogId && <BlogIndexPanel blogId={myBlogId} bare className="border-0 p-0 shadow-none" />}
        </DialogContent>
      </Dialog>
    </div>
  )
}
