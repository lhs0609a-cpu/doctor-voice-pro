'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ExtensionStatusCard,
  LATEST_EXTENSION_VERSION,
  EXTENSION_DOWNLOAD_URL,
  AUTO_UPDATE_INSTALLER_URL,
} from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { cn } from '@/lib/utils'
import {
  Download,
  Zap,
  CheckCircle2,
  Circle,
  RefreshCw,
  AlertTriangle,
  ArrowLeft,
} from 'lucide-react'

type Method = 'auto' | 'manual'

const AUTO_STEPS = [
  {
    title: '설치 파일 받기',
    body: '아래 버튼을 누르면 doctorvoice-auto-update-install.bat 파일이 다운로드됩니다. 크롬이 "이 파일은 일반적으로 다운로드되지 않는 파일입니다"라고 물으면 계속을 눌러 저장하세요.',
    action: { label: '설치 파일 받기 (.bat)', href: AUTO_UPDATE_INSTALLER_URL, icon: Download },
  },
  {
    title: '더블클릭해서 실행',
    body: '다운로드 폴더에서 받은 파일을 더블클릭합니다. "Windows의 PC 보호" 창이 뜨면 추가 정보를 누르고 실행을 선택하세요.',
  },
  {
    title: '관리자 승인에서 "예"',
    body: '사용자 계정 컨트롤 창이 뜹니다. 예를 누르면 자동으로 등록됩니다. 검은 창이 잠깐 떴다가 닫힙니다.',
  },
  {
    title: '크롬 완전히 껐다 켜기',
    body: '크롬 창을 전부 닫고 다시 엽니다. 작업 표시줄에 크롬이 남아 있으면 안 됩니다. 다시 열면 확장 프로그램이 자동으로 설치돼 있습니다.',
  },
  {
    title: '이 페이지 새로고침',
    body: '위쪽 상태가 "실시간 연동 중"으로 바뀌면 끝입니다.',
  },
]

const MANUAL_STEPS = [
  {
    title: '압축 파일 받기',
    body: `doctorvoice-extension-v${LATEST_EXTENSION_VERSION}.zip 을 내려받습니다.`,
    action: { label: `.zip 받기 (v${LATEST_EXTENSION_VERSION})`, href: EXTENSION_DOWNLOAD_URL, icon: Download },
  },
  {
    title: '압축 풀기',
    body: '받은 파일을 우클릭 → 압축 풀기. 폴더 위치를 기억해 두세요. 이 폴더를 지우면 확장이 꺼지므로 바탕화면보다는 문서 폴더처럼 안 지우는 곳에 두세요.',
  },
  {
    title: '크롬 확장 프로그램 페이지 열기',
    body: '주소창에 chrome://extensions 를 입력해 엽니다. (주소창에 붙여넣어야 합니다. 검색창이 아닙니다)',
  },
  {
    title: '개발자 모드 켜기',
    body: '오른쪽 위 개발자 모드 스위치를 켭니다.',
  },
  {
    title: '압축해제된 확장 프로그램 로드',
    body: '왼쪽 위에 나타난 압축해제된 확장 프로그램을 로드합니다 버튼을 누르고, 2번에서 압축을 푼 폴더를 선택합니다. (폴더 안이 아니라 폴더 자체를 선택)',
  },
  {
    title: '이 페이지 새로고침',
    body: '위쪽 상태가 "실시간 연동 중"으로 바뀌면 끝입니다.',
  },
]

const TROUBLES = [
  {
    q: '설치했는데도 계속 "연결 안 됨"으로 나옵니다',
    a: '이 페이지를 새로고침해 보세요. 그래도 안 되면 chrome://extensions 에서 닥터보이스 프로가 켜져 있는지(스위치가 파란색인지) 확인하세요. 크롬이 아닌 다른 브라우저(엣지, 웨일, 사파리)에서는 동작하지 않습니다.',
  },
  {
    q: '.bat 파일을 실행했는데 아무 일도 안 일어납니다',
    a: '관리자 권한이 없는 계정일 수 있습니다. 파일을 우클릭 → 관리자 권한으로 실행을 눌러 보세요. 회사 PC라 정책이 막혀 있다면 아래 수동 설치로 진행하시면 됩니다.',
  },
  {
    q: '"조직에서 관리하는 브라우저"라고 뜹니다',
    a: '정상입니다. 자동 업데이트 설치는 크롬 정책으로 등록하는 방식이라 이 문구가 나타납니다. 다른 기능에는 영향이 없습니다.',
  },
  {
    q: '예전에 설치한 확장이 있습니다',
    a: '자동 업데이트로 새로 설치하기 전에 chrome://extensions 에서 기존 닥터보이스 확장을 먼저 삭제하세요. 둘이 같이 있으면 충돌합니다.',
  },
  {
    q: '수동 설치 후 크롬을 껐다 켜니 확장이 사라졌습니다',
    a: '압축을 푼 폴더를 옮기거나 지우면 확장이 사라집니다. 폴더를 원래 자리에 두거나, 자동 업데이트 방식으로 다시 설치하세요.',
  },
]

function StepList({ steps, done }: { steps: typeof AUTO_STEPS; done: boolean }) {
  return (
    <ol className="space-y-3">
      {steps.map((s, i) => {
        const Icon = s.action?.icon
        return (
          <li key={i} className="flex gap-3">
            <span
              className={cn(
                'mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-semibold',
                done ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground',
              )}
            >
              {done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
            </span>
            <div className="min-w-0 flex-1 pb-1">
              <p className="text-sm font-medium">{s.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{s.body}</p>
              {s.action && (
                <a href={s.action.href} className="mt-2 inline-block">
                  <Button size="sm">
                    {Icon && <Icon />}
                    {s.action.label}
                  </Button>
                </a>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export default function ExtensionGuidePage() {
  const { connected, refresh } = useExtensionStatus()
  const [method, setMethod] = useState<Method>('auto')

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm" className="w-8 px-0">
            <ArrowLeft />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-semibold">확장 프로그램 설치</h1>
          <p className="text-sm text-muted-foreground">
            글 자동작성과 자동발행은 크롬 확장 프로그램이 있어야 동작합니다
          </p>
        </div>
      </div>

      {/* 현재 상태 */}
      <ExtensionStatusCard />

      {connected ? (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 flex-none text-emerald-600" />
            <div className="text-sm">
              <p className="font-medium">설치가 끝났습니다</p>
              <p className="text-muted-foreground">
                이제 원스톱 자동화로 돌아가서 글 생성을 시작하시면 됩니다.
              </p>
            </div>
            <Link href="/dashboard/one-stop" className="ml-auto flex-none">
              <Button size="sm">원스톱 자동화로</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* 설치 방식 선택 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">어떻게 설치할까요?</CardTitle>
              <CardDescription>
                대부분은 자동 업데이트 설치가 편합니다. 회사 PC라 관리자 권한이 막혀 있으면 수동
                설치를 쓰세요.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setMethod('auto')}
                  className={cn(
                    'rounded-lg border p-3 text-left transition',
                    method === 'auto' ? 'border-primary bg-accent' : 'hover:bg-accent/50',
                  )}
                >
                  <div className="flex items-center gap-1.5 text-sm font-semibold">
                    <Zap className="h-4 w-4" />
                    자동 업데이트 설치
                    <span className="ml-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      권장
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    파일 하나 실행하면 끝. 새 버전이 나와도 알아서 갱신됩니다.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setMethod('manual')}
                  className={cn(
                    'rounded-lg border p-3 text-left transition',
                    method === 'manual' ? 'border-primary bg-accent' : 'hover:bg-accent/50',
                  )}
                >
                  <div className="flex items-center gap-1.5 text-sm font-semibold">
                    <Download className="h-4 w-4" />
                    수동 설치
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    관리자 권한이 필요 없습니다. 대신 새 버전마다 다시 받아야 합니다.
                  </p>
                </button>
              </div>

              <div className="border-t pt-4">
                <StepList steps={method === 'auto' ? AUTO_STEPS : MANUAL_STEPS} done={false} />
              </div>

              <div className="flex items-center gap-2 border-t pt-4">
                <Button size="sm" variant="outline" onClick={refresh}>
                  <RefreshCw />
                  설치했어요, 다시 확인
                </Button>
                <span className="text-xs text-muted-foreground">
                  버튼을 눌러도 안 바뀌면 페이지를 새로고침하세요
                </span>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* 문제 해결 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            잘 안 될 때
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {TROUBLES.map((t, i) => (
            <div key={i} className="flex gap-2.5">
              <Circle className="mt-1 h-2 w-2 flex-none fill-muted-foreground text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">{t.q}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{t.a}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
