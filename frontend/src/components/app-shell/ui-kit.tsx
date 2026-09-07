import type { ReactNode } from 'react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

/** 상태 알약. 색은 의미(성공/주의/위험)로만 쓴다. */
export function Pill({ tone = 'muted', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cn('pill', `pill-${tone}`, className)}>{children}</span>
}

/** KPI 타일. 숫자는 28px tabular, 라벨은 위, 힌트는 아래. */
export function StatTile({
  label, value, hint, tone, href, icon, className,
}: { label: ReactNode; value: ReactNode; hint?: ReactNode; tone?: Tone; href?: string; icon?: ReactNode; className?: string }) {
  const toneText = tone === 'ok' ? 'text-success' : tone === 'warn' ? 'text-warning' : tone === 'danger' ? 'text-danger' : tone === 'accent' ? 'text-primary' : 'text-foreground'
  const body = (
    <div className={cn('surface flex h-full flex-col justify-between gap-3 p-4 transition-colors', href && 'hover:bg-muted/40', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[13px] font-medium text-muted-foreground">{label}</div>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div>
        <div className={cn('kpi', toneText)}>{value}</div>
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </div>
    </div>
  )
  return href ? <Link href={href} className="block h-full">{body}</Link> : body
}

/** 빈 상태. 제목 + 한 줄 설명 + 행동 버튼. */
export function EmptyState({ icon, title, description, action, className }: { icon?: ReactNode; title: ReactNode; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center', className)}>
      {icon && <div className="mb-3 text-muted-foreground">{icon}</div>}
      <div className="text-[15px] font-semibold">{title}</div>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/** 리스트 행(카드 안에서 반복되는 항목). */
export function ListRow({ children, className, href }: { children: ReactNode; className?: string; href?: string }) {
  const cls = cn('flex items-center gap-3 px-4 py-3 text-sm border-b last:border-b-0', href && 'hover:bg-muted/40 transition-colors', className)
  return href ? <Link href={href} className={cls}>{children}</Link> : <div className={cls}>{children}</div>
}
