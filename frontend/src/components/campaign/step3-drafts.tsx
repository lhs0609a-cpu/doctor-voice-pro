'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { ChevronDown, ChevronUp, FileText, Loader2, Sparkles, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { campaignAPI, type Brief, type Draft, type Keyword, type Task } from '@/lib/campaign-api'
import { EmptyNote, Pill, StepFooter, TABLE_CLS, TaskProgress, errMsg, fmt, taskOutcome, type StepProps } from './common'
import { DraftDialog, summarizeChecks } from './draft-dialog'

const NONE = '__none__'
const SOURCE_LABEL: Record<string, string> = { generated: '자동 작성', variant: '변형', upload: '파일', manual: '붙여넣기' }

export function Step3Drafts({ campaign, client, goStep }: StepProps) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [briefs, setBriefs] = useState<Brief[]>(client.briefs || [])
  const [loading, setLoading] = useState(true)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [openDraft, setOpenDraft] = useState<Draft | null>(null)

  // 자동 작성
  const [briefId, setBriefId] = useState(campaign.brief_id || NONE)
  const [advOpen, setAdvOpen] = useState(false)
  const [targetChars, setTargetChars] = useState('')
  const [headingCount, setHeadingCount] = useState('')
  const [keywordCount, setKeywordCount] = useState('')
  const [imageCount, setImageCount] = useState('')
  const [instructions, setInstructions] = useState('')
  const [starting, setStarting] = useState(false)

  // 변형
  const [sourceText, setSourceText] = useState('')
  const [variantCount, setVariantCount] = useState('3')
  const [variantKeyword, setVariantKeyword] = useState('')

  // 업로드/붙여넣기
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const [pasteTitle, setPasteTitle] = useState('')
  const [pasteBody, setPasteBody] = useState('')
  const [pasteKeyword, setPasteKeyword] = useState('')
  const [pasting, setPasting] = useState(false)

  const loadDrafts = useCallback(async () => {
    try { setDrafts(await campaignAPI.listDrafts(campaign.id)) }
    catch (err: any) { toast.error('원고 불러오기 실패', { description: errMsg(err) }) }
    finally { setLoading(false) }
  }, [campaign.id])

  useEffect(() => {
    loadDrafts()
    campaignAPI.listKeywords(campaign.id).then(setKeywords).catch(() => { /* noop */ })
    campaignAPI.listBriefs(client.id).then((list) => {
      const m = new Map<string, Brief>()
      ;[...(client.briefs || []), ...list].forEach((b) => m.set(b.id, b))
      setBriefs(Array.from(m.values()))
    }).catch(() => { /* noop */ })
    campaignAPI.listTasks({ campaign_id: campaign.id, active_only: true, limit: 5 })
      .then((ts) => { const t = ts.find((x) => x.type.includes('draft') || x.type.includes('variant') || x.type.includes('generate')); if (t) setTaskId(t.id) })
      .catch(() => { /* noop */ })
  }, [campaign.id, client.id, client.briefs, loadDrafts])

  // 작업 중엔 3초마다 목록 갱신
  useEffect(() => {
    if (!taskId) return
    const iv = setInterval(loadDrafts, 3000)
    return () => clearInterval(iv)
  }, [taskId, loadDrafts])

  const onTaskDone = (t: Task) => {
    const o = taskOutcome(t)
    if (o.ok) toast.success(o.text); else toast.error(o.text)
    setTaskId(null)
    loadDrafts()
  }

  const selectedNoDraft = useMemo(() => keywords.filter((k) => k.selected && !k.has_draft), [keywords])
  const selectedAll = useMemo(() => keywords.filter((k) => k.selected), [keywords])

  const startGenerate = async () => {
    if (selectedAll.length === 0) { toast.error('2단계에서 키워드를 먼저 선택하세요'); return }
    setStarting(true)
    try {
      const num = (s: string) => (s.trim() ? Number(s) : undefined)
      const t = await campaignAPI.generateDrafts(campaign.id, {
        brief_id: briefId === NONE ? null : briefId,
        target_chars: num(targetChars), heading_count: num(headingCount), keyword_count: num(keywordCount), image_count: num(imageCount),
        instructions: instructions.trim() || undefined,
      })
      setTaskId(t.id)
    } catch (err: any) {
      toast.error('원고 작성 시작 실패', { description: errMsg(err) })
    } finally { setStarting(false) }
  }

  const startVariants = async () => {
    if (sourceText.trim().length < 100) { toast.error('원본 원고를 100자 이상 붙여넣어 주세요'); return }
    const count = Math.min(10, Math.max(1, Number(variantCount) || 3))
    setStarting(true)
    try {
      const t = await campaignAPI.makeVariants(campaign.id, { source_text: sourceText, count, keyword: variantKeyword.trim() || undefined })
      setTaskId(t.id)
    } catch (err: any) {
      toast.error('변형 시작 실패', { description: errMsg(err) })
    } finally { setStarting(false) }
  }

  const uploadFiles = async (files: File[]) => {
    const ok = files.filter((f) => /\.(txt|md|docx)$/i.test(f.name))
    if (!ok.length) { toast.error('.txt .md .docx 파일만 올릴 수 있어요'); return }
    setUploading(true)
    try {
      const res = await campaignAPI.uploadDrafts(campaign.id, ok)
      toast.success(`${res.length}개 원고를 올렸어요`)
      loadDrafts()
    } catch (err: any) {
      toast.error('업로드 실패', { description: errMsg(err) })
    } finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const addPaste = async () => {
    if (!pasteTitle.trim() || !pasteBody.trim()) { toast.error('제목과 본문을 넣어주세요'); return }
    setPasting(true)
    try {
      await campaignAPI.addDraftText(campaign.id, { title: pasteTitle.trim(), body: pasteBody, keyword: pasteKeyword.trim() || undefined })
      toast.success('원고를 추가했어요')
      setPasteTitle(''); setPasteBody(''); setPasteKeyword('')
      loadDrafts()
    } catch (err: any) {
      toast.error('추가 실패', { description: errMsg(err) })
    } finally { setPasting(false) }
  }

  const removeDraft = async (d: Draft) => {
    try { await campaignAPI.deleteDraft(d.id); setDrafts((prev) => prev.filter((x) => x.id !== d.id)) }
    catch (err: any) { toast.error('삭제 실패', { description: errMsg(err) }) }
  }

  const parentIds = useMemo(() => new Set(drafts.map((d) => d.parent_draft_id).filter(Boolean) as string[]), [drafts])
  const isSourceOnly = (d: Draft) => parentIds.has(d.id) && d.source === 'upload'
  const readyCount = drafts.filter((d) => d.status === 'ready' && !isSourceOnly(d)).length
  const running = !!taskId

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-5">
        <div>
          <h3 className="section-title">원고 만들기</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">키워드로 자동 작성하거나, 원본 원고를 변형하거나, 가지고 있는 파일을 올리세요.</p>
        </div>
        <div>
          <Tabs defaultValue="generate">
            <TabsList>
              <TabsTrigger value="generate">키워드로 자동 작성</TabsTrigger>
              <TabsTrigger value="variants">원본 원고 변형</TabsTrigger>
              <TabsTrigger value="upload">파일 올리기</TabsTrigger>
            </TabsList>

            <TabsContent value="generate" className="space-y-4 pt-3">
              <div className="rounded-lg bg-muted/60 p-3 text-sm tabular-nums">
                선택한 키워드 <b>{fmt(selectedAll.length)}</b>개 중 원고가 없는 키워드 <b>{fmt(selectedNoDraft.length)}</b>개를 작성합니다.
                {selectedAll.length === 0 && <span className="text-warning"> 2단계에서 키워드를 먼저 선택하세요.</span>}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>브리프</Label>
                  <Select value={briefId} onValueChange={setBriefId}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NONE}>기본 브리프 (자동)</SelectItem>
                      {briefs.map((b) => <SelectItem key={b.id} value={b.id}>{b.name} · {fmt(b.target_chars)}자</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <button type="button" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" onClick={() => setAdvOpen((v) => !v)}>
                {advOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />} 고급 (비우면 브리프·통검 분석값 사용)
              </button>
              {advOpen && (
                <div className="grid gap-3 sm:grid-cols-4">
                  <div className="space-y-1.5"><Label>목표 글자수</Label><Input type="number" value={targetChars} onChange={(e) => setTargetChars(e.target.value)} placeholder="예: 2800" /></div>
                  <div className="space-y-1.5"><Label>소제목 수</Label><Input type="number" value={headingCount} onChange={(e) => setHeadingCount(e.target.value)} placeholder="예: 5" /></div>
                  <div className="space-y-1.5"><Label>키워드 등장 수</Label><Input type="number" value={keywordCount} onChange={(e) => setKeywordCount(e.target.value)} placeholder="예: 8" /></div>
                  <div className="space-y-1.5"><Label>사진 수</Label><Input type="number" value={imageCount} onChange={(e) => setImageCount(e.target.value)} placeholder="예: 9" /></div>
                </div>
              )}
              <div className="space-y-1.5">
                <Label>추가 지시 (선택)</Label>
                <Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} placeholder="예: 40대 여성 환자 사례를 하나 넣어주세요. 가격 언급은 하지 마세요." />
              </div>
              <Button onClick={startGenerate} disabled={running || starting || selectedAll.length === 0}>
                {starting ? <Loader2 className="animate-spin" /> : <Sparkles />} 원고 작성 시작
              </Button>
            </TabsContent>

            <TabsContent value="variants" className="space-y-4 pt-3">
              <div className="space-y-1.5">
                <Label>원본 원고</Label>
                <Textarea value={sourceText} onChange={(e) => setSourceText(e.target.value)} rows={10} placeholder="원본 글을 그대로 붙여넣으세요. 구조는 살리고 표현은 새로 쓴 변형 원고를 만듭니다." />
                <div className="text-xs tabular-nums text-muted-foreground">{fmt(sourceText.length)}자</div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1.5"><Label>변형 개수 (1–10)</Label><Input type="number" min={1} max={10} value={variantCount} onChange={(e) => setVariantCount(e.target.value)} /></div>
                <div className="space-y-1.5 sm:col-span-2"><Label>키워드 (선택)</Label><Input value={variantKeyword} onChange={(e) => setVariantKeyword(e.target.value)} placeholder="변형 원고에 넣을 키워드" /></div>
              </div>
              <Button onClick={startVariants} disabled={running || starting}>
                {starting ? <Loader2 className="animate-spin" /> : <Sparkles />} 변형 원고 만들기
              </Button>
            </TabsContent>

            <TabsContent value="upload" className="space-y-4 pt-3">
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); uploadFiles(Array.from(e.dataTransfer.files)) }}
                onClick={() => fileRef.current?.click()}
                className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-sm transition-colors ${dragOver ? 'border-primary bg-accent' : 'border-input hover:bg-muted/40'}`}
              >
                {uploading ? <Loader2 className="h-6 w-6 animate-spin text-primary" /> : <Upload className="h-6 w-6 text-muted-foreground" />}
                <div>파일을 끌어다 놓거나 클릭해서 선택 (.txt .md .docx, 여러 개 가능)</div>
                <input ref={fileRef} type="file" multiple accept=".txt,.md,.docx" className="hidden" onChange={(e) => uploadFiles(Array.from(e.target.files || []))} />
              </div>
              <div className="space-y-3 border-t pt-4">
                <div className="text-sm font-medium">직접 붙여넣기</div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5"><Label>제목</Label><Input value={pasteTitle} onChange={(e) => setPasteTitle(e.target.value)} /></div>
                  <div className="space-y-1.5"><Label>키워드 (선택)</Label><Input value={pasteKeyword} onChange={(e) => setPasteKeyword(e.target.value)} /></div>
                </div>
                <div className="space-y-1.5"><Label>본문</Label><Textarea value={pasteBody} onChange={(e) => setPasteBody(e.target.value)} rows={8} /></div>
                <Button variant="outline" onClick={addPaste} disabled={pasting}>
                  {pasting ? <Loader2 className="animate-spin" /> : <FileText />} 원고로 추가
                </Button>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </Card>

      <TaskProgress taskId={taskId} onDone={onTaskDone} />

      {/* 원고 목록 */}
      <Card className="space-y-4 p-5">
        <div className="flex items-center gap-2">
          <h3 className="section-title">원고 <span className="tabular-nums">{fmt(drafts.length)}</span>개</h3>
          <span className="text-xs tabular-nums text-muted-foreground">검수 통과 {fmt(readyCount)}</span>
        </div>
        <div>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중...</div>
          ) : drafts.length === 0 ? (
            <EmptyNote>아직 원고가 없습니다. 위에서 원고를 만들어 주세요.</EmptyNote>
          ) : (
            <div className="overflow-x-auto">
              <Table className={TABLE_CLS}>
                <TableHeader>
                  <TableRow>
                    <TableHead>제목</TableHead>
                    <TableHead>키워드</TableHead>
                    <TableHead>출처</TableHead>
                    <TableHead className="text-right">글자</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>검수</TableHead>
                    <TableHead className="w-28" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {drafts.map((d) => {
                    const chips = summarizeChecks(d.checks)
                    const src = isSourceOnly(d)
                    return (
                      <TableRow key={d.id} className={src ? 'opacity-70' : ''}>
                        <TableCell className="max-w-[320px]">
                          <div className="truncate font-medium">{d.title || '(제목 없음)'}</div>
                          {src && <Pill tone="muted" className="mt-1">원본(발행 안 함)</Pill>}
                          {d.error && <div className="truncate text-[11px] text-danger">{d.error}</div>}
                        </TableCell>
                        <TableCell className="text-xs">{d.keyword || '-'}</TableCell>
                        <TableCell className="text-xs">{SOURCE_LABEL[d.source] || d.source}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(d.char_count)}</TableCell>
                        <TableCell><DraftStatusPill status={d.status} /></TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {chips.length === 0 && d.status !== 'generating' && <span className="text-[11px] text-muted-foreground">이상 없음</span>}
                            {chips.map((c) => <Pill key={c.label} tone={c.tone}>{c.label}</Pill>)}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1 justify-end">
                            <Button variant="outline" size="sm" onClick={() => setOpenDraft(d)} disabled={d.status === 'generating'}>열기</Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-danger" onClick={() => removeDraft(d)} title="삭제">
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </Card>

      <StepFooter onBack={() => goStep(2)} onNext={() => goStep(4)} nextLabel={`다음: 사진 (준비된 원고 ${fmt(readyCount)}건)`} />

      <DraftDialog
        draft={openDraft}
        onClose={() => setOpenDraft(null)}
        onSaved={(d) => setDrafts((prev) => prev.map((x) => (x.id === d.id ? { ...x, ...d, body: undefined } : x)))}
      />
    </div>
  )
}

export function DraftStatusPill({ status }: { status: string }) {
  if (status === 'generating') return <Pill tone="info"><Loader2 className="h-3 w-3 animate-spin" /> 작성 중</Pill>
  if (status === 'ready') return <Pill tone="ok">검수 통과</Pill>
  if (status === 'needs_review') return <Pill tone="warn">확인 필요</Pill>
  if (status === 'failed') return <Pill tone="crit">실패</Pill>
  return <Pill tone="muted">{status}</Pill>
}
