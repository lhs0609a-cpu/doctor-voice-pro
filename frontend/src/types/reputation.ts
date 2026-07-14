/**
 * 평판 모니터링 시스템 타입 정의
 */

// ==================== Enums ====================

export type MentionPlatform =
  | 'naver_place' | 'google_maps' | 'kakao_map'
  | 'naver_blog' | 'naver_cafe'
  | 'dcinside' | 'fmkorea' | 'theqoo' | 'blind' | 'danggeun'
  | 'instagram' | 'youtube'
  | 'baemin' | 'yogiyo' | 'gangnam_unni' | 'babitalk'
  | 'other'

export type MentionSentiment = 'positive' | 'neutral' | 'negative' | 'mixed'

export type RiskLevel = 'critical' | 'warning' | 'normal' | 'positive'

export type MentionStatus = 'new' | 'read' | 'responding' | 'responded' | 'escalated' | 'resolved' | 'ignored'

export type ResponseStyle = 'apologetic' | 'explanatory' | 'compensatory'

export type CrawlJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type AlertSeverity = 'critical' | 'warning' | 'info'

export type SpreadStatus = 'monitoring' | 'spreading' | 'contained' | 'resolved'

export type GuideCategory = 'report' | 'delete_request' | 'legal' | 'reply' | 'prevention'

// ==================== Models ====================

export interface MonitorProfile {
  id: string
  user_id: string
  business_name: string
  business_type: string | null
  address: string | null
  phone: string | null
  naver_place_id: string | null
  google_place_id: string | null
  kakao_place_id: string | null
  baemin_store_id: string | null
  yogiyo_store_id: string | null
  keywords: string[] | null
  negative_keywords: string[] | null
  crawl_interval_minutes: number
  enabled_platforms: string[] | null
  is_active: boolean
  alert_email: string | null
  alert_phone: string | null
  alert_kakao: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Mention {
  id: string
  profile_id: string
  platform: MentionPlatform | null
  platform_post_id: string | null
  source_url: string | null
  author_name: string | null
  author_id: string | null
  title: string | null
  content: string
  rating: number | null
  images: string[] | null
  sentiment: MentionSentiment | null
  sentiment_score: number | null
  risk_level: RiskLevel | null
  risk_score: number | null
  issues: string[] | null
  spread_potential: number | null
  is_defamation: boolean
  ai_summary: string | null
  platform_data: Record<string, any> | null
  status: MentionStatus | null
  is_bookmarked: boolean
  note: string | null
  published_at: string | null
  collected_at: string | null
  analyzed_at: string | null
  responded_at: string | null
  created_at: string | null
  responses?: GeneratedResponse[]
}

export interface GeneratedResponse {
  id: string
  style: ResponseStyle
  content: string
  is_selected: boolean
  is_posted: boolean
  edited_content: string | null
  created_at: string | null
}

export interface AlertRule {
  id: string
  profile_id: string
  name: string
  is_active: boolean
  severity: AlertSeverity | null
  platforms: string[] | null
  keyword_contains: string[] | null
  min_risk_score: number | null
  sentiment_filter: string[] | null
  min_rating: number | null
  max_rating: number | null
  notify_email: boolean
  notify_sms: boolean
  notify_kakao: boolean
  notify_webhook_url: string | null
  cooldown_minutes: number
  last_triggered_at: string | null
  created_at: string | null
}

export interface AlertLog {
  id: string
  rule_id: string
  mention_id: string | null
  severity: AlertSeverity | null
  title: string
  message: string
  channel: string | null
  is_sent: boolean
  sent_at: string | null
  error_message: string | null
  created_at: string | null
}

export interface SpreadIncident {
  id: string
  profile_id: string
  title: string
  description: string | null
  status: SpreadStatus | null
  first_detected_at: string | null
  platform_count: number
  mention_count: number
  estimated_reach: number
  timeline: Array<{
    time: string
    platform: string
    event: string
    url: string | null
    mention_id?: string
  }> | null
  response_plan: string | null
  resolved_at: string | null
  created_at: string | null
  related_mentions?: Mention[]
}

export interface ReputationSnapshot {
  date: string
  reputation_score: number | null
  avg_rating: number | null
  positive_count: number
  neutral_count: number
  negative_count: number
  mixed_count: number
  platform_stats: Record<string, { count: number; avg_rating: number }> | null
  top_issues: Array<{ issue: string; count: number }> | null
}

export interface ReputationCompetitor {
  id: string
  profile_id: string
  business_name: string
  naver_place_id: string | null
  google_place_id: string | null
  address: string | null
  current_rating: number | null
  review_count: number
  reputation_score: number | null
  is_active: boolean
  created_at: string | null
}

export interface PlatformGuide {
  id: string
  platform: MentionPlatform
  category: GuideCategory
  title: string
  description: string | null
  steps: Array<{ step_number: number; title: string; description: string; image_url?: string }> | null
  legal_basis: Array<{ law: string; article: string; description: string }> | null
  tips: string[] | null
  template_text: string | null
  difficulty: string | null
  estimated_days: number | null
  success_rate: number | null
}

export interface CrawlJob {
  id: string
  platform: MentionPlatform
  status: CrawlJobStatus
  mentions_found: number
  mentions_new: number
  error_message: string | null
}

// ==================== Dashboard ====================

export interface DashboardData {
  profile: MonitorProfile
  stats: {
    total_mentions: number
    positive: number
    neutral: number
    negative: number
    mixed: number
    critical_count: number
    unread_count: number
    avg_rating: number
  }
  reputation_score: number | null
  score_history: Array<{
    date: string
    score: number | null
    avg_rating: number | null
    positive: number
    negative: number
  }>
  critical_mentions: Mention[]
  platform_distribution: Record<string, number>
}

// ==================== Platform Labels ====================

export const PLATFORM_LABELS: Record<MentionPlatform, string> = {
  naver_place: '네이버 플레이스',
  google_maps: '구글 지도',
  kakao_map: '카카오맵',
  naver_blog: '네이버 블로그',
  naver_cafe: '네이버 카페',
  dcinside: 'DC인사이드',
  fmkorea: 'FM코리아',
  theqoo: '더쿠',
  blind: '블라인드',
  danggeun: '당근마켓',
  instagram: '인스타그램',
  youtube: '유튜브',
  baemin: '배달의민족',
  yogiyo: '요기요',
  gangnam_unni: '강남언니',
  babitalk: '바비톡',
  other: '기타',
}

export const SENTIMENT_LABELS: Record<MentionSentiment, string> = {
  positive: '긍정',
  neutral: '중립',
  negative: '부정',
  mixed: '혼합',
}

export const RISK_LABELS: Record<RiskLevel, string> = {
  critical: '긴급',
  warning: '주의',
  normal: '일반',
  positive: '긍정',
}

export const STATUS_LABELS: Record<MentionStatus, string> = {
  new: '새 멘션',
  read: '읽음',
  responding: '대응 중',
  responded: '대응 완료',
  escalated: '에스컬레이션',
  resolved: '해결됨',
  ignored: '무시',
}
