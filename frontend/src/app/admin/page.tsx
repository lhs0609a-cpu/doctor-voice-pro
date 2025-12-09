'use client'

import { useEffect, useState } from 'react'
import { adminAPI, APIKeyInfo, APIKeyStatus } from '@/lib/api'
import type { User } from '@/types'
import { useRouter } from 'next/navigation'

export default function AdminPage() {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all')
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [subscriptionEndDate, setSubscriptionEndDate] = useState('')

  // API 키 관리 상태
  const [activeTab, setActiveTab] = useState<'users' | 'apikeys'>('users')
  const [apiKeyStatus, setApiKeyStatus] = useState<Record<string, APIKeyStatus>>({})
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({
    claude: '',
    gpt: '',
    gemini: ''
  })
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [savingProvider, setSavingProvider] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
    checkAdminAccess()
    loadAPIKeyStatus()
  }, [filter])

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
