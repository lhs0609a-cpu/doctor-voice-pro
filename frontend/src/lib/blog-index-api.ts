/**
 * 블로그 지수 / 상위노출 가능성 판정 API (backend/app/api/blog_index.py, prefix /api/v1/blog-index)
 * 무거운 작업은 Task 로 돌아오며 campaign-api 의 pollTask 로 진행률을 본다.
 */
import api from '@/lib/api'
import type { Task } from '@/lib/campaign-api'

const B = '/api/v1/blog-index'

export interface BlogIndexResult {
  blog_id: string
  success: boolean
  error_code?: string | null
  error_message?: string | null
  canonical_blog_id?: string | null
  blog_name?: string | null
  naver_level?: number | null
  data_sources?: string[]
  stats?: {
    total_posts?: number | null; total_posts_min?: number | null; neighbor_count?: number | null
    total_visitors?: number | null; daily_visitors?: number | null; recent_avg_visitors?: number | null
    visitor_measured?: boolean; visitor_series?: { date: string; count: number }[]
  }
  index?: {
    total_score?: number | null; level?: number | null; grade?: string | null; level_category?: string | null
    percentile?: number | null; level_basis?: string; level_source?: string; confidence?: string
    vitality?: number; vitality_state?: string; days_since_last_post?: number | null; posts_last_90d?: number | null
    rss_truncated?: boolean; extra_bonus?: number; unmeasured_dimensions?: string[]; measurement_complete?: boolean
    unmeasurable_reason?: string | null
    score_breakdown?: {
      c_rank?: number | null; dia?: number | null; content_factors?: number | null
      c_rank_detail?: Record<string, number>; dia_detail?: Record<string, number>
      content_detail?: Record<string, { score: number; raw: number }>
      weights_used?: Record<string, unknown>; keyword_category?: string
    }
  }
  estimated_fields?: string[]
  unmeasured?: string[]
  rss_empty?: boolean
  snapshot_at?: string
  disclaimer?: string
}

export type VerdictKind = 'already_ranked' | 'likely' | 'contested' | 'unlikely' | 'unknown' | string

export interface VerdictSummary {
  keyword: string
  verdict: VerdictKind
  label: string
  probability: number | null
  percent: number | null
  confidence?: string | null
  my_score?: number | null
  my_grade?: string | null
  cut_line?: number | null
  median_score?: number | null
  my_rank?: number | null
  volume?: number | null
  reasons: string[]
  scored_competitors?: number | null
  vacancy_count?: number | null
  ok: boolean
  at?: string
}

export interface VerdictDetail {
  ok: boolean
  blog_id: string
  keyword: string
  facts?: {
    volume?: number; volume_measured?: boolean; my_rank?: number | null; already_page1?: boolean
    serp_source?: string; serp_parse_mode?: string; serp_cached?: boolean; serp_measured_at?: string; serp_size?: number
    page1?: { rank: number; blog_id: string; blog_name?: string; post_title?: string; post_url?: string }[]
  }
  competitors?: { rank: number; blog_id: string; blog_name?: string; post_title?: string; score?: number | null; level?: number | null; grade?: string | null; recent_activity_days?: number | null; measured?: boolean }[]
  my?: { score: number; level?: number; grade?: string } | null
  topical_posts?: number | null
  ceiling?: { ceiling_p50?: number | null; ceiling_volume?: number | null; confidence?: string } | null
  verdict: VerdictKind
  probability: number | null
  confidence?: string
  reasons: string[]
  features?: Record<string, number>
  cut_line?: number | null
  entry_bar?: number | null
  median_score?: number | null
  my_score?: number | null
  scored_competitors?: number
  vacancy_count?: number
  model_version?: string
  elapsed?: number
  disclaimer?: string
  summary?: VerdictSummary
}

export interface VerdictBatchResult {
  blog_id: string
  partial?: boolean
  my: { score?: number | null; level?: number | null; grade?: string | null; blog_name?: string | null } | null
  items: (VerdictSummary & { detail?: VerdictDetail })[]
  disclaimer?: string
}

export const blogIndexAPI = {
  config: async (): Promise<{ search_ad: boolean; openapi: boolean; scoring_version: number; disclaimers: Record<string, string> }> =>
    (await api.get(`${B}/config`)).data,

  analyze: async (body: { blog_id: string; keyword?: string; fullparse?: boolean; refresh?: boolean; verify_index?: boolean; background?: boolean }): Promise<BlogIndexResult | { task: Task }> =>
    (await api.post(`${B}/analyze`, body, { timeout: 300000 })).data,
  latestIndex: async (blogId: string): Promise<BlogIndexResult> => (await api.get(`${B}/${encodeURIComponent(blogId)}/index`)).data,
  history: async (blogId: string, limit = 60): Promise<{ at: string; score: number; level: number; grade: string }[]> =>
    (await api.get(`${B}/${encodeURIComponent(blogId)}/history`, { params: { limit } })).data,

  verdictFacts: async (blogId: string, keyword: string): Promise<NonNullable<VerdictDetail['facts']> & { ok: boolean; error?: string }> =>
    (await api.post(`${B}/verdict/facts`, { blog_id: blogId, keyword }, { timeout: 120000 })).data,
  verdict: async (blogId: string, keyword: string): Promise<Task> => (await api.post(`${B}/verdict`, { blog_id: blogId, keyword })).data,
  verdictBatch: async (blogId: string, keywords: string[], campaignId?: string): Promise<Task> =>
    (await api.post(`${B}/verdict/batch`, { blog_id: blogId, keywords, campaign_id: campaignId })).data,
  /** 키워드들의 경쟁 블로그를 미리 채점(블로그 무관). 결과를 기다리지 않는다 — 판정이 캐시 히트로 몇 초 안에 끝나게. */
  prewarm: async (keywords: string[]): Promise<Task> => (await api.post(`${B}/prewarm`, { keywords: keywords.slice(0, 40) })).data,
  verdictLatest: async (blogId: string, keywords?: string[], hours = 24): Promise<{ blog_id: string; items: VerdictSummary[] }> =>
    (await api.get(`${B}/verdict/latest`, { params: { blog_id: blogId, keywords: (keywords || []).join(','), hours } })).data,

  getCeiling: async (blogId: string): Promise<Record<string, unknown>> => (await api.get(`${B}/exposure-ceiling`, { params: { blog_id: blogId } })).data,
  measureCeiling: async (blogId: string, refresh = false): Promise<Task> => (await api.post(`${B}/exposure-ceiling`, { blog_id: blogId, refresh })).data,
  serpDifficulty: async (keyword: string, topN = 10): Promise<Record<string, unknown>> => (await api.get(`${B}/serp-difficulty`, { params: { keyword, top_n: topN }, timeout: 120000 })).data,
  judgeKeywordV1: async (blogId: string, keyword: string, includeSerp = true): Promise<Record<string, unknown>> =>
    (await api.post(`${B}/judge-keyword`, { blog_id: blogId, keyword, include_serp: includeSerp }, { timeout: 120000 })).data,
  verifyIndex: async (blogId: string): Promise<Task> => (await api.post(`${B}/verify-index`, { blog_id: blogId })).data,
  competition: async (keyword: string, myBlogId?: string): Promise<Task> => (await api.post(`${B}/competition`, { keyword, my_blog_id: myBlogId })).data,
  postExposure: async (blogId: string): Promise<Task> => (await api.post(`${B}/post-exposure`, { blog_id: blogId })).data,
}

export const VERDICT_TONE: Record<string, 'ok' | 'warn' | 'danger' | 'accent' | 'muted'> = {
  already_ranked: 'accent', likely: 'ok', contested: 'warn', unlikely: 'danger', unknown: 'muted',
}
export const VERDICT_LABEL: Record<string, string> = {
  already_ranked: '이미 노출 중', likely: '가능성 높음', contested: '경합', unlikely: '가능성 낮음', unknown: '측정 불가',
}
export const LEVEL_CATEGORY = (level?: number | null) => (level == null ? '측정 불가' : level >= 12 ? '최적+' : level >= 9 ? '최적' : level >= 2 ? '준최' : '일반')
