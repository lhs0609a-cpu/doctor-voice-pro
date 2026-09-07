import type { LucideIcon } from 'lucide-react'
import {
  BarChart3, Building2, Calendar, CircleDollarSign, Coffee, Database, FileBarChart, FileSpreadsheet,
  HelpCircle, Image as ImagesIcon, Layers, LayoutDashboard, Mail, MapPin, PenTool, Rocket, Save,
  Settings, Share2, Shield, Sparkles, TrendingUp, User, CreditCard,
} from 'lucide-react'

export interface NavItem {
  href: string
  label: string
  icon: LucideIcon
  /** 정확히 일치할 때만 활성(대시보드 홈처럼 하위 경로가 많은 경우) */
  exact?: boolean
  badge?: string
  /** 아직 완성되지 않은 기능. 메뉴에 '개발 중' 배지, 화면 상단에 안내 띠가 붙는다. */
  dev?: boolean
  devNote?: string
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** 사이드바 메뉴. 순서 = 초보자가 쓰는 순서. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: '시작',
    items: [
      { href: '/dashboard', label: '홈', icon: LayoutDashboard, exact: true },
      { href: '/dashboard/campaign', label: '캠페인', icon: Rocket, badge: '대량 발행' },
      { href: '/dashboard/clients', label: '병원 관리', icon: Building2 },
    ],
  },
  {
    label: '콘텐츠',
    items: [
      { href: '/dashboard/one-stop', label: '원스톱 자동화', icon: Sparkles },
      { href: '/dashboard/create', label: '글 작성', icon: PenTool },
      { href: '/dashboard/keywords', label: '키워드 대량 생성', icon: FileSpreadsheet },
      { href: '/dashboard/saved', label: '저장된 글', icon: Save },
      { href: '/dashboard/bulk', label: '대량 발행(구)', icon: Layers, dev: true, devNote: "구버전 대량 발행입니다. 캠페인(키워드→원고→사진→예약)을 사용해 주세요." },
      { href: '/dashboard/media', label: '사진 풀', icon: ImagesIcon },
      { href: '/dashboard/schedule', label: '예약발행', icon: Calendar, dev: true, devNote: "예약발행은 캠페인 5단계(예약 걸기)로 옮겨 가는 중입니다. 이 화면의 예약은 실제로 실행되지 않습니다." },
    ],
  },
  {
    label: '분석',
    items: [
      { href: '/dashboard/top-post-analysis', label: '상위노출 분석', icon: TrendingUp, dev: true, devNote: "상위노출 분석은 캠페인·원스톱 2단계의 '내 블로그 기준 판정'으로 대체되고 있습니다." },
      { href: '/dashboard/reports', label: '리포트', icon: FileBarChart, dev: true, devNote: "리포트 생성·발송은 준비 중입니다." },
      { href: '/dashboard/roi', label: 'ROI 추적', icon: CircleDollarSign, dev: true, devNote: "ROI 추적은 준비 중입니다." },
      { href: '/dashboard/analytics', label: '통계', icon: BarChart3, dev: true, devNote: "통계 화면은 준비 중입니다." },
    ],
  },
  {
    label: '채널',
    items: [
      { href: '/dashboard/cafe', label: '카페 바이럴', icon: Coffee, dev: true, devNote: "카페 바이럴 자동 게시는 준비 중입니다. 카페 원고 변형은 캠페인 3단계에서 쓸 수 있습니다." },
      { href: '/dashboard/knowledge', label: '지식인 답변', icon: HelpCircle, dev: true, devNote: "지식인 답변 자동화는 준비 중입니다." },
      { href: '/dashboard/place', label: '플레이스', icon: MapPin, dev: true, devNote: "플레이스 관리는 준비 중입니다." },
      { href: '/dashboard/sns', label: 'SNS', icon: Share2, dev: true, devNote: "SNS 연동은 준비 중입니다." },
      { href: '/dashboard/reputation', label: '평판 모니터링', icon: Shield, dev: true, devNote: "평판 모니터링은 준비 중입니다." },
      { href: '/dashboard/outreach', label: '이메일 영업', icon: Mail, dev: true, devNote: "이메일 영업은 준비 중입니다." },
      { href: '/dashboard/outreach/leads', label: '리드 수집', icon: Database, dev: true, devNote: "리드 수집은 준비 중입니다." },
    ],
  },
  {
    label: '설정',
    items: [
      { href: '/dashboard/profile', label: '프로필', icon: User },
      { href: '/dashboard/subscription', label: '구독·결제', icon: CreditCard, dev: true, devNote: "구독·결제는 준비 중입니다. 지금은 관리자가 계정을 직접 승인합니다." },
      { href: '/dashboard/tags', label: '태그', icon: Settings },
    ],
  },
]

export function isActive(pathname: string, item: NavItem): boolean {
  if (item.exact) return pathname === item.href
  if (pathname === item.href) return true
  // 더 구체적인 메뉴가 있으면 그쪽만 활성(예: /dashboard/outreach/leads)
  const longer = NAV_GROUPS.flatMap((g) => g.items).some(
    (o) => o.href !== item.href && o.href.startsWith(item.href + '/') && pathname.startsWith(o.href),
  )
  return !longer && pathname.startsWith(item.href + '/')
}

export function currentTitle(pathname: string): string {
  const all = NAV_GROUPS.flatMap((g) => g.items)
  const hit = all.filter((i) => isActive(pathname, i)).sort((a, b) => b.href.length - a.href.length)[0]
  return hit?.label ?? '닥터보이스 프로'
}


export const DEV_NOTICE_DEFAULT = '이 기능은 아직 개발 중입니다. 화면은 미리보기이며 일부 동작이 완성되지 않았습니다.'

/** 현재 경로가 개발 중 메뉴에 속하면 그 항목을 돌려준다. */
export function devItemFor(pathname: string): NavItem | null {
  const all = NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.dev)
  const hit = all.filter((i) => isActive(pathname, i)).sort((a, b) => b.href.length - a.href.length)[0]
  return hit ?? null
}
