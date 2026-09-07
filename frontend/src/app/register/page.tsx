'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Logo } from '@/components/app-shell/logo'
import { useAuthStore } from '@/store/auth'
import { Mail, Lock, User, Building, Stethoscope, Loader2, CheckSquare, Square, ExternalLink } from 'lucide-react'

export default function RegisterPage() {
  const router = useRouter()
  const { register, isLoading, error } = useAuthStore()
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    hospital_name: '',
    specialty: '',
  })
  const [agreements, setAgreements] = useState({
    terms: false,        // 이용약관
    privacy: false,      // 개인정보처리방침
    disclaimer: false,   // 면책조항
    all: false,          // 전체 동의
  })

  const handleAgreementChange = (key: keyof typeof agreements) => {
    if (key === 'all') {
      const newValue = !agreements.all
      setAgreements({
        terms: newValue,
        privacy: newValue,
        disclaimer: newValue,
        all: newValue,
      })
    } else {
      const newAgreements = { ...agreements, [key]: !agreements[key] }
      newAgreements.all = newAgreements.terms && newAgreements.privacy && newAgreements.disclaimer
      setAgreements(newAgreements)
    }
  }

  const isAllRequiredAgreed = agreements.terms && agreements.privacy && agreements.disclaimer

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!isAllRequiredAgreed) {
      alert('필수 약관에 모두 동의해주세요.')
      return
    }

    try {
      await register(formData)
      alert('회원가입이 완료되었습니다!\n관리자 승인 후 로그인이 가능합니다.')
      router.push('/login')
    } catch (error) {
      // Error is handled in store
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const agreementItems: { key: 'terms' | 'privacy' | 'disclaimer'; label: string; href: string }[] = [
    { key: 'terms', label: '서비스 이용약관 동의', href: '/legal#terms' },
    { key: 'privacy', label: '개인정보처리방침 동의', href: '/legal#privacy' },
    { key: 'disclaimer', label: '면책조항 및 콘텐츠 정책 동의', href: '/legal#disclaimer' },
  ]

  const iconClass = 'pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground'

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <Logo href="/" />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>회원가입</CardTitle>
            <CardDescription>AI 블로그 자동 각색을 무료로 시작하세요</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">이메일 *</Label>
                <div className="relative">
                  <Mail className={iconClass} />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="doctor@example.com"
                    className="pl-9"
                    value={formData.email}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">비밀번호 *</Label>
                <div className="relative">
                  <Lock className={iconClass} />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    placeholder="최소 8자 이상"
                    className="pl-9"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    minLength={8}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">이름</Label>
                <div className="relative">
                  <User className={iconClass} />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="김정형"
                    className="pl-9"
                    value={formData.name}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="hospital_name">병원명</Label>
                <div className="relative">
                  <Building className={iconClass} />
                  <Input
                    id="hospital_name"
                    name="hospital_name"
                    type="text"
                    placeholder="서울정형외과"
                    className="pl-9"
                    value={formData.hospital_name}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="specialty">진료 과목</Label>
                <div className="relative">
                  <Stethoscope className={iconClass} />
                  <Input
                    id="specialty"
                    name="specialty"
                    type="text"
                    placeholder="정형외과"
                    className="pl-9"
                    value={formData.specialty}
                    onChange={handleChange}
                  />
                </div>
              </div>

              {/* 약관 동의 섹션 */}
              <div className="space-y-3 border-t pt-4">
                <Label className="text-[13px] font-medium text-muted-foreground">약관 동의</Label>

                {/* 전체 동의 */}
                <button
                  type="button"
                  onClick={() => handleAgreementChange('all')}
                  className="flex w-full items-center gap-3 rounded-lg bg-muted/40 p-3 text-sm transition-colors hover:bg-muted"
                >
                  {agreements.all ? (
                    <CheckSquare className="h-5 w-5 text-primary" />
                  ) : (
                    <Square className="h-5 w-5 text-muted-foreground" />
                  )}
                  <span className="font-medium text-foreground">전체 동의</span>
                </button>

                {/* 개별 약관 */}
                <div className="space-y-2 pl-2">
                  {agreementItems.map((item) => (
                    <div key={item.key} className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => handleAgreementChange(item.key)}
                        className="flex items-center gap-2"
                      >
                        {agreements[item.key] ? (
                          <CheckSquare className="h-4 w-4 text-primary" />
                        ) : (
                          <Square className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="text-sm text-foreground">
                          <span className="text-primary">[필수]</span> {item.label}
                        </span>
                      </button>
                      <Link
                        href={item.href}
                        target="_blank"
                        className="text-muted-foreground hover:text-primary"
                        aria-label={`${item.label} 전문 보기`}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Link>
                    </div>
                  ))}
                </div>

                {/* 경고 메시지 */}
                <div className="rounded-lg bg-warning-soft p-3">
                  <p className="text-xs text-warning">
                    <strong>중요:</strong> 본 서비스에서 생성된 콘텐츠의 사용에 대한 모든 법적 책임은
                    이용자에게 있습니다. 가입 전 약관 내용을 반드시 확인해주세요.
                  </p>
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading || !isAllRequiredAgreed}>
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" />
                    회원가입 중...
                  </>
                ) : (
                  '가입하기'
                )}
              </Button>
            </form>

            <p className="text-center text-sm text-muted-foreground">
              이미 계정이 있으신가요?{' '}
              <Link href="/login" className="font-medium text-primary hover:underline">
                로그인
              </Link>
            </p>
          </CardContent>
        </Card>

        <div className="space-y-2 text-center text-xs text-muted-foreground">
          <p>
            닥터보이스 프로는 <span className="font-medium text-foreground">플라톤마케팅</span>에서 개발했습니다.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link href="/legal" className="hover:text-primary">이용약관</Link>
            <span aria-hidden="true">·</span>
            <Link href="/legal" className="hover:text-primary">개인정보처리방침</Link>
            <span aria-hidden="true">·</span>
            <Link href="/legal" className="hover:text-primary">법적고지</Link>
          </div>
          <p>&copy; 2024 플라톤마케팅. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}
