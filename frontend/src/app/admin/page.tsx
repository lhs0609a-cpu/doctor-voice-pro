'use client'

import { useEffect, useState } from 'react'
import { adminAPI, APIKeyInfo, APIKeyStatus, subscriptionAPI, type Plan } from '@/lib/api'
import type { User } from '@/types'
import { useRouter } from 'next/navigation'

// 크레딧 팩 정보 (백엔드와 동일)
const CREDIT_PACKS = {
  post_10: { id: 'post_10', name: '글 생성 크레딧 10회', credit_type: 'post', amount: 10, price: 9900 },
  post_50: { id: 'post_50', name: '글 생성 크레딧 50회', credit_type: 'post', amount: 50, price: 39900, discount_rate: 20 },
  post_100: { id: 'post_100', name: '글 생성 크레딧 100회', credit_type: 'post', amount: 100, price: 69900, discount_rate: 30 },
  analysis_50: { id: 'analysis_50', name: '분석 크레딧 50회', credit_type: 'analysis', amount: 50, price: 9900 },
  analysis_200: { id: 'analysis_200', name: '분석 크레딧 200회', credit_type: 'analysis', amount: 200, price: 29900, discount_rate: 25 },
}

// 법적 리스크 가이드라인 데이터
const LEGAL_RISKS = [
  {
    id: 'cafe_review',
    name: '카페 리뷰 자동 생성',
    severity: 'critical',
    location: 'backend/app/services/review_service.py, frontend/src/components/cafe-review/',
    description: '불특정 다수의 가짜 후기를 의도적으로 자연스럽게 작성하도록 설계됨. 오타, 이모티콘 등을 포함해 실제 사용자 후기로 위장.',
    laws: [
      '소비자기본법: 허위·과장 표시광고 금지',
      '전자상거래법: 소비자 기만행위 금지',
      '공정거래법: 부당한 표시·광고 금지',
      '형법: 사기죄 (조직적인 가짜 리뷰 생성 시)',
    ],
    problems: [
      '조직적인 가짜 후기 생성 시스템',
      '실제 사용자 후기로 위장하는 기능',
      '의도적 오타/비격식 표현으로 탐지 회피',
      '병원에 대한 허위 평가 게시',
    ],
    solutions: [
      '기능 완전 제거 또는 비활성화 권장',
      '실제 환자 후기만 수집하는 시스템으로 전환',
      '후기 작성 시 "AI 생성 콘텐츠" 명시 의무화',
      '병원 관계자임을 명시하는 방식으로 변경',
    ],
    safeImplementation: '실제 환자가 직접 작성한 리뷰만 수집하고, 리뷰 작성 대가로 과도한 보상을 제공하지 않아야 함. AI 보조 시 반드시 표기 필요.',
  },
  {
    id: 'review_campaign',
    name: '리뷰 캠페인 (보상 제공)',
    severity: 'critical',
    location: 'backend/app/api/campaigns.py, backend/app/services/campaign_service.py',
    description: '리뷰 작성 조건으로 현금, 할인, 사은품 등 보상 제공. 최소 별점, 최소 글자 수 등 조건 설정 가능.',
    laws: [
      '소비자기본법: 리뷰 조작 금지',
      '경품법: 과도한 경품 제공 제한',
      '의료법 제56조: 의료광고의 금지사항',
      '공정거래법: 기만적 광고행위',
    ],
    problems: [
      '보상을 조건으로 한 리뷰 유도 = 리뷰 조작',
      '최소 별점 요구 = 긍정 리뷰 강요',
      '의료기관의 경품/할인 제공 제한 위반',
      '소비자의 공정한 판단 방해',
    ],
    solutions: [
      '보상 조건부 리뷰 요청 기능 제거',
      '최소 별점/내용 조건 설정 기능 제거',
      '리뷰 작성 자체에 대한 보상은 허용, 내용 조건 금지',
      '보상 제공 시 "광고" 또는 "협찬" 명시 의무화',
    ],
    safeImplementation: '리뷰 작성에 대한 소정의 감사 표시는 가능하나, 특정 내용이나 평점을 조건으로 하면 안 됨. 보상 리뷰는 반드시 표기.',
  },
  {
    id: 'knowledge_answer',
    name: '네이버 지식인 자동 답변',
    severity: 'high',
    location: 'backend/app/api/knowledge.py, backend/app/services/knowledge_service.py',
    description: '네이버 지식인 질문을 수집하고 AI로 답변을 자동 생성하여 게시. 90점 이상 자동 승인 기능.',
    laws: [
      '의료법 제27조: 무면허 의료행위 금지',
      '의료법 제56조: 의료광고 금지사항',
      '네이버 이용약관: 자동화된 글 작성 금지',
      '개인정보보호법: 질문자 정보 무단 수집',
    ],
    problems: [
      '비등록 의료인이 의료 조언을 제공하는 것처럼 보임',
      '의사 자격 없이 의료 상담 제공',
      '자동화된 답변으로 플랫폼 약관 위반',
      '답변의 의학적 정확성 검증 불가',
    ],
    solutions: [
      '의료 관련 답변 자동 게시 기능 비활성화',
      '답변 시 "AI 생성 참고 자료"임을 명시',
      '반드시 의료인 검토 후 수동 게시 절차 추가',
      '"전문의 상담을 권장합니다" 문구 필수 포함',
    ],
    safeImplementation: 'AI는 답변 초안 생성만 지원하고, 의료 전문가가 검토 후 게시. 일반 건강정보 제공이라는 점을 명확히 하고 의료 상담이 아님을 표기.',
  },
  {
    id: 'naver_blog',
    name: '네이버 블로그 자동 발행',
    severity: 'high',
    location: 'backend/app/api/naver.py, backend/app/services/naver_blog_service.py',
    description: 'OAuth를 통해 사용자 네이버 블로그에 AI 생성 콘텐츠를 자동 발행.',
    laws: [
      '네이버 이용약관: 자동화된 콘텐츠 생성/게시 제한',
      '의료법 제56조: 의료광고 금지사항',
      '저작권법: AI 생성 콘텐츠의 저작권 문제',
    ],
    problems: [
      'AI 생성 콘텐츠 대량 발행 시 스팸으로 분류 가능',
      '의료 광고 심의 없는 의료 정보 게시',
      '계정 정지/제재 위험',
      '콘텐츠 품질 보장 어려움',
    ],
    solutions: [
      'AI 생성 콘텐츠임을 명시적으로 표기',
      '의료 정보 게시 시 의료법 검사 강제화',
      '발행 빈도 제한 설정',
      '사용자 최종 검토 후 발행하는 프로세스 추가',
    ],
    safeImplementation: '사용자가 AI 초안을 검토하고 수정 후 직접 발행 버튼을 누르는 방식. 완전 자동화보다는 반자동화 권장.',
  },
  {
    id: 'sns_auto_post',
    name: 'SNS 자동 포스팅',
    severity: 'medium',
    location: 'backend/app/api/sns.py, backend/app/services/sns_service.py',
    description: 'Instagram, Facebook에 블로그 글을 SNS 포맷으로 자동 변환하여 발행.',
    laws: [
      'Instagram/Facebook 이용약관: 자동화된 콘텐츠 게시 제한',
      '의료법 제56조: 의료광고 금지사항',
      '표시광고법: 광고의 명확한 표시',
    ],
    problems: [
      '의료인 표시 없는 의료 관련 광고 가능성',
      '플랫폼 API 이용약관 위반 가능성',
      '계정 정지 위험',
    ],
    solutions: [
      '광고성 게시물임을 명시 (#광고 #협찬)',
      '의료인/병원 정보 명확히 표기',
      'Meta Business Suite 공식 API 사용',
      '발행 전 미리보기 및 사용자 승인 절차',
    ],
    safeImplementation: '공식 API를 통한 연동, 광고 표기 의무화, 사용자 승인 후 발행.',
  },
  {
    id: 'medical_content',
    name: '의료 콘텐츠 AI 생성',
    severity: 'medium',
    location: 'backend/app/services/medical_law_checker.py, backend/app/api/posts.py',
    description: 'AI로 의료 정보/광고 콘텐츠 생성. 의료법 검사 기능은 있으나 강제가 아님.',
    laws: [
      '의료법 제56조: 의료광고 금지사항',
      '의료법 제57조: 의료광고 심의',
      '소비자기본법: 허위·과장 광고 금지',
    ],
    problems: [
      '의료법 검사를 건너뛸 수 있음',
      '의료광고 심의 없이 게시 가능',
      '치료 효과 과장, 비교 광고 등 위반 가능',
    ],
    solutions: [
      '의료법 검사를 발행 전 필수 단계로 설정',
      '검사 통과 전 발행 버튼 비활성화',
      '의료광고 심의 절차 안내 추가',
      '위반 표현 자동 수정 후에만 발행 허용',
    ],
    safeImplementation: '모든 의료 관련 콘텐츠는 의료법 검사 통과 필수. 검사 우회 불가능하게 설계.',
  },
  {
    id: 'crawling',
    name: '크롤링/스크래핑',
    severity: 'low',
    location: 'backend/app/services/knowledge_service.py',
    description: '네이버 지식인 질문 수집 (현재 시뮬레이션, 실제 크롤링 구현 예정)',
    laws: [
      '정보통신망법: 부정한 접근 금지',
      '저작권법: 무단 복제 금지',
      '네이버 이용약관: 자동 크롤링 금지',
    ],
    problems: [
      '플랫폼 이용약관 위반',
      '서버에 과도한 부하 시 업무방해죄 가능',
      '수집 데이터의 저작권 문제',
    ],
    solutions: [
      '공식 API가 있다면 해당 API 사용',
      'robots.txt 준수',
      '수집 빈도 제한 (rate limiting)',
      '수집 데이터 상업적 이용 시 법적 검토',
    ],
    safeImplementation: '가능한 공식 API 사용. 불가피한 크롤링 시 robots.txt 준수, 최소한의 데이터만 수집, 서버 부하 최소화.',
  },
]

export default function AdminPage() {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all')
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [subscriptionEndDate, setSubscriptionEndDate] = useState('')

  // API 키 관리 상태
  const [activeTab, setActiveTab] = useState<'users' | 'apikeys' | 'system' | 'legal'>('users')
  const [expandedRisk, setExpandedRisk] = useState<string | null>(null)
  const [apiKeyStatus, setApiKeyStatus] = useState<Record<string, APIKeyStatus>>({})
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({
    claude: '',
    gpt: '',
    gemini: ''
  })
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [savingProvider, setSavingProvider] = useState<string | null>(null)

  // 시스템 정보 상태
  const [plans, setPlans] = useState<Plan[]>([])
  const [aiPricing, setAiPricing] = useState<any>(null)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [backendUrl, setBackendUrl] = useState('')

  useEffect(() => {
    loadUsers()
    checkAdminAccess()
    loadAPIKeyStatus()
    loadSystemInfo()
  }, [filter])

  const loadSystemInfo = async () => {
    // 백엔드 연결 상태 확인
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010'
    setBackendUrl(apiUrl)

    try {
      const response = await fetch(`${apiUrl}/health`)
      setBackendStatus(response.ok ? 'connected' : 'disconnected')
    } catch {
      setBackendStatus('disconnected')
    }

    // 플랜 정보 로드
    try {
      const plansData = await subscriptionAPI.getPlans()
      setPlans(plansData)
    } catch (error) {
      console.error('플랜 정보 로드 실패:', error)
    }

    // AI 비용 정보 로드
    try {
      const response = await fetch(`${apiUrl}/api/v1/system/ai-pricing`)
      if (response.ok) {
        const data = await response.json()
        setAiPricing(data)
      }
    } catch (error) {
      console.error('AI 비용 정보 로드 실패:', error)
    }
  }

  const loadAPIKeyStatus = async () => {
    try {
      const status = await adminAPI.getAPIKeysStatus()
      setApiKeyStatus(status)
    } catch (error) {
      console.error('API 키 상태 조회 실패:', error)
    }
  }

  const handleSaveAPIKey = async (provider: string) => {
    const apiKey = apiKeyInputs[provider]
    if (!apiKey.trim()) {
      alert('API 키를 입력해주세요')
      return
    }

    setSavingProvider(provider)
    try {
      await adminAPI.saveAPIKey({ provider, api_key: apiKey.trim() })
      alert(`${provider.toUpperCase()} API 키가 저장되었습니다`)
      setApiKeyInputs(prev => ({ ...prev, [provider]: '' }))
      await loadAPIKeyStatus()
    } catch (error: any) {
      console.error('API 키 저장 실패:', error)
      alert(error.response?.data?.detail || 'API 키 저장 중 오류가 발생했습니다')
    } finally {
      setSavingProvider(null)
    }
  }

  const handleTestAPIKey = async (provider: string) => {
    setTestingProvider(provider)
    try {
      const result = await adminAPI.testAPIKey(provider)
      if (result.connected) {
        alert(`${provider.toUpperCase()} 연결 성공!\n모델: ${result.model}`)
      } else {
        alert(`${provider.toUpperCase()} 연결 실패\n${result.message}`)
      }
      await loadAPIKeyStatus()
    } catch (error: any) {
      console.error('API 키 테스트 실패:', error)
      alert(error.response?.data?.detail || '연결 테스트 중 오류가 발생했습니다')
    } finally {
      setTestingProvider(null)
    }
  }

  const handleDeleteAPIKey = async (provider: string) => {
    if (!confirm(`${provider.toUpperCase()} API 키를 삭제하시겠습니까?`)) return

    try {
      await adminAPI.deleteAPIKey(provider)
      alert(`${provider.toUpperCase()} API 키가 삭제되었습니다`)
      await loadAPIKeyStatus()
    } catch (error: any) {
      console.error('API 키 삭제 실패:', error)
      alert(error.response?.data?.detail || 'API 키 삭제 중 오류가 발생했습니다')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-green-500'
      case 'failed': return 'bg-red-500'
      case 'not_configured': return 'bg-gray-400'
      default: return 'bg-yellow-500'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'connected': return '연결됨'
      case 'failed': return '연결 실패'
      case 'not_configured': return '미설정'
      default: return '확인 필요'
    }
  }

  const providerInfo = {
    claude: { name: 'Claude (Anthropic)', prefix: 'sk-ant-' },
    gpt: { name: 'GPT (OpenAI)', prefix: 'sk-' },
    gemini: { name: 'Gemini (Google)', prefix: 'AI' }
  }

  const checkAdminAccess = () => {
    const userStr = localStorage.getItem('user')
    if (userStr && userStr !== 'undefined') {
      try {
        const user = JSON.parse(userStr)
        setCurrentUser(user)
        if (!user.is_admin) {
          alert('관리자 권한이 필요합니다')
          router.push('/dashboard')
        }
      } catch (error) {
        console.error('User parse error:', error)
        router.push('/login')
      }
    } else {
      router.push('/login')
    }
  }

  const loadUsers = async () => {
    try {
      setLoading(true)
      let is_approved: boolean | undefined
      if (filter === 'pending') is_approved = false
      if (filter === 'approved') is_approved = true

      const data = await adminAPI.getUsers(is_approved)
      setUsers(data)
    } catch (error: any) {
      console.error('사용자 목록 조회 실패:', error)
      if (error.response?.status === 403) {
        alert('관리자 권한이 필요합니다')
        router.push('/dashboard')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (userId: string, isApproved: boolean) => {
    try {
      await adminAPI.approveUser({ user_id: userId, is_approved: isApproved })
      alert(isApproved ? '승인되었습니다' : '승인이 거부되었습니다')
      loadUsers()
    } catch (error) {
      console.error('승인 처리 실패:', error)
      alert('승인 처리 중 오류가 발생했습니다')
    }
  }

  const handleSetSubscription = async (userId: string) => {
    if (!subscriptionEndDate) {
      alert('종료일을 선택하세요')
      return
    }

    try {
      const now = new Date().toISOString()
      await adminAPI.setUserSubscription({
        user_id: userId,
        subscription_start_date: now,
        subscription_end_date: subscriptionEndDate,
      })
      alert('사용 기간이 설정되었습니다')
      setEditingUser(null)
      setSubscriptionEndDate('')
      loadUsers()
    } catch (error) {
      console.error('사용 기간 설정 실패:', error)
      alert('사용 기간 설정 중 오류가 발생했습니다')
    }
  }

  const handleDelete = async (userId: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      await adminAPI.deleteUser(userId)
      alert('삭제되었습니다')
      loadUsers()
    } catch (error) {
      console.error('삭제 실패:', error)
      alert('삭제 중 오류가 발생했습니다')
    }
  }

  const handleUnlimitedAccess = async (userId: string, grant: boolean, userEmail: string) => {
    const action = grant ? '부여' : '해제'
    const reason = grant ? prompt(`무제한 권한 ${action} 사유를 입력하세요:`) : null

    if (grant && reason === null) return // 취소됨

    if (!confirm(`${userEmail}에게 글 무제한 권한을 ${action}하시겠습니까?`)) return

    try {
      await adminAPI.grantUnlimitedAccess({
        user_id: userId,
        grant,
        reason: reason || undefined
      })
      alert(`글 무제한 권한이 ${action}되었습니다`)
      loadUsers()
    } catch (error: any) {
      console.error('무제한 권한 처리 실패:', error)
      alert(error.response?.data?.detail || '무제한 권한 처리 중 오류가 발생했습니다')
    }
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString('ko-KR')
  }

  if (loading && users.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold mb-2">관리자 페이지</h1>
          <p className="text-gray-600">사용자 및 API 키 관리</p>
        </div>

        {/* 메인 탭 */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex gap-2 border-b pb-4 mb-4">
            <button
              onClick={() => setActiveTab('users')}
              className={`px-4 py-2 rounded-md font-medium ${
                activeTab === 'users'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              사용자 관리
            </button>
            <button
              onClick={() => setActiveTab('apikeys')}
              className={`px-4 py-2 rounded-md font-medium ${
                activeTab === 'apikeys'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              API 키 관리
            </button>
            <button
              onClick={() => setActiveTab('system')}
              className={`px-4 py-2 rounded-md font-medium ${
                activeTab === 'system'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              시스템 정보
            </button>
            <button
              onClick={() => setActiveTab('legal')}
              className={`px-4 py-2 rounded-md font-medium ${
                activeTab === 'legal'
                  ? 'bg-red-600 text-white'
                  : 'bg-red-50 text-red-700 hover:bg-red-100'
              }`}
            >
              법적 리스크
            </button>
          </div>

          {/* 사용자 관리 탭 - 필터 */}
          {activeTab === 'users' && (
            <div className="flex gap-2">
              <button
                onClick={() => setFilter('all')}
                className={`px-4 py-2 rounded-md ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                전체
              </button>
              <button
                onClick={() => setFilter('pending')}
                className={`px-4 py-2 rounded-md ${
                  filter === 'pending'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                승인 대기
              </button>
              <button
                onClick={() => setFilter('approved')}
                className={`px-4 py-2 rounded-md ${
                  filter === 'approved'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                승인됨
              </button>
            </div>
          )}
        </div>

        {/* API 키 관리 탭 내용 */}
        {activeTab === 'apikeys' && (
          <div className="space-y-6">
            {(['claude', 'gpt', 'gemini'] as const).map((provider) => {
              const status = apiKeyStatus[provider]
              const info = providerInfo[provider]

              return (
                <div key={provider} className="bg-white rounded-lg shadow-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold">{info.name}</h3>
                      {/* 연결 상태 표시등 */}
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${getStatusColor(status?.last_status || 'not_configured')} ${status?.last_status === 'connected' ? 'animate-pulse' : ''}`}></div>
                        <span className={`text-sm ${status?.last_status === 'connected' ? 'text-green-600' : status?.last_status === 'failed' ? 'text-red-600' : 'text-gray-500'}`}>
                          {getStatusText(status?.last_status || 'not_configured')}
                        </span>
                      </div>
                    </div>
                    {status?.configured && (
                      <div className="text-sm text-gray-500">
                        키: {status.api_key_preview}
                      </div>
                    )}
                  </div>

                  {/* API 키 입력 폼 */}
                  <div className="flex gap-2 mb-4">
                    <input
                      type="password"
                      value={apiKeyInputs[provider]}
                      onChange={(e) => setApiKeyInputs(prev => ({ ...prev, [provider]: e.target.value }))}
                      placeholder={`${info.name} API 키 입력 (${info.prefix}...)`}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => handleSaveAPIKey(provider)}
                      disabled={savingProvider === provider}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed min-w-[80px]"
                    >
                      {savingProvider === provider ? '저장 중...' : '저장'}
                    </button>
                  </div>

                  {/* 버튼들 */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleTestAPIKey(provider)}
                      disabled={!status?.configured || testingProvider === provider}
                      className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {testingProvider === provider ? '테스트 중...' : '연결 테스트'}
                    </button>
                    {status?.configured && (
                      <button
                        onClick={() => handleDeleteAPIKey(provider)}
                        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                      >
                        삭제
                      </button>
                    )}
                  </div>

                  {/* 마지막 확인 시간 및 에러 메시지 */}
                  {status?.last_checked_at && (
                    <div className="mt-3 text-sm text-gray-500">
                      마지막 확인: {new Date(status.last_checked_at).toLocaleString('ko-KR')}
                    </div>
                  )}
                  {status?.last_error && (
                    <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">
                      {status.last_error}
                    </div>
                  )}
                </div>
              )
            })}

            {/* 안내 메시지 */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-semibold text-blue-800 mb-2">API 키 안내</h4>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>- Claude API 키는 Anthropic Console에서 발급받을 수 있습니다.</li>
                <li>- GPT API 키는 OpenAI Platform에서 발급받을 수 있습니다.</li>
                <li>- Gemini API 키는 Google AI Studio에서 발급받을 수 있습니다.</li>
                <li>- API 키는 서버에 암호화되어 저장되며, 서버 재시작 후에도 유지됩니다.</li>
              </ul>
            </div>
          </div>
        )}

        {/* 시스템 정보 탭 */}
        {activeTab === 'system' && (
          <div className="space-y-6">
            {/* 백엔드 연결 상태 */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">백엔드 연결 상태</h3>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    backendStatus === 'connected' ? 'bg-green-500 animate-pulse' :
                    backendStatus === 'disconnected' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
                  }`}></div>
                  <span className={`font-medium ${
                    backendStatus === 'connected' ? 'text-green-600' :
                    backendStatus === 'disconnected' ? 'text-red-600' : 'text-yellow-600'
                  }`}>
                    {backendStatus === 'connected' ? '연결됨' :
                     backendStatus === 'disconnected' ? '연결 안됨' : '확인 중...'}
                  </span>
                </div>
                <span className="text-gray-500">|</span>
                <span className="text-sm text-gray-600 font-mono">{backendUrl}</span>
                <button
                  onClick={loadSystemInfo}
                  className="ml-auto px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                >
                  새로고침
                </button>
              </div>
            </div>

            {/* AI 모델별 비용 */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">AI 모델별 비용 (1건당 예상)</h3>
              {aiPricing?.pricing ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">모델</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">제공사</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">입력 (100만 토큰)</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">출력 (100만 토큰)</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">글 1건 예상 비용</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {aiPricing.pricing.map((model: any) => (
                        <tr key={model.model_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium">{model.model_id}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{model.provider}</td>
                          <td className="px-4 py-3 text-sm text-right">${model.input_price_per_1m}</td>
                          <td className="px-4 py-3 text-sm text-right">${model.output_price_per_1m}</td>
                          <td className="px-4 py-3 text-sm text-right font-semibold text-blue-600">
                            ₩{model.estimated_cost_per_post_krw?.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500">AI 비용 정보를 불러오는 중...</p>
              )}
            </div>

            {/* 구독 플랜 정보 */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">구독 플랜 가격</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">플랜</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">월간 가격</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">연간 가격</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">글 생성/월</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">분석/월</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">추가 글 단가</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">추가 분석 단가</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {plans.map((plan) => (
                      <tr key={plan.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium">
                          {plan.name}
                          {plan.id === 'pro' && (
                            <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">추천</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-right">
                          {plan.price_monthly === 0 ? '무료' : `₩${plan.price_monthly.toLocaleString()}`}
                        </td>
                        <td className="px-4 py-3 text-sm text-right">
                          {plan.price_yearly === 0 ? '-' : `₩${plan.price_yearly.toLocaleString()}`}
                        </td>
                        <td className="px-4 py-3 text-sm text-right">
                          {plan.posts_per_month === -1 ? '무제한' : plan.posts_per_month}
                        </td>
                        <td className="px-4 py-3 text-sm text-right">
                          {plan.analysis_per_month === -1 ? '무제한' : plan.analysis_per_month}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-orange-600">
                          ₩{plan.extra_post_price?.toLocaleString() || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-orange-600">
                          ₩{plan.extra_analysis_price?.toLocaleString() || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 크레딧 팩 가격 */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">크레딧 팩 가격</h3>
              <div className="grid md:grid-cols-2 gap-6">
                {/* 글 생성 크레딧 */}
                <div>
                  <h4 className="font-medium text-gray-700 mb-3">글 생성 크레딧</h4>
                  <div className="space-y-2">
                    {Object.values(CREDIT_PACKS)
                      .filter(pack => pack.credit_type === 'post')
                      .map(pack => (
                        <div key={pack.id} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                          <div>
                            <span className="font-medium">{pack.amount}개</span>
                            {(pack as any).discount_rate && (
                              <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">
                                {(pack as any).discount_rate}% 할인
                              </span>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="font-semibold">₩{pack.price.toLocaleString()}</span>
                            <span className="text-xs text-gray-500 ml-2">
                              (개당 ₩{Math.round(pack.price / pack.amount).toLocaleString()})
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* 분석 크레딧 */}
                <div>
                  <h4 className="font-medium text-gray-700 mb-3">분석 크레딧</h4>
                  <div className="space-y-2">
                    {Object.values(CREDIT_PACKS)
                      .filter(pack => pack.credit_type === 'analysis')
                      .map(pack => (
                        <div key={pack.id} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                          <div>
                            <span className="font-medium">{pack.amount}개</span>
                            {(pack as any).discount_rate && (
                              <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">
                                {(pack as any).discount_rate}% 할인
                              </span>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="font-semibold">₩{pack.price.toLocaleString()}</span>
                            <span className="text-xs text-gray-500 ml-2">
                              (개당 ₩{Math.round(pack.price / pack.amount).toLocaleString()})
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 환경 정보 */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">환경 정보</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-3 bg-gray-50 rounded">
                  <span className="text-gray-500">프론트엔드:</span>
                  <span className="ml-2 font-mono">{typeof window !== 'undefined' ? window.location.origin : '-'}</span>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <span className="text-gray-500">백엔드:</span>
                  <span className="ml-2 font-mono">{backendUrl}</span>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <span className="text-gray-500">NEXT_PUBLIC_API_URL:</span>
                  <span className="ml-2 font-mono">{process.env.NEXT_PUBLIC_API_URL || '(미설정)'}</span>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <span className="text-gray-500">환경:</span>
                  <span className="ml-2 font-mono">{process.env.NODE_ENV}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 법적 리스크 탭 */}
        {activeTab === 'legal' && (
          <div className="space-y-4">
            {/* 경고 배너 */}
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0">
                  <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-red-800">법적 리스크 가이드라인</h3>
                  <p className="text-sm text-red-700 mt-1">
                    이 시스템에 구현된 기능 중 법적으로 문제가 될 수 있는 항목들입니다.
                    서비스 운영 전 반드시 검토하고 필요한 조치를 취하세요.
                  </p>
                </div>
              </div>
            </div>

            {/* 위험도 요약 */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-red-100 border border-red-300 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-red-700">
                  {LEGAL_RISKS.filter(r => r.severity === 'critical').length}
                </div>
                <div className="text-sm text-red-600 font-medium">심각 (Critical)</div>
              </div>
              <div className="bg-orange-100 border border-orange-300 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-orange-700">
                  {LEGAL_RISKS.filter(r => r.severity === 'high').length}
                </div>
                <div className="text-sm text-orange-600 font-medium">높음 (High)</div>
              </div>
              <div className="bg-yellow-100 border border-yellow-300 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-yellow-700">
                  {LEGAL_RISKS.filter(r => r.severity === 'medium').length}
                </div>
                <div className="text-sm text-yellow-600 font-medium">보통 (Medium)</div>
              </div>
              <div className="bg-gray-100 border border-gray-300 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-gray-700">
                  {LEGAL_RISKS.filter(r => r.severity === 'low').length}
                </div>
                <div className="text-sm text-gray-600 font-medium">낮음 (Low)</div>
              </div>
            </div>

            {/* 리스크 목록 */}
            <div className="space-y-3">
              {LEGAL_RISKS.map((risk) => {
                const isExpanded = expandedRisk === risk.id
                const severityColors = {
                  critical: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-600 text-white', text: 'text-red-800' },
                  high: { bg: 'bg-orange-50', border: 'border-orange-200', badge: 'bg-orange-500 text-white', text: 'text-orange-800' },
                  medium: { bg: 'bg-yellow-50', border: 'border-yellow-200', badge: 'bg-yellow-500 text-white', text: 'text-yellow-800' },
                  low: { bg: 'bg-gray-50', border: 'border-gray-200', badge: 'bg-gray-500 text-white', text: 'text-gray-800' },
                }
                const colors = severityColors[risk.severity as keyof typeof severityColors]
                const severityLabel = {
                  critical: '심각',
                  high: '높음',
                  medium: '보통',
                  low: '낮음',
                }

                return (
                  <div key={risk.id} className={`rounded-lg border ${colors.border} ${colors.bg} overflow-hidden`}>
                    {/* 헤더 - 클릭 가능 */}
                    <button
                      onClick={() => setExpandedRisk(isExpanded ? null : risk.id)}
                      className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${colors.badge}`}>
                          {severityLabel[risk.severity as keyof typeof severityLabel]}
                        </span>
                        <span className={`font-semibold ${colors.text}`}>{risk.name}</span>
                      </div>
                      <svg
                        className={`w-5 h-5 ${colors.text} transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {/* 상세 내용 */}
                    {isExpanded && (
                      <div className="px-6 pb-6 space-y-4 border-t border-white/50">
                        {/* 설명 */}
                        <div className="pt-4">
                          <p className="text-gray-700">{risk.description}</p>
                          <p className="text-xs text-gray-500 mt-2 font-mono">위치: {risk.location}</p>
                        </div>

                        {/* 관련 법률 */}
                        <div className="bg-white/70 rounded-lg p-4">
                          <h4 className="font-semibold text-gray-800 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                            </svg>
                            관련 법률
                          </h4>
                          <ul className="space-y-1">
                            {risk.laws.map((law, idx) => (
                              <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                                <span className="text-blue-500 mt-1">•</span>
                                {law}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* 문제점 */}
                        <div className="bg-red-100/50 rounded-lg p-4">
                          <h4 className="font-semibold text-red-800 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            현재 문제점
                          </h4>
                          <ul className="space-y-1">
                            {risk.problems.map((problem, idx) => (
                              <li key={idx} className="text-sm text-red-700 flex items-start gap-2">
                                <span className="text-red-500 mt-1">•</span>
                                {problem}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* 해결 방안 */}
                        <div className="bg-green-100/50 rounded-lg p-4">
                          <h4 className="font-semibold text-green-800 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            해결 방안
                          </h4>
                          <ul className="space-y-1">
                            {risk.solutions.map((solution, idx) => (
                              <li key={idx} className="text-sm text-green-700 flex items-start gap-2">
                                <span className="text-green-500 mt-1">•</span>
                                {solution}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* 안전한 구현 방법 */}
                        <div className="bg-blue-100/50 rounded-lg p-4">
                          <h4 className="font-semibold text-blue-800 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                            안전한 구현 가이드
                          </h4>
                          <p className="text-sm text-blue-700">{risk.safeImplementation}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* 면책 조항 */}
            <div className="bg-gray-100 border border-gray-300 rounded-lg p-4 mt-6">
              <h4 className="font-semibold text-gray-700 mb-2">면책 조항</h4>
              <p className="text-sm text-gray-600">
                이 가이드라인은 참고용으로 제공되며, 법률 자문을 대체하지 않습니다.
                실제 서비스 운영 전 반드시 법률 전문가와 상담하시기 바랍니다.
                관련 법률은 변경될 수 있으며, 최신 법령을 확인하시기 바랍니다.
              </p>
            </div>
          </div>
        )}

        {/* 사용자 목록 */}
        {activeTab === 'users' && (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">이메일</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">이름</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">병원명</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">전문과목</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">승인 상태</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">글 무제한</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">사용 종료일</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">가입일</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-900">{user.email}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{user.name || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{user.hospital_name || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{user.specialty || '-'}</td>
                    <td className="px-6 py-4 text-sm">
                      {user.is_admin ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-purple-100 text-purple-800">
                          관리자
                        </span>
                      ) : user.is_approved ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">
                          승인됨
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">
                          대기 중
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {user.has_unlimited_posts ? (
                        <div className="flex flex-col gap-1">
                          <span className="px-2 py-1 text-xs rounded-full bg-indigo-100 text-indigo-800 inline-block w-fit">
                            무제한
                          </span>
                          {!user.is_admin && (
                            <button
                              onClick={() => handleUnlimitedAccess(user.id, false, user.email)}
                              className="text-xs text-red-600 hover:text-red-800"
                            >
                              해제
                            </button>
                          )}
                        </div>
                      ) : (
                        !user.is_admin && (
                          <button
                            onClick={() => handleUnlimitedAccess(user.id, true, user.email)}
                            className="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
                          >
                            부여
                          </button>
                        )
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {user.subscription_end_date ? formatDate(user.subscription_end_date) : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{formatDate(user.created_at)}</td>
                    <td className="px-6 py-4 text-sm">
                      {!user.is_admin && (
                        <div className="flex flex-col gap-2">
                          {!user.is_approved && (
                            <button
                              onClick={() => handleApprove(user.id, true)}
                              className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                            >
                              승인
                            </button>
                          )}
                          {user.is_approved && (
                            <button
                              onClick={() => handleApprove(user.id, false)}
                              className="px-3 py-1 bg-yellow-600 text-white text-xs rounded hover:bg-yellow-700"
                            >
                              승인 취소
                            </button>
                          )}
                          <button
                            onClick={() => setEditingUser(user)}
                            className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                          >
                            기간 설정
                          </button>
                          <button
                            onClick={() => handleDelete(user.id)}
                            className="px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700"
                          >
                            삭제
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {users.length === 0 && (
            <div className="text-center py-12 text-gray-500">사용자가 없습니다</div>
          )}
        </div>
        )}
      </div>

      {/* 사용 기간 설정 모달 */}
      {editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">사용 기간 설정</h3>
            <p className="text-sm text-gray-600 mb-4">
              사용자: {editingUser.email}
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                종료일
              </label>
              <input
                type="datetime-local"
                value={subscriptionEndDate}
                onChange={(e) => setSubscriptionEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleSetSubscription(editingUser.id)}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                설정
              </button>
              <button
                onClick={() => {
                  setEditingUser(null)
                  setSubscriptionEndDate('')
                }}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
