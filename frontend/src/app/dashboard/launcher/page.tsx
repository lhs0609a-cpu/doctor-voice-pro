'use client'

// PC 실행기 설치 안내. 예전 크롬 확장 설치 안내(/dashboard/extension)를 대신한다 —
// 압축 풀기도, 개발자 모드도 없다. 설치 파일 하나로 끝나고 업데이트는 스스로 한다.

import Link from 'next/link'
import { ArrowLeft, CheckCircle2, Download, Laptop, ShieldAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LAUNCHER_DOWNLOAD_URL, LauncherCard } from '@/components/launcher/launcher-card'

const STEPS = [
  {
    title: '설치 파일 받기',
    body: '아래 버튼을 누르면 DoctorVoiceAutopilotSetup.exe 가 내려받아집니다. 압축 파일이 아니라 설치 파일이라 압축을 풀 필요가 없습니다.',
  },
  {
    title: '두 번 클릭해서 설치',
    body: '“Windows의 PC 보호” 창이 뜨면 추가 정보 → 실행을 누르세요. 관리자 권한은 필요 없고, 설치는 몇 초면 끝납니다.',
  },
  {
    title: '홈페이지 계정 연결 (저절로 됩니다)',
    body: '실행기를 켜면 브라우저가 열리면서 이 계정에 연결됩니다. 로그인돼 있으면 누를 것도, 칠 것도 없습니다. 로그인 화면이 뜨면 한 번만 로그인하면 그대로 연결됩니다. 한 번 연결한 PC는 다음부터 켜기만 하면 됩니다.',
  },
  {
    title: '자동 발행 시작 누르기',
    body: '실행기가 서버에서 대기 중인 글을 가져와 네이버에 등록합니다. 네이버 로그인이나 보안문자는 실행기가 연 크롬 창에서 한 번만 처리하면 유지됩니다.',
  },
  {
    title: '켜 두기',
    body: '예약 등록이 끝날 때까지 PC와 실행기를 켜 두세요. PC를 꺼도 이미 네이버에 걸어둔 예약은 그대로 발행됩니다.',
  },
]

export default function LauncherPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link href="/dashboard/one-stop" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          원스톱 자동화로 돌아가기
        </Link>
        <h1 className="mt-2 flex items-center gap-2 text-2xl font-semibold">
          <Laptop className="h-6 w-6 text-muted-foreground" />
          PC 실행기 연결 안내
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          네이버에 글을 올리는 일은 이 프로그램이 합니다. 크롬 확장 프로그램은 더 이상 쓰지 않습니다.
        </p>
      </div>

      <LauncherCard inline compact />

      <Card>
        <CardHeader>
          <CardTitle>설치 순서</CardTitle>
          <CardDescription>다섯 단계, 몇 분이면 끝납니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {STEPS.map((step, index) => (
            <div key={step.title} className="flex gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium">{step.title}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </div>
          ))}
          <a href={LAUNCHER_DOWNLOAD_URL} download className="block pt-2">
            <Button className="w-full" size="lg">
              <Download />
              Windows 실행기 설치 파일 받기
            </Button>
          </a>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-4 w-4 text-warning" />
            경고 창이 뜨는 이유
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-[13px] leading-relaxed text-muted-foreground">
          <p>
            코드 서명 인증서를 아직 붙이지 않아서 Windows가 처음 보는 프로그램이라고 경고합니다.
            바이러스가 있다는 뜻이 아니라 &lsquo;만든 사람을 확인할 수 없다&rsquo;는 뜻입니다.
            <b className="text-foreground"> 추가 정보 → 실행</b>으로 넘어가세요.
          </p>
          <p className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            새 버전은 실행기가 스스로 확인해 설치합니다. 다시 받으러 올 필요가 없습니다.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
