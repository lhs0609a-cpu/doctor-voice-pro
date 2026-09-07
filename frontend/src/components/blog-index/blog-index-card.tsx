'use client'

/**
 * 블로그 지수 카드. BlogIndexResult 하나를 보여준다.
 *  - BlogIndexCard  : 순수 표시(결과·로딩·다시 분석 버튼)
 *  - BlogIndexPanel : blogId 만 주면 최근 결과를 가져오고, 없으면 분석까지 돌린다
 */
import { useCallback, useEffect, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { EmptyState, Pill } from '@/components/app-shell/ui-kit'
import { cn } from '@/lib/utils'
import { pollTask } from '@/lib/campaign-api'
import { blogIndexAPI, LEVEL_CATEGORY, type BlogIndexResult } from '@/lib/blog-index-api'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

/** 등급 분류 → Pill 톤. 최적+ accent / 최적 ok / 준최 warn / 일반·측정 불가 muted */
export function indexTone(level?: number | null): Tone {
  const c = LEVEL_CATEGORY(level)
  return c === '최적+' ? 'accent' : c === '최적' ? 'ok' : c === '준최' ? 'warn' : 'muted'
}

const VITALITY_LABEL: Record<string, { label: string; tone: Tone }> = {
  active: { label: '활발', tone: 'ok' },
  normal: { label: '보통', tone: 'muted' },
  slow: { label: '뜸함', tone: 'warn' },
  dormant: { label: '휴면', tone: 'danger' },
  inactive: { label: '비활성', tone: 'danger' },
  dead: { label: '중단', tone: 'danger' },
  unknown: { label: '측정 불가', tone: 'muted' },
}

const DETAIL_LABEL: Record<string, string> = {
  context: '맥락', content: '콘텐츠', chain: '연결',
  depth: '깊이', information: '정보성', accuracy: '정확성',
  content_length: '글 길이', heading_count: '소제목', paragraph_count: '문단', image_count: '이미지',
  keyword_count: '키워드 수', keyword_density: '키워드 밀도', freshness: '최신성', title_keyword: '제목 키워드',
}

const FIELD_LABEL: Record<string, string> = {
  total_posts: '총 글 수', total_posts_min: '총 글 수', neighbor_count: '이웃 수', total_visitors: '누적 방문',
  daily_visitors: '일 방문', recent_avg_visitors: '최근 평균 방문', naver_level: '네이버 레벨', visitor_series: '방문자 추이',
  c_rank: 'C-Rank', dia: 'D.I.A.', content_factors: '콘텐츠 요소', percentile: '백분위', level: '레벨',
  fullparse: '본문 정밀 분석', rss: 'RSS', engagement: '반응', ...DETAIL_LABEL,
}

const label = (k: string) => FIELD_LABEL[k] || k

const num = (v?: number | null, digits = 0) => (v == null || Number.isNaN(v) ? '측정 불가' : v.toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits }))

/** 0~100 가로 막대 */
function Bar({ value, tone = 'accent', className }: { value?: number | null; tone?: Tone; className?: string }) {
  const w = value == null ? 0 : Math.max(0, Math.min(100, value))
  const color = tone === 'ok' ? 'bg-success' : tone === 'warn' ? 'bg-warning' : tone === 'danger' ? 'bg-danger' : tone === 'accent' ? 'bg-primary' : 'bg-muted-foreground/40'
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-muted', className)}>
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${w}%` }} />
    </div>
  )
}

function BreakdownRow({ title, value, detail }: { title: string; value?: number | null; detail?: Record<string, number | { score: number; raw: number }> }) {
  const entries = Object.entries(detail || {})
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3 text-sm">
        <span className="w-24 shrink-0 text-[13px] text-muted-foreground">{title}</span>
        <Bar value={value} tone={value == null ? 'muted' : value >= 70 ? 'ok' : value >= 40 ? 'warn' : 'danger'} className="flex-1" />
        <span className="w-16 text-right font-medium tabular-nums">{num(value, 1)}</span>
      </div>
      {entries.length > 0 && (
        <div className="ml-[6.75rem] flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] tabular-nums text-muted-foreground">
          {entries.map(([k, v]) => {
            const score = typeof v === 'number' ? v : v?.score
            const raw = typeof v === 'number' ? undefined : v?.raw
            return (
              <span key={k}>
                {label(k)} <span className="text-foreground">{num(score, 1)}</span>
                {raw != null && <span className="opacity-70"> (실측 {num(raw, 1)})</span>}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

interface CardProps {
  result?: BlogIndexResult | null
  loading?: boolean
  refreshing?: boolean
  onRefresh?: () => void
  className?: string
  /** 상단 헤더(제목 줄) 숨김 */
  bare?: boolean
}

export function BlogIndexCard({ result, loading, refreshing, onRefresh, className, bare }: CardProps) {
  if (loading && !result) {
    return (
      <div className={cn('surface flex items-center gap-3 p-5 text-sm text-muted-foreground', className)}>
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        블로그를 분석하는 중입니다… 처음이면 20~60초 걸립니다.
      </div>
    )
  }
  if (!result) {
    return (
      <EmptyState
        title="아직 지수 결과가 없습니다"
        description="위에서 블로그를 고르고 판정을 누르면 지수가 함께 나옵니다."
        className={cn('py-8', className)}
      />
    )
  }
  if (!result.success) {
    return (
      <div className={cn('surface space-y-2 p-5', className)}>
        <div className="text-sm font-semibold">블로그 지수를 측정하지 못했습니다</div>
        <p className="text-sm text-muted-foreground">{result.error_message || result.error_code || '블로그를 읽을 수 없습니다. ID 를 다시 확인해 주세요.'}</p>
        {onRefresh && (
          <Button size="sm" variant="outline" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? <Loader2 className="animate-spin" /> : <RefreshCw />} 다시 분석
          </Button>
        )}
      </div>
    )
  }

  const idx = result.index || {}
  const st = result.stats || {}
  const bd = idx.score_breakdown || {}
  const category = idx.level_category || LEVEL_CATEGORY(idx.level)
  const tone = indexTone(idx.level)
  const vit = idx.vitality_state ? (VITALITY_LABEL[idx.vitality_state] || { label: idx.vitality_state, tone: 'muted' as Tone }) : null
  const days = idx.days_since_last_post
  const visitors = st.visitor_measured ? (st.daily_visitors ?? st.recent_avg_visitors) : null
  const posts = st.total_posts ?? st.total_posts_min
  const unmeasured = Array.from(new Set([...(result.unmeasured || []), ...(idx.unmeasured_dimensions || [])]))

  return (
    <div className={cn('surface p-5', className)}>
      {!bare && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="eyebrow">블로그 지수</div>
            <div className="truncate text-[15px] font-semibold">
              {result.blog_name || result.canonical_blog_id || result.blog_id}
              <span className="ml-1.5 font-mono text-xs font-normal text-muted-foreground">{result.canonical_blog_id || result.blog_id}</span>
            </div>
          </div>
          {onRefresh && (
            <Button size="sm" variant="outline" onClick={onRefresh} disabled={refreshing || loading}>
              {refreshing || loading ? <Loader2 className="animate-spin" /> : <RefreshCw />} 다시 분석
            </Button>
          )}
        </div>
      )}

      {/* 점수 + 등급 */}
      <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
        <div>
          <div className="text-[13px] font-medium text-muted-foreground">종합 점수</div>
          <div className={cn('kpi', tone === 'accent' ? 'text-primary' : tone === 'ok' ? 'text-success' : tone === 'warn' ? 'text-warning' : 'text-foreground')}>
            {idx.total_score == null ? '측정 불가' : num(idx.total_score, 1)}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 pb-1">
          <Pill tone={tone}>{idx.grade ? `${idx.grade} · ${category}` : category}</Pill>
          {vit && <Pill tone={vit.tone}>활동 {vit.label}</Pill>}
          {idx.confidence && <Pill tone="muted">신뢰도 {CONF_LABEL[idx.confidence] || idx.confidence}</Pill>}
          {idx.measurement_complete === false && <Pill tone="muted">일부만 측정</Pill>}
        </div>
        <div className="ml-auto text-xs tabular-nums text-muted-foreground">
          {days == null ? '마지막 글: 측정 불가' : days === 0 ? '오늘 글 올림' : `마지막 글 ${num(days)}일 전`}
          {idx.posts_last_90d != null && ` · 최근 90일 ${num(idx.posts_last_90d)}편`}
        </div>
      </div>

      {/* 실측 통계 */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Stat label="총 글" value={num(posts)} estimated={result.estimated_fields?.includes('total_posts')} />
        <Stat label="이웃" value={num(st.neighbor_count)} estimated={result.estimated_fields?.includes('neighbor_count')} />
        <Stat label="일 방문" value={num(visitors)} hint={st.visitor_measured ? '실측' : undefined} />
      </div>

      {/* 점수 구성 */}
      <div className="mt-5 space-y-3">
        <div className="text-[13px] font-medium text-muted-foreground">점수 구성</div>
        <BreakdownRow title="C-Rank" value={bd.c_rank} detail={bd.c_rank_detail} />
        <BreakdownRow title="D.I.A." value={bd.dia} detail={bd.dia_detail} />
        <BreakdownRow title="콘텐츠 요소" value={bd.content_factors} detail={bd.content_detail} />
        {bd.keyword_category && <div className="text-[11px] text-muted-foreground">가중치 기준: {bd.keyword_category}</div>}
      </div>

      {/* 추정·미측정 */}
      {(result.estimated_fields?.length || unmeasured.length || idx.unmeasurable_reason || result.rss_empty) ? (
        <div className="mt-4 space-y-0.5 text-[11px] text-muted-foreground">
          {!!result.estimated_fields?.length && <div>추정값: {result.estimated_fields.map(label).join(', ')}</div>}
          {unmeasured.length > 0 && <div>측정 불가: {unmeasured.map(label).join(', ')}</div>}
          {idx.unmeasurable_reason && <div>{idx.unmeasurable_reason}</div>}
          {result.rss_empty && <div>RSS 가 비어 있어 글 분석을 건너뛰었습니다.</div>}
        </div>
      ) : null}

      {result.disclaimer && <p className="mt-4 border-t pt-3 text-xs leading-5 text-muted-foreground">{result.disclaimer}</p>}
    </div>
  )
}

const CONF_LABEL: Record<string, string> = { high: '높음', medium: '보통', mid: '보통', low: '낮음' }

function Stat({ label: l, value, hint, estimated }: { label: string; value: string; hint?: string; estimated?: boolean }) {
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{l}{estimated && <span className="ml-1">(추정)</span>}</div>
      <div className="text-sm font-semibold tabular-nums">{value}{hint && <span className="ml-1 text-[11px] font-normal text-muted-foreground">{hint}</span>}</div>
    </div>
  )
}

// ───────────────────────── 자가 관리 패널 ─────────────────────────
export interface IndexSeed { score?: number | null; level?: number | null; grade?: string | null; blog_name?: string | null }

/** 판정 결과의 my 요약으로 임시 카드를 만든다(상세를 받기 전까지 보여줄 것) */
export function seedToResult(blogId: string, seed?: IndexSeed | null): BlogIndexResult | null {
  if (!seed) return null
  return {
    blog_id: blogId, success: true, blog_name: seed.blog_name,
    index: { total_score: seed.score, level: seed.level, grade: seed.grade, level_category: LEVEL_CATEGORY(seed.level) },
  }
}

/** 분석 API 응답이 Task 면 끝날 때까지 기다린 뒤 최근 결과를 가져온다 */
export async function analyzeAndWait(blogId: string, refresh = false): Promise<BlogIndexResult> {
  const r = await blogIndexAPI.analyze({ blog_id: blogId, refresh })
  if (r && typeof r === 'object' && 'task' in r) {
    const t = await pollTask(r.task.id)
    if (t.status !== 'done') throw new Error(t.error || '분석이 끝나지 않았습니다')
    return blogIndexAPI.latestIndex(blogId)
  }
  return r as BlogIndexResult
}

interface PanelProps {
  blogId: string
  /** 상세를 받기 전까지 보여줄 요약(판정 결과의 my) */
  seed?: IndexSeed | null
  /** 최근 결과가 없을 때 바로 분석까지 돌릴지(기본 true) */
  analyzeIfMissing?: boolean
  className?: string
  bare?: boolean
}

export function BlogIndexPanel({ blogId, seed, analyzeIfMissing = true, className, bare }: PanelProps) {
  const [result, setResult] = useState<BlogIndexResult | null>(() => seedToResult(blogId, seed))
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (refresh: boolean) => {
    if (!blogId) return
    refresh ? setRefreshing(true) : setLoading(true)
    try {
      if (refresh) {
        setResult(await analyzeAndWait(blogId, true))
        toast.success('블로그 지수를 다시 쟀습니다')
        return
      }
      try {
        setResult(await blogIndexAPI.latestIndex(blogId))
      } catch {
        if (analyzeIfMissing) setResult(await analyzeAndWait(blogId, false))
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '블로그 지수를 가져오지 못했습니다'
      toast.error('블로그 지수 분석 실패', { description: msg })
      setResult((prev) => prev ?? { blog_id: blogId, success: false, error_message: msg })
    } finally {
      setLoading(false); setRefreshing(false)
    }
  }, [blogId, analyzeIfMissing])

  useEffect(() => {
    setResult(seedToResult(blogId, seed))
    load(false)
    // seed 는 보조 표시용이라 의존성에서 뺀다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blogId, load])

  if (!blogId) return <EmptyState title="블로그를 골라 주세요" description="블로그 ID 를 넣으면 지수를 보여 드립니다." className={cn('py-8', className)} />
  return <BlogIndexCard result={result} loading={loading} refreshing={refreshing} onRefresh={() => load(true)} className={className} bare={bare} />
}
