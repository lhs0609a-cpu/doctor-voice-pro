'use client'

import Link from 'next/link'

import { useExtensionStatus, type ExtLight } from '@/lib/use-extension-status'
import { Button } from '@/components/ui/button'
import { Download, RefreshCw, Wifi, WifiOff, ArrowUpCircle, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

// 최신 확장 프로그램 버전/다운로드 (릴리스 시 이 두 값 + version.json 갱신)
export const LATEST_EXTENSION_VERSION = '16.1.0'
export const EXTENSION_DOWNLOAD_URL = `/extension/doctorvoice-extension-v${LATEST_EXTENSION_VERSION}.zip`
// 자동 업데이트 원클릭 설치(관리자 정책). 한 번 설치하면 이후 새 버전은 크롬이 자동 갱신.
export const AUTO_UPDATE_INSTALLER_URL = '/extension/doctorvoice-auto-update-install.bat'

const LIGHT_META: Record<ExtLight, { dot: string; pill: string; label: string }> = {
  connected: { dot: 'bg-success', pill: 'pill-ok', label: '실시간 연동 중' },
  update: { dot: 'bg-warning', pill: 'pill-warn', label: '업데이트 필요' },
  disconnected: { dot: 'bg-danger', pill: 'pill-danger', label: '연결 안 됨' },
  checking: { dot: 'bg-muted-foreground', pill: 'pill-muted', label: '확인 중' },
}

function Light({ light, size = 'sm' }: { light: ExtLight; size?: 'sm' | 'lg' }) {
  const m = LIGHT_META[light]
  const dot = size === 'lg' ? 'h-3 w-3' : 'h-2.5 w-2.5'
  return (
    <span className={cn('relative inline-flex', dot)}>
      {(light === 'connected' || light === 'update') && (
        <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-50', m.dot)} />
      )}
      <span className={cn('relative inline-flex rounded-full', dot, m.dot)} />
    </span>
  )
}

// ── 컴팩트: 상단 네비게이션용 알약 ──────────────────────────────
export function ExtensionStatusBadge({ className }: { className?: string }) {
  const { light, version } = useExtensionStatus()
  const m = LIGHT_META[light]
  const body = (
    <>
      <Light light={light} />
      <span className="hidden sm:inline">{m.label}</span>
      {version && <span className="tabular-nums opacity-70">v{version}</span>}
    </>
  )
  const cls = cn('pill', m.pill, 'gap-1.5 px-2.5 py-1', className)

  // 연결이 안 됐거나 업데이트가 필요하면 눌러서 바로 설치 안내로 갈 수 있게 한다
  if (light === 'disconnected' || light === 'update') {
    return (
      <Link href="/dashboard/extension" className={cn(cls, 'cursor-pointer hover:opacity-80')} title="설치 안내 보기">
        {body}
      </Link>
    )
  }
  return (
    <div className={cls} title={version ? `확장 프로그램 v${version} · ${m.label}` : m.label}>
      {body}
    </div>
  )
}

// ── 풀: 카드형 상태 패널 (버전 + 업데이트 + 설치 안내) ────────────
export function ExtensionStatusCard({ className }: { className?: string }) {
  const { light, connected, version, latest, updateAvailable, downloadUrl, notes, refresh } =
    useExtensionStatus()
  const m = LIGHT_META[light]

  return (
    <div className={cn('surface p-4', className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Light light={light} size="lg" />
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              {connected ? <Wifi className="h-4 w-4 text-muted-foreground" /> : <WifiOff className="h-4 w-4 text-muted-foreground" />}
              확장 프로그램 {m.label}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {version ? (
                <>
                  현재 <b className="tabular-nums text-foreground">v{version}</b>
                  {updateAvailable && latest && (
                    <> → 최신 <b className="tabular-nums text-warning">v{latest}</b></>
                  )}
                  {!updateAvailable && connected && <span className="text-success"> · 최신 버전</span>}
                </>
              ) : (
                <>최신 버전 <span className="tabular-nums">v{LATEST_EXTENSION_VERSION}</span></>
              )}
            </div>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="w-8 px-0" onClick={refresh} title="새로고침">
          <RefreshCw />
        </Button>
      </div>

      {/* 업데이트 있음 */}
      {updateAvailable && (
        <div className="mt-3 border-t pt-3">
          {notes && <p className="mb-2 text-xs text-muted-foreground">{notes}</p>}
          <a href={downloadUrl || EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer">
            <Button size="sm" className="w-full">
              <ArrowUpCircle />
              새 버전 다운로드 후 폴더 교체
            </Button>
          </a>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            다운로드 → 압축 해제 → chrome://extensions 에서 기존 폴더를 새 폴더로 교체(또는 새로고침)
          </p>
          <a
            href={AUTO_UPDATE_INSTALLER_URL}
            className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-primary hover:underline"
          >
            <Zap className="h-3 w-3" />
            매번 이렇게 하기 번거롭다면 → 자동 업데이트로 전환
          </a>
        </div>
      )}

      {/* 연결 안 됨 → 설치 유도 (자동 업데이트를 권장 옵션으로) */}
      {light === 'disconnected' && (
        <div className="mt-3 space-y-3 border-t pt-3">
          <AutoUpdateCallout />
          <div>
            <a href={EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer">
              <Button size="sm" variant="outline" className="w-full">
                <Download />
                수동 설치 (.zip)
              </Button>
            </a>
            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
              이미 설치했다면, 이 페이지를 새로고침하거나 크롬에서 확장 프로그램이 켜져 있는지 확인하세요.
            </p>
          </div>
        </div>
      )}

      {/* 정상 연결 상태 → 아직 수동 설치라면 자동 업데이트로 전환 유도 */}
      {connected && !updateAvailable && (
        <div className="mt-3">
          <a
            href={AUTO_UPDATE_INSTALLER_URL}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-primary hover:underline"
          >
            <Zap className="h-3 w-3" />
            자동 업데이트로 전환 (다시 다운로드 안 해도 됨) →
          </a>
        </div>
      )}
    </div>
  )
}

// ── 자동 업데이트 원클릭 설치 안내 ────────────────────────────
// 정책(ExtensionInstallForcelist) 설치로 이후 새 버전을 크롬이 자동 갱신한다.
function AutoUpdateCallout() {
  return (
    <div className="rounded-lg bg-accent p-3">
      <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-accent-foreground">
        <Zap className="h-4 w-4" />
        자동 업데이트로 설치 (권장)
      </div>
      <p className="mb-2.5 text-[11px] leading-relaxed text-muted-foreground">
        한 번만 설치하면 이후 새 버전을 크롬이 알아서 업데이트합니다. 다시 다운로드할 필요가 없습니다.
      </p>
      <a href={AUTO_UPDATE_INSTALLER_URL}>
        <Button size="sm" className="w-full">
          <Download />
          설치 파일 받기 (.bat)
        </Button>
      </a>
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
        받은 파일을 더블클릭 → 관리자 승인 &ldquo;예&rdquo; → 크롬 재시작. 그게 끝입니다.
      </p>
    </div>
  )
}
