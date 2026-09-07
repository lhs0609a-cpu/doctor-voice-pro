'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Hammer } from 'lucide-react'
import { devItemFor, DEV_NOTICE_DEFAULT } from './nav-config'

/** 개발 중인 화면 상단에 붙는 안내 띠. 메뉴 설정(nav-config)의 dev 플래그 하나로 관리한다. */
export function DevBanner() {
  const pathname = usePathname() || ''
  const item = devItemFor(pathname)
  if (!item) return null
  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-dashed border-warning/50 bg-warning-soft px-4 py-3 text-sm" role="status">
      <Hammer className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
      <div className="min-w-0">
        <div className="font-semibold text-warning">개발 중인 기능입니다</div>
        <p className="mt-0.5 text-[13px] text-foreground/80">{item.devNote || DEV_NOTICE_DEFAULT}</p>
        <p className="mt-1 text-[12px] text-muted-foreground">
          지금 쓸 수 있는 기능:{' '}
          <Link href="/dashboard/campaign" className="font-medium text-primary underline-offset-2 hover:underline">캠페인</Link> ·{' '}
          <Link href="/dashboard/one-stop" className="font-medium text-primary underline-offset-2 hover:underline">원스톱 자동화</Link> ·{' '}
          <Link href="/dashboard/clients" className="font-medium text-primary underline-offset-2 hover:underline">병원 관리</Link>
        </p>
      </div>
    </div>
  )
}
