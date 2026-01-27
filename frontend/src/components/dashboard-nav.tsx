'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sparkles,
  LayoutDashboard,
  User,
  LogOut,
  PenTool,
  Shield,
  Save,
  TrendingUp,
  CreditCard,
  Calendar,
  FileBarChart,
  Share2,
  CircleDollarSign,
  MapPin,
  HelpCircle,
  ChevronDown,
  BarChart3,
  Store,
  Settings,
  Coffee,
  Mail,
  Database,
  Menu,
  X,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function DashboardNav() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  const handleMobileNavClick = (href: string) => {
    router.push(href)
    setMobileMenuOpen(false)
  }

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  // 개별 메뉴 (드롭다운 없이)
  const mainLinks = [
    {
      href: '/dashboard',
      label: '대시보드',
      icon: LayoutDashboard,
    },
    {
      href: '/dashboard/create',
      label: '글 작성',
      icon: PenTool,
    },
    {
      href: '/dashboard/saved',
      label: '저장된 글',
      icon: Save,
    },
    {
      href: '/dashboard/schedule',
      label: '예약발행',
      icon: Calendar,
    },
  ]

  // 마케팅 분석 탭
  const analyticsLinks = [
    {
      href: '/dashboard/reports',
      label: '리포트',
      icon: FileBarChart,
    },
    {
      href: '/dashboard/top-post-analysis',
      label: '상위노출 분석',
      icon: TrendingUp,
    },
    {
      href: '/dashboard/roi',
      label: 'ROI 추적',
      icon: CircleDollarSign,
    },
  ]

  // 채널 관리 탭
  const channelLinks = [
    {
      href: '/dashboard/sns',
      label: 'SNS 관리',
      icon: Share2,
    },
    {
      href: '/dashboard/place',
      label: '플레이스 관리',
      icon: MapPin,
    },
    {
      href: '/dashboard/knowledge',
      label: '지식인 답변',
      icon: HelpCircle,
    },
    {
      href: '/dashboard/cafe',
      label: '카페 바이럴',
      icon: Coffee,
    },
    {
      href: '/dashboard/outreach',
      label: '이메일 영업',
      icon: Mail,
    },
    {
      href: '/dashboard/outreach/leads',
      label: '리드 수집',
      icon: Database,
    },
  ]

  // 설정 탭
  const settingsLinks = [
    {
      href: '/subscription/manage',
      label: '구독 관리',
      icon: CreditCard,
    },
    {
      href: '/dashboard/profile',
      label: '프로필 설정',
      icon: User,
    },
  ]

  // 관리자 메뉴
  if (user?.is_admin) {
    settingsLinks.push({
      href: '/admin',
      label: '관리자',
      icon: Shield,
    })
  }

  // 드롭다운 탭이 활성화되어 있는지 확인
  const isAnalyticsActive = analyticsLinks.some(link => pathname === link.href || pathname.startsWith(link.href + '/'))
  const isChannelActive = channelLinks.some(link => pathname === link.href || pathname.startsWith(link.href + '/'))
  const isSettingsActive = settingsLinks.some(link => pathname === link.href || pathname.startsWith(link.href + '/'))

  // 모든 메뉴 통합 (모바일용)
  const allMenuSections = [
    { id: 'main', title: '메인', links: mainLinks },
    { id: 'analytics', title: '마케팅 분석', links: analyticsLinks },
    { id: 'channel', title: '채널 관리', links: channelLinks },
    { id: 'settings', title: '설정', links: settingsLinks },
  ]

  return (
    <>
      {/* 모바일 메뉴 오버레이 */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 모바일 사이드 메뉴 */}
      <div
        className={cn(
          'fixed top-0 left-0 h-full w-72 bg-white z-50 transform transition-transform duration-300 ease-in-out md:hidden shadow-xl',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* 모바일 메뉴 헤더 */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-blue-600" />
            <span className="font-bold text-lg">닥터보이스 프로</span>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 모바일 메뉴 내용 */}
        <div className="overflow-y-auto h-[calc(100%-64px)] py-4">
          {allMenuSections.map((section) => (
            <div key={section.id} className="mb-2">
              {/* 섹션 헤더 (메인 제외) */}
              {section.id !== 'main' ? (
                <button
                  onClick={() => toggleSection(section.id)}
                  className="w-full flex items-center justify-between px-4 py-2 text-sm font-semibold text-gray-500 hover:bg-gray-50"
                >
                  {section.title}
                  <ChevronRight
                    className={cn(
                      'h-4 w-4 transition-transform',
                      expandedSection === section.id && 'rotate-90'
                    )}
                  />
                </button>
              ) : (
                <div className="px-4 py-2 text-sm font-semibold text-gray-500">
                  {section.title}
                </div>
              )}

              {/* 섹션 링크들 */}
              <div
                className={cn(
                  section.id !== 'main' && expandedSection !== section.id && 'hidden'
                )}
              >
                {section.links.map((link) => {
                  const Icon = link.icon
                  const isActive = pathname === link.href || pathname.startsWith(link.href + '/')
                  return (
                    <button
                      key={link.href}
                      onClick={() => handleMobileNavClick(link.href)}
                      className={cn(
                        'w-full flex items-center gap-3 px-4 py-3 text-sm transition-colors',
                        isActive
                          ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600'
                          : 'text-gray-700 hover:bg-gray-50'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {link.label}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          {/* 로그아웃 */}
          <div className="border-t mt-4 pt-4 px-4">
            <div className="text-sm text-gray-500 mb-2">{user?.name || user?.email}</div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-600 hover:bg-red-50 rounded-lg"
            >
              <LogOut className="h-4 w-4" />
              로그아웃
            </button>
          </div>
        </div>
      </div>

      {/* 메인 네비게이션 바 */}
      <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-30">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* 모바일 햄버거 메뉴 버튼 */}
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden p-2 hover:bg-gray-100 rounded-lg"
            >
              <Menu className="h-6 w-6" />
            </button>

            <Link href="/dashboard" className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-blue-600" />
              <div className="flex flex-col">
                <span className="font-bold text-xl leading-tight hidden sm:block">닥터보이스 프로</span>
                <span className="font-bold text-lg leading-tight sm:hidden">DVP</span>
                <span className="text-[10px] text-gray-400 leading-tight hidden sm:block">by 플라톤마케팅</span>
              </div>
            </Link>

            {/* 데스크톱 네비게이션 */}
            <nav className="hidden md:flex items-center gap-1 ml-2">
            {/* 개별 메뉴 */}
            {mainLinks.map((link) => {
              const Icon = link.icon
              const isActive = pathname === link.href
              return (
                <Link key={link.href} href={link.href}>
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    size="sm"
                    className={cn(
                      'gap-1.5',
                      isActive && 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {link.label}
                  </Button>
                </Link>
              )
            })}

            {/* 마케팅 분석 드롭다운 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant={isAnalyticsActive ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'gap-1.5',
                    isAnalyticsActive && 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  )}
                >
                  <BarChart3 className="h-4 w-4" />
                  마케팅 분석
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                {analyticsLinks.map((link) => {
                  const Icon = link.icon
                  const isActive = pathname === link.href || pathname.startsWith(link.href + '/')
                  return (
                    <DropdownMenuItem
                      key={link.href}
                      className={cn(
                        'gap-2 cursor-pointer',
                        isActive && 'bg-blue-50 text-blue-700'
                      )}
                      onClick={() => router.push(link.href)}
                    >
                      <Icon className="h-4 w-4" />
                      {link.label}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* 채널 관리 드롭다운 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant={isChannelActive ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'gap-1.5',
                    isChannelActive && 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  )}
                >
                  <Store className="h-4 w-4" />
                  채널 관리
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                {channelLinks.map((link) => {
                  const Icon = link.icon
                  const isActive = pathname === link.href || pathname.startsWith(link.href + '/')
                  return (
                    <DropdownMenuItem
                      key={link.href}
                      className={cn(
                        'gap-2 cursor-pointer',
                        isActive && 'bg-blue-50 text-blue-700'
                      )}
                      onClick={() => router.push(link.href)}
                    >
                      <Icon className="h-4 w-4" />
                      {link.label}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* 설정 드롭다운 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant={isSettingsActive ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'gap-1.5',
                    isSettingsActive && 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  )}
                >
                  <Settings className="h-4 w-4" />
                  설정
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                {settingsLinks.map((link) => {
                  const Icon = link.icon
                  const isActive = pathname === link.href || pathname.startsWith(link.href + '/')
                  return (
                    <DropdownMenuItem
                      key={link.href}
                      className={cn(
                        'gap-2 cursor-pointer',
                        isActive && 'bg-blue-50 text-blue-700'
                      )}
                      onClick={() => router.push(link.href)}
                    >
                      <Icon className="h-4 w-4" />
                      {link.label}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-sm text-muted-foreground hidden sm:block">
            {user?.name || user?.email}
          </div>
          <ThemeToggle />
          <Button variant="ghost" size="icon" onClick={handleLogout}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
