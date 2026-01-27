// Industry Type Enum
export type IndustryType =
  | 'medical'     // 의료 (병원/의원/한의원)
  | 'legal'       // 법률 (변호사/법무사)
  | 'restaurant'  // 음식점/카페
  | 'beauty'      // 미용/뷰티 (미용실/네일/피부관리)
  | 'fitness'     // 피트니스/헬스
  | 'education'   // 교육/학원
  | 'realestate'  // 부동산
  | 'other'       // 기타 자영업

// User & Auth Types
export interface User {
  id: string
  email: string
  name: string | null
  industry_type: IndustryType
  business_name: string | null
  hospital_name: string | null  // 레거시 호환
  specialty: string | null
  subscription_tier: string
  is_active: boolean
  is_approved: boolean
  is_admin: boolean
  has_unlimited_posts?: boolean
  unlimited_granted_at?: string | null
  unlimited_granted_by?: string | null
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

// 로컬 저장 글 타입 (localStorage에 저장되는 글)
export interface SavedPost {
  id: string
  savedAt: string
  suggested_titles?: string[]
  generated_content?: string
  seo_keywords?: string[]
  original_content?: string
  title?: string
  content?: string
  hashtags?: string[]
  // DB에서 온 글 식별용
  sourcePostId?: string
  sourceType?: 'database' | 'local'
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
  sample_posts: string[]
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

// ============================================================
// 대량 분석 관련 타입
// ============================================================

export interface AnalysisJob {
  id: string
  category: string
  category_name: string
  target_count: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  keywords_collected: number
  keywords_total: number
  posts_analyzed: number
  posts_failed: number
  keywords: string[]
  error_message?: string
  result_summary?: {
    total_keywords: number
    posts_analyzed: number
    posts_failed: number
    category: string
  }
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface CategoryWithStats {
  id: string
  name: string
  seeds: string[]
  posts_count: number
  sample_count: number
  confidence: number
  has_rules: boolean
}

export interface CategoryStats {
  category: string
  category_name: string
  posts_count: number
  keywords_count: number
  sample_count: number
  confidence: number
  last_updated?: string
}

export interface AnalysisDashboard {
  total_posts: number
  total_keywords: number
  categories: CategoryStats[]
  recent_jobs: AnalysisJob[]
}

export interface WritingRules {
  title: {
    length: { optimal: number; min: number; max: number }
    keyword_placement: {
      include_keyword: boolean
      rate: number
      best_position: string
      position_distribution: { front: number; middle: number; end: number }
    }
  }
  content: {
    length: { optimal: number; min: number; max: number }
    structure: {
      heading_count: { optimal: number; min: number; max: number }
      keyword_density: { optimal: number; min: number; max: number }
      keyword_count: { optimal: number; min: number; max: number }
    }
  }
  media: {
    images: { optimal: number; min: number; max: number }
    videos: { usage_rate: number; recommended: boolean }
  }
}

export interface CategoryRules {
  status: 'data_driven' | 'insufficient_data'
  category: string
  category_name: string
  sample_count: number
  confidence: number
  message?: string
  rules: WritingRules | null
}

export interface BulkAnalyzeRequest {
  category: string
  target_count: number
  keywords?: string[]
}

export interface BulkAnalyzeResponse {
  job_id: string
  category: string
  target_count: number
  status: string
  message: string
}

export interface CollectedKeyword {
  keyword: string
  source: string
  is_analyzed: boolean
  analysis_count: number
  created_at: string
}
