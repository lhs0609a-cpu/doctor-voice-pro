'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut, Menu, User, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ThemeToggle } from '@/components/theme-toggle'
import { ExtensionStatusBadge } from '@/components/extension-status'
import { useAuthStore } from '@/store/auth'
import { Sidebar } from './sidebar'
import { LogoMark } from './logo'
import { currentTitle } from './nav-config'

/** 상단 바: 모바일 메뉴, 현재 화면 이름, 확장 상태, 테마, 계정. */
export function Topbar() {
  const pathname = usePathname() || ''
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    setOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const initials = (user?.name || user?.email || '?').trim().slice(0, 1).toUpperCase()

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70 lg:px-6">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="메뉴 열기">
          <Menu className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-2 lg:hidden">
          <LogoMark className="h-6 w-6" />
        </div>
        <div className="min-w-0 text-[13.5px] font-medium text-muted-foreground">
          <span className="text-foreground">{currentTitle(pathname)}</span>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <ExtensionStatusBadge />
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="ml-1 flex h-9 items-center gap-2 rounded-lg px-2 hover:bg-muted" aria-label="계정 메뉴">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-[12px] font-semibold text-primary-foreground">
                  {initials}
                </span>
                <span className="hidden max-w-[160px] truncate text-[13px] md:inline">{user?.name || user?.email}</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="text-[13px] font-medium">{user?.name || '사용자'}</div>
                <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => router.push('/dashboard/profile')}>
                <User className="mr-2 h-4 w-4" /> 프로필
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => { logout(); router.push('/login') }}>
                <LogOut className="mr-2 h-4 w-4" /> 로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* 모바일 드로어 */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-foreground/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[236px] shadow-pop">
            <Sidebar onNavigate={() => setOpen(false)} />
            <button
              className="absolute right-2 top-3 rounded-md p-1.5 text-muted-foreground hover:bg-muted"
              onClick={() => setOpen(false)}
              aria-label="메뉴 닫기"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
