'use client'

import { useEffect, useState } from 'react'
import { adminAPI } from '@/lib/api'
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

  useEffect(() => {
    loadUsers()
    checkAdminAccess()
  }, [filter])

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
          <p className="text-gray-600">사용자 승인 및 관리</p>
        </div>

        {/* 필터 */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
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
        </div>

        {/* 사용자 목록 */}
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
