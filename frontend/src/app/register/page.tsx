'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/store/auth'
import { Sparkles, Mail, Lock, User, Building, Stethoscope, Loader2, CheckSquare, Square, ExternalLink } from 'lucide-react'

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <Link href="/" className="flex items-center gap-2">
            <Sparkles className="h-8 w-8 text-blue-600" />
            <span className="font-bold text-2xl">닥터보이스 프로</span>
          </Link>
          <span className="text-xs text-gray-400 mt-1">by 플라톤마케팅</span>
        </div>

        {/* Register Card */}
        <Card className="border-0 shadow-xl">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">회원가입</CardTitle>
            <CardDescription>
              AI 블로그 자동 각색을 무료로 시작하세요
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-600 text-sm">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">이메일 *</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="doctor@example.com"
                    className="pl-10"
                    value={formData.email}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">비밀번호 *</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    placeholder="최소 8자 이상"
                    className="pl-10"
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
                  <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="김정형"
                    className="pl-10"
                    value={formData.name}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="hospital_name">병원명</Label>
                <div className="relative">
                  <Building className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="hospital_name"
                    name="hospital_name"
                    type="text"
                    placeholder="서울정형외과"
                    className="pl-10"
                    value={formData.hospital_name}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="specialty">진료 과목</Label>
                <div className="relative">
                  <Stethoscope className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="specialty"
                    name="specialty"
                    type="text"
                    placeholder="정형외과"
                    className="pl-10"
                    value={formData.specialty}
                    onChange={handleChange}
                  />
                </div>
              </div>

              {/* 약관 동의 섹션 */}
              <div className="space-y-3 pt-4 border-t">
                <Label className="text-sm font-semibold">약관 동의</Label>

                {/* 전체 동의 */}
                <button
                  type="button"
                  onClick={() => handleAgreementChange('all')}
                  className="w-full flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                >
                  {agreements.all ? (
                    <CheckSquare className="w-5 h-5 text-blue-600" />
                  ) : (
                    <Square className="w-5 h-5 text-gray-400" />
                  )}
                  <span className="font-semibold text-gray-800">전체 동의</span>
                </button>

                {/* 개별 약관 */}
                <div className="space-y-2 pl-2">
                  {/* 이용약관 */}
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handleAgreementChange('terms')}
                      className="flex items-center gap-2"
                    >
                      {agreements.terms ? (
                        <CheckSquare className="w-4 h-4 text-blue-600" />
                      ) : (
                        <Square className="w-4 h-4 text-gray-400" />
                      )}
                      <span className="text-sm text-gray-700">
                        <span className="text-red-500">[필수]</span> 서비스 이용약관 동의
                      </span>
                    </button>
                    <Link
                      href="/legal#terms"
                      target="_blank"
                      className="text-gray-400 hover:text-blue-600"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                  </div>

                  {/* 개인정보처리방침 */}
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handleAgreementChange('privacy')}
                      className="flex items-center gap-2"
                    >
                      {agreements.privacy ? (
                        <CheckSquare className="w-4 h-4 text-blue-600" />
                      ) : (
                        <Square className="w-4 h-4 text-gray-400" />
                      )}
                      <span className="text-sm text-gray-700">
                        <span className="text-red-500">[필수]</span> 개인정보처리방침 동의
                      </span>
                    </button>
                    <Link
                      href="/legal#privacy"
                      target="_blank"
                      className="text-gray-400 hover:text-blue-600"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                  </div>

                  {/* 면책조항 */}
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handleAgreementChange('disclaimer')}
                      className="flex items-center gap-2"
                    >
                      {agreements.disclaimer ? (
                        <CheckSquare className="w-4 h-4 text-blue-600" />
                      ) : (
                        <Square className="w-4 h-4 text-gray-400" />
                      )}
                      <span className="text-sm text-gray-700">
                        <span className="text-red-500">[필수]</span> 면책조항 및 콘텐츠 정책 동의
                      </span>
                    </button>
                    <Link
                      href="/legal#disclaimer"
                      target="_blank"
                      className="text-gray-400 hover:text-blue-600"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                  </div>
                </div>

                {/* 경고 메시지 */}
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-xs text-yellow-800">
                    <strong>중요:</strong> 본 서비스에서 생성된 콘텐츠의 사용에 대한 모든 법적 책임은
                    이용자에게 있습니다. 가입 전 약관 내용을 반드시 확인해주세요.
                  </p>
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading || !isAllRequiredAgreed}>
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    회원가입 중...
                  </>
                ) : (
                  '가입하기'
                )}
              </Button>
            </form>

            <div className="mt-6 text-center text-sm">
              <span className="text-muted-foreground">이미 계정이 있으신가요? </span>
              <Link href="/login" className="text-blue-600 hover:underline font-medium">
                로그인
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-xs text-gray-500">
            닥터보이스 프로는 <span className="font-semibold text-purple-600">플라톤마케팅</span>에서 개발했습니다.
          </p>
          <div className="flex items-center justify-center gap-3 mt-2">
            <Link href="/legal" className="text-xs text-gray-400 hover:text-blue-600">
              이용약관
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/legal" className="text-xs text-gray-400 hover:text-blue-600">
              개인정보처리방침
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/legal" className="text-xs text-gray-400 hover:text-blue-600">
              법적고지
            </Link>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            &copy; 2024 플라톤마케팅. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  )
}
