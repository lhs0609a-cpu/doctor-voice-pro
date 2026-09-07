'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AlertTriangle, ArrowRight, Building2, CalendarClock, CheckCircle2, FileText, Image as ImagesIcon, PenTool, Rocket, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/app-shell/page-header'
import { EmptyState, ListRow, Pill, StatTile } from '@/components/app-shell/ui-kit'
import { useAuthStore } from '@/store/auth'
import { postsAPI, systemAPI } from '@/lib/api'
import { campaignAPI, BLOG_STATUS_LABEL, type AgentBlogSummary, type Campaign } from '@/lib/campaign-api'
import type { Post } from '@/types'

const STEP_LABEL = ['', '병원·블로그', '키워드', '원고', '사진', '예약', '현황']
const STATUS_LABEL: Record<string, { text: string; tone: 'ok' | 'warn' | 'danger' | 'accent' | 'muted' }> = {
  draft: { text: '준비 중', tone: 'muted' },
  scheduled: { text: '예약 걸림', tone: 'accent' },
  running: { text: '발행 중', tone: 'accent' },
  done: { text: '완료', tone: 'ok' },
  cancelled: { text: '취소', tone: 'muted' },
}

function fmtDate(s?: string | null) {
  if (!s) return ''
  const d = new Date(s)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function DashboardHome() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [blogs, setBlogs] = useState<AgentBlogSummary[]>([])
  const [posts, setPosts] = useState<Post[]>([])
  const [system, setSystem] = useState<{ status: string; ai: boolean } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    ;(async () => {
      const [c, b, p, h] = await Promise.allSettled([
        campaignAPI.listCampaigns(),
        campaignAPI.agentSummary(),
        postsAPI.list(1, 5),
        systemAPI.healthCheck(),
      ])
      if (!alive) return
      if (c.status === 'fulfilled') setCampaigns(c.value)
      if (b.status === 'fulfilled') setBlogs(b.value)
      if (p.status === 'fulfilled') setPosts(p.value.posts)
      setSystem(h.status === 'fulfilled' ? { status: h.value.status, ai: !!h.value.ai?.connected } : { status: 'offline', ai: false })
      setLoading(false)
    })()
    return () => {
      alive = false
    }
  }, [])

  const totals = useMemo(() => {
    const sum = (k: keyof Campaign['stats']) => campaigns.reduce((n, c) => n + (Number(c.stats?.[k]) || 0), 0)
    return {
      queued: sum('queued'),
      published: sum('published'),
      attention: sum('failed') + sum('uncertain'),
      active: campaigns.filter((c) => c.status === 'draft' || c.status === 'scheduled' || c.status === 'running').length,
    }
  }, [campaigns])

  const blogIssues = blogs.filter((b) => b.status !== 'active')
  const activeCampaigns = campaigns.filter((c) => c.status !== 'done' && c.status !== 'cancelled').slice(0, 5)
  const today = new Date()
  const greeting = `${today.getMonth() + 1}월 ${today.getDate()}일 · ${['일', '월', '화', '수', '목', '금', '토'][today.getDay()]}요일`

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={greeting}
        title={`${user?.name || '안녕하세요'}님, 오늘 발행 현황입니다`}
        description="키워드부터 예약 발행까지 캠페인 하나로 이어집니다. 새 캠페인을 열거나 진행 중인 캠페인을 이어서 하세요."
        actions={
          <>
            <Button variant="outline" onClick={() => router.push('/dashboard/create')}>
              <PenTool /> 글 하나 작성
            </Button>
            <Button onClick={() => router.push('/dashboard/campaign')}>
              <Rocket /> 새 캠페인
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="예약 대기" value={totals.queued.toLocaleString()} hint="발행 실행기가 가져갈 글" icon={<CalendarClock className="h-4 w-4" />} href="/dashboard/campaign" />
        <StatTile label="발행 완료" value={totals.published.toLocaleString()} hint="캠페인으로 나간 글" tone="ok" icon={<CheckCircle2 className="h-4 w-4" />} href="/dashboard/campaign" />
        <StatTile label="확인 필요" value={totals.attention.toLocaleString()} hint="실패 또는 시간초과" tone={totals.attention ? 'danger' : 'muted'} icon={<AlertTriangle className="h-4 w-4" />} href="/dashboard/campaign" />
        <StatTile label="진행 중 캠페인" value={totals.active.toLocaleString()} hint={`전체 ${campaigns.length}개`} tone="accent" icon={<Rocket className="h-4 w-4" />} href="/dashboard/campaign" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle>진행 중인 캠페인</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/campaign">전체 보기 <ArrowRight /></Link>
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="px-5 pb-5 text-sm text-muted-foreground">불러오는 중…</div>
              ) : activeCampaigns.length === 0 ? (
                <div className="px-5 pb-5">
                  <EmptyState
                    icon={<Rocket className="h-6 w-6" />}
                    title="아직 캠페인이 없습니다"
                    description="병원을 고르고 키워드를 확인하면 원고·사진·예약까지 한 번에 진행됩니다."
                    action={<Button onClick={() => router.push('/dashboard/campaign')}>첫 캠페인 만들기</Button>}
                  />
                </div>
              ) : (
                <div className="border-t">
                  {activeCampaigns.map((c) => {
                    const st = STATUS_LABEL[c.status] ?? STATUS_LABEL.draft
                    return (
                      <ListRow key={c.id} href={`/dashboard/campaign/${c.id}`}>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-medium">{c.name}</span>
                            <Pill tone={st.tone}>{st.text}</Pill>
                          </div>
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {c.client_name} · {c.step}/6단계 {STEP_LABEL[c.step] ?? ''} · 키워드 {c.stats?.keywords_selected ?? 0} · 원고 {c.stats?.drafts_ready ?? 0} · 예약 {c.stats?.queued ?? 0}
                          </div>
                        </div>
                        <span className="text-xs text-muted-foreground">{fmtDate(c.updated_at)}</span>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      </ListRow>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle>최근 작성한 글</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/posts">전체 보기 <ArrowRight /></Link>
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {posts.length === 0 ? (
                <div className="px-5 pb-5">
                  <EmptyState
                    icon={<FileText className="h-6 w-6" />}
                    title="작성한 글이 없습니다"
                    description="원고 하나를 바로 만들어 보거나, 캠페인에서 키워드로 여러 개를 한 번에 만드세요."
                    action={<Button variant="outline" onClick={() => router.push('/dashboard/create')}>글 작성</Button>}
                  />
                </div>
              ) : (
                <div className="border-t">
                  {posts.map((p) => (
                    <ListRow key={p.id} href={`/dashboard/posts/${p.id}`}>
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate">{p.title || p.suggested_titles?.[0] || '제목 없음'}</span>
                      {typeof p.persuasion_score === 'number' && p.persuasion_score > 0 && (
                        <span className="text-xs tabular-nums text-muted-foreground">설득력 {p.persuasion_score}</span>
                      )}
                      <span className="text-xs text-muted-foreground">{fmtDate(p.created_at)}</span>
                    </ListRow>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>블로그 계정</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {blogs.length === 0 ? (
                <div className="px-5 pb-5 text-sm text-muted-foreground">
                  등록된 블로그가 없습니다.{' '}
                  <Link href="/dashboard/clients" className="font-medium text-primary underline-offset-2 hover:underline">병원 관리</Link>에서 추가하세요.
                </div>
              ) : (
                <div className="border-t">
                  {blogs.map((b) => (
                    <ListRow key={b.blog_ref_id}>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{b.label}</div>
                        <div className="text-xs text-muted-foreground">
                          대기 {b.pending}건{b.next_at ? ` · 다음 ${b.next_at.slice(5, 16).replace('T', ' ')}` : ''}
                        </div>
                      </div>
                      <Pill tone={b.status === 'active' ? 'ok' : b.status === 'paused' ? 'muted' : 'warn'}>
                        {BLOG_STATUS_LABEL[b.status] ?? b.status}
                      </Pill>
                    </ListRow>
                  ))}
                </div>
              )}
              {blogIssues.length > 0 && (
                <div className="border-t bg-warning-soft/60 px-5 py-3 text-xs text-warning">
                  {blogIssues.length}개 블로그가 멈춰 있습니다. {blogIssues[0].status_reason || '크롬에서 확인 후 병원 관리에서 정상으로 바꾸세요.'}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>바로가기</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2">
              {[
                { href: '/dashboard/clients', label: '병원 관리', icon: Building2 },
                { href: '/dashboard/media', label: '사진 풀', icon: ImagesIcon },
                { href: '/dashboard/saved', label: '저장된 글', icon: Save },
                { href: '/dashboard/one-stop', label: '원스톱 자동화', icon: Rocket },
              ].map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-[13px] font-medium hover:bg-muted/50">
                  <Icon className="h-4 w-4 text-muted-foreground" /> {label}
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>시스템</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">서버</span>
                <Pill tone={system ? (system.status === 'offline' ? 'danger' : 'ok') : 'muted'}>{system ? (system.status === 'offline' ? '연결 안 됨' : '정상') : '확인 중'}</Pill>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">AI</span>
                <Pill tone={system?.ai ? 'ok' : 'muted'}>{system?.ai ? '연결됨' : '키 필요'}</Pill>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">크롬 확장</span>
                <span className="text-xs text-muted-foreground">상단 표시등 참고</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
