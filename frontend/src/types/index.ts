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
export interface DIAScore {
  total: number
  experience: {
    score: number
    analysis: string
    suggestions: string[]
  }
  information: {
    score: number
    analysis: string
    suggestions: string[]
  }
  originality: {
    score: number
    analysis: string
    suggestions: string[]
  }
  timeliness: {
    score: number
    analysis: string
    suggestions: string[]
  }
}

export interface CRANKScore {
  total: number
  context: {
    score: number
    analysis: string
    suggestions: string[]
  }
  content: {
    score: number
    analysis: string
    suggestions: string[]
  }
  chain: {
    score: number
    analysis: string
    suggestions: string[]
  }
  creator: {
    score: number
    analysis: string
    suggestions: string[]
  }
}

export interface DIACRANKAnalysis {
  dia_score: DIAScore
  crank_score: CRANKScore
  overall_grade: string
  estimated_ranking: string
  summary: string
}

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
  suggested_titles: string[] | null
  suggested_subtitles: string[] | null
  content_analysis: ContentAnalysis | null
  forbidden_words_check: ForbiddenWordsCheck | null
  dia_crank_analysis: DIACRANKAnalysis | null
}

export interface MedicalLawCheck {
  is_compliant: boolean
  violations: any[]
  warnings: any[]
  total_issues: number
}

export interface ContentAnalysis {
  character_count: {
    total: number
    no_space: number
    no_markdown: number
    spaces: number
    lines: number
  }
  keywords: Array<{
    word: string
    count: number
    is_medical: boolean
    importance: string
  }>
  sentence_count: number
  paragraph_count: number
  readability: string
}

export interface ForbiddenWordsCheck {
  content_replacements: Array<{
    original: string
    replaced: string
    count: number
  }>
  title_replacements: Array<{
    original: string
    replaced: string
    count: number
  }>
}

export interface SEOOptimization {
  enabled: boolean
  experience_focus: boolean
  expertise: boolean
  originality: boolean
  timeliness: boolean
  topic_concentration: boolean
}

export interface TopPostRules {
  title?: {
    length?: { optimal?: number; min?: number; max?: number }
    keyword_placement?: Record<string, unknown>
  }
  content?: {
    length?: { optimal?: number; min?: number; max?: number }
    structure?: Record<string, unknown>
  }
  media?: {
    images?: { optimal?: number; min?: number; max?: number }
    videos?: Record<string, unknown>
  }
}

export interface PostCreateRequest {
  original_content: string
  persuasion_level: number
  framework: string
  target_length: number
  writing_perspective?: string
  ai_provider?: string
  ai_model?: string
  writing_style?: WritingStyle
  requirements?: RequestRequirements
  seo_optimization?: SEOOptimization
  top_post_rules?: TopPostRules
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
  humor: number
  question_usage: number
  metaphor_usage: number
  sentence_length: number
}

export interface RequestRequirements {
  common: string[]
  individual: string
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

// Cafe Review Types (카페 바이럴 후기)
export interface CafeReviewStyle {
  friendliness: number      // 친근함 (1: 격식있게 ~ 10: 친구처럼)
  emotion: number           // 감정 표현 (1: 담담하게 ~ 10: 감정 풍부)
  humor: number             // 유머 (1: 진지하게 ~ 10: 재치있게)
  colloquial: number        // 구어체 (1: 문어체 ~ 10: 말하듯)
  emoji_usage: number       // 이모티콘 사용 (1: 없음 ~ 10: 많이)
  detail_level: number      // 디테일 (1: 간략히 ~ 10: 구체적으로)
  honesty: number           // 솔직함 (1: 긍정만 ~ 10: 단점도 언급)
}

export interface CafeReviewInput {
  hospital_name: string
  visit_purpose: string          // 방문 목적 (치료/시술 종류)
  experience_content: string     // 경험 내용 (Before/After, 느낀점)
  emphasis_points: string        // 강조하고 싶은 포인트
  target_length?: number         // 목표 글자수
}

export interface CafeReviewCreateRequest {
  review_input: CafeReviewInput
  review_style: CafeReviewStyle
  writing_perspective?: string   // 1인칭, 3인칭 등
  ai_provider?: string
  ai_model?: string
}
