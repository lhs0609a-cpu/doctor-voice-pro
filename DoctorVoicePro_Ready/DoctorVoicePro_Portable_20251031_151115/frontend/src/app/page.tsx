'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Sparkles, Brain, Shield, TrendingUp, Zap, CheckCircle } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 overflow-hidden">
      {/* Animated Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        <div className="container mx-auto px-4 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 group">
            <div className="relative">
              <Sparkles className="h-8 w-8 text-blue-600 transition-transform group-hover:scale-110 group-hover:rotate-12" />
              <div className="absolute inset-0 bg-blue-400 rounded-full blur-lg opacity-0 group-hover:opacity-50 transition-opacity"></div>
            </div>
            <span className="font-bold text-2xl bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">닥터보이스 프로</span>
          </div>
          <div className="flex gap-3">
            <Link href="/login">
              <Button variant="ghost" size="lg" className="hover:bg-blue-50 transition-all">로그인</Button>
            </Link>
            <Link href="/register">
              <Button size="lg" className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transition-all">시작하기</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-20 relative z-10">
        <div className="text-center space-y-10 max-w-5xl mx-auto">
          <div className="inline-block animate-fade-in-up">
            <span className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-blue-100 to-purple-100 text-blue-700 text-sm font-semibold shadow-md hover:shadow-lg transition-shadow">
              <Zap className="h-4 w-4 animate-pulse" />
              AI 기반 의료 블로그 자동 각색
            </span>
          </div>

          <h1 className="text-6xl md:text-7xl font-extrabold tracking-tight leading-tight animate-fade-in-up animation-delay-200">
            의료 정보를
            <br />
            <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent inline-block mt-2">
              원장님의 목소리로
            </span>
          </h1>

          <p className="text-xl md:text-2xl text-gray-600 max-w-3xl mx-auto leading-relaxed animate-fade-in-up animation-delay-400">
            <span className="font-semibold text-blue-600">1시간</span> 걸리던 블로그 작성을 <span className="font-semibold text-purple-600">5분</span>으로 단축하세요.
            <br />
            AI가 원장님의 말투를 학습하여 설득력 있는 포스팅을 자동 생성합니다.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-6 animate-fade-in-up animation-delay-600">
            <Link href="/register">
              <Button size="lg" className="text-lg px-8 py-6 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-xl hover:shadow-2xl transform hover:scale-105 transition-all">
                <Sparkles className="h-5 w-5 mr-2" />
                무료로 시작하기
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline" className="text-lg px-8 py-6 border-2 border-blue-300 hover:bg-blue-50 hover:border-blue-400 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all">
                로그인
              </Button>
            </Link>
          </div>

          {/* Quick Stats */}
          <div className="flex flex-wrap justify-center gap-8 pt-8 animate-fade-in-up animation-delay-800">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span>무료 체험 가능</span>
            </div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span>설치 불필요</span>
            </div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span>5분만에 시작</span>
            </div>
          </div>

          {/* Features Grid */}
          <div className="grid md:grid-cols-3 gap-8 pt-24 animate-fade-in-up animation-delay-1000">
            <div className="group p-8 rounded-3xl bg-white shadow-lg border-2 border-transparent hover:border-blue-200 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform shadow-lg">
                <Brain className="h-8 w-8 text-white" />
              </div>
              <h3 className="font-bold text-xl mb-3 text-gray-800">AI 자동 각색</h3>
              <p className="text-gray-600 leading-relaxed">
                Claude AI가 의료 정보를 공감 가는 이야기로 변환합니다
              </p>
            </div>

            <div className="group p-8 rounded-3xl bg-white shadow-lg border-2 border-transparent hover:border-purple-200 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform shadow-lg">
                <Shield className="h-8 w-8 text-white" />
              </div>
              <h3 className="font-bold text-xl mb-3 text-gray-800">의료법 자동 검증</h3>
              <p className="text-gray-600 leading-relaxed">
                과장 광고와 금지 표현을 자동으로 탐지하고 수정합니다
              </p>
            </div>

            <div className="group p-8 rounded-3xl bg-white shadow-lg border-2 border-transparent hover:border-green-200 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform shadow-lg">
                <TrendingUp className="h-8 w-8 text-white" />
              </div>
              <h3 className="font-bold text-xl mb-3 text-gray-800">SEO 자동 최적화</h3>
              <p className="text-gray-600 leading-relaxed">
                네이버 검색 상위 노출을 위한 키워드와 해시태그 생성
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-24 max-w-4xl mx-auto animate-fade-in-up animation-delay-1200">
            <div className="p-8 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-xl transform hover:scale-105 transition-transform">
              <div className="text-5xl font-extrabold mb-2">80%</div>
              <div className="text-blue-100 font-medium">작성 시간 단축</div>
            </div>
            <div className="p-8 rounded-2xl bg-gradient-to-br from-purple-500 to-purple-600 text-white shadow-xl transform hover:scale-105 transition-transform">
              <div className="text-5xl font-extrabold mb-2">35%</div>
              <div className="text-purple-100 font-medium">환자 문의 증가</div>
            </div>
            <div className="p-8 rounded-2xl bg-gradient-to-br from-green-500 to-green-600 text-white shadow-xl transform hover:scale-105 transition-transform">
              <div className="text-5xl font-extrabold mb-2">3배</div>
              <div className="text-green-100 font-medium">콘텐츠 생산량</div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-32 py-12 bg-white/70 backdrop-blur-sm relative z-10">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="h-6 w-6 text-blue-600" />
            <span className="font-bold text-xl bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">닥터보이스 프로</span>
          </div>
          <p className="text-sm text-gray-600">© 2025 닥터보이스 프로. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
