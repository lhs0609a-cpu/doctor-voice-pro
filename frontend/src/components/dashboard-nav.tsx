'use client'

/**
 * 예전 상단 내비게이션. 2026-09 디자인 개편으로 사이드바(app-shell/sidebar)가 대신한다.
 * 몇몇 페이지가 아직 <DashboardNav /> 를 직접 렌더하므로, 이중 표시가 안 나게 빈 컴포넌트로 남겨 둔다.
 * 메뉴 항목은 app-shell/nav-config.ts 에서 관리한다.
 */
export function DashboardNav() {
  return null
}

export default DashboardNav
