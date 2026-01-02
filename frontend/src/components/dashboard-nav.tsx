'use client'

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
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function DashboardNav() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    router.push('/login')
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

  return (
    <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-blue-600" />
            <div className="flex flex-col">
              <span className="font-bold text-xl leading-tight">닥터보이스 프로</span>
              <span className="text-[10px] text-gray-400 leading-tight">by 플라톤마케팅</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
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
