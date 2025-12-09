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

// Get dynamic API URL - check localStorage first, then env, then default
const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const storedUrl = localStorage.getItem('BACKEND_URL')
    if (storedUrl) return storedUrl
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010'
}

const API_URL = getApiUrl()

// Axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - Add token to headers and log API calls
api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      // Update baseURL dynamically from localStorage
      const currentBackendUrl = localStorage.getItem('BACKEND_URL')
      if (currentBackendUrl) {
        config.baseURL = currentBackendUrl
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
    const response = await api.post<Post>('/api/v1/posts/', data)
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

export default api
