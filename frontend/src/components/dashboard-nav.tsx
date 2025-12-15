'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'
import {
  Sparkles,
  LayoutDashboard,
  FileText,
  User,
  LogOut,
  PenTool,
  Shield,
  BarChart3,
  Tags,
  Save,
  TrendingUp,
  CreditCard,
  Calendar,
  FileBarChart,
  Share2,
  CircleDollarSign,
  MapPin
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

  const links = [
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
    {
      href: '/dashboard/reports',
      label: '리포트',
      icon: FileBarChart,
    },
    {
      href: '/dashboard/sns',
      label: 'SNS',
      icon: Share2,
    },
    {
      href: '/dashboard/top-post-analysis',
      label: '상위노출',
      icon: TrendingUp,
    },
    {
      href: '/dashboard/roi',
      label: 'ROI',
      icon: CircleDollarSign,
    },
    {
      href: '/dashboard/place',
      label: '플레이스',
      icon: MapPin,
    },
    {
      href: '/dashboard/subscription',
      label: '구독',
      icon: CreditCard,
    },
    {
      href: '/dashboard/profile',
      label: '프로필 설정',
      icon: User,
    },
  ]

  // 관리자 링크
  if (user?.is_admin) {
    links.push({
      href: '/admin',
      label: '관리자',
      icon: Shield,
    })
  }

  return (
    <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-blue-600" />
            <div className="flex flex-col">
              <span className="font-bold text-xl leading-tight">닥터보이스 프로</span>
              <span className="text-[10px] text-gray-400 leading-tight">by 플라톤마케팅</span>
            </div>
          </Link>

          <nav className="hidden md:flex gap-1">
            {links.map((link) => {
              const Icon = link.icon
              const isActive = pathname === link.href
              return (
                <Link key={link.href} href={link.href}>
                  <Button
                    variant={isActive ? 'secondary' : 'ghost'}
                    className={cn(
                      'gap-2',
                      isActive && 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {link.label}
                  </Button>
                </Link>
              )
            })}
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
