'use client'

// 네이버에 실제로 글을 올리는 일은 PC 실행기(Windows 프로그램)가 한다.
// 예전에는 크롬 확장이 브라우저 안에서 했지만, 확장은 설치가 번거롭고 자동 업데이트가
// 되지 않아 실행기로 옮겼다. 웹은 서버 큐에 글을 쌓기만 하고, 실행기가 가져가 등록한다.

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowUpCircle, Download, Laptop, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { campaignAPI, type AgentBlogSummary } from '@/lib/campaign-api'
import { useLauncherStatus, type LauncherLight } from '@/lib/use-launcher-status'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/auth'

export const LAUNCHER_DOWNLOAD_URL = '/downloads/DoctorVoiceAutopilotSetup.exe'
const BLOG_KEY = 'doctorvoice-target-blog'

const LIGHT_STYLE: Record<LauncherLight, { dot: string; pill: string }> = {
  running: { dot: 'bg-success', pill: 'pill-ok' },
  idle: { dot: 'bg-warning', pill: 'pill-warn' },
  update: { dot: 'bg-warning', pill: 'pill-warn' },
  offline: { dot: 'bg-danger', pill: 'pill-danger' },
  checking: { dot: 'bg-muted-foreground', pill: 'pill-muted' },
  connecting: { dot: 'bg-warning', pill: 'pill-warn' },
  other: { dot: 'bg-warning', pill: 'pill-warn' },
  error: { dot: 'bg-warning', pill: 'pill-warn' },
}

/** 신호등 점. 실행기가 실제로 일하고 있을 때만 깜빡인다. */
function Light({ light, size = 'sm' }: { light: LauncherLight; size?: 'sm' | 'lg' }) {
  const dot = size === 'lg' ? 'h-3 w-3' : 'h-2.5 w-2.5'
  return (
    <span className={cn('relative inline-flex', dot)}>
      {light === 'running' && (
        <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-50', LIGHT_STYLE[light].dot)} />
      )}
      <span className={cn('relative inline-flex rounded-full', dot, LIGHT_STYLE[light].dot)} />
    </span>
  )
}

/** 상단 바용 알약. 꺼져 있거나 업데이트가 필요하면 눌러서 안내로 간다. */
export function LauncherStatusBadge({ className }: { className?: string }) {
  const status = useLauncherStatus()
  const body = (
    <>
      <Light light={status.light} />
      <span className="hidden sm:inline">{status.label}</span>
      {status.version && <span className="tabular-nums opacity-70">v{status.version}</span>}
    </>
  )
  const cls = cn('pill', LIGHT_STYLE[status.light].pill, 'gap-1.5 px-2.5 py-1', className)
  const title = status.online
    ? `${status.label}${status.note ? ` · ${status.note}` : ''}`
    : status.local ? '이 PC의 실행기를 찾았습니다 — 자동으로 연결합니다'
      : '실행기 연결이 확인되지 않았습니다. 눌러서 연결 방법을 확인하세요.'
  if (!status.running || status.updateAvailable) {
    return (
      <Link href="/dashboard/launcher" className={cn(cls, 'cursor-pointer hover:opacity-80')} title={title}>
        {body}
      </Link>
    )
  }
  return <div className={cls} title={title}>{body}</div>
}

export function LauncherCard({ className, compact = false, inline = false }: { className?: string; compact?: boolean; inline?: boolean }) {
  const status = useLauncherStatus()
  const email = useAuthStore((s) => s.user?.email)
  return (
    <div className={cn('surface space-y-3 p-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Laptop className="h-4 w-4 text-muted-foreground" />
          PC 실행기
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('pill gap-1.5 px-2 py-0.5 text-xs', LIGHT_STYLE[status.light].pill)}>
            <Light light={status.light} size="lg" />
            {status.label}
          </span>
          <Button variant="ghost" size="sm" onClick={status.refresh} title="지금 확인">
            <RefreshCw />
            다시 확인
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-6" role="status" aria-live="polite">
        <p className="font-semibold">
          {status.light === 'error' ? '연결 상태를 확인하지 못했어요' : status.running ? '실행기가 자동 발행을 처리하고 있어요'
            : status.online ? '연결 완료! 실행기에서 시작 버튼을 눌러 주세요'
              : status.local ? '열려 있는 실행기를 찾았어요' : '실행기 창이 열려 있어도 계정 연결이 필요해요'}
        </p>
        <p className="mt-1 text-muted-foreground">
          {status.light === 'error' ? status.note : status.running ? '다음 단계에서 블로그와 발행할 글을 준비하세요. PC와 실행기는 켜 두세요.'
            : status.online ? 'PC의 닥터보이스 창에서 [자동 발행 시작]을 누르세요. 실행 상태가 확인되면 1단계가 완료됩니다.'
              : status.local ? '연결 후 실행기 창에서 [자동 발행 시작]을 눌러 주세요.'
                : '아직 서버에 연결 신호가 도착하지 않았습니다. 실행기가 닫혀 있거나, 로그인 전이거나, 브라우저가 연결을 막은 경우일 수 있습니다.'}
        </p>
      </div>

      {!status.online && !status.local && status.light !== 'error' && (
        <div className="rounded-xl border p-4 text-sm">
          <h3 className="font-semibold">이미 실행기 창을 열었다면</h3>
          <ol className="mt-2 list-decimal space-y-2 pl-5 leading-6">
            <li>이 페이지를 열어 두고, 브라우저에서 로컬 네트워크 접근을 물으면 <b>허용</b>하세요.</li>
            <li>자동 연결이 안 되면 실행기에 <b>이 사이트의 이메일{email ? ` (${email})` : ''}과 비밀번호</b>를 입력하세요. 네이버 비밀번호가 아닙니다. 서버 주소는 기본값 그대로 두세요.</li>
            <li>실행기에서 <b>자동 발행 시작</b>을 누른 뒤 여기서 <b>다시 확인</b>을 누르세요. 연결 확인에는 약 15초가 걸릴 수 있습니다.</li>
          </ol>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">실행기 제목 옆에 버전이나 [업데이트 확인] 버튼이 없다면 아래 최신 실행기를 설치하세요. 기존 창을 종료한 뒤 새 실행기를 열어 주세요.</p>
        </div>
      )}

      {status.online ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {status.note || '대기 중'}
          {status.version && <> · 실행기 v<span className="tabular-nums">{status.version}</span></>}
          {status.devices[0]?.label && <> · {status.devices[0].label}</>}
        </p>
      ) : (
        <div className="space-y-1 text-xs leading-relaxed text-muted-foreground">
          <p>
            여기서 담은 글은 서버에 쌓입니다. PC 실행기를 켜 두면 순서대로 네이버에 등록하고,
            이 창을 닫아도 계속됩니다. 크롬 확장 프로그램은 필요하지 않습니다.
          </p>
          <p>
            <b>최신 실행기는 이 페이지에서 자동 연결을 시도합니다.</b> 연결되지 않으면 위 안내대로 로그인하세요.
            브라우저가 &lsquo;로컬 네트워크 기기 접근&rsquo;을 물으면 <b>허용</b>을 눌러 주세요.
          </p>
          {status.latest && <p>최신 버전 v<span className="tabular-nums">{status.latest}</span></p>}
        </div>
      )}

      {!status.online && status.local && (
        <div className="rounded-lg border bg-muted/40 p-2.5 text-xs leading-relaxed">
          {status.light === 'other' ? (
            <>
              이 PC의 실행기는 <b>{status.local.email}</b> 계정에 연결돼 있습니다.
              <Button size="sm" variant="outline" className="mt-2 w-full" onClick={status.pairNow} disabled={status.pairing}>
                지금 로그인한 계정으로 바꾸기
              </Button>
            </>
          ) : status.pairError ? (
            <>
              <span className="text-danger">{status.pairError}</span>
              <Button size="sm" variant="outline" className="mt-2 w-full" onClick={status.pairNow} disabled={status.pairing}>
                다시 연결
              </Button>
            </>
          ) : (
            <>이 PC의 실행기를 찾았습니다 · {status.pairing ? '이 계정으로 연결하는 중…' : '곧 연결됩니다'}</>
          )}
        </div>
      )}

      {status.updateAvailable && (
        <p className="flex items-start gap-1.5 text-xs text-warning">
          <ArrowUpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          새 버전 v{status.latest} 이 있습니다. 실행기에서 <b>업데이트 확인</b>을 누르면 바로 설치됩니다.
        </p>
      )}

      {!compact && !status.online && !status.local && (
        <ol className="list-decimal space-y-1 pl-5 text-xs leading-relaxed text-muted-foreground">
          <li>설치 파일을 받아 두 번 클릭합니다.</li>
          <li>&quot;Windows의 PC 보호&quot;가 뜨면 <b>추가 정보 → 실행</b>.</li>
          <li>설치가 끝나면 실행기를 열고 이 페이지로 돌아와 연결을 확인하세요.</li>
          <li>실행기 창의 <b>자동 발행 시작</b>을 누릅니다.</li>
        </ol>
      )}

      {((!status.online && !status.local) || status.updateAvailable) && (
        <a href={LAUNCHER_DOWNLOAD_URL} download>
          <Button size="sm" variant="outline" className="w-full">
            <Download />
            {status.latest ? `최신 Windows 실행기 설치 · v${status.latest}` : 'Windows 실행기 설치'}
          </Button>
        </a>
      )}
      {!inline && <Link href="/dashboard/launcher" className="block text-center text-xs text-muted-foreground underline">
        {status.online ? '실행기 사용 안내' : '설치가 막히면 자세한 안내 보기'}
      </Link>}
    </div>
  )
}

/** 발행 대상 블로그 목록(캠페인에 등록한 네이버 블로그). 마지막 선택을 기억한다. */
export function useTargetBlog() {
  const [blogs, setBlogs] = useState<AgentBlogSummary[]>([])
  const [blogRefId, setBlogRefId] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await campaignAPI.agentSummary()
      setBlogs(rows)
      setBlogRefId((current) => {
        if (current && rows.some((b) => b.blog_ref_id === current)) return current
        let saved: string | null = null
        try { saved = localStorage.getItem(BLOG_KEY) } catch { /* private mode */ }
        if (saved && rows.some((b) => b.blog_ref_id === saved)) return saved
        return rows[0]?.blog_ref_id || ''
      })
    } catch {
      setBlogs([])
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { load() }, [load])

  const choose = useCallback((id: string) => {
    setBlogRefId(id)
    try { localStorage.setItem(BLOG_KEY, id) } catch { /* private mode */ }
  }, [])

  const selected = blogs.find((b) => b.blog_ref_id === blogRefId) || null
  return { blogs, blogRefId, blogId: selected?.naver_blog_id || '', selected, loading, choose, refresh: load }
}

/** useTargetBlog 의 값을 그대로 받는 표시용 선택기(상태는 부모가 가진다). */
export function TargetBlogSelect({ blogs, value, onChange, loading, onRefresh, className }: {
  blogs: AgentBlogSummary[]
  value: string
  onChange: (id: string) => void
  loading?: boolean
  onRefresh?: () => void
  className?: string
}) {
  const blogRefId = value
  const choose = onChange
  const refresh = onRefresh
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <select
        aria-label="발행할 블로그"
        value={blogRefId}
        onChange={(e) => choose(e.target.value)}
        disabled={loading || blogs.length === 0}
        className="h-9 w-full rounded-lg border border-input bg-card px-3 text-sm"
      >
        {blogs.length === 0 && <option value="">{loading ? '블로그 확인 중…' : '등록된 블로그 없음'}</option>}
        {blogs.map((b) => (
          <option key={b.blog_ref_id} value={b.blog_ref_id}>
            {b.label || b.naver_blog_id} ({b.naver_blog_id})
          </option>
        ))}
      </select>
      <Button variant="ghost" size="sm" className="w-8 px-0" onClick={refresh} title="블로그 목록 새로고침">
        <RefreshCw />
      </Button>
    </div>
  )
}
