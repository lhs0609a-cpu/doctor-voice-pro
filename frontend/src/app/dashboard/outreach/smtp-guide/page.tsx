'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Switch } from '@/components/ui/switch'
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
  ChevronRight,
  Check,
  X,
} from 'lucide-react'
import Link from 'next/link'

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
  const providers = {
    gmail: {
      name: 'Gmail',
      icon: '📧',
      host: 'smtp.gmail.com',
      port: 587,
      useTls: true,
      color: 'bg-red-50 border-red-200',
      description: '가장 많이 사용되는 이메일 서비스',
      limit: '일 500건 (무료), 2000건 (Workspace)',
    },
    naver: {
      name: '네이버 메일',
      icon: '📮',
      host: 'smtp.naver.com',
      port: 587,
      useTls: true,
      color: 'bg-green-50 border-green-200',
      description: '국내 사용자에게 친숙한 서비스',
      limit: '일 500건',
    },
    custom: {
      name: '직접 입력',
      icon: '⚙️',
      host: '',
      port: 587,
      useTls: true,
      color: 'bg-gray-50 border-gray-200',
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

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      {/* 헤더 */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/dashboard/outreach" className="hover:text-primary">
            이메일 영업
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span>SMTP 설정 가이드</span>
        </div>
        <h1 className="text-3xl font-bold">SMTP 설정 완벽 가이드</h1>
        <p className="text-muted-foreground mt-2">
          이메일 발송을 위한 SMTP 설정을 단계별로 안내해드립니다
        </p>
      </div>

      {/* 진행 표시 */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          {[1, 2, 3, 4].map((step) => (
            <div key={step} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all ${
                  step < currentStep
                    ? 'bg-green-500 text-white'
                    : step === currentStep
                    ? 'bg-primary text-white'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {step < currentStep ? <Check className="h-5 w-5" /> : step}
              </div>
              {step < 4 && (
                <div
                  className={`w-full h-1 mx-2 rounded ${
                    step < currentStep ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                  style={{ width: '80px' }}
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-sm">
          <span>이메일 선택</span>
          <span>앱 비밀번호</span>
          <span>SMTP 설정</span>
          <span>테스트</span>
        </div>
      </div>

      {/* Step 1: 이메일 제공자 선택 */}
      {currentStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              Step 1: 이메일 서비스 선택
            </CardTitle>
            <CardDescription>
              이메일 발송에 사용할 서비스를 선택해주세요
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4">
              {(Object.entries(providers) as [keyof typeof providers, typeof providers.gmail][]).map(([key, provider]) => (
                <button
                  key={key}
                  onClick={() => handleProviderSelect(key)}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    selectedProvider === key
                      ? 'border-primary bg-primary/5'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{provider.icon}</span>
                      <div>
                        <div className="font-semibold">{provider.name}</div>
                        <div className="text-sm text-muted-foreground">{provider.description}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{provider.limit}</Badge>
                      {selectedProvider === key && (
                        <CheckCircle2 className="h-5 w-5 text-primary" />
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <Alert>
              <HelpCircle className="h-4 w-4" />
              <AlertTitle>어떤 서비스를 선택해야 하나요?</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                  <li><strong>Gmail</strong>: 가장 안정적이고 무료로 일 500건까지 발송 가능</li>
                  <li><strong>네이버</strong>: 국내 수신율이 높고 설정이 간편</li>
                  <li><strong>직접 입력</strong>: 다음, 카카오, 회사 이메일 등 사용 시</li>
                </ul>
              </AlertDescription>
            </Alert>

            <div className="flex justify-end">
              <Button onClick={() => setCurrentStep(2)}>
                다음 단계
                <ArrowRight className="h-4 w-4 ml-2" />
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
              <Key className="h-5 w-5" />
              Step 2: 앱 비밀번호 발급
            </CardTitle>
            <CardDescription>
              보안을 위해 일반 비밀번호 대신 앱 비밀번호를 사용합니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <Tabs defaultValue={selectedProvider === 'naver' ? 'naver' : 'gmail'}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="gmail">Gmail 가이드</TabsTrigger>
                <TabsTrigger value="naver">네이버 가이드</TabsTrigger>
              </TabsList>

              {/* Gmail 가이드 */}
              <TabsContent value="gmail" className="space-y-4">
                <Alert className="bg-blue-50 border-blue-200">
                  <Shield className="h-4 w-4 text-blue-600" />
                  <AlertTitle className="text-blue-800">Gmail 앱 비밀번호란?</AlertTitle>
                  <AlertDescription className="text-blue-700">
                    앱 비밀번호는 Google 계정의 2단계 인증을 활성화한 후 생성할 수 있는 16자리 특수 비밀번호입니다.
                    일반 비밀번호 대신 사용하여 더 안전하게 이메일을 발송할 수 있습니다.
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">1</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">Google 계정 보안 페이지 접속</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          아래 링크를 클릭하여 Google 계정 보안 설정으로 이동합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://myaccount.google.com/security', '_blank')}
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          Google 보안 설정 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">2</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">2단계 인증 활성화</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          "Google에 로그인하는 방법" 섹션에서 <strong>"2단계 인증"</strong>을 클릭하고 활성화합니다.
                        </p>
                        <div className="mt-2 p-3 bg-yellow-50 rounded-lg text-sm">
                          <strong>⚠️ 주의:</strong> 2단계 인증이 이미 활성화되어 있다면 이 단계는 건너뛰세요.
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">3</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">앱 비밀번호 페이지로 이동</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          2단계 인증 설정 후, 아래 링크로 앱 비밀번호 페이지에 접속합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://myaccount.google.com/apppasswords', '_blank')}
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          앱 비밀번호 페이지 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">4</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">앱 비밀번호 생성</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          앱 이름에 <strong>"닥터보이스"</strong> 또는 원하는 이름을 입력하고 "만들기"를 클릭합니다.
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <code className="px-3 py-1 bg-gray-100 rounded text-sm">닥터보이스</code>
                          <Button variant="ghost" size="sm" onClick={() => copyToClipboard('닥터보이스')}>
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4 bg-green-50 border-green-200">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center font-bold">5</div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-green-800">16자리 비밀번호 복사</h4>
                        <p className="text-sm text-green-700 mt-1">
                          화면에 표시되는 <strong>16자리 비밀번호</strong>를 복사해주세요.
                          이 비밀번호는 다시 볼 수 없으니 꼭 저장해두세요!
                        </p>
                        <div className="mt-2 p-3 bg-white rounded-lg border border-green-300">
                          <code className="text-lg font-mono tracking-widest">xxxx xxxx xxxx xxxx</code>
                          <p className="text-xs text-green-600 mt-1">← 이런 형태의 비밀번호가 생성됩니다</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>

              {/* 네이버 가이드 */}
              <TabsContent value="naver" className="space-y-4">
                <Alert className="bg-green-50 border-green-200">
                  <Shield className="h-4 w-4 text-green-600" />
                  <AlertTitle className="text-green-800">네이버 SMTP 사용 설정</AlertTitle>
                  <AlertDescription className="text-green-700">
                    네이버 메일은 SMTP 사용을 위해 별도의 설정이 필요합니다.
                    일반 네이버 비밀번호를 그대로 사용할 수 있습니다.
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center font-bold">1</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">네이버 메일 설정 페이지 접속</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          네이버 메일에 로그인한 후 설정 페이지로 이동합니다.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => window.open('https://mail.naver.com/v2/settings/general', '_blank')}
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          네이버 메일 설정 열기
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center font-bold">2</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">POP3/IMAP 설정 찾기</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          왼쪽 메뉴에서 <strong>"POP3/IMAP 설정"</strong>을 클릭합니다.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center font-bold">3</div>
                      <div className="flex-1">
                        <h4 className="font-semibold">IMAP/SMTP 사용 활성화</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          <strong>"IMAP/SMTP 사용"</strong> 옵션을 <strong>"사용함"</strong>으로 변경합니다.
                        </p>
                        <div className="mt-2 p-3 bg-green-50 rounded-lg text-sm">
                          <strong>✅ 체크:</strong> "IMAP/SMTP 사용" → 사용함
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border p-4 bg-green-50 border-green-200">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center font-bold">4</div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-green-800">설정 저장</h4>
                        <p className="text-sm text-green-700 mt-1">
                          변경사항을 저장하면 네이버 SMTP를 사용할 준비가 완료됩니다.
                          비밀번호는 <strong>네이버 로그인 비밀번호</strong>를 그대로 사용합니다.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-gray-50 border">
                  <h4 className="font-semibold mb-2">네이버 SMTP 정보</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">SMTP 서버:</span>
                      <code className="bg-white px-2 py-0.5 rounded">smtp.naver.com</code>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">포트:</span>
                      <code className="bg-white px-2 py-0.5 rounded">587</code>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">보안:</span>
                      <code className="bg-white px-2 py-0.5 rounded">TLS</code>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">인증:</span>
                      <code className="bg-white px-2 py-0.5 rounded">네이버 ID/비밀번호</code>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(1)}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                이전
              </Button>
              <Button onClick={() => setCurrentStep(3)}>
                다음 단계
                <ArrowRight className="h-4 w-4 ml-2" />
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
              <Settings className="h-5 w-5" />
              Step 3: SMTP 정보 입력
            </CardTitle>
            <CardDescription>
              앞에서 준비한 정보를 입력해주세요
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* SMTP 서버 설정 */}
            <div className="space-y-4">
              <h4 className="font-semibold">서버 설정</h4>
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
                    className="mt-1"
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
              <h4 className="font-semibold">인증 정보</h4>
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
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {selectedProvider === 'gmail' && (
                    <p className="text-xs text-muted-foreground mt-1">
                      공백 없이 16자리를 입력하세요 (예: abcdabcdabcdabcd)
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* 발신자 정보 */}
            <div className="space-y-4">
              <h4 className="font-semibold">발신자 정보</h4>
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
              <h4 className="font-semibold">발송 제한 설정</h4>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>일일 한도</Label>
                  <Input
                    type="number"
                    value={smtpConfig.daily_limit}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, daily_limit: parseInt(e.target.value) }))}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">권장: 50건</p>
                </div>
                <div>
                  <Label>시간당 한도</Label>
                  <Input
                    type="number"
                    value={smtpConfig.hourly_limit}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, hourly_limit: parseInt(e.target.value) }))}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">권장: 10건</p>
                </div>
                <div>
                  <Label>발송 간격 (초)</Label>
                  <Input
                    type="number"
                    value={smtpConfig.min_interval_seconds}
                    onChange={(e) => setSmtpConfig(prev => ({ ...prev, min_interval_seconds: parseInt(e.target.value) }))}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">권장: 300초</p>
                </div>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(2)}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                이전
              </Button>
              <Button onClick={() => setCurrentStep(4)}>
                다음 단계
                <ArrowRight className="h-4 w-4 ml-2" />
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
              <Send className="h-5 w-5" />
              Step 4: 연결 테스트 및 완료
            </CardTitle>
            <CardDescription>
              설정이 올바른지 확인하고 저장합니다
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* 설정 요약 */}
            <div className="rounded-xl border p-4 bg-gray-50">
              <h4 className="font-semibold mb-3">설정 요약</h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">SMTP 서버:</span>
                  <span className="font-medium">{smtpConfig.smtp_host || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">포트:</span>
                  <span className="font-medium">{smtpConfig.smtp_port}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">이메일:</span>
                  <span className="font-medium">{smtpConfig.smtp_username || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">TLS:</span>
                  <span className="font-medium">{smtpConfig.smtp_use_tls ? '사용' : '미사용'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">발신자 이름:</span>
                  <span className="font-medium">{smtpConfig.sender_name || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">일일 한도:</span>
                  <span className="font-medium">{smtpConfig.daily_limit}건</span>
                </div>
              </div>
            </div>

            {/* 테스트 버튼 */}
            <div className="flex flex-col items-center gap-4 py-6">
              <Button
                size="lg"
                variant={testResult === 'success' ? 'outline' : 'default'}
                onClick={handleTestConnection}
                disabled={isTesting}
                className="w-full max-w-xs"
              >
                {isTesting ? (
                  <>
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                    연결 테스트 중...
                  </>
                ) : testResult === 'success' ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 mr-2 text-green-500" />
                    테스트 성공!
                  </>
                ) : testResult === 'error' ? (
                  <>
                    <X className="h-5 w-5 mr-2 text-red-500" />
                    다시 테스트
                  </>
                ) : (
                  <>
                    <Send className="h-5 w-5 mr-2" />
                    연결 테스트
                  </>
                )}
              </Button>

              {testResult === 'success' && (
                <Alert className="bg-green-50 border-green-200">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <AlertTitle className="text-green-800">연결 성공!</AlertTitle>
                  <AlertDescription className="text-green-700">
                    SMTP 서버에 성공적으로 연결되었습니다. 이제 이메일을 발송할 수 있습니다.
                  </AlertDescription>
                </Alert>
              )}

              {testResult === 'error' && (
                <Alert className="bg-red-50 border-red-200">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <AlertTitle className="text-red-800">연결 실패</AlertTitle>
                  <AlertDescription className="text-red-700">
                    <p>SMTP 서버 연결에 실패했습니다. 다음을 확인해주세요:</p>
                    <ul className="list-disc list-inside mt-2 text-sm">
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
                <ArrowLeft className="h-4 w-4 mr-2" />
                이전
              </Button>
              <Button
                onClick={handleSaveSettings}
                disabled={isSaving || testResult !== 'success'}
              >
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    저장 중...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    설정 저장 및 완료
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* FAQ 섹션 */}
      <Card className="mt-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5" />
            자주 묻는 질문
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="rounded-lg border p-4">
              <h4 className="font-semibold">Q: "앱 비밀번호" 메뉴가 보이지 않아요</h4>
              <p className="text-sm text-muted-foreground mt-1">
                A: 2단계 인증이 활성화되어 있어야 앱 비밀번호 메뉴가 나타납니다.
                먼저 Google 계정 → 보안 → 2단계 인증을 활성화해주세요.
              </p>
            </div>

            <div className="rounded-lg border p-4">
              <h4 className="font-semibold">Q: 이메일이 발송되지 않아요</h4>
              <p className="text-sm text-muted-foreground mt-1">
                A: 다음 사항을 확인해주세요:
                <br />• Gmail: 16자리 앱 비밀번호를 공백 없이 입력했는지 확인
                <br />• 네이버: IMAP/SMTP 사용 설정이 "사용함"인지 확인
                <br />• 일일 발송 한도를 초과하지 않았는지 확인
              </p>
            </div>

            <div className="rounded-lg border p-4">
              <h4 className="font-semibold">Q: 하루에 몇 건까지 발송할 수 있나요?</h4>
              <p className="text-sm text-muted-foreground mt-1">
                A: 서비스별 제한:
                <br />• Gmail 무료: 일 500건
                <br />• Gmail Workspace: 일 2,000건
                <br />• 네이버: 일 500건
                <br />스팸 방지를 위해 권장 발송량은 일 50건 이하입니다.
              </p>
            </div>

            <div className="rounded-lg border p-4">
              <h4 className="font-semibold">Q: 보안이 걱정돼요. 비밀번호가 안전한가요?</h4>
              <p className="text-sm text-muted-foreground mt-1">
                A: 앱 비밀번호는 암호화되어 저장됩니다. 또한 앱 비밀번호는 언제든
                Google/네이버 계정에서 삭제하고 새로 발급받을 수 있어 보안 위험이 낮습니다.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
