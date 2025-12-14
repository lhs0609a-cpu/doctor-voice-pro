'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/store/auth'
import { Sparkles, Mail, Lock, User, Building, Stethoscope, Loader2 } from 'lucide-react'

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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

              <Button type="submit" className="w-full" disabled={isLoading}>
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
          <p className="text-xs text-gray-400 mt-1">
            &copy; 2024 플라톤마케팅. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  )
}
