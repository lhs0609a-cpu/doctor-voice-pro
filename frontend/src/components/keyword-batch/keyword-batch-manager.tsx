'use client';

/**
 * 키워드 대량 생성 UI
 *
 * 흐름: 엑셀 업로드 → 프롬프트 선택 → 실행 → Gemini 가 한 건씩 생성 → 결과 수집
 * 실제 자동화는 확장 프로그램이 하고, 이 화면은 지시와 진행 상황만 담당한다.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  Upload, FileSpreadsheet, Play, Square, Trash2, Save, Copy, Download,
  AlertCircle, CheckCircle2, Loader2, Settings2, Plus,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

import {
  parseKeywordFile, sortByVolume, loadTemplates, saveTemplates, renderPrompt,
  startGeneration, cancelGeneration, onGenResult, splitTitleBody, appendSavedPosts,
  DEFAULT_TEMPLATE, DEFAULT_GEN_OPTIONS,
  type KeywordRow, type GenItem, type PromptTemplate, type GenOptions,
} from '@/lib/keyword-batch';

const uid = () => `tpl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

export function KeywordBatchManager() {
  // ---------- 키워드 ----------
  const [rows, setRows] = useState<GenItem[]>([]);
  const [minVolume, setMinVolume] = useState(0);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ---------- 프롬프트 ----------
  const [templates, setTemplates] = useState<PromptTemplate[]>([DEFAULT_TEMPLATE]);
  const [activeId, setActiveId] = useState(DEFAULT_TEMPLATE.id);
  const [draft, setDraft] = useState(DEFAULT_TEMPLATE.body);
  const [draftName, setDraftName] = useState(DEFAULT_TEMPLATE.name);

  // ---------- 실행 ----------
  const [options, setOptions] = useState<GenOptions>(DEFAULT_GEN_OPTIONS);
  const [showOptions, setShowOptions] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const list = loadTemplates();
    setTemplates(list);
    setActiveId(list[0].id);
    setDraft(list[0].body);
    setDraftName(list[0].name);
  }, []);

  // ---------- 파일 ----------
  const ingest = useCallback(async (file: File) => {
    try {
      const parsed: KeywordRow[] = await parseKeywordFile(file);
      setRows(sortByVolume(parsed).map((r) => ({ ...r, status: 'pending' as const })));
      setMinVolume(0);
      toast.success(`키워드 ${parsed.length}개를 불러왔습니다`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '파일을 읽지 못했습니다');
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f) void ingest(f);
    },
    [ingest],
  );

  // ---------- 선택 대상 ----------
  const maxVolume = useMemo(
    () => rows.reduce((m, r) => Math.max(m, r.volume ?? 0), 0),
    [rows],
  );
  const targets = useMemo(
    () => rows.filter((r) => (r.volume ?? 0) >= minVolume),
    [rows, minVolume],
  );
  const doneCount = rows.filter((r) => r.status === 'done').length;
  const failCount = rows.filter((r) => r.status === 'failed').length;
  const progressPct = targets.length
    ? Math.round(((doneCount + failCount) / targets.length) * 100)
    : 0;

  // ---------- 템플릿 ----------
  const persist = (list: PromptTemplate[]) => {
    setTemplates(list);
    saveTemplates(list);
  };

  const selectTemplate = (id: string) => {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    setActiveId(id);
    setDraft(t.body);
    setDraftName(t.name);
  };

  const saveDraft = () => {
    if (!draftName.trim()) {
      toast.error('템플릿 이름을 입력하세요');
      return;
    }
    const next = templates.map((t) =>
      t.id === activeId ? { ...t, name: draftName.trim(), body: draft, updatedAt: Date.now() } : t,
    );
    persist(next);
    toast.success('템플릿을 저장했습니다');
  };

  const addTemplate = () => {
    const t: PromptTemplate = {
      id: uid(),
      name: `새 템플릿 ${templates.length + 1}`,
      body: DEFAULT_TEMPLATE.body,
      updatedAt: Date.now(),
    };
    persist([...templates, t]);
    selectTemplate(t.id);
  };

  const removeTemplate = () => {
    if (templates.length <= 1) {
      toast.error('템플릿은 최소 1개가 필요합니다');
      return;
    }
    const next = templates.filter((t) => t.id !== activeId);
    persist(next);
    selectTemplate(next[0].id);
  };

  const hasKeywordVar = /\{\{\s*(키워드|keyword)\s*\}\}/i.test(draft);
  const preview = useMemo(
    () => renderPrompt(draft, { 키워드: targets[0]?.keyword ?? '예시키워드', keyword: targets[0]?.keyword ?? '예시키워드' }),
    [draft, targets],
  );

  // ---------- 실행 ----------
  const [savedCount, setSavedCount] = useState(0);

  useEffect(() => {
    const off = onGenResult((r) => {
      if (r.done) {
        setRunning(false);
        toast.success('생성이 끝났습니다');
        return;
      }
      if (r.fatal) toast.error(r.error || '생성을 시작하지 못했습니다');

      // 한 건 끝날 때마다 바로 저장한다. 배치가 중간에 끊기거나 탭이 닫혀도
      // 그때까지 나온 글은 저장된 글에 남는다.
      if (r.ok && r.text) {
        try {
          const { title, content } = splitTitleBody(r.text);
          appendSavedPosts([{ keyword: r.keyword, title, content }]);
          setSavedCount((n) => n + 1);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : '저장에 실패했습니다');
        }
      }

      setRows((prev) =>
        prev.map((row) =>
          row.id === r.id
            ? {
                ...row,
                status: r.ok ? 'done' : 'failed',
                text: r.ok ? r.text : row.text,
                chars: r.chars,
                error: r.ok ? undefined : r.error,
              }
            : row,
        ),
      );
    });
    return off;
  }, []);

  const run = async () => {
    if (!targets.length) {
      toast.error('생성할 키워드가 없습니다');
      return;
    }
    if (!hasKeywordVar) {
      toast.error('프롬프트에 {{키워드}} 가 없습니다. 모든 글이 같은 내용으로 나옵니다.');
      return;
    }
    const items = targets.map((r) => ({
      id: r.id,
      keyword: r.keyword,
      prompt: renderPrompt(draft, { 키워드: r.keyword, keyword: r.keyword }),
    }));
    try {
      const res = await startGeneration(items, options);
      if (!res.success) {
        toast.error(res.error || '시작하지 못했습니다');
        return;
      }
      setRows((prev) =>
        prev.map((r) =>
          targets.some((t) => t.id === r.id)
            ? { ...r, status: 'running', text: undefined, error: undefined }
            : r,
        ),
      );
      setRunning(true);
      toast.success(`${res.accepted}건 생성을 시작합니다. Gemini 탭에서 진행됩니다.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '확장 프로그램 호출 실패');
    }
  };

  const stop = async () => {
    try {
      await cancelGeneration();
      toast.info('현재 건이 끝나면 중단됩니다');
    } catch {
      toast.error('중단 요청에 실패했습니다');
    }
  };

  // ---------- 결과 ----------
  const downloadAll = () => {
    const done = rows.filter((r) => r.status === 'done' && r.text);
    if (!done.length) {
      toast.error('저장할 결과가 없습니다');
      return;
    }
    const body = done
      .map((r) => {
        const { title, content } = splitTitleBody(r.text!);
        return `===== ${r.keyword} =====\n[제목] ${title}\n\n${content}`;
      })
      .join('\n\n\n');
    const blob = new Blob([body], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `생성글_${done.length}건.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const copyOne = async (r: GenItem) => {
    if (!r.text) return;
    await navigator.clipboard.writeText(r.text);
    toast.success(`'${r.keyword}' 복사됨`);
  };

  // ============================================================
  return (
    <div className="space-y-6">
      {/* 1. 키워드 업로드 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="h-4 w-4" /> 1. 키워드 엑셀 업로드
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
              dragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'
            }`}
          >
            <Upload className="mx-auto mb-2 h-7 w-7 text-muted-foreground" />
            <p className="text-sm font-medium">엑셀 파일을 끌어다 놓거나 클릭해서 선택</p>
            <p className="mt-1 text-xs text-muted-foreground">
              .xlsx · .xls · .csv — 첫 열 키워드, 둘째 열 검색량
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void ingest(f);
                e.target.value = '';
              }}
            />
          </div>

          {rows.length > 0 && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary">전체 {rows.length}개</Badge>
                <Badge>생성 대상 {targets.length}개</Badge>
                {doneCount > 0 && (
                  <Badge className="bg-emerald-600 hover:bg-emerald-600">완료 {doneCount}</Badge>
                )}
                {failCount > 0 && <Badge variant="destructive">실패 {failCount}</Badge>}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-muted-foreground"
                  onClick={() => setRows([])}
                  disabled={running}
                >
                  <Trash2 className="mr-1 h-3.5 w-3.5" /> 비우기
                </Button>
              </div>

              {maxVolume > 0 && (
                <div className="space-y-2">
                  <Label className="text-xs">
                    최소 검색량 {minVolume.toLocaleString()} 이상만 생성
                  </Label>
                  <Slider
                    value={[minVolume]}
                    onValueChange={([v]) => setMinVolume(v)}
                    max={maxVolume}
                    step={Math.max(1, Math.round(maxVolume / 100))}
                    disabled={running}
                  />
                </div>
              )}

              <div className="max-h-64 overflow-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/60 text-xs">
                    <tr>
                      <th className="p-2 text-left font-medium">키워드</th>
                      <th className="w-24 p-2 text-right font-medium">검색량</th>
                      <th className="w-28 p-2 text-center font-medium">상태</th>
                      <th className="w-20 p-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const included = (r.volume ?? 0) >= minVolume;
                      return (
                        <tr
                          key={r.id}
                          className={`border-t ${included ? '' : 'opacity-40'}`}
                        >
                          <td className="p-2">{r.keyword}</td>
                          <td className="p-2 text-right tabular-nums text-muted-foreground">
                            {r.volume?.toLocaleString() ?? '—'}
                          </td>
                          <td className="p-2 text-center">
                            <StatusCell item={r} included={included} />
                          </td>
                          <td className="p-2 text-right">
                            {r.status === 'done' && (
                              <Button variant="ghost" size="sm" onClick={() => copyOne(r)}>
                                <Copy className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 2. 프롬프트 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">2. 명령 프롬프트</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Select value={activeId} onValueChange={selectTemplate}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={addTemplate}>
              <Plus className="mr-1 h-3.5 w-3.5" /> 새 템플릿
            </Button>
            <Button variant="outline" size="sm" onClick={removeTemplate}>
              <Trash2 className="mr-1 h-3.5 w-3.5" /> 삭제
            </Button>
            <Button size="sm" className="ml-auto" onClick={saveDraft}>
              <Save className="mr-1 h-3.5 w-3.5" /> 저장
            </Button>
          </div>

          <div className="space-y-2">
            <Label className="text-xs">템플릿 이름</Label>
            <Input value={draftName} onChange={(e) => setDraftName(e.target.value)} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">프롬프트 본문</Label>
              <code className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{'{{키워드}}'}</code>
            </div>
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={12}
              className="font-mono text-xs leading-relaxed"
            />
            {!hasKeywordVar && (
              <p className="flex items-center gap-1.5 text-xs text-amber-600">
                <AlertCircle className="h-3.5 w-3.5" />
                {'{{키워드}}'} 가 없습니다. 이대로면 모든 글이 같은 내용으로 나옵니다.
              </p>
            )}
          </div>

          <details className="rounded-lg border bg-muted/30 p-3">
            <summary className="cursor-pointer text-xs font-medium">
              실제로 보내질 내용 미리보기
            </summary>
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground">
              {preview}
            </pre>
          </details>
        </CardContent>
      </Card>

      {/* 3. 실행 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center justify-between text-base">
            <span>3. 생성 실행</span>
            <Button variant="ghost" size="sm" onClick={() => setShowOptions((v) => !v)}>
              <Settings2 className="mr-1 h-3.5 w-3.5" /> 고급 설정
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {showOptions && (
            <div className="grid gap-4 rounded-lg border bg-muted/30 p-4 sm:grid-cols-2">
              <NumField
                label="새 채팅 주기"
                hint="1 = 매 글마다 새 대화. 문맥이 안 쌓여 품질이 균일합니다."
                value={options.newChatEvery}
                min={1}
                onChange={(v) => setOptions((o) => ({ ...o, newChatEvery: v }))}
              />
              <NumField
                label="탭 새로고침 주기"
                hint="오래 돌리면 Gemini 앱이 느려집니다. N건마다 새로고침합니다."
                value={options.reloadEvery}
                min={1}
                onChange={(v) => setOptions((o) => ({ ...o, reloadEvery: v }))}
              />
              <NumField
                label="최소 글자수"
                hint="이보다 짧으면 실패로 보고 재시도합니다."
                value={options.minChars}
                min={0}
                step={100}
                onChange={(v) => setOptions((o) => ({ ...o, minChars: v }))}
              />
              <NumField
                label="재시도 횟수"
                hint="품질 미달일 때 새 대화로 다시 시도합니다."
                value={options.retries}
                min={0}
                onChange={(v) => setOptions((o) => ({ ...o, retries: v }))}
              />
              <div className="flex items-center justify-between sm:col-span-2">
                <div>
                  <Label className="text-xs">임시 채팅 사용</Label>
                  <p className="text-[11px] text-muted-foreground">
                    Gemini 사이드바에 대화 기록이 쌓이지 않습니다.
                  </p>
                </div>
                <Switch
                  checked={options.tempChat}
                  onCheckedChange={(v) => setOptions((o) => ({ ...o, tempChat: v }))}
                />
              </div>
            </div>
          )}

          {running && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>
                  {doneCount + failCount} / {targets.length} 처리됨
                </span>
                <span>{progressPct}%</span>
              </div>
              <Progress value={progressPct} />
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {running ? (
              <Button variant="destructive" onClick={stop}>
                <Square className="mr-1.5 h-4 w-4" /> 중단
              </Button>
            ) : (
              <Button onClick={run} disabled={!targets.length}>
                <Play className="mr-1.5 h-4 w-4" /> {targets.length}건 생성 시작
              </Button>
            )}
            <Button variant="outline" onClick={downloadAll} disabled={!doneCount}>
              <Download className="mr-1.5 h-4 w-4" /> 결과 내려받기 ({doneCount})
            </Button>
            {savedCount > 0 && (
              <Button variant="secondary" asChild>
                <a href="/dashboard/saved">
                  <Save className="mr-1.5 h-4 w-4" /> 저장된 글 {savedCount}건 보기 →
                </a>
              </Button>
            )}
          </div>

          {savedCount > 0 && (
            <p className="flex items-center gap-1.5 text-xs text-emerald-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              완성된 글은 자동으로 &lsquo;저장된 글&rsquo;에 저장됩니다. 거기서 사진을 넣고
              예약발행을 걸 수 있습니다.
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            생성은 Gemini 탭에서 진행됩니다. 그 탭을 닫지 마세요. 다른 탭에서 작업하셔도 됩니다.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================
function StatusCell({ item, included }: { item: GenItem; included: boolean }) {
  if (!included) return <span className="text-xs text-muted-foreground">제외</span>;
  switch (item.status) {
    case 'running':
      return (
        <span className="inline-flex items-center gap-1 text-xs text-blue-600">
          <Loader2 className="h-3 w-3 animate-spin" /> 대기/생성
        </span>
      );
    case 'done':
      return (
        <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
          <CheckCircle2 className="h-3 w-3" /> {item.chars?.toLocaleString()}자
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1 text-xs text-red-600" title={item.error}>
          <AlertCircle className="h-3 w-3" /> 실패
        </span>
      );
    default:
      return <span className="text-xs text-muted-foreground">대기</span>;
  }
}

function NumField({
  label, hint, value, onChange, min = 0, step = 1,
}: {
  label: string; hint: string; value: number;
  onChange: (v: number) => void; min?: number; step?: number;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        value={value}
        min={min}
        step={step}
        onChange={(e) => onChange(Math.max(min, Number(e.target.value) || 0))}
        className="h-8"
      />
      <p className="text-[11px] leading-snug text-muted-foreground">{hint}</p>
    </div>
  );
}
