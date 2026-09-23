/**
 * 캠페인(병원 단위 대량 발행) API 클라이언트.
 * 백엔드: backend/app/api/campaign.py  (prefix /api/v1/campaign)
 *
 * 긴 작업(키워드 확장·통검 분석·원고 생성·사진 배치)은 TaskOut 을 돌려주고
 * 화면은 pollTask() 로 진행률을 본다.
 */
import api from '@/lib/api'

const C = '/api/v1/campaign'

export interface AutopilotConfig {
  daily_posts: number
  buffer_days: number
  image_count: number
  target_chars: number
  min_score: number
  max_rewrites: number
  daily_generation_limit: number
  landing_url: string
  landing_label: string
  landing_purpose: string
  landing_tracking: boolean
}
export interface AutopilotState {
  enabled: boolean
  config: AutopilotConfig
  message: string | null
  next_run_at: string | null
  reserved_today: number
  task: Task | null
}

// ───────────────────────── 타입 ─────────────────────────
/** 이 아이디로 올리는 글 끝에 늘 붙는 것들(예약 링크·플레이스 지도). */
export interface BlogFooter {
  footer_link_url?: string | null
  footer_link_label?: string | null
  place_url?: string | null
  place_label?: string | null
}

export interface BlogAccount extends BlogFooter {
  id: string
  client_id: string
  blog_id: string
  label?: string | null
  login_id?: string | null
  has_password: boolean
  daily_limit: number
  window_start: string
  window_end: string
  min_gap_minutes: number
  default_category?: string | null
  open_type: string
  status: 'active' | 'paused' | 'captcha' | 'login_required' | 'disabled' | string
  status_reason?: string | null
  last_published_at?: string | null
  proxy_label?: string | null      // 이 블로그 전용 고정 IP. host:port 만 온다(비밀번호는 서버에 남는다)
  // 블로그 지수(blog-index 분석 결과 캐시)
  index_score?: number | null
  index_level?: number | null
  index_grade?: string | null
  index_at?: string | null
}

export interface BlogInput {
  blog_id: string
  label?: string | null
  login_id?: string | null
  login_pw?: string | null
  proxy_url?: string | null        // 비우면 기존 값 유지, "-" 하나면 프록시를 지운다
  daily_limit: number
  window_start: string
  window_end: string
  min_gap_minutes: number
  default_category?: string | null
  open_type: string
  footer_link_url?: string | null
  footer_link_label?: string | null
  place_url?: string | null
  place_label?: string | null
}

export interface BriefFlowStep { title: string; goal?: string; min_chars?: number }

export interface Brief {
  id: string
  client_id?: string | null
  name: string
  description?: string | null
  flow: BriefFlowStep[]
  rules?: string | null
  must_include: string[]
  avoid: string[]
  source_text?: string | null
  target_chars: number
  heading_count: number
  keyword_count: number
  is_default: boolean
}

export type BriefInput = Omit<Brief, 'id'>

export interface ClientInput {
  name: string
  short_name?: string | null
  specialty?: string | null
  diseases: string[]
  treatments: string[]
  regions: string[]
  region_expand_level: number
  suffixes: string[]
  min_volume_region: number
  min_volume_national: number
  forbidden_words: string[]
  tone?: string | null
  facts?: string | null
  default_collection_id?: string | null
  sheet_url?: string | null
  sheet_blog_tab?: string | null
  sheet_cafe_tab?: string | null
}

export interface Client extends ClientInput {
  id: string
  active: boolean
  created_at?: string
  blogs: BlogAccount[]
  briefs: Brief[]
}

export interface Task {
  id: string
  type: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  progress: number
  total: number
  message?: string | null
  result?: Record<string, unknown> | null
  error?: string | null
  created_at?: string
  finished_at?: string | null
}

export interface Campaign {
  id: string
  client_id: string
  client_name?: string | null
  name: string
  step: number
  status: 'draft' | 'scheduled' | 'running' | 'done' | 'cancelled' | string
  blog_ids: string[]
  brief_id?: string | null
  collection_id?: string | null
  settings: Record<string, unknown>
  stats: {
    keywords?: number; keywords_selected?: number; drafts?: number; drafts_ready?: number
    jobs?: number; published?: number; failed?: number; queued?: number; uncertain?: number
  }
  created_at?: string
  updated_at?: string
}

export interface SerpSummary {
  exposed_count?: number; analyzed_count?: number; hospital_count?: number; hospital_ratio?: number
  influencer_count?: number; daily_count?: number; has_influencer?: boolean
  avg_kw_count?: number; avg_image_count?: number; avg_chars?: number; avg_headings?: number
  recommended_kw_count?: number; recommended_image_count?: number; recommended_chars?: number
}

export interface Keyword {
  id: string
  keyword: string
  region?: string | null
  disease?: string | null
  /** 글의 성격 — 대표|증상|원인|치료|관리|검사|비용|병원|기타 */
  category?: string | null
  /** 간절함(내원 의도) 0~100. 검색량과 다른 축이다. */
  intent_score?: number
  intent_reason?: string | null
  source: 'manual' | 'combo' | 'related' | 'seed' | string
  scope: 'region' | 'national' | string
  monthly_mobile: number
  monthly_pc: number
  total_volume: number
  competition: 'low' | 'mid' | 'high' | string
  verdict: 'possible' | 'contested' | 'avoid' | 'unknown' | string
  verdict_reason?: string | null
  serp_summary?: SerpSummary | null
  in_sheet: boolean
  sheet_note?: string | null
  selected: boolean
  passes_filter: boolean
  has_draft: boolean
  // 내 블로그 기준 상위노출 판정(blog-index verdict/batch 가 채움). my_probability 는 0~1
  my_blog_id?: string | null
  my_verdict?: 'already_ranked' | 'likely' | 'contested' | 'unlikely' | 'unknown' | string | null
  my_probability?: number | null
  my_verdict_result?: MyVerdictResult | null
}

/** 키워드 행에 저장되는 내 블로그 판정 요약(blog-index-api 의 VerdictSummary 에서 detail 을 뺀 것) */
export interface MyVerdictResult {
  keyword?: string
  verdict?: string
  label?: string
  probability?: number | null
  percent?: number | null
  confidence?: string | null
  my_score?: number | null
  my_grade?: string | null
  cut_line?: number | null
  median_score?: number | null
  my_rank?: number | null
  volume?: number | null
  reasons?: string[]
  scored_competitors?: number | null
  vacancy_count?: number | null
  ok?: boolean
  at?: string
}

export interface SerpPost {
  url: string; title: string; blog_id: string; blog_name?: string; blog_type: string; section?: string
  position?: number; kw_count?: number; image_count?: number; chars?: number; headings?: number; is_ad?: boolean
}

export interface ImageSlot {
  slot: number
  after_paragraph: number
  pool_image_id?: string | null
  score?: number
  reason?: string
  need?: string
  keywords?: string[]
  stage?: string
}

/** 워드에서 읽어 온 내역 — checks.import 에 들어 있다(backend/app/services/docx_import.py) */
export interface DocImport {
  source: 'docx'
  images: number
  tables: number
  headings: number
  warnings: string[]
}

export interface PointFormattingConfig {
  enabled: boolean; bold: boolean; quote: boolean; color: boolean; background: boolean
  text_color: string; background_color: string; phrases: string[]
}
export interface FormattedSpan { t: string; b?: boolean; i?: boolean; u?: boolean; color?: string; background?: string; size?: number }
export interface FormattedBlock { type: string; content?: string; spans?: FormattedSpan[]; items?: FormattedSpan[][]; rows?: FormattedSpan[][][] }

export interface Draft {
  id: string
  campaign_id?: string | null
  keyword_id?: string | null
  keyword?: string | null
  source: 'generated' | 'variant' | 'upload' | 'manual' | string
  parent_draft_id?: string | null
  title: string
  body?: string | null
  char_count: number
  status: 'generating' | 'ready' | 'needs_review' | 'failed' | string
  checks: Record<string, unknown>
  image_plan: ImageSlot[]
  image_count_target: number
  tags: string[]
  error?: string | null
  created_at?: string
  updated_at?: string
  /** 이미 예약이 걸린 원고의 예약 시각(KST). 있으면 다시 고를 수 없다. */
  booked_at?: string | null
  booked_job_id?: string | null
  /** queued = 아직 네이버에 안 올림 / submitted = 네이버에 이미 등록됨 */
  booked_status?: string | null
}

export interface PhotoMeta {
  id: string
  thumbnail?: string | null
  scene?: string | null
  tags: string[]
  caption?: string | null
  has_text?: boolean | null
  suitable_for: string[]
  use_count: number
  tagged: boolean
}

export interface ScheduleInput {
  start_date: string           // YYYY-MM-DD
  days: number
  blog_ids?: string[]
  per_day?: number | null
  draft_ids?: string[]
  include_needs_review?: boolean
  seed?: number | null
  /** spread: 기간 안에 흩뿌린다(마법사). interval: 고른 시각부터 고른 간격으로 하나씩(원스톱). */
  mode?: 'spread' | 'interval'
  start_at?: string            // interval 전용. 첫 글 시각 YYYY-MM-DDTHH:mm (KST)
  every_minutes?: number       // interval 전용. 글 사이 간격(분)
  /** at: start_at 부터 / after_last: 이미 예약된 글 다음부터 */
  start_mode?: 'at' | 'after_last'
}

/** 블로그 한 개에 이미 잡혀 있는 자리(우리 예약 + 네이버에서 읽어 온 남의 예약). */
export interface BlogReservations {
  blog_ref_id: string
  label: string
  count: number
  last_at?: string | null
  scanned_at?: string | null
  stale: boolean
  note?: string | null
}

export interface ScheduleItem { draft_id: string; title: string; blog_ref_id: string; blog_label: string; scheduled_at: string }
export interface SchedulePreview {
  total: number
  assigned: ScheduleItem[]
  unassigned: number
  calendar: { date: string; total: number; blogs: Record<string, number> }[]
  warnings: string[]
  starts_after?: string | null        // '이미 예약된 글 다음부터'의 기준이 된 마지막 예약
  reservations?: BlogReservations[]
}

export interface PublishJobItem {
  id: string
  draft_id: string
  title: string
  keyword?: string | null
  blog_ref_id: string
  blog_label: string
  naver_blog_id?: string | null
  scheduled_at: string
  status: 'queued' | 'assigned' | 'publishing' | 'published' | 'failed' | 'uncertain' | 'cancelled' | string
  attempts: number
  result_url?: string | null
  error?: string | null
  images_ready: boolean
  image_count: number
  published_at?: string | null
}

export interface ClaimedJob {
  id: string
  lock_token: string
  title: string
  content: string
  blocks: { type: 'text' | 'image'; content?: string | null; image?: string | null }[]
  tags: string[]
  emphasize: string[]
  finalAction: 'schedule'
  schedule: { datetime: string }
  options: { openType: string; search: boolean; category: string | null }
  expectedBlogId?: string | null
  blog_ref_id: string
  draft_id: string
}

export interface AgentBlogSummary {
  blog_ref_id: string; naver_blog_id: string; label: string; status: string; status_reason?: string | null
  pending: number; next_at?: string | null; login_id?: string | null
}

// PC 실행기 신호등. 실행기가 주기적으로 서버에 남긴 흔적을 읽는다.
export interface AgentDevice {
  device_id: string
  version?: string | null
  running: boolean
  label?: string | null
  note?: string | null
  last_seen_at: string
  seconds_ago: number
}

/** 실행기가 만든 연결 요청. 승인 화면이 '어느 PC인지' 보여주는 데 쓴다. */
export interface AgentPairRequestInfo {
  device_id: string
  label?: string | null
  approved: boolean
  mine: boolean
}

export interface AgentStatus {
  online: boolean
  running: boolean
  version?: string | null
  devices: AgentDevice[]
  /** 켜져 있다고는 하는데 올릴 글을 한참째 가져가지 않는 상태 */
  stalled?: boolean
  stalled_hint?: string | null
}

// ───────────────────────── API ─────────────────────────
export const campaignAPI = {
  // 병원
  listClients: async (): Promise<Client[]> => (await api.get(`${C}/clients`)).data,
  createClient: async (body: ClientInput): Promise<Client> => (await api.post(`${C}/clients`, body)).data,
  getClient: async (id: string): Promise<Client> => (await api.get(`${C}/clients/${id}`)).data,
  updateClient: async (id: string, body: ClientInput): Promise<Client> => (await api.put(`${C}/clients/${id}`, body)).data,
  deleteClient: async (id: string): Promise<{ success: boolean }> => (await api.delete(`${C}/clients/${id}`)).data,
  seedExampleClients: async (): Promise<Client[]> => (await api.post(`${C}/clients/seed-examples`)).data,

  // 블로그 계정
  addBlog: async (clientId: string, body: BlogInput): Promise<BlogAccount> => (await api.post(`${C}/clients/${clientId}/blogs`, body)).data,
  updateBlog: async (blogRefId: string, body: BlogInput): Promise<BlogAccount> => (await api.put(`${C}/blogs/${blogRefId}`, body)).data,
  setBlogStatus: async (blogRefId: string, status: string, reason?: string): Promise<BlogAccount> =>
    (await api.post(`${C}/blogs/${blogRefId}/status`, { status, reason })).data,
  deleteBlog: async (blogRefId: string): Promise<{ success: boolean }> => (await api.delete(`${C}/blogs/${blogRefId}`)).data,

  // 브리프
  builtinBriefs: async (): Promise<{ key: string; label: string; preset: BriefInput }[]> => (await api.get(`${C}/briefs/builtin`)).data,
  listBriefs: async (clientId?: string): Promise<Brief[]> => (await api.get(`${C}/briefs`, { params: clientId ? { client_id: clientId } : {} })).data,
  createBrief: async (body: BriefInput): Promise<Brief> => (await api.post(`${C}/briefs`, body)).data,
  updateBrief: async (id: string, body: BriefInput): Promise<Brief> => (await api.put(`${C}/briefs/${id}`, body)).data,
  deleteBrief: async (id: string): Promise<{ success: boolean }> => (await api.delete(`${C}/briefs/${id}`)).data,

  // 작업
  getTask: async (id: string): Promise<Task> => (await api.get(`${C}/tasks/${id}`)).data,
  listTasks: async (params?: { campaign_id?: string; active_only?: boolean; limit?: number }): Promise<Task[]> =>
    (await api.get(`${C}/tasks`, { params })).data,
  cancelTask: async (id: string): Promise<{ success: boolean }> => (await api.post(`${C}/tasks/${id}/cancel`)).data,

  // 캠페인
  getAutopilot: async (id: string): Promise<AutopilotState> => (await api.get(`${C}/campaigns/${id}/autopilot`)).data,
  setLanding: async (id: string, body: AutopilotConfig): Promise<void> => { await api.put(`${C}/campaigns/${id}/landing`, body) },
  setAutopilot: async (id: string, body: AutopilotConfig & { enabled: boolean }): Promise<AutopilotState> =>
    (await api.put(`${C}/campaigns/${id}/autopilot`, body)).data,
  startAutomation: async (id: string, body: { max_keywords: number; image_count: number; auto_schedule: boolean; start_date: string; days: number; discover_keywords?: boolean; strict_quality?: boolean; quality?: AutopilotConfig }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/automation`, body)).data,
  listCampaigns: async (clientId?: string): Promise<Campaign[]> => (await api.get(`${C}/campaigns`, { params: clientId ? { client_id: clientId } : {} })).data,
  createCampaign: async (clientId: string, name?: string): Promise<Campaign> => (await api.post(`${C}/campaigns`, { client_id: clientId, name })).data,
  getCampaign: async (id: string): Promise<Campaign> => (await api.get(`${C}/campaigns/${id}`)).data,
  patchCampaign: async (id: string, body: Partial<Pick<Campaign, 'name' | 'step' | 'blog_ids' | 'brief_id' | 'collection_id' | 'settings' | 'status'>>): Promise<Campaign> =>
    (await api.patch(`${C}/campaigns/${id}`, body)).data,
  deleteCampaign: async (id: string): Promise<{ success: boolean }> => (await api.delete(`${C}/campaigns/${id}`)).data,

  // 2단계 키워드
  expandKeywords: async (id: string, body: { seeds?: string[]; regions?: string[]; diseases?: string[]; level?: number; min_volume_region?: number; min_volume_national?: number; include_related?: boolean; analyze_after?: boolean }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/keywords/expand`, body)).data,
  // 발굴 — 씨앗 확장 → 통합검색 자리 확인 → 내 블로그로 뚫리는지 판정을 한 작업으로
  huntKeywords: async (id: string, body: {
    target: number; blog_id?: string; screen_limit?: number; verdict_limit?: number
    /** 직접 찾고 싶은 키워드. 주면 진료 항목 대신 이것만 판다. */
    seeds?: string[]
    /** 질환별 개수 {"건선": 30} */
    disease_quota?: Record<string, number>
    /** 글 성격 비율 {"증상": 20, "치료": 25} */
    category_ratio?: Record<string, number>
  }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/keywords/hunt`, body)).data,
  keywordCategories: async (): Promise<{ categories: { key: string; label: string; default_ratio: number }[] }> =>
    (await api.get(`${C}/keyword-categories`)).data,
  addKeywords: async (id: string, keywords: string[], fetchVolume = true): Promise<Keyword[]> =>
    (await api.post(`${C}/campaigns/${id}/keywords`, { keywords, fetch_volume: fetchVolume })).data,
  listKeywords: async (id: string): Promise<Keyword[]> => (await api.get(`${C}/campaigns/${id}/keywords`)).data,
  selectKeywords: async (id: string, ids: string[], selected: boolean): Promise<{ success: boolean }> =>
    (await api.patch(`${C}/campaigns/${id}/keywords/select`, { ids, selected })).data,
  clearKeywords: async (id: string): Promise<{ removed: number }> => (await api.delete(`${C}/campaigns/${id}/keywords`)).data,
  deleteKeyword: async (id: string, keywordId: string): Promise<{ success: boolean }> => (await api.delete(`${C}/campaigns/${id}/keywords/${keywordId}`)).data,
  analyzeKeywords: async (id: string, keywordIds?: string[], limit = 60): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/keywords/analyze`, { keyword_ids: keywordIds, limit })).data,
  sheetCheck: async (id: string): Promise<Task> => (await api.post(`${C}/campaigns/${id}/keywords/sheet-check`)).data,
  keywordSerp: async (id: string, keywordId: string): Promise<{ keyword: string; fetched_at?: string; posts: SerpPost[]; summary: SerpSummary | null; verdict?: string; verdict_reason?: string; error?: string | null }> =>
    (await api.get(`${C}/campaigns/${id}/keywords/${keywordId}/serp`)).data,

  getPointFormatting: async (id: string): Promise<PointFormattingConfig> => (await api.get(`${C}/campaigns/${id}/formatting`)).data,
  savePointFormatting: async (id: string, body: PointFormattingConfig): Promise<PointFormattingConfig> => (await api.put(`${C}/campaigns/${id}/formatting`, body)).data,
  previewPointFormatting: async (id: string, body: PointFormattingConfig): Promise<{ title: string; blocks: FormattedBlock[] }> => (await api.post(`${C}/drafts/${id}/formatting-preview`, body)).data,

  // 3단계 원고
  generateDrafts: async (id: string, body: { keyword_ids?: string[]; brief_id?: string | null; target_chars?: number; heading_count?: number; keyword_count?: number; image_count?: number; instructions?: string; force?: boolean }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/drafts/generate`, body)).data,
  makeVariants: async (id: string, body: { source_text: string; count: number; keyword?: string; title?: string; target_chars?: number }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/drafts/variants`, body)).data,
  uploadDrafts: async (id: string, files: File[]): Promise<Draft[]> => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return (await api.post(`${C}/campaigns/${id}/drafts/upload`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000 })).data
  },
  addDraftText: async (id: string, body: { title: string; body: string; keyword?: string }): Promise<Draft> => (await api.post(`${C}/campaigns/${id}/drafts`, body)).data,
  listDrafts: async (id: string, withBody = false): Promise<Draft[]> => (await api.get(`${C}/campaigns/${id}/drafts`, { params: { with_body: withBody } })).data,
  getDraft: async (draftId: string): Promise<Draft> => (await api.get(`${C}/drafts/${draftId}`)).data,
  updateDraft: async (draftId: string, body: { title?: string; body?: string; keyword?: string; status?: string; tags?: string[] }): Promise<Draft> =>
    (await api.put(`${C}/drafts/${draftId}`, body)).data,
  approveDraft: async (draftId: string): Promise<Draft> => (await api.post(`${C}/drafts/${draftId}/approve`)).data,
  deleteDraft: async (draftId: string): Promise<{ success: boolean }> => (await api.delete(`${C}/drafts/${draftId}`)).data,

  // 4단계 사진
  planPhotos: async (id: string, body: { collection_id?: string | null; image_count?: number | null; draft_ids?: string[] }): Promise<Task> =>
    (await api.post(`${C}/campaigns/${id}/photos/plan`, body)).data,
  tagPhotos: async (collectionId?: string | null): Promise<Task> => (await api.post(`${C}/photos/tag`, { collection_id: collectionId })).data,
  listPhotos: async (collectionId?: string | null, limit = 300): Promise<PhotoMeta[]> =>
    (await api.get(`${C}/photos`, { params: { collection_id: collectionId || undefined, limit } })).data,
  editPhotoTags: async (imageId: string, body: { scene?: string; tags?: string[]; caption?: string; suitable_for?: string[] }): Promise<PhotoMeta> =>
    (await api.put(`${C}/photos/${imageId}/tags`, body)).data,
  setImagePlan: async (draftId: string, slots: { slot: number; pool_image_id?: string; after_paragraph?: number }[]): Promise<Draft> =>
    (await api.put(`${C}/drafts/${draftId}/image-plan`, { slots })).data,

  // 5단계 예약
  listReservations: async (id: string): Promise<BlogReservations[]> => (await api.get(`${C}/campaigns/${id}/reservations`)).data,
  rescanReservations: async (id: string): Promise<{ requested: number }> => (await api.post(`${C}/campaigns/${id}/reservations/rescan`)).data,
  schedulePreview: async (id: string, body: ScheduleInput): Promise<SchedulePreview> => (await api.post(`${C}/campaigns/${id}/schedule/preview`, body)).data,
  scheduleCommit: async (id: string, body: ScheduleInput): Promise<SchedulePreview> => (await api.post(`${C}/campaigns/${id}/schedule/commit`, body)).data,
  scheduleCancel: async (id: string): Promise<{ success: boolean; cancelled: number }> => (await api.delete(`${C}/campaigns/${id}/schedule`)).data,

  // 6단계 현황
  listJobs: async (id: string): Promise<PublishJobItem[]> => (await api.get(`${C}/campaigns/${id}/jobs`)).data,
  retryJob: async (jobId: string): Promise<PublishJobItem> => (await api.post(`${C}/jobs/${jobId}/retry`)).data,
  cancelJob: async (jobId: string): Promise<PublishJobItem> => (await api.post(`${C}/jobs/${jobId}/cancel`)).data,
  markPublished: async (jobId: string, resultUrl?: string): Promise<PublishJobItem> => (await api.post(`${C}/jobs/${jobId}/mark-published`, { result_url: resultUrl })).data,

  // 발행 실행기(확장) 연동
  agentClaim: async (body: { blog_ref_id?: string; naver_blog_id?: string; limit?: number; include_images?: boolean }): Promise<ClaimedJob[]> =>
    (await api.post(`${C}/agent/claim`, { ...body, protocol_version: 2, limit: 1, capabilities: ['landing_links_v1'] }, { timeout: 600000 })).data,
  executionServer: (): string => process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' && localStorage.getItem('BACKEND_URL')) || 'http://localhost:8010',
  reconcileJob: async (jobId: string, outcome: 'registered' | 'not_registered', evidence: string): Promise<PublishJobItem> =>
    (await api.post(`${C}/jobs/${jobId}/reconcile`, { outcome, evidence })).data,
  agentResult: async (jobId: string, body: { lock_token?: string; ok: boolean; uncertain?: boolean; message?: string; url?: string; need_login?: boolean; captcha?: boolean; release?: boolean }): Promise<{ success: boolean; status: string }> =>
    (await api.post(`${C}/agent/jobs/${jobId}/result`, body)).data,
  agentSummary: async (): Promise<AgentBlogSummary[]> => (await api.get(`${C}/agent/summary`)).data,
  agentStatus: async (): Promise<AgentStatus> => (await api.get(`${C}/agent/status`)).data,
  // 홈페이지 자동 연결: 로그인된 이 페이지가 받는 1회용 코드(10분). 같은 PC의 실행기에 건넨다.
  agentPair: async (): Promise<{ code: string; expires_in: number }> => (await api.post(`${C}/agent/pair`)).data,
  // 반대 방향: 실행기가 먼저 만든 연결 요청을 로그인된 이 페이지가 승인한다(브라우저가 127.0.0.1 을 막아도 연결된다).
  agentPairRequestInfo: async (requestId: string): Promise<AgentPairRequestInfo> =>
    (await api.get(`${C}/agent/pair/request/${encodeURIComponent(requestId)}`)).data,
  agentPairApprove: async (requestId: string): Promise<{ success: boolean; device_id: string }> =>
    (await api.post(`${C}/agent/pair/approve`, { request_id: requestId })).data,
  revokeAgentDevice: async (deviceId: string): Promise<{ success: boolean }> =>
    (await api.delete(`${C}/agent/devices/${encodeURIComponent(deviceId)}`)).data,
}

/** 작업이 끝날 때까지 폴링. onTick 으로 진행률을 넘긴다. */
export async function pollTask(taskId: string, onTick?: (t: Task) => void, intervalMs = 1500, timeoutMs = 60 * 60 * 1000): Promise<Task> {
  const started = Date.now()
  for (;;) {
    const t = await campaignAPI.getTask(taskId)
    onTick?.(t)
    if (t.status === 'done' || t.status === 'failed' || t.status === 'cancelled') return t
    if (Date.now() - started > timeoutMs) throw new Error('작업이 너무 오래 걸립니다. 잠시 후 다시 확인하세요.')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

export const VERDICT_LABEL: Record<string, { label: string; tone: 'ok' | 'warn' | 'crit' | 'muted' }> = {
  possible: { label: '가능', tone: 'ok' },
  contested: { label: '경쟁', tone: 'warn' },
  avoid: { label: '비추천', tone: 'crit' },
  unknown: { label: '미분석', tone: 'muted' },
}

export const JOB_STATUS_LABEL: Record<string, string> = {
  queued: '대기', assigned: '작성 중', publishing: '등록 처리 중', submitted: '네이버 예약 등록', published: '공개 확인', failed: '실패', uncertain: '결과 대조 필요', cancelled: '취소', dry_run: '시험 완료',
}

export const BLOG_STATUS_LABEL: Record<string, string> = {
  active: '정상', paused: '일시정지', captcha: '캡차 확인 필요', login_required: '로그인 필요', disabled: '사용 안 함',
}
