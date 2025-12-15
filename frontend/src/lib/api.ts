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

export default api
