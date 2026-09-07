'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Logo } from './logo'
import { NAV_GROUPS, isActive } from './nav-config'

interface Props {
  onNavigate?: () => void
  className?: string
}

/** 왼쪽 사이드바. 데스크톱은 고정, 모바일은 Topbar 의 드로어 안에서 같은 컴포넌트를 쓴다. */
export function Sidebar({ onNavigate, className }: Props) {
  const pathname = usePathname() || ''
  return (
    <aside className={cn('flex h-full w-[236px] flex-col border-r bg-sidebar', className)}>
      <div className="flex h-14 items-center px-5">
        <Logo />
      </div>
      <nav className="flex-1 overflow-y-auto px-3 pb-10" aria-label="주 메뉴">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mt-4 first:mt-1">
            <div className="eyebrow px-2 pb-1.5">{group.label}</div>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(pathname, item)
                const Icon = item.icon
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'group flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] font-medium transition-colors',
                        active
                          ? 'bg-accent text-accent-foreground'
                          : 'text-sidebar-foreground hover:bg-muted hover:text-foreground',
                      )}
                    >
                      <Icon className={cn('h-[18px] w-[18px] shrink-0', active ? 'text-accent-foreground' : 'text-muted-foreground group-hover:text-foreground')} />
                      <span className="truncate">{item.label}</span>
                      {item.dev && (
                        <span className="ml-auto rounded-md border border-dashed px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground" title={item.devNote}>
                          개발 중
                        </span>
                      )}
                      {item.badge && !item.dev && (
                        <span className="ml-auto rounded-md bg-primary/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-primary">
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t px-5 py-3 text-[11px] leading-4 text-muted-foreground">
        생성된 콘텐츠의 법적 책임은 이용자에게 있습니다.
        <div className="mt-1">© 2026 플라톤마케팅 · <Link href="/legal" className="underline-offset-2 hover:underline">약관</Link></div>
      </div>
    </aside>
  )
}
