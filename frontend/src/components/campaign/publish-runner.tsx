'use client'

// 예약 실행 현황. 실제 등록은 PC 실행기가 한다 — 예전에는 이 화면의 버튼이 확장에게
// 한 건씩 밀어 넣었지만, 실행기가 대기 작업을 알아서 순차 처리하므로 버튼을 없앴다.

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { LauncherCard } from '@/components/launcher/launcher-card'
import { campaignAPI, type AgentBlogSummary, type Campaign } from '@/lib/campaign-api'
import { errMsg } from './common'

export function PublishRunner({ campaign }: { campaign: Campaign; onJobsChanged?: () => void }) {
  const [blogs, setBlogs] = useState<AgentBlogSummary[]>([])
  const refresh = useCallback(async () => {
    try {
      setBlogs(await campaignAPI.agentSummary())
    } catch (e) { toast.error('실행 상태 조회 실패', { description: errMsg(e) }) }
  }, [])
  useEffect(() => { refresh() }, [refresh, campaign.stats?.queued])

  return <Card className="space-y-4 p-5">
    <div>
      <h3 className="section-title">예약 실행</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        검수를 통과한 글은 PC 실행기가 대기 순서대로 네이버에 예약 등록합니다. 이 창을 닫아도 됩니다.
      </p>
    </div>
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-2">
        {blogs.length === 0
          ? <p className="text-sm text-muted-foreground">등록된 블로그가 없습니다. 1단계에서 블로그를 연결하세요.</p>
          : blogs.map(b => (
            <div key={b.blog_ref_id} className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">{b.label || b.naver_blog_id}</p>
                <p className="text-xs text-muted-foreground">
                  대기 <span className="tabular-nums">{b.pending}</span>건
                  {b.next_at ? ` · 다음 ${b.next_at.replace('T', ' ').slice(0, 16)}` : ''}
                </p>
              </div>
              <span className={`pill ${b.status === 'active' ? 'pill-ok' : 'pill-warn'}`}>
                {b.status === 'active' ? '정상' : b.status === 'captcha' ? '보안문자 필요' : b.status === 'login_required' ? '로그인 필요' : b.status}
              </span>
            </div>
          ))}
        {blogs.some(b => b.status !== 'active') && (
          <p className="text-xs text-warning">
            실행기가 연 크롬 창에서 해당 블로그에 다시 로그인하거나 보안문자를 입력하면 자동으로 정상으로 돌아갑니다.
          </p>
        )}
      </div>
      <LauncherCard compact />
    </div>
    <p className="text-xs text-muted-foreground">등록 응답만으로 공개 완료로 표시하지 않습니다. 결과가 불명확하면 아래 목록에서 네이버 예약 내역을 대조하세요.</p>
  </Card>
}
