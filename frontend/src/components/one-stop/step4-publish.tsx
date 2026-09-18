'use client'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { SavedPostsManager } from '@/components/saved-posts/saved-posts-manager'
import type { WizardState } from './use-wizard-state'

interface Props {
  state: WizardState
  onBack: () => void
  onRestart: () => void
}

export function Step4Publish({ state, onBack, onRestart }: Props) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>4단계 · 예약발행</CardTitle>
          <CardDescription>
            방금 생성한 <span className="tabular-nums">{state.generatedCount}</span>개 글이 아래{' '}
            <b className="font-medium text-foreground">저장된 글</b> 목록에 있습니다. 이미지를 배정하고 시작 시각·간격을 정한 뒤{' '}
            <b className="font-medium text-foreground">예약발행</b>하면 확장 프로그램이 네이버 블로그에 순차 예약등록합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="rounded-lg border bg-accent p-3 text-sm text-accent-foreground">
            네이버에 로그인되어 있지 않으면 발행 시작 시 확장이 저장된 계정으로 자동 로그인합니다.
            보안문자(캡차)나 신규기기 인증이 뜨면 직접 완료해 주세요 — 이후 자동으로 이어집니다.
            (계정 저장은 확장 팝업에서 설정)
          </p>
        </CardContent>
      </Card>

      {/* 이미지 배정 + 계정검증 + 큐 등록 + 예약발행: 검증된 기존 매니저 재사용 */}
      <SavedPostsManager />

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          이전
        </Button>
        <Button variant="outline" onClick={onRestart}>
          새 작업 시작
        </Button>
      </div>
    </div>
  )
}
