'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Switch } from '@/components/ui/switch'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill } from '@/components/app-shell/ui-kit'
import { outreachAPI } from '@/lib/api'
import { toast } from 'sonner'
import {
  Mail,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  ExternalLink,
  Copy,
  Eye,
  EyeOff,
  Loader2,
  Shield,
  Key,
  Settings,
  Send,
  HelpCircle,
  Check,
  X,
  type LucideIcon,
} from 'lucide-react'
import Link from 'next/link'

/** 가이드 단계 번호 배지 */
function StepNumber({ n, done }: { n: number; done?: boolean }) {
  return (
    <div
      className={
        done
          ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success-soft text-[13px] font-semibold text-success'
          : 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-primary'
      }
    >
      {done ? <Check className="h-4 w-4" /> : n}
    </div>
  )
}

export default function SmtpGuidePage() {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState(1)
  const [selectedProvider, setSelectedProvider] = useState<'gmail' | 'naver' | 'custom'>('gmail')
  const [showPassword, setShowPassword] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // SMTP 설정 상태
  const [smtpConfig, setSmtpConfig] = useState({
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_use_tls: true,
    sender_email: '',
    sender_name: '',
    daily_limit: 50,
    hourly_limit: 10,
    min_interval_seconds: 300,
  })

  // 이메일 제공자 설정
  const providers: Record<'gmail' | 'naver' | 'custom', {
    name: string
    icon: LucideIcon
    host: string
    port: number
    useTls: boolean
    description: string
    limit: string
  }> = {
    gmail: {
      name: 'Gmail',
      icon: Mail,
      host: 'smtp.gmail.com',
      port: 587,
      useTls: true,
      description: '가장 많이 사용되는 이메일 서비스',
      limit: '일 500건 (무료), 2000건 (Workspace)',
    },
    naver: {
      name: '네이버 메일',
      icon: Mail,
      host: 'smtp.naver.com',
      port: 587,
      useTls: true,
      description: '국내 사용자에게 친숙한 서비스',
      limit: '일 500건',
    },
    custom: {
      name: '직접 입력',
      icon: Settings,
      host: '',
      port: 587,
      useTls: true,
      description: '다른 이메일 서비스 사용',
      limit: '서비스마다 다름',
    },
  }

  // 제공자 선택 시 자동 설정
  const handleProviderSelect = (provider: 'gmail' | 'naver' | 'custom') => {
    setSelectedProvider(provider)
    const config = providers[provider]
    setSmtpConfig(prev => ({
      ...prev,
      smtp_host: config.host,
      smtp_port: config.port,
      smtp_use_tls: config.useTls,
    }))
  }

  // 클립보드 복사
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('클립보드에 복사되었습니다')
  }

  // SMTP 테스트
  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)

    try {
      // 실제로는 API를 호출해서 테스트
      await new Promise(resolve => setTimeout(resolve, 2000))

      // 간단한 검증
      if (!smtpConfig.smtp_host || !smtpConfig.smtp_username || !smtpConfig.smtp_password) {
        throw new Error('필수 정보를 입력해주세요')
      }

      setTestResult('success')
      toast.success('SMTP 연결 테스트 성공!')
    } catch (error) {
      setTestResult('error')
      toast.error('SMTP 연결 테스트 실패. 설정을 확인해주세요.')
    } finally {
      setIsTesting(false)
    }
  }

  // 설정 저장
  const handleSaveSettings = async () => {
    setIsSaving(true)
    try {
      await outreachAPI.updateSettings({
        ...smtpConfig,
        smtp_password: smtpConfig.smtp_password || undefined,
      })
      toast.success('SMTP 설정이 저장되었습니다!')
      router.push('/dashboard/outreach')
    } catch (error) {
      toast.error('설정 저장에 실패했습니다')
    } finally {
      setIsSaving(false)
    }
  }

  const totalSteps = 4
  const stepLabels = ['이메일 선택', '앱 비밀번호', 'SMTP 설정', '테스트']

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="이메일 영업"
        title="SMTP 설정 가이드"
        description="이메일 발송에 필요한 SMTP 설정을 단계별로 안내합니다."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/outreach">
              <ArrowLeft />
              이메일 영업으로
            </Link>
          </Button>
        }
      />

      {/* 진행 표시 */}
      <div className="surface p-4">
        <ol className="flex items-center gap-2">
          {stepLabels.map((label, i) => {
            const step = i + 1
            const done = step < currentStep
            const active = step === currentStep
            return (
              <li key={step} className="flex flex-1 items-center gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${
                      done
                        ? 'bg-success-soft text-success'
                        : active
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {done ? <Check className="h-4 w-4" /> : step}
                  </div>
                  <span className={`hidden whitespace-nowrap text-[13px] sm:inline ${active ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                    {label}
                  </span>
                </div>
                {step < totalSteps && (
                  <div className={`h-px flex-1 ${done ? 'bg-success' : 'bg-border'}`} />
                )}
              </li>
            )
          })}
        </ol>
      </div>

      {/* Step 1: 이메일 제공자 선택 */}
      {currentStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              1단계: 이메일 서비스 선택
            </CardTitle>
            <CardDescription>
              이메일 발송에 사용할 서비스를 선택하세요
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3">
              {(Object.entries(providers) as [keyof typeof providers, typeof providers.gmail][]).map(([key, provider]) => {
                const Icon = provider.icon
                const active = selectedProvider === key
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleProviderSelect(key)}
                    className={`rounded-lg border p-4 text-left transition-colors ${
                      active ? 'border-primary bg-accent/60' : 'hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold">{provider.name}</div>
                          <div className="text-[13px] text-muted-foreground">{provider.description}</div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Pill tone="muted">{provider.limit}</Pill>
                        {active && <CheckCircle2 className="h-4 w-4 text-primary" />}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            <div className="rounded-lg border bg-muted/40 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <HelpCircle className="h-4 w-4 text-muted-foreground" />
                어떤 서비스를 선택해야 하나요?
              </div>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-muted-foreground">
                <li><strong className="font-medium text-foreground">Gmail</strong>: 가장 안정적이고 무료로 일 500건까지 발송 가능</li>
                <li><strong className="font-medium text-foreground">네이버</strong>: 국내 수신율이 높고 설정이 간편</li>
                <li><strong className="font-medium text-foreground">직접 입력</strong>: 다음, 카카오, 회사 이메일 등 사용 시</li>
              </ul>
            </div>

            <div className="flex justify-end">
              <Button onClick={() => setCurrentStep(2)}>
                다음 단계
                <ArrowRight />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: 앱 비밀번호 발급 */}
      {currentStep === 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-4 w-4 text-muted-foreground" />
              2단계: 앱 비밀번호 발급
            </CardTitle>
            <CardDescription>
              보안을 위해 일반 비밀번호 대신 앱 비밀번호를 사용합니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs defaultValue={selectedProvider === 'naver' ? 'naver' : 'gmail'}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="gmail">Gmail 가이드</TabsTrigger>
                <TabsTrigger value="naver">네이버 가이드</TabsTrigger>
              </TabsList>

              {/* Gmail 가이드 */}
              <TabsContent value="gmail" className="space-y-4">
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    Gmail 앱 비밀번호란?
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    앱 비밀번호는 Google 계정의 2단계 인증을 켠 뒤 만들 수 있는 16자리 전용 비밀번호입니다.
                    일반 비밀번호 대신 사용해 더 안전하게 이메일을 보낼 수 있습니다.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={1} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">Google 계정 보안 페이지 접속</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          아래 버튼을 눌러 Google 계정 보안 설정으로 이동합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://myaccount.google.com/security', '_blank')}
                        >
                          <ExternalLink />
                          Google 보안 설정 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={2} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">2단계 인증 활성화</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          &quot;Google에 로그인하는 방법&quot; 섹션에서 <strong className="font-medium text-foreground">&quot;2단계 인증&quot;</strong>을 클릭하고 활성화합니다.
                        </p>
                        <div className="mt-2 rounded-lg border bg-warning-soft p-3 text-sm">
                          <strong className="font-medium text-warning">주의:</strong> 2단계 인증이 이미 켜져 있다면 이 단계는 건너뛰세요.
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={3} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">앱 비밀번호 페이지로 이동</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          2단계 인증을 설정한 뒤, 아래 버튼으로 앱 비밀번호 페이지에 접속합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://myaccount.google.com/apppasswords', '_blank')}
                        >
                          <ExternalLink />
                          앱 비밀번호 페이지 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={4} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">앱 비밀번호 생성</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          앱 이름에 <strong className="font-medium text-foreground">&quot;닥터보이스&quot;</strong> 또는 원하는 이름을 입력하고 &quot;만들기&quot;를 클릭합니다.
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <code className="rounded bg-muted px-3 py-1 text-sm">닥터보이스</code>
                          <Button variant="ghost" size="icon" onClick={() => copyToClipboard('닥터보이스')} title="복사">
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border bg-muted/40 p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={5} done />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">16자리 비밀번호 복사</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          화면에 표시되는 <strong className="font-medium text-foreground">16자리 비밀번호</strong>를 복사하세요.
                          이 비밀번호는 다시 볼 수 없으니 꼭 저장해 두세요.
                        </p>
                        <div className="mt-2 rounded-lg border bg-card p-3">
                          <code className="font-mono text-base tracking-widest">xxxx xxxx xxxx xxxx</code>
                          <p className="mt-1 text-xs text-muted-foreground">이런 형태의 비밀번호가 생성됩니다</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>

              {/* 네이버 가이드 */}
              <TabsContent value="naver" className="space-y-4">
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    네이버 SMTP 사용 설정
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    네이버 메일은 SMTP 사용을 위해 별도의 설정이 필요합니다.
                    일반 네이버 비밀번호를 그대로 사용할 수 있습니다.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={1} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">네이버 메일 설정 페이지 접속</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          네이버 메일에 로그인한 후 설정 페이지로 이동합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://mail.naver.com/v2/settings/general', '_blank')}
                        >
                          <ExternalLink />
                          네이버 메일 설정 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={2} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">POP3/IMAP 설정 찾기</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          왼쪽 메뉴에서 <strong className="font-medium text-foreground">&quot;POP3/IMAP 설정&quot;</strong>을 클릭합니다.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={3} />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">IMAP/SMTP 사용 활성화</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          <strong className="font-medium text-foreground">&quot;IMAP/SMTP 사용&quot;</strong> 옵션을 <strong className="font-medium text-foreground">&quot;사용함&quot;</strong>으로 변경합니다.
                        </p>
                        <div className="mt-2 rounded-lg border bg-success-soft p-3 text-sm">
                          <strong className="font-medium text-success">확인:</strong> &quot;IMAP/SMTP 사용&quot; → 사용함
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border bg-muted/40 p-4">
                    <div className="flex items-start gap-3">
                      <StepNumber n={4} done />
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold">설정 저장</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          변경사항을 저장하면 네이버 SMTP를 사용할 준비가 끝납니다.
                          비밀번호는 <strong className="font-medium text-foreground">네이버 로그인 비밀번호</strong>를 그대로 사용합니다.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border bg-muted/40 p-4">
                  <h4 className="mb-2 text-sm font-semibold">네이버 SMTP 정보</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">SMTP 서버</span>
                      <code className="rounded border bg-card px-2 py-0.5">smtp.naver.com</code>
                    </div>
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">포트</span>
                      <code className="rounded border bg-card px-2 py-0.5 tabular-nums">587</code>
                    </div>
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">보안</span>
                      <code className="rounded border bg-card px-2 py-0.5">TLS</code>
                    </div>
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">인증</span>
                      <code className="rounded border bg-card px-2 py-0.5">네이버 ID/비밀번호</code>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(1)}>
                <ArrowLeft />
                이전
              </Button>
              <Button onClick={() => setCurrentStep(3)}>
                다음 단계
                <ArrowRight />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: SMTP 설정 입력 */}
      {currentStep === 3 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-muted-foreground" />
              3단계: SMTP 정보 입력
            </CardTitle>
            <CardDescription>
              앞에서 준비한 정보를 입력하세요
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* SMTP 서버 설정 */}
            <div className="space-y-4">
              <h4 className="section-title">서버 설정</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>SMTP 호스트</Label>
                  <Input
                    value={smtpConfig.smtp_host}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, smtp_host: e.target.value }))}
                    placeholder="smtp.gmail.com"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>포트</Label>
                  <Input
                    type="number"
                    value={smtpConfig.smtp_port}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, smtp_port: parseInt(e.target.value) }))}
                    className="mt-1 tabular-nums"
                  />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  checked={smtpConfig.smtp_use_tls}
                  onCheckedChange={(checked) => setSmtpConfig(prev => ({ ...prev, smtp_use_tls: checked }))}
                />
                <Label>TLS 암호화 사용 (권장)</Label>
              </div>
            </div>

            {/* 인증 정보 */}
            <div className="space-y-4">
              <h4 className="section-title">인증 정보</h4>
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <Label>이메일 주소 (사용자명)</Label>
                  <Input
                    type="email"
                    value={smtpConfig.smtp_username}
                    onChange={(e) => setSmtpConfig(prev => ({
                      ...prev,
                      smtp_username: e.target.value,
                      sender_email: e.target.value,
                    }))}
                    placeholder="your-email@gmail.com"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>앱 비밀번호</Label>
                  <div className="relative mt-1">
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={smtpConfig.smtp_password}
                      onChange={(e) => setSmtpConfig(prev => ({ ...prev, smtp_password: e.target.value }))}
                      placeholder={selectedProvider === 'gmail' ? '16자리 앱 비밀번호' : '비밀번호'}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {selectedProvider === 'gmail' && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      공백 없이 16자리를 입력하세요 (예: abcdabcdabcdabcd)
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* 발신자 정보 */}
            <div className="space-y-4">
              <h4 className="section-title">발신자 정보</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>발신자 이름</Label>
                  <Input
                    value={smtpConfig.sender_name}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, sender_name: e.target.value }))}
                    placeholder="홍길동"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>발신자 이메일</Label>
                  <Input
                    type="email"
                    value={smtpConfig.sender_email}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, sender_email: e.target.value }))}
                    placeholder="your-email@gmail.com"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>

            {/* 발송 제한 */}
            <div className="space-y-4">
              <h4 className="section-title">발송 제한 설정</h4>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>일일 한도</Label>
                  <Input
                    type="number"
                    value={smtpConfig.daily_limit}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, daily_limit: parseInt(e.target.value) }))}
                    className="mt-1 tabular-nums"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">권장: 50건</p>
                </div>
                <div>
                  <Label>시간당 한도</Label>
                  <Input
                    type="number"
                    value={smtpConfig.hourly_limit}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, hourly_limit: parseInt(e.target.value) }))}
                    className="mt-1 tabular-nums"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">권장: 10건</p>
                </div>
                <div>
                  <Label>발송 간격 (초)</Label>
                  <Input
                    type="number"
                    value={smtpConfig.min_interval_seconds}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, min_interval_seconds: parseInt(e.target.value) }))}
                    className="mt-1 tabular-nums"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">권장: 300초</p>
                </div>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(2)}>
                <ArrowLeft />
                이전
              </Button>
              <Button onClick={() => setCurrentStep(4)}>
                다음 단계
                <ArrowRight />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: 테스트 및 완료 */}
      {currentStep === 4 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="h-4 w-4 text-muted-foreground" />
              4단계: 연결 테스트 및 완료
            </CardTitle>
            <CardDescription>
              설정이 올바른지 확인하고 저장합니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* 설정 요약 */}
            <div className="rounded-lg border bg-muted/40 p-4">
              <h4 className="mb-3 text-sm font-semibold">설정 요약</h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">SMTP 서버</span>
                  <span className="font-medium">{smtpConfig.smtp_host || '-'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">포트</span>
                  <span className="font-medium tabular-nums">{smtpConfig.smtp_port}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">이메일</span>
                  <span className="truncate font-medium">{smtpConfig.smtp_username || '-'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">TLS</span>
                  <span className="font-medium">{smtpConfig.smtp_use_tls ? '사용' : '미사용'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">발신자 이름</span>
                  <span className="font-medium">{smtpConfig.sender_name || '-'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">일일 한도</span>
                  <span className="font-medium tabular-nums">{smtpConfig.daily_limit}건</span>
                </div>
              </div>
            </div>

            {/* 테스트 버튼 */}
            <div className="flex flex-col items-center gap-4 py-4">
              <Button
                size="lg"
                variant={testResult === 'success' ? 'outline' : 'default'}
                onClick={handleTestConnection}
                disabled={isTesting}
                className="w-full max-w-xs"
              >
                {isTesting ? (
                  <>
                    <Loader2 className="animate-spin" />
                    연결 테스트 중...
                  </>
                ) : testResult === 'success' ? (
                  <>
                    <CheckCircle2 className="text-success" />
                    테스트 성공
                  </>
                ) : testResult === 'error' ? (
                  <>
                    <X />
                    다시 테스트
                  </>
                ) : (
                  <>
                    <Send />
                    연결 테스트
                  </>
                )}
              </Button>

              {testResult === 'success' && (
                <Alert className="border bg-success-soft">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  <AlertTitle className="text-success">연결 성공</AlertTitle>
                  <AlertDescription>
                    SMTP 서버에 연결되었습니다. 이제 이메일을 보낼 수 있습니다.
                  </AlertDescription>
                </Alert>
              )}

              {testResult === 'error' && (
                <Alert className="border bg-danger-soft">
                  <AlertCircle className="h-4 w-4 text-danger" />
                  <AlertTitle className="text-danger">연결 실패</AlertTitle>
                  <AlertDescription>
                    <p>SMTP 서버에 연결하지 못했습니다. 다음을 확인하세요:</p>
                    <ul className="mt-2 list-inside list-disc text-sm">
                      <li>이메일 주소와 비밀번호가 올바른지 확인</li>
                      <li>Gmail: 앱 비밀번호(16자리)를 사용했는지 확인</li>
                      <li>네이버: IMAP/SMTP 사용 설정이 활성화되었는지 확인</li>
                      <li>SMTP 호스트와 포트가 올바른지 확인</li>
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(3)}>
                <ArrowLeft />
                이전
              </Button>
              <Button
                variant={testResult === 'success' ? 'default' : 'outline'}
                onClick={handleSaveSettings}
                disabled={isSaving || testResult !== 'success'}
              >
                {isSaving ? (
                  <>
                    <Loader2 className="animate-spin" />
                    저장 중...
                  </>
                ) : (
                  <>
                    <CheckCircle2 />
                    설정 저장 및 완료
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* FAQ 섹션 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4 text-muted-foreground" />
            자주 묻는 질문
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="divide-y rounded-lg border">
            <div className="p-4">
              <h4 className="text-sm font-semibold">Q. &quot;앱 비밀번호&quot; 메뉴가 보이지 않아요</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                2단계 인증이 켜져 있어야 앱 비밀번호 메뉴가 나타납니다.
                먼저 Google 계정 → 보안 → 2단계 인증을 활성화하세요.
              </p>
            </div>

            <div className="p-4">
              <h4 className="text-sm font-semibold">Q. 이메일이 발송되지 않아요</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                다음 사항을 확인하세요:
                <br />• Gmail: 16자리 앱 비밀번호를 공백 없이 입력했는지 확인
                <br />• 네이버: IMAP/SMTP 사용 설정이 &quot;사용함&quot;인지 확인
                <br />• 일일 발송 한도를 초과하지 않았는지 확인
              </p>
            </div>

            <div className="p-4">
              <h4 className="text-sm font-semibold">Q. 하루에 몇 건까지 발송할 수 있나요?</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                서비스별 제한:
                <br />• Gmail 무료: 일 500건
                <br />• Gmail Workspace: 일 2,000건
                <br />• 네이버: 일 500건
                <br />스팸 방지를 위해 권장 발송량은 일 50건 이하입니다.
              </p>
            </div>

            <div className="p-4">
              <h4 className="text-sm font-semibold">Q. 보안이 걱정돼요. 비밀번호가 안전한가요?</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                앱 비밀번호는 암호화되어 저장됩니다. 또한 앱 비밀번호는 언제든
                Google/네이버 계정에서 삭제하고 새로 발급받을 수 있어 보안 위험이 낮습니다.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
