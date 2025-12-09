// User & Auth Types
export interface User {
  id: string
  email: string
  name: string | null
  hospital_name: string | null
  specialty: string | null
  subscription_tier: string
  is_active: boolean
  is_approved: boolean
  is_admin: boolean
  subscription_start_date: string | null
  subscription_end_date: string | null
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name?: string
  hospital_name?: string
  specialty?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

// Post Types
export interface Post {
  id: string
  user_id: string
  title: string | null
  original_content: string
  generated_content: string | null
  persuasion_score: number
  medical_law_check: MedicalLawCheck | null
  seo_keywords: string[]
  hashtags: string[]
  meta_description: string | null
  status: string
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface MedicalLawCheck {
  is_compliant: boolean
  violations: any[]
  warnings: any[]
  total_issues: number
}

export interface PostCreateRequest {
  original_content: string
  persuasion_level: number
  framework: string
  target_length: number
}

export interface PostListResponse {
  posts: Post[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Profile Types
export interface WritingStyle {
  formality: number
  friendliness: number
  technical_depth: number
  storytelling: number
  emotion: number
}

export interface TargetAudience {
  age_range?: string
  gender?: string
  concerns: string[]
}

export interface DoctorProfile {
  id: string
  user_id: string
  writing_style: WritingStyle | null
  signature_phrases: string[]
  target_audience: TargetAudience | null
  preferred_structure: string
  learned_at: string | null
  profile_version: number
  created_at: string
  updated_at: string
}

// Admin Types
export interface UserApprovalRequest {
  user_id: string
  is_approved: boolean
}

export interface UserSubscriptionRequest {
  user_id: string
  subscription_start_date?: string
  subscription_end_date?: string
}
