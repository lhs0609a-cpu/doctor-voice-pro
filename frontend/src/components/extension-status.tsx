'use client'

import { useExtensionStatus, type ExtLight } from '@/lib/use-extension-status'
import { Button } from '@/components/ui/button'
import { Download, RefreshCw, Wifi, WifiOff, ArrowUpCircle, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

// 최신 확장 프로그램 버전/다운로드 (릴리스 시 이 두 값 + version.json 갱신)
export const LATEST_EXTENSION_VERSION = '16.0.1'
export const EXTENSION_DOWNLOAD_URL = `/extension/doctorvoice-extension-v${LATEST_EXTENSION_VERSION}.zip`
// 자동 업데이트 원클릭 설치(관리자 정책). 한 번 설치하면 이후 새 버전은 크롬이 자동 갱신.
export const AUTO_UPDATE_INSTALLER_URL = '/extension/doctorvoice-auto-update-install.bat'

const LIGHT_META: Record<ExtLight, { color: string; ring: string; label: string }> = {
  connected: { color: 'bg-emerald-500', ring: 'bg-emerald-400', label: '실시간 연동 중' },
  update: { color: 'bg-amber-500', ring: 'bg-amber-400', label: '업데이트 필요' },
  disconnected: { color: 'bg-rose-500', ring: 'bg-rose-400', label: '연결 안 됨' },
  checking: { color: 'bg-gray-400', ring: 'bg-gray-300', label: '확인 중' },
}

function Light({ light, size = 'sm' }: { light: ExtLight; size?: 'sm' | 'lg' }) {
  const m = LIGHT_META[light]
  const dot = size === 'lg' ? 'h-3 w-3' : 'h-2.5 w-2.5'
  return (
    <span className={cn('relative inline-flex', dot)}>
      {(light === 'connected' || light === 'update') && (
        <span className={cn('absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping', m.ring)} />
      )}
      <span className={cn('relative inline-flex rounded-full', dot, m.color)} />
    </span>
  )
}

// ── 컴팩트: 상단 네비게이션용 알약 ──────────────────────────────
export function ExtensionStatusBadge({ className }: { className?: string }) {
  const { light, version } = useExtensionStatus()
  const m = LIGHT_META[light]
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
        light === 'connected' && 'border-emerald-200 bg-emerald-50 text-emerald-700',
        light === 'update' && 'border-amber-200 bg-amber-50 text-amber-700',
        light === 'disconnected' && 'border-rose-200 bg-rose-50 text-rose-700',
        light === 'checking' && 'border-gray-200 bg-gray-50 text-gray-500',
        className,
      )}
      title={version ? `확장 프로그램 v${version} · ${m.label}` : m.label}
    >
      <Light light={light} />
      <span className="hidden sm:inline">{m.label}</span>
      {version && <span className="tabular-nums opacity-70">v{version}</span>}
    </div>
  )
}

// ── 풀: 카드형 상태 패널 (버전 + 업데이트 + 설치 안내) ────────────
export function ExtensionStatusCard({ className }: { className?: string }) {
  const { light, connected, version, latest, updateAvailable, downloadUrl, notes, refresh } =
    useExtensionStatus()
  const m = LIGHT_META[light]

  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        light === 'connected' && 'border-emerald-200 bg-emerald-50/50',
        light === 'update' && 'border-amber-200 bg-amber-50/50',
        light === 'disconnected' && 'border-rose-200 bg-rose-50/50',
        light === 'checking' && 'border-gray-200 bg-gray-50',
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Light light={light} size="lg" />
          <div>
            <div className="flex items-center gap-2 font-semibold">
              {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
              확장 프로그램 {m.label}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {version ? (
                <>
                  현재 <b className="tabular-nums">v{version}</b>
                  {updateAvailable && latest && (
                    <> → 최신 <b className="tabular-nums text-amber-600">v{latest}</b></>
                  )}
                  {!updateAvailable && connected && <span className="text-emerald-600"> · 최신 버전</span>}
                </>
              ) : (
                <>최신 버전 v{LATEST_EXTENSION_VERSION}</>
              )}
            </div>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={refresh} title="새로고침">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* 업데이트 있음 */}
      {updateAvailable && (
        <div className="mt-3 rounded-lg bg-white/70 p-3">
          {notes && <p className="mb-2 text-xs text-amber-800">{notes}</p>}
          <a href={downloadUrl || EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer">
            <Button size="sm" className="w-full gap-2 bg-amber-600 hover:bg-amber-700">
              <ArrowUpCircle className="h-4 w-4" />
              새 버전 다운로드 후 폴더 교체
            </Button>
          </a>
          <p className="mt-2 text-[11px] leading-relaxed text-amber-700">
            다운로드 → 압축 해제 → chrome://extensions 에서 기존 폴더를 새 폴더로 교체(또는 새로고침)
          </p>
          <a
            href={AUTO_UPDATE_INSTALLER_URL}
            className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700 hover:underline"
          >
            <Zap className="h-3 w-3" />
            매번 이렇게 하기 번거롭다면 → 자동 업데이트로 전환
          </a>
        </div>
      )}

      {/* 연결 안 됨 → 설치 유도 (자동 업데이트를 권장 옵션으로) */}
      {light === 'disconnected' && (
        <div className="mt-3 space-y-3">
          <AutoUpdateCallout />
          <div className="rounded-lg bg-white/70 p-3">
            <a href={EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer">
              <Button size="sm" variant="outline" className="w-full gap-2">
                <Download className="h-4 w-4" />
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
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700 hover:underline"
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
    <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
      <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-emerald-800">
        <Zap className="h-4 w-4" />
        자동 업데이트로 설치 (권장)
      </div>
      <p className="mb-2.5 text-[11px] leading-relaxed text-emerald-700">
        한 번만 설치하면 이후 새 버전을 크롬이 알아서 업데이트합니다. 다시 다운로드할 필요가 없습니다.
      </p>
      <a href={AUTO_UPDATE_INSTALLER_URL}>
        <Button size="sm" className="w-full gap-2 bg-emerald-600 hover:bg-emerald-700">
          <Download className="h-4 w-4" />
          설치 파일 받기 (.bat)
        </Button>
      </a>
      <p className="mt-2 text-[11px] leading-relaxed text-emerald-700/80">
        받은 파일을 더블클릭 → 관리자 승인 &ldquo;예&rdquo; → 크롬 재시작. 그게 끝입니다.
      </p>
    </div>
  )
}
