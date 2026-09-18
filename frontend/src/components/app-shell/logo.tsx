import Link from 'next/link'
import { cn } from '@/lib/utils'

/** 닥터보이스 프로 로고. 마크(말풍선+파형) + 워드마크. 좁은 곳에서는 마크만. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('h-7 w-7', className)} aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="hsl(var(--primary))" />
      <path
        d="M8 16.5h2.2l1.6-4.2 2.4 8 2.4-11 2.4 9.5 1.7-4.3H24"
        fill="none"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function Logo({ compact = false, href = '/dashboard', className }: { compact?: boolean; href?: string; className?: string }) {
  return (
    <Link href={href} className={cn('flex items-center gap-2.5 whitespace-nowrap', className)} aria-label="닥터보이스 프로 홈">
      <LogoMark />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-[15px] font-semibold tracking-tight text-foreground">닥터보이스 프로</span>
          <span className="mt-1 text-[10.5px] font-medium tracking-[0.06em] text-muted-foreground">by 플라톤마케팅</span>
        </span>
      )}
    </Link>
  )
}
