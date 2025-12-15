import axios from 'axios'
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  PostCreateRequest,
  Post,
  PostListResponse,
  DoctorProfile,
  UserApprovalRequest,
  UserSubscriptionRequest,
} from '@/types'
import { logger } from '@/lib/logger'

// Extend Axios config to include metadata for tracking
declare module 'axios' {
  export interface AxiosRequestConfig {
    metadata?: {
      startTime: number
    }
  }
}

// Get dynamic API URL - prioritize env, then localStorage, then default
const getApiUrl = () => {
  // Always use environment variable if set
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }

  // Fallback to localStorage for development
  if (typeof window !== 'undefined') {
    const storedUrl = localStorage.getItem('BACKEND_URL')
    if (storedUrl) return storedUrl
  }

  return 'http://localhost:8010'
}

const API_URL = getApiUrl()

// Axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 3분 타임아웃 (AI 생성 시간 고려)
})

// Request interceptor - Add token to headers and log API calls
api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      // Only use localStorage if env variable is not set
      if (!process.env.NEXT_PUBLIC_API_URL) {
        const currentBackendUrl = localStorage.getItem('BACKEND_URL')
        if (currentBackendUrl) {
          config.baseURL = currentBackendUrl
        }
      }

      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }

    // Add metadata for tracking
    config.metadata = { startTime: Date.now() }

    // Log API request
    const method = (config.method || 'GET').toUpperCase()
    const endpoint = config.url || ''
    logger.logApiCall(method, endpoint)

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - Handle 401 and log responses
api.interceptors.response.use(
  (response) => {
    // Calculate duration from request metadata
    const duration = response.config.metadata?.startTime
      ? (Date.now() - response.config.metadata.startTime) / 1000
      : undefined

    // Log successful API call
    const method = (response.config.method || 'GET').toUpperCase()
    const endpoint = response.config.url || ''
    logger.logApiCall(method, endpoint, duration)

    return response
  },
  (error) => {
    // Log API error
    if (error.config) {
      const method = (error.config.method || 'GET').toUpperCase()
      const endpoint = error.config.url || ''
      const status = error.response?.status
      logger.logApiError(method, endpoint, error, status)
    }

    // Handle 401 - redirect to login
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  register: async (data: RegisterRequest): Promise<User> => {
    const response = await api.post<User>('/api/v1/auth/register', data)
    return response.data
  },

  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/v1/auth/login', data)
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/api/v1/auth/me')
    return response.data
  },
}

// Posts API
export const postsAPI = {
  create: async (data: PostCreateRequest): Promise<Post> => {
    // AI 생성은 오래 걸릴 수 있으므로 타임아웃을 더 길게 설정 (6분)
    const response = await api.post<Post>('/api/v1/posts/', data, {
      timeout: 360000, // 6분 타임아웃 (AI 생성 + 네트워크 지연 고려)
    })
    return response.data
  },

  list: async (page: number = 1, pageSize: number = 10): Promise<PostListResponse> => {
    const response = await api.get<PostListResponse>('/api/v1/posts/', {
      params: { page, page_size: pageSize },
    })
    return response.data
  },

  get: async (id: string): Promise<Post> => {
    const response = await api.get<Post>(`/api/v1/posts/${id}`)
    return response.data
  },

  getById: async (id: number): Promise<Post> => {
    const response = await api.get<Post>(`/api/v1/posts/${id}`)
    return response.data
  },

  update: async (id: string, data: Partial<Post>): Promise<Post> => {
    const response = await api.put<Post>(`/api/v1/posts/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/posts/${id}`)
  },

  rewrite: async (
    id: string,
    data: {
      persuasion_level?: number
      framework?: string
      target_length?: number
    }
  ): Promise<Post> => {
    const response = await api.post<Post>(`/api/v1/posts/${id}/rewrite`, data)
    return response.data
  },
}

// Profile API
export const profileAPI = {
  get: async (): Promise<DoctorProfile> => {
    const response = await api.get<DoctorProfile>('/api/v1/profiles/me')
    return response.data
  },

  update: async (data: Partial<DoctorProfile>): Promise<DoctorProfile> => {
    const response = await api.put<DoctorProfile>('/api/v1/profiles/me', data)
    return response.data
  },
}

// API Key 타입 정의
export interface APIKeyInfo {
  id: string
  provider: string
  name: string | null
  is_active: boolean
  last_checked_at: string | null
  last_status: string
  last_error: string | null
  created_at: string
  updated_at: string
  api_key_preview: string
}

export interface APIKeyStatus {
  configured: boolean
  is_active: boolean
  last_status: string
  last_checked_at: string | null
  last_error: string | null
  api_key_preview: string | null
}

export interface APIKeyTestResult {
  provider: string
  connected: boolean
  message: string
  model: string | null
}

// Admin API
export const adminAPI = {
  getUsers: async (
    is_approved?: boolean,
    is_active?: boolean,
    skip: number = 0,
    limit: number = 100
  ): Promise<User[]> => {
    const params: any = { skip, limit }
    if (is_approved !== undefined) params.is_approved = is_approved
    if (is_active !== undefined) params.is_active = is_active

    const response = await api.get<User[]>('/api/v1/admin/users', { params })
    return response.data
  },

  approveUser: async (data: UserApprovalRequest): Promise<User> => {
    const response = await api.post<User>('/api/v1/admin/users/approve', data)
    return response.data
  },

  setUserSubscription: async (data: UserSubscriptionRequest): Promise<User> => {
    const response = await api.post<User>('/api/v1/admin/users/subscription', data)
    return response.data
  },

  getUserDetail: async (userId: string): Promise<User> => {
    const response = await api.get<User>(`/api/v1/admin/users/${userId}`)
    return response.data
  },

  deleteUser: async (userId: string): Promise<void> => {
    await api.delete(`/api/v1/admin/users/${userId}`)
  },

  // API 키 관리
  getAPIKeys: async (): Promise<APIKeyInfo[]> => {
    const response = await api.get<APIKeyInfo[]>('/api/v1/admin/api-keys')
    return response.data
  },

  saveAPIKey: async (data: { provider: string; api_key: string; name?: string }): Promise<APIKeyInfo> => {
    const response = await api.post<APIKeyInfo>('/api/v1/admin/api-keys', data)
    return response.data
  },

  deleteAPIKey: async (provider: string): Promise<void> => {
    await api.delete(`/api/v1/admin/api-keys/${provider}`)
  },

  testAPIKey: async (provider: string): Promise<APIKeyTestResult> => {
    const response = await api.post<APIKeyTestResult>(`/api/v1/admin/api-keys/${provider}/test`)
    return response.data
  },

  getAPIKeysStatus: async (): Promise<Record<string, APIKeyStatus>> => {
    const response = await api.get<Record<string, APIKeyStatus>>('/api/v1/admin/api-keys/status')
    return response.data
  },
}

// Naver Blog API
export const naverAPI = {
  getAuthUrl: async (): Promise<{ auth_url: string; state: string }> => {
    const response = await api.get('/api/v1/naver/auth/url')
    return response.data
  },

  handleCallback: async (code: string, state: string): Promise<any> => {
    const response = await api.post('/api/v1/naver/auth/callback', { code, state })
    return response.data
  },

  getConnection: async (): Promise<any> => {
    const response = await api.get('/api/v1/naver/connection')
    return response.data
  },

  disconnect: async (): Promise<void> => {
    await api.delete('/api/v1/naver/connection')
  },

  getCategories: async (): Promise<any[]> => {
    const response = await api.get('/api/v1/naver/categories')
    return response.data
  },

  publishPost: async (data: {
    post_id: string
    category_no?: string
    open_type?: string
    tags?: string[]
  }): Promise<{ success: boolean; naver_post_url?: string; message: string }> => {
    const response = await api.post('/api/v1/naver/publish', data)
    return response.data
  },
}

// Analytics API
export const analyticsAPI = {
  getOverview: async () => {
    const response = await api.get('/api/v1/analytics/overview')
    return response.data
  },

  getPostAnalytics: async (postId: string) => {
    const response = await api.get(`/api/v1/analytics/post/${postId}`)
    return response.data
  },

  getTrends: async (days: number = 30) => {
    const response = await api.get(`/api/v1/analytics/trends?days=${days}`)
    return response.data
  },

  getComparison: async () => {
    const response = await api.get('/api/v1/analytics/comparison')
    return response.data
  },
}

// Tags API
export const tagsAPI = {
  getAll: async () => {
    const response = await api.get('/api/v1/tags')
    return response.data
  },

  create: async (data: { name: string; color: string }) => {
    const response = await api.post('/api/v1/tags', data)
    return response.data
  },

  update: async (tagId: string, data: { name?: string; color?: string }) => {
    const response = await api.put(`/api/v1/tags/${tagId}`, data)
    return response.data
  },

  delete: async (tagId: string) => {
    const response = await api.delete(`/api/v1/tags/${tagId}`)
    return response.data
  },

  addToPost: async (tagId: string, postId: string) => {
    const response = await api.post(`/api/v1/tags/${tagId}/posts/${postId}`)
    return response.data
  },

  removeFromPost: async (tagId: string, postId: string) => {
    const response = await api.delete(`/api/v1/tags/${tagId}/posts/${postId}`)
    return response.data
  },
}

// System API
export interface SystemInfo {
  name: string
  version: string
  status: string
  docs: string
}

export const systemAPI = {
  getInfo: async (): Promise<SystemInfo> => {
    const response = await api.get<SystemInfo>('/')
    return response.data
  },

  healthCheck: async (): Promise<{ status: string; ai: { connected: boolean; model: string | null } }> => {
    const response = await api.get('/health')
    return response.data
  },
}

// Extended Posts API
export const postsAPIExtended = {
  toggleFavorite: async (postId: string) => {
    const response = await api.post(`/api/v1/posts/${postId}/favorite`)
    return response.data
  },

  duplicate: async (postId: string) => {
    const response = await api.post(`/api/v1/posts/${postId}/duplicate`)
    return response.data
  },

  search: async (params: {
    q?: string
    status?: string
    is_favorited?: boolean
    tag_id?: string
    min_score?: number
    max_score?: number
    date_from?: string
    date_to?: string
    page?: number
    page_size?: number
  }) => {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        queryParams.append(key, String(value))
      }
    })
    const response = await api.get(`/api/v1/posts/search?${queryParams}`)
    return response.data
  },

  schedule: async (postId: string, scheduledAt: string) => {
    const response = await api.post(
      `/api/v1/posts/${postId}/schedule?scheduled_at=${encodeURIComponent(scheduledAt)}`
    )
    return response.data
  },

  getSuggestions: async (postId: string) => {
    const response = await api.get(`/api/v1/posts/${postId}/suggestions`)
    return response.data
  },

  getSeoAnalysis: async (postId: string) => {
    const response = await api.get(`/api/v1/posts/${postId}/seo-analysis`)
    return response.data
  },
}

// Images API (imgBB)
export interface ImageUploadResponse {
  success: boolean
  url: string
  delete_url?: string
  thumbnail?: string
}

export interface MultiImageUploadResponse {
  success: boolean
  images: ImageUploadResponse[]
  failed: number
}

export const imagesAPI = {
  // 파일 업로드
  upload: async (file: File): Promise<ImageUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post<ImageUploadResponse>('/api/v1/images/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return response.data
  },

  // Base64 이미지 업로드
  uploadBase64: async (base64Image: string, name?: string): Promise<ImageUploadResponse> => {
    const response = await api.post<ImageUploadResponse>('/api/v1/images/upload-base64', {
      image: base64Image,
      name: name || 'image',
    }, { timeout: 60000 })
    return response.data
  },

  // 여러 이미지 업로드
  uploadMultiple: async (files: File[]): Promise<MultiImageUploadResponse> => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    const response = await api.post<MultiImageUploadResponse>('/api/v1/images/upload-multiple', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    return response.data
  },

  // 상태 확인
  getStatus: async () => {
    const response = await api.get('/api/v1/images/status')
    return response.data
  },
}

// Top Post Analysis API (대량 분석)
export interface TopPostDashboard {
  total_posts: number
  total_keywords: number
  categories: {
    category: string
    category_name: string
    posts_count: number
    keywords_count: number
    sample_count: number
    confidence: number
    last_updated?: string
  }[]
  recent_jobs: {
    id: string
    category: string
    category_name: string
    target_count: number
    status: string
    progress: number
    posts_analyzed: number
    created_at: string
  }[]
}

export const topPostsAPI = {
  // 대시보드 통계
  getDashboard: async (): Promise<TopPostDashboard> => {
    const response = await api.get('/api/v1/top-posts/dashboard')
    return response.data
  },

  // 카테고리 목록 (통계 포함)
  getCategoriesWithStats: async () => {
    const response = await api.get('/api/v1/top-posts/categories-with-stats')
    return response.data
  },

  // 대량 분석 시작
  startBulkAnalysis: async (data: { category: string; target_count: number; keywords?: string[] }) => {
    const response = await api.post('/api/v1/top-posts/bulk-analyze', data)
    return response.data
  },

  // 분석 작업 목록
  getJobs: async (params?: { category?: string; status?: string; limit?: number }) => {
    const response = await api.get('/api/v1/top-posts/jobs', { params })
    return response.data
  },

  // 작업 상태 조회
  getJobStatus: async (jobId: string) => {
    const response = await api.get(`/api/v1/top-posts/jobs/${jobId}`)
    return response.data
  },

  // 작업 취소
  cancelJob: async (jobId: string) => {
    const response = await api.delete(`/api/v1/top-posts/jobs/${jobId}`)
    return response.data
  },

  // 연관검색어 수집
  collectKeywords: async (category: string, maxKeywords: number = 100) => {
    const response = await api.post('/api/v1/top-posts/collect-keywords', null, {
      params: { category, max_keywords: maxKeywords }
    })
    return response.data
  },

  // 카테고리별 키워드 조회
  getCategoryKeywords: async (category: string, limit: number = 100, onlyUnanalyzed: boolean = false) => {
    const response = await api.get(`/api/v1/top-posts/keywords/${category}`, {
      params: { limit, only_unanalyzed: onlyUnanalyzed }
    })
    return response.data
  },

  // 카테고리별 규칙 조회
  getCategoryRules: async (category: string) => {
    const response = await api.get(`/api/v1/top-posts/rules/${category}`)
    return response.data
  },

  // 단일 키워드 분석
  analyzeKeyword: async (keyword: string, topN: number = 3) => {
    const response = await api.post('/api/v1/top-posts/analyze', { keyword, top_n: topN })
    return response.data
  },

  // 글쓰기 가이드 조회
  getWritingGuide: async (category?: string, keyword?: string) => {
    const params: any = {}
    if (category) params.category = category
    if (keyword) params.keyword = keyword
    const response = await api.get('/api/v1/top-posts/writing-guide', { params })
    return response.data
  },

  // 전체 통계
  getStats: async () => {
    const response = await api.get('/api/v1/top-posts/stats')
    return response.data
  },

  // 분석된 글 목록 조회
  getAnalyzedPosts: async (params?: {
    category?: string
    keyword?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/api/v1/top-posts/analyzed-posts', { params })
    return response.data
  },

  // 카테고리별 공통점 요약
  getPatternsSummary: async (category: string) => {
    const response = await api.get(`/api/v1/top-posts/patterns-summary/${category}`)
    return response.data
  }
}

// ==================== Subscription API ====================

export interface Plan {
  id: string
  name: string
  description: string | null
  price_monthly: number
  price_yearly: number
  posts_per_month: number
  analysis_per_month: number
  keywords_per_month: number
  has_api_access: boolean
  has_priority_support: boolean
  has_advanced_analytics: boolean
  has_team_features: boolean
  extra_post_price: number
  extra_analysis_price: number
}

export interface Subscription {
  id: string
  plan_id: string
  status: 'active' | 'cancelled' | 'expired' | 'past_due' | 'trialing'
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  trial_end: string | null
  plan?: Plan
}

export interface UsageSummary {
  posts_used: number
  posts_limit: number
  analysis_used: number
  analysis_limit: number
  keywords_used: number
  keywords_limit: number
  extra_posts: number
  extra_analysis: number
  extra_cost: number
}

export interface UserCredit {
  post_credits: number
  analysis_credits: number
}

export const subscriptionAPI = {
  // 플랜 목록 조회
  getPlans: async (): Promise<Plan[]> => {
    const response = await api.get('/api/v1/subscriptions/plans')
    return response.data
  },

  // 현재 구독 조회
  getCurrentSubscription: async (): Promise<Subscription | null> => {
    const response = await api.get('/api/v1/subscriptions/current')
    return response.data
  },

  // 사용량 조회
  getUsage: async (): Promise<UsageSummary> => {
    const response = await api.get('/api/v1/subscriptions/usage')
    return response.data
  },

  // 크레딧 잔액 조회
  getCredits: async (): Promise<UserCredit> => {
    const response = await api.get('/api/v1/subscriptions/credits')
    return response.data
  },

  // 구독 시작
  subscribe: async (planId: string, paymentMethod?: string): Promise<Subscription> => {
    const response = await api.post('/api/v1/subscriptions/subscribe', {
      plan_id: planId,
      payment_method: paymentMethod
    })
    return response.data
  },

  // 구독 취소
  cancel: async (): Promise<{ message: string; period_end: string }> => {
    const response = await api.post('/api/v1/subscriptions/cancel')
    return response.data
  },

  // 플랜 변경
  changePlan: async (newPlanId: string): Promise<Subscription> => {
    const response = await api.post('/api/v1/subscriptions/change-plan', {
      new_plan_id: newPlanId
    })
    return response.data
  },

  // 구독 내역
  getHistory: async (limit: number = 10, offset: number = 0) => {
    const response = await api.get('/api/v1/subscriptions/history', {
      params: { limit, offset }
    })
    return response.data
  },

  // 사용량 로그
  getUsageLogs: async (usageType?: string, limit: number = 50, offset: number = 0) => {
    const response = await api.get('/api/v1/subscriptions/usage-logs', {
      params: { usage_type: usageType, limit, offset }
    })
    return response.data
  }
}

// ==================== Payment API ====================

export interface PaymentConfig {
  client_key: string
  success_url: string
  fail_url: string
}

export interface PaymentIntent {
  payment_id: string
  order_id: string
  amount: number
  order_name: string
  client_key: string
}

export interface Payment {
  id: string
  amount: number
  status: 'pending' | 'completed' | 'failed' | 'cancelled' | 'refunded'
  payment_method: string | null
  payment_method_detail: string | null
  description: string | null
  receipt_url: string | null
  paid_at: string | null
  created_at: string
}

export const paymentAPI = {
  // 결제 설정 조회
  getConfig: async (): Promise<PaymentConfig> => {
    const response = await api.get('/api/v1/payments/config')
    return response.data
  },

  // 결제 의도 생성
  createIntent: async (data: {
    amount: number
    order_name: string
    subscription_id?: string
    metadata?: Record<string, unknown>
  }): Promise<PaymentIntent> => {
    const response = await api.post('/api/v1/payments/intent', data)
    return response.data
  },

  // 결제 승인
  confirm: async (data: {
    payment_key: string
    order_id: string
    amount: number
  }): Promise<Payment> => {
    const response = await api.post('/api/v1/payments/confirm', data)
    return response.data
  },

  // 결제 취소
  cancel: async (paymentId: string, cancelReason: string, refundAmount?: number): Promise<Payment> => {
    const response = await api.post(`/api/v1/payments/${paymentId}/cancel`, {
      cancel_reason: cancelReason,
      refund_amount: refundAmount
    })
    return response.data
  },

  // 결제 내역 조회
  getHistory: async (status?: string, limit: number = 20, offset: number = 0): Promise<Payment[]> => {
    const response = await api.get('/api/v1/payments/history', {
      params: { status_filter: status, limit, offset }
    })
    return response.data
  },

  // 결제 상세 조회
  getPayment: async (paymentId: string): Promise<Payment> => {
    const response = await api.get(`/api/v1/payments/${paymentId}`)
    return response.data
  },

  // 크레딧 구매 정보 생성
  purchaseCredits: async (creditType: string, amount: number) => {
    const response = await api.post('/api/v1/payments/credits/purchase', {
      credit_type: creditType,
      amount
    })
    return response.data
  },

  // 크레딧 구매 결제 승인
  confirmCreditPurchase: async (data: {
    payment_key: string
    order_id: string
    amount: number
  }) => {
    const response = await api.post('/api/v1/payments/credits/confirm', data)
    return response.data
  }
}

// ==================== Schedule API ====================

export type ScheduleType = 'one_time' | 'recurring'
export type RecurrencePattern = 'daily' | 'weekly' | 'monthly'
export type ScheduleStatus = 'active' | 'paused' | 'completed' | 'cancelled'

export interface Schedule {
  id: string
  name: string | null
  schedule_type: ScheduleType
  scheduled_time: string
  scheduled_date: string | null
  post_id: string | null
  post_title: string | null
  recurrence_pattern: RecurrencePattern | null
  days_of_week: number[] | null
  day_of_month: number | null
  category_no: string | null
  open_type: string
  auto_hashtags: boolean
  status: ScheduleStatus
  last_executed_at: string | null
  next_execution_at: string | null
  execution_count: number
  max_executions: number | null
  created_at: string
}

export interface ScheduleExecution {
  id: string
  schedule_id: string
  post_id: string | null
  status: 'pending' | 'success' | 'failed'
  executed_at: string
  completed_at: string | null
  naver_post_url: string | null
  error_message: string | null
}

export interface OptimalTime {
  day_of_week: number
  day_name: string
  recommended_hour: number
  recommended_minute: number
  engagement_score: number
  confidence_score: number
}

export interface UpcomingPost {
  schedule_id: string
  schedule_name: string | null
  next_execution_at: string
  post_id: string | null
  post_title: string | null
  schedule_type: string
  recurrence_pattern: string | null
}

export const scheduleAPI = {
  // 예약 생성
  create: async (data: {
    name?: string
    schedule_type: ScheduleType
    scheduled_time: string
    scheduled_date?: string
    post_id?: string
    recurrence_pattern?: RecurrencePattern
    days_of_week?: number[]
    day_of_month?: number
    category_no?: string
    open_type?: string
    auto_hashtags?: boolean
    max_executions?: number
  }): Promise<Schedule> => {
    const response = await api.post('/api/v1/schedules/', data)
    return response.data
  },

  // 예약 목록 조회
  getList: async (params?: {
    status?: ScheduleStatus
    limit?: number
    offset?: number
  }): Promise<Schedule[]> => {
    const response = await api.get('/api/v1/schedules/', { params })
    return response.data
  },

  // 예약 상세 조회
  get: async (scheduleId: string): Promise<Schedule> => {
    const response = await api.get(`/api/v1/schedules/${scheduleId}`)
    return response.data
  },

  // 예약 수정
  update: async (scheduleId: string, data: Partial<Schedule>): Promise<Schedule> => {
    const response = await api.put(`/api/v1/schedules/${scheduleId}`, data)
    return response.data
  },

  // 예약 삭제
  delete: async (scheduleId: string): Promise<void> => {
    await api.delete(`/api/v1/schedules/${scheduleId}`)
  },

  // 예약 토글 (활성화/비활성화)
  toggle: async (scheduleId: string): Promise<Schedule> => {
    const response = await api.post(`/api/v1/schedules/${scheduleId}/toggle`)
    return response.data
  },

  // 실행 이력 조회
  getExecutions: async (scheduleId: string, params?: {
    limit?: number
    offset?: number
  }): Promise<ScheduleExecution[]> => {
    const response = await api.get(`/api/v1/schedules/${scheduleId}/executions`, { params })
    return response.data
  },

  // 예정된 발행 목록
  getUpcoming: async (params?: {
    days?: number
    limit?: number
  }): Promise<UpcomingPost[]> => {
    const response = await api.get('/api/v1/schedules/upcoming', { params })
    return response.data
  },

  // 최적 시간 추천
  getOptimalTimes: async (category?: string): Promise<OptimalTime[]> => {
    const response = await api.get('/api/v1/schedules/optimal-times', {
      params: { category }
    })
    return response.data
  },
}

// ==================== Report API ====================

export type ReportType = 'monthly' | 'weekly' | 'custom'
export type ReportFormat = 'pdf' | 'excel' | 'html'
export type ReportStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface Report {
  id: string
  report_type: ReportType | string
  title: string
  period_start: string
  period_end: string
  status: ReportStatus | string
  generated_at?: string | null
  pdf_url?: string | null
  excel_url?: string | null
  email_sent?: boolean
  created_at: string
  report_data?: ReportData
  // 직접 접근 가능한 요약 필드들
  total_posts?: number
  avg_persuasion_score?: number | null
  total_views?: number | null
  top_keywords?: string[] | null
  recommendations?: string[] | null
  file_path?: string | null
}

export interface ReportData {
  summary: {
    total_posts: number
    published_posts: number
    draft_posts: number
    publish_rate: number
    avg_persuasion_score: number
    total_views: number
    total_inquiries: number
    avg_views_per_post: number
  }
  persuasion_trend: {
    date: string
    score: number
    count: number
  }[]
  keyword_analysis: {
    total_unique_keywords: number
    top_keywords: { keyword: string; count: number }[]
  }
  top_posts: {
    id: string
    title: string
    persuasion_score: number
    status: string
    views: number
    created_at: string
  }[]
  recommendations: {
    type: string
    priority: string
    title: string
    description: string
    action: string
  }[]
}

export interface ReportSubscriptionSettings {
  auto_monthly: boolean
  auto_weekly: boolean
  email_enabled: boolean
  email_recipients: string[] | null
  preferred_format: ReportFormat
}

export const reportAPI = {
  // 리포트 생성
  generate: async (data: {
    report_type: ReportType
    period_start: string
    period_end: string
    title?: string
  }): Promise<Report> => {
    const response = await api.post('/api/v1/reports/generate', data)
    return response.data
  },

  // 월간 리포트 생성
  generateMonthly: async (year: number, month: number): Promise<Report> => {
    const response = await api.post('/api/v1/reports/generate/monthly', { year, month })
    return response.data
  },

  // 주간 리포트 생성
  generateWeekly: async (weekStart?: string): Promise<Report> => {
    const response = await api.post('/api/v1/reports/generate/weekly', null, {
      params: { week_start: weekStart }
    })
    return response.data
  },

  // 리포트 목록 조회
  getList: async (params?: {
    report_type?: ReportType
    limit?: number
    offset?: number
  }): Promise<Report[]> => {
    const response = await api.get('/api/v1/reports/', { params })
    return response.data
  },

  // 리포트 상세 조회
  get: async (reportId: string): Promise<Report> => {
    const response = await api.get(`/api/v1/reports/${reportId}`)
    return response.data
  },

  // 리포트 삭제
  delete: async (reportId: string): Promise<void> => {
    await api.delete(`/api/v1/reports/${reportId}`)
  },

  // Excel 다운로드
  downloadExcel: async (reportId: string): Promise<Blob> => {
    const response = await api.get(`/api/v1/reports/${reportId}/download/excel`, {
      responseType: 'blob'
    })
    return response.data
  },

  // 구독 설정 조회
  getSubscription: async (): Promise<ReportSubscriptionSettings> => {
    const response = await api.get('/api/v1/reports/subscription')
    return response.data
  },

  // 구독 설정 업데이트
  updateSubscription: async (data: Partial<ReportSubscriptionSettings>): Promise<ReportSubscriptionSettings> => {
    const response = await api.put('/api/v1/reports/subscription', data)
    return response.data
  },
}

// ==================== SNS API ====================

export type SNSPlatform = 'instagram' | 'facebook' | 'threads' | 'twitter'
export type SNSPostStatus = 'draft' | 'scheduled' | 'publishing' | 'published' | 'failed'
export type SNSContentType = 'post' | 'reel' | 'story' | 'short'

export interface SNSConnection {
  id: string
  platform: SNSPlatform
  platform_username: string | null
  profile_image_url: string | null
  page_name: string | null
  is_active: boolean
  connection_status: string
  created_at: string
}

export interface SNSPost {
  id: string
  platform: SNSPlatform
  content_type: SNSContentType
  caption: string | null
  hashtags: string[] | null
  media_urls: string[] | null
  script: string | null
  script_duration: number | null
  status: SNSPostStatus
  scheduled_at: string | null
  published_at: string | null
  platform_post_url: string | null
  error_message: string | null
  original_post_id: string | null
  created_at: string
}

export interface SNSConvertResult {
  caption: string
  hashtags: string[]
  original_post_id: string
  original_title: string
  platform: string
  content_type: string
}

export interface ShortformScript {
  script: string
  duration: number
  sections: {
    time: string
    type: string
    text: string
  }[]
  hooks: string[]
  cta: string[]
  original_post_id: string
}

export interface HashtagRecommendation {
  hashtag: string
  category: string
  popularity_score: number
  engagement_rate: number
  priority: number
}

export const snsAPI = {
  // OAuth 인증 URL 생성
  getAuthUrl: async (platform: SNSPlatform, redirectUri: string): Promise<{ auth_url: string; state: string }> => {
    const response = await api.get(`/api/v1/sns/${platform}/auth/url`, {
      params: { redirect_uri: redirectUri }
    })
    return response.data
  },

  // OAuth 콜백 처리
  authCallback: async (platform: SNSPlatform, data: {
    code: string
    state: string
    redirect_uri: string
  }): Promise<SNSConnection> => {
    const response = await api.post(`/api/v1/sns/${platform}/auth/callback`, data)
    return response.data
  },

  // 연동 목록 조회
  getConnections: async (): Promise<SNSConnection[]> => {
    const response = await api.get('/api/v1/sns/connections')
    return response.data
  },

  // 연동 해제
  disconnect: async (platform: SNSPlatform): Promise<void> => {
    await api.delete(`/api/v1/sns/connections/${platform}`)
  },

  // 블로그 → SNS 변환
  convert: async (data: {
    post_id: string
    platform: SNSPlatform
    content_type?: SNSContentType
  }): Promise<SNSConvertResult> => {
    const response = await api.post('/api/v1/sns/convert', data)
    return response.data
  },

  // 숏폼 스크립트 생성
  generateScript: async (data: {
    post_id: string
    duration?: number
  }): Promise<ShortformScript> => {
    const response = await api.post('/api/v1/sns/generate-script', data)
    return response.data
  },

  // 해시태그 추천
  getHashtagRecommendations: async (category: string, platform?: SNSPlatform): Promise<HashtagRecommendation[]> => {
    const response = await api.get('/api/v1/sns/hashtag-recommendations', {
      params: { category, platform }
    })
    return response.data
  },

  // SNS 포스트 생성
  createPost: async (data: {
    platform: SNSPlatform
    caption: string
    content_type?: SNSContentType
    hashtags?: string[]
    media_urls?: string[]
    original_post_id?: string
    script?: string
    script_duration?: number
  }): Promise<SNSPost> => {
    const response = await api.post('/api/v1/sns/posts', data)
    return response.data
  },

  // SNS 포스트 목록 조회
  getPosts: async (params?: {
    platform?: SNSPlatform
    status?: SNSPostStatus
    limit?: number
    offset?: number
  }): Promise<SNSPost[]> => {
    const response = await api.get('/api/v1/sns/posts', { params })
    return response.data
  },

  // SNS 포스트 상세 조회
  getPost: async (snsPostId: string): Promise<SNSPost> => {
    const response = await api.get(`/api/v1/sns/posts/${snsPostId}`)
    return response.data
  },

  // SNS 포스트 수정
  updatePost: async (snsPostId: string, data: Partial<SNSPost>): Promise<SNSPost> => {
    const response = await api.put(`/api/v1/sns/posts/${snsPostId}`, data)
    return response.data
  },

  // SNS 포스트 삭제
  deletePost: async (snsPostId: string): Promise<void> => {
    await api.delete(`/api/v1/sns/posts/${snsPostId}`)
  },

  // SNS 포스트 발행
  publishPost: async (snsPostId: string): Promise<{ success: boolean; platform_post_url?: string; error?: string }> => {
    const response = await api.post(`/api/v1/sns/posts/${snsPostId}/publish`)
    return response.data
  },
}

// ==================== ROI API ====================

export type EventType = 'view' | 'inquiry' | 'visit' | 'reservation'

export interface ConversionEvent {
  id: string
  event_type: EventType
  event_date: string
  keyword: string | null
  source: string | null
  channel: string | null
  revenue: number | null
  cost: number | null
  created_at: string
}

export interface ROIDashboard {
  period: { start_date?: string; end_date?: string; start?: string; end?: string }
  stats?: {
    total_views: number
    total_inquiries: number
    total_visits: number
    total_reservations: number
    total_revenue: number
    total_cost: number
  }
  summary?: {
    total_views: number
    total_inquiries: number
    total_visits: number
    total_reservations: number
    total_revenue: number
    conversion_rate_inquiry: number
    conversion_rate_visit: number
    conversion_rate_reservation: number
  }
  channel_breakdown: Record<string, { views: number; inquiries: number; visits: number; revenue: number }>
  source_breakdown?: { source: string; count: number; revenue: number }[]
  daily_trend?: { date: string; views: number; inquiries: number; visits: number; reservations?: number }[]
  trends?: Array<{ date: string; views: number; inquiries: number; visits: number; revenue: number }>
  funnel: Array<{ stage?: string; name?: string; count: number; rate: number }>
  top_keywords: { keyword: string; views?: number; inquiries?: number; revenue: number; roi?: number; total_events?: number; conversions?: number }[]
  roi_percentage?: number
}

export interface KeywordROI {
  keyword: string
  views: number
  inquiries: number
  visits: number
  reservations: number
  revenue: number
  cost: number
  roi_percentage: number
  conversion_rate: number
}

export interface MarketingCost {
  id: string
  date: string
  channel: string
  cost: number
  description: string | null
  cost_type: string | null
  campaign_name: string | null
}

export const roiAPI = {
  // 전환 이벤트 기록
  createEvent: async (data: {
    event_type: EventType
    event_date: string
    keyword?: string
    post_id?: string
    source?: string
    channel?: string
    revenue?: number
    cost?: number
    customer_id?: string
    notes?: string
  }) => {
    const response = await api.post('/api/v1/roi/events', data)
    return response.data
  },

  // 대량 이벤트 기록
  createBulkEvents: async (events: any[]) => {
    const response = await api.post('/api/v1/roi/events/bulk', { events })
    return response.data
  },

  // 이벤트 조회
  getEvents: async (params?: {
    start_date?: string
    end_date?: string
    event_type?: EventType
    source?: string
    channel?: string
    keyword?: string
    limit?: number
    offset?: number
  }): Promise<ConversionEvent[]> => {
    const response = await api.get('/api/v1/roi/events', { params })
    return response.data
  },

  // 대시보드
  getDashboard: async (params?: { start_date?: string; end_date?: string }): Promise<ROIDashboard> => {
    const response = await api.get('/api/v1/roi/dashboard', { params })
    return response.data
  },

  // 키워드별 ROI
  getKeywordROI: async (params?: { start_date?: string; end_date?: string; limit?: number }): Promise<KeywordROI[]> => {
    const response = await api.get('/api/v1/roi/keywords', { params })
    return response.data
  },

  // 전환 퍼널
  getFunnel: async (params?: { start_date?: string; end_date?: string }) => {
    const response = await api.get('/api/v1/roi/funnel', { params })
    return response.data
  },

  // 트렌드
  getTrends: async (months: number = 6) => {
    const response = await api.get('/api/v1/roi/trends', { params: { months } })
    return response.data
  },

  // 마케팅 비용 추가
  addCost: async (data: {
    date: string
    channel: string
    cost: number
    description?: string
    cost_type?: string
    campaign_name?: string
  }) => {
    const response = await api.post('/api/v1/roi/costs', data)
    return response.data
  },

  // 마케팅 비용 조회
  getCosts: async (params?: { start_date?: string; end_date?: string }): Promise<MarketingCost[]> => {
    const response = await api.get('/api/v1/roi/costs', { params })
    return response.data
  },

  // 월별 요약 계산
  calculateMonthly: async (year: number, month: number) => {
    const response = await api.post('/api/v1/roi/calculate', null, { params: { year, month } })
    return response.data
  },
}

// ==================== Place API ====================

export type OptimizationStatus = 'pass' | 'fail' | 'warning'

export interface NaverPlace {
  id: string
  place_id: string
  place_name: string
  place_url: string | null
  category: string | null
  sub_category: string | null
  address: string | null
  road_address: string | null
  phone: string | null
  business_hours: Record<string, string> | null
  description: string | null
  tags: string[]
  images: string[]
  review_count: number
  visitor_review_count: number
  blog_review_count: number
  avg_rating: number
  save_count: number
  optimization_score: number
  optimization_details: Record<string, any>
  is_connected: boolean
  last_synced_at: string | null
  created_at: string
}

export interface OptimizationCheck {
  type: string
  name: string
  status: OptimizationStatus
  score: number
  message: string | null
  suggestion: string | null
  priority: number
}

export interface PlaceDescription {
  id: string
  description: string
  tone: string
  keywords_used: string[]
}

export const placeAPI = {
  // 플레이스 연동
  connect: async (data: {
    place_id: string
    place_name: string
    place_url?: string
    category?: string
    sub_category?: string
    address?: string
    road_address?: string
    phone?: string
    business_hours?: Record<string, string>
    description?: string
    tags?: string[]
  }) => {
    const response = await api.post('/api/v1/place/connect', data)
    return response.data
  },

  // 플레이스 목록
  getList: async (): Promise<NaverPlace[]> => {
    const response = await api.get('/api/v1/place/')
    return response.data
  },

  // 플레이스 정보
  getInfo: async (place_db_id?: string): Promise<NaverPlace> => {
    const response = await api.get('/api/v1/place/info', { params: { place_db_id } })
    return response.data
  },

  // 플레이스 수정
  update: async (place_db_id: string, data: Partial<NaverPlace>) => {
    const response = await api.put(`/api/v1/place/info/${place_db_id}`, data)
    return response.data
  },

  // 최적화 점수
  getOptimization: async (place_db_id: string): Promise<{ optimization_score: number; checks: OptimizationCheck[] }> => {
    const response = await api.get('/api/v1/place/optimization', { params: { place_db_id } })
    return response.data
  },

  // 최적화 재계산
  refreshOptimization: async (place_db_id: string) => {
    const response = await api.post('/api/v1/place/optimization/refresh', null, { params: { place_db_id } })
    return response.data
  },

  // AI 소개글 생성
  generateDescription: async (place_db_id: string, data?: { tone?: string; keywords?: string[]; specialty_focus?: string }): Promise<PlaceDescription> => {
    const response = await api.post('/api/v1/place/generate-description', data || {}, { params: { place_db_id } })
    return response.data
  },

  // 태그 추천
  getTagRecommendations: async (place_db_id: string) => {
    const response = await api.get('/api/v1/place/tag-recommendations', { params: { place_db_id } })
    return response.data
  },
}

// ==================== Reviews API ====================

export type Sentiment = 'positive' | 'negative' | 'neutral'

export interface PlaceReview {
  id: string
  review_id: string
  author_name: string | null
  rating: number | null
  content: string | null
  images: string[]
  sentiment: Sentiment | null
  sentiment_score: number
  keywords: string[]
  is_replied: boolean
  reply_content: string | null
  replied_at: string | null
  is_urgent: boolean
  needs_attention: boolean
  review_type: string
  visit_date: string | null
  written_at: string | null
  created_at: string
}

export interface ReviewAnalytics {
  period: { start_date: string; end_date: string }
  summary: {
    total_reviews: number
    avg_rating: number
    replied_count: number
    reply_rate: number
  }
  sentiment_breakdown: { positive: number; negative: number; neutral: number }
  rating_breakdown: Record<number, number>
  daily_trend: { date: string; count: number; avg_rating: number }[]
}

export interface ReviewTemplate {
  id: string
  name: string
  sentiment_type: Sentiment | null
  category: string | null
  template_content: string
  variables: string[]
  usage_count: number
  is_default: boolean
}

export const reviewsAPI = {
  // 리뷰 목록
  getList: async (place_db_id: string, params?: {
    sentiment?: Sentiment
    is_replied?: boolean
    is_urgent?: boolean
    min_rating?: number
    max_rating?: number
    start_date?: string
    end_date?: string
    search?: string
    limit?: number
    offset?: number
  }): Promise<PlaceReview[]> => {
    const response = await api.get('/api/v1/reviews/', { params: { place_db_id, ...params } })
    return response.data
  },

  // 리뷰 상세
  get: async (review_db_id: string): Promise<PlaceReview> => {
    const response = await api.get(`/api/v1/reviews/${review_db_id}`)
    return response.data
  },

  // 리뷰 답변
  reply: async (review_db_id: string, reply_content: string) => {
    const response = await api.post(`/api/v1/reviews/${review_db_id}/reply`, { reply_content })
    return response.data
  },

  // AI 답변 생성
  generateReply: async (review_db_id: string, tone?: string) => {
    const response = await api.post(`/api/v1/reviews/${review_db_id}/generate-reply`, { tone })
    return response.data
  },

  // 리뷰 분석
  getAnalytics: async (place_db_id: string, params?: { start_date?: string; end_date?: string }): Promise<ReviewAnalytics> => {
    const response = await api.get('/api/v1/reviews/analytics/summary', { params: { place_db_id, ...params } })
    return response.data
  },

  // 알림 설정 조회
  getAlertSettings: async (place_db_id?: string) => {
    const response = await api.get('/api/v1/reviews/alerts/settings', { params: { place_db_id } })
    return response.data
  },

  // 알림 설정 수정
  updateAlertSettings: async (data: {
    place_db_id: string
    alert_type: string
    is_active?: boolean
    channels?: string[]
    keywords?: string[]
    rating_threshold?: number
  }) => {
    const response = await api.put('/api/v1/reviews/alerts/settings', data)
    return response.data
  },

  // 템플릿 조회
  getTemplates: async (sentiment_type?: Sentiment): Promise<ReviewTemplate[]> => {
    const response = await api.get('/api/v1/reviews/templates/list', { params: { sentiment_type } })
    return response.data
  },

  // 템플릿 생성
  createTemplate: async (data: {
    name: string
    template_content: string
    sentiment_type?: Sentiment
    category?: string
    variables?: string[]
  }) => {
    const response = await api.post('/api/v1/reviews/templates', data)
    return response.data
  },
}

// ==================== Competitors API ====================

export interface Competitor {
  id: string
  place_id: string
  place_name: string
  place_url: string | null
  category: string | null
  address: string | null
  distance_km: number | null
  review_count: number
  avg_rating: number
  visitor_review_count: number
  blog_review_count: number
  is_active: boolean
  priority: number
  is_auto_detected: boolean
  similarity_score: number
  strengths: string[]
  weaknesses: string[]
  notes: string | null
  last_synced_at: string | null
  created_at: string
}

export interface CompetitorComparison {
  my_stats: Record<string, any>
  competitor_stats: Record<string, any>[]
  ranking: { total_compared: number; rating_rank: number; review_rank: number }
  comparison: { rating_vs_avg: number; reviews_vs_avg: number }
  analysis_date: string
}

export interface CompetitorAlert {
  id: string
  competitor_id: string
  alert_type: string
  title: string
  message: string
  data: Record<string, any>
  severity: string
  is_read: boolean
  created_at: string
}

export const competitorsAPI = {
  // 경쟁사 목록
  getList: async (is_active?: boolean): Promise<Competitor[]> => {
    const response = await api.get('/api/v1/competitors/', { params: { is_active } })
    return response.data
  },

  // 경쟁사 추가
  add: async (data: {
    place_id: string
    place_name: string
    place_url?: string
    category?: string
    address?: string
    phone?: string
    distance_km?: number
    priority?: number
    notes?: string
  }) => {
    const response = await api.post('/api/v1/competitors/', data)
    return response.data
  },

  // 경쟁사 제거
  remove: async (competitor_id: string) => {
    const response = await api.delete(`/api/v1/competitors/${competitor_id}`)
    return response.data
  },

  // 경쟁사 상세
  get: async (competitor_id: string): Promise<Competitor> => {
    const response = await api.get(`/api/v1/competitors/${competitor_id}`)
    return response.data
  },

  // 경쟁사 자동 탐지
  autoDetect: async (place_db_id: string, radius_km?: number, limit?: number) => {
    const response = await api.post('/api/v1/competitors/auto-detect', null, {
      params: { place_db_id, radius_km, limit }
    })
    return response.data
  },

  // 비교 분석
  getComparison: async (my_place_db_id: string, competitor_ids?: string[]): Promise<CompetitorComparison> => {
    const response = await api.get('/api/v1/competitors/comparison/summary', {
      params: { my_place_db_id, competitor_ids: competitor_ids?.join(',') }
    })
    return response.data
  },

  // 경쟁사 리뷰 분석
  getReviews: async (competitor_id: string) => {
    const response = await api.get(`/api/v1/competitors/${competitor_id}/reviews`)
    return response.data
  },

  // 주간 리포트
  getWeeklyReport: async (week_start?: string) => {
    const response = await api.get('/api/v1/competitors/report/weekly', { params: { week_start } })
    return response.data
  },

  // 주간 리포트 생성
  generateWeeklyReport: async (place_db_id: string) => {
    const response = await api.post('/api/v1/competitors/report/generate', null, { params: { place_db_id } })
    return response.data
  },

  // 알림 조회
  getAlerts: async (unread_only?: boolean, limit?: number): Promise<CompetitorAlert[]> => {
    const response = await api.get('/api/v1/competitors/alerts/list', { params: { unread_only, limit } })
    return response.data
  },

  // 알림 읽음 처리
  markAlertRead: async (alert_id: string) => {
    const response = await api.post(`/api/v1/competitors/alerts/${alert_id}/read`)
    return response.data
  },
}

// ==================== Rankings API ====================

export interface PlaceKeyword {
  id: string
  keyword: string
  category: string | null
  priority: number
  current_rank: number | null
  rank_change: number
  trend: 'up' | 'down' | 'stable' | 'new'
  best_rank: number | null
  worst_rank: number | null
  estimated_search_volume: number
  competition_level: string | null
  is_active: boolean
  check_frequency: string
  last_checked_at: string | null
  created_at: string
}

export interface RankingHistory {
  id: string
  rank: number | null
  total_results: number
  top_competitors: any[]
  checked_at: string
}

export interface RankingSummary {
  summary_date: string
  total_keywords: number
  keywords_in_top10: number
  keywords_in_top30: number
  keywords_out_of_rank: number
  avg_rank: number | null
  best_rank: number | null
  worst_rank: number | null
  improved_count: number
  declined_count: number
  stable_count: number
  keywords: { keyword: string; rank: number | null; change: number | null; trend: string | null }[]
}

export interface RankingAlert {
  id: string
  keyword_id: string
  alert_type: string
  previous_rank: number | null
  current_rank: number | null
  change: number
  message: string
  is_read: boolean
  created_at: string
}

export const rankingsAPI = {
  // 키워드 목록
  getKeywords: async (place_db_id?: string, is_active?: boolean): Promise<PlaceKeyword[]> => {
    const response = await api.get('/api/v1/rankings/keywords', { params: { place_db_id, is_active } })
    return response.data
  },

  // 키워드 추가
  addKeyword: async (data: { place_db_id: string; keyword: string; category?: string; priority?: number }) => {
    const response = await api.post('/api/v1/rankings/keywords', data)
    return response.data
  },

  // 키워드 제거
  removeKeyword: async (keyword_id: string) => {
    const response = await api.delete(`/api/v1/rankings/keywords/${keyword_id}`)
    return response.data
  },

  // 순위 히스토리
  getHistory: async (keyword_id: string, days?: number): Promise<RankingHistory[]> => {
    const response = await api.get(`/api/v1/rankings/history/${keyword_id}`, { params: { days } })
    return response.data
  },

  // 현재 순위
  getCurrent: async (place_db_id?: string) => {
    const response = await api.get('/api/v1/rankings/current', { params: { place_db_id } })
    return response.data
  },

  // 순위 체크
  check: async (data: { keyword_id: string; rank?: number; total_results?: number; top_competitors?: any[] }) => {
    const response = await api.post('/api/v1/rankings/check', data)
    return response.data
  },

  // 키워드 추천
  getRecommendations: async (place_db_id: string, limit?: number) => {
    const response = await api.get('/api/v1/rankings/recommendations', { params: { place_db_id, limit } })
    return response.data
  },

  // 요약
  getSummary: async (place_db_id: string): Promise<RankingSummary> => {
    const response = await api.get('/api/v1/rankings/summary', { params: { place_db_id } })
    return response.data
  },

  // 알림 조회
  getAlerts: async (unread_only?: boolean, limit?: number): Promise<RankingAlert[]> => {
    const response = await api.get('/api/v1/rankings/alerts', { params: { unread_only, limit } })
    return response.data
  },
}

// ==================== Campaigns API ====================

export type CampaignStatus = 'draft' | 'active' | 'paused' | 'ended'
export type RewardType = 'discount' | 'gift' | 'point' | 'cash' | 'coupon'

export interface ReviewCampaign {
  id: string
  name: string
  description: string | null
  terms: string | null
  reward_type: RewardType
  reward_description: string
  reward_value: number | null
  start_date: string
  end_date: string
  status: CampaignStatus
  target_count: number
  current_count: number
  verified_count: number
  min_rating: number
  min_content_length: number
  require_photo: boolean
  short_url: string | null
  qr_code_url: string | null
  landing_page_url: string | null
  total_budget: number
  spent_budget: number
  total_views: number
  total_clicks: number
  created_at: string
  updated_at: string
}

export interface CampaignParticipation {
  id: string
  participation_code: string
  customer_name: string | null
  source: string
  review_url: string | null
  review_rating: number | null
  is_verified: boolean
  verified_at: string | null
  reward_given: boolean
  reward_given_at: string | null
  status: string
  participated_at: string
}

export interface CampaignStats {
  campaign: { id: string; name: string; status: string; start_date: string; end_date: string }
  participation: { total: number; verified: number; rewarded: number; pending: number; verification_rate: number }
  progress: { target_count: number; current_count: number; progress_percentage: number }
  budget: { total: number; spent: number; remaining: number; usage_percentage: number }
  reviews: { avg_rating: number }
  source_breakdown: Record<string, number>
  traffic: { views: number; clicks: number; conversion_rate: number }
}

export const campaignsAPI = {
  // 캠페인 목록
  getList: async (status?: CampaignStatus, place_db_id?: string): Promise<ReviewCampaign[]> => {
    const response = await api.get('/api/v1/campaigns/', { params: { status, place_db_id } })
    return response.data
  },

  // 캠페인 생성
  create: async (data: {
    name: string
    reward_type: RewardType
    reward_description: string
    start_date: string
    end_date: string
    place_db_id?: string
    description?: string
    terms?: string
    reward_value?: number
    target_count?: number
    min_rating?: number
    min_content_length?: number
    require_photo?: boolean
    total_budget?: number
  }) => {
    const response = await api.post('/api/v1/campaigns/', data)
    return response.data
  },

  // 캠페인 상세
  get: async (campaign_id: string): Promise<ReviewCampaign> => {
    const response = await api.get(`/api/v1/campaigns/${campaign_id}`)
    return response.data
  },

  // 캠페인 수정
  update: async (campaign_id: string, data: Partial<ReviewCampaign>) => {
    const response = await api.put(`/api/v1/campaigns/${campaign_id}`, data)
    return response.data
  },

  // 캠페인 활성화
  activate: async (campaign_id: string) => {
    const response = await api.post(`/api/v1/campaigns/${campaign_id}/activate`)
    return response.data
  },

  // 캠페인 일시정지
  pause: async (campaign_id: string) => {
    const response = await api.post(`/api/v1/campaigns/${campaign_id}/pause`)
    return response.data
  },

  // 캠페인 종료
  end: async (campaign_id: string) => {
    const response = await api.post(`/api/v1/campaigns/${campaign_id}/end`)
    return response.data
  },

  // 캠페인 삭제
  delete: async (campaign_id: string) => {
    const response = await api.delete(`/api/v1/campaigns/${campaign_id}`)
    return response.data
  },

  // QR 코드 생성
  generateQR: async (campaign_id: string) => {
    const response = await api.get(`/api/v1/campaigns/${campaign_id}/qr`)
    return response.data
  },

  // 캠페인 통계
  getStats: async (campaign_id: string): Promise<CampaignStats> => {
    const response = await api.get(`/api/v1/campaigns/${campaign_id}/stats`)
    return response.data
  },

  // 참여 목록
  getParticipations: async (campaign_id: string, status?: string, limit?: number, offset?: number): Promise<CampaignParticipation[]> => {
    const response = await api.get(`/api/v1/campaigns/${campaign_id}/participations`, { params: { status, limit, offset } })
    return response.data
  },

  // 참여 검증
  verifyParticipation: async (participation_id: string, data: {
    review_url?: string
    review_content?: string
    review_rating?: number
    verification_method?: string
  }) => {
    const response = await api.post(`/api/v1/campaigns/participations/${participation_id}/verify`, data)
    return response.data
  },

  // 보상 지급
  giveReward: async (participation_id: string, reward_amount?: number, notes?: string) => {
    const response = await api.post(`/api/v1/campaigns/participations/${participation_id}/reward`, { reward_amount, notes })
    return response.data
  },

  // 템플릿 조회
  getTemplates: async () => {
    const response = await api.get('/api/v1/campaigns/templates/list')
    return response.data
  },
}

export default api
