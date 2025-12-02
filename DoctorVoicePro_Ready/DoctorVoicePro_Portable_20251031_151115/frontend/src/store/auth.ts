import { create } from 'zustand'
import { authAPI } from '@/lib/api'
import type { User, LoginRequest, RegisterRequest } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isLoading: false,
  error: null,

  login: async (data: LoginRequest) => {
    set({ isLoading: true, error: null })
    try {
      const response = await authAPI.login(data)
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)
      localStorage.setItem('user', JSON.stringify(response.user))
      set({ user: response.user, token: response.access_token, isLoading: false })
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '로그인에 실패했습니다',
        isLoading: false,
      })
      throw error
    }
  },

  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null })
    try {
      // 회원가입은 승인 대기 상태로 등록되며, 자동 로그인되지 않음
      await authAPI.register(data)
      set({ isLoading: false })
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '회원가입에 실패했습니다',
        isLoading: false,
      })
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    set({ user: null, token: null })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ user: null, token: null })
      return
    }

    try {
      const user = await authAPI.getMe()
      localStorage.setItem('user', JSON.stringify(user))
      set({ user, token })
    } catch (error) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      set({ user: null, token: null })
    }
  },
}))
