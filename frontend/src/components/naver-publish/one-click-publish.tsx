'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useRef, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { Send, Upload, Image as ImageIcon, X, Loader2, FileEdit, Zap, Clock } from 'lucide-react'
import { ExtensionStatusCard } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { publishQueueAPI, type NaverCategory } from '@/lib/api'
import type { Post } from '@/types'

type FinalAction = 'draft' | 'publishNow' | 'schedule'
type OpenType = 'public' | 'neighbor' | 'both' | 'private'

const ACTIONS: { key: FinalAction; label: string; icon: any }[] = [
  { key: 'draft', label: '임시저장', icon: FileEdit },
  { key: 'publishNow', label: '즉시 발행', icon: Zap },
  { key: 'schedule', label: '예약 발행', icon: Clock },
]

function sendMessageToExtension(extId: string, message: any): Promise<any> {
  return new Promise((resolve, reject) => {
    if (typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      reject(new Error('Chrome API를 사용할 수 없습니다')); return
    }
    try {
      chrome.runtime.sendMessage(extId, message, (res: any) => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError)
        else resolve(res)
      })
    } catch (e) { reject(e) }
  })
}

// 이미지 → EXIF 제거된 base64
function imageToCleanBase64(file: File, maxWidth = 1280, quality = 0.9): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new window.Image()
    img.onload = () => {
      let w = img.width, h = img.height
      if (w > maxWidth) { h = Math.round((h * maxWidth) / w); w = maxWidth }
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('canvas 미지원')); return }
      ctx.drawImage(img, 0, 0, w, h)
      resolve(canvas.toDataURL('image/jpeg', quality))
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

interface OneClickPublishProps {
  post: Post
}

export function OneClickPublish({ post }: OneClickPublishProps) {
  const ext = useExtensionStatus()
  const [open, setOpen] = useState(false)
  const [images, setImages] = useState<{ file: File; preview: string }[]>([])
  const [finalAction, setFinalAction] = useState<FinalAction>('publishNow')
  const [openType, setOpenType] = useState<OpenType>('public')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [categories, setCategories] = useState<NaverCategory[]>([])
  const [category, setCategory] = useState('')        // '' = 네이버 기본 카테고리
  const [syncingCats, setSyncingCats] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 확장이 스스로 네이버 글쓰기를 열어 카테고리를 읽어오고 서버에 저장한다.
  // silent=true 면 자동 확보(첫 진입) — 실패해도 조용히 넘어가고 사용자가 직접 누를 수 있게 둔다.
  const syncCategories = useCallback(async (silent = false) => {
    if (!ext.extensionId) {
      if (!silent) toast.error('확장 프로그램이 연결되어 있지 않습니다')
      return
    }
    setSyncingCats(true)
    try {
      const res = await new Promise<any>((resolve) => {
        chrome.runtime.sendMessage(ext.extensionId, { action: 'SYNC_CATEGORIES' }, resolve)
      })
      if (!res?.success || !res.categories?.length) {
        if (!silent || res?.needLogin) {
          toast.error(res?.error || '카테고리를 불러오지 못했습니다')
        }
        return
      }
      await publishQueueAPI.setCategories(res.categories)
      setCategories(res.categories)
      if (!silent) toast.success(`카테고리 ${res.categories.length}개를 불러왔습니다`)
    } catch {
      if (!silent) toast.error('카테고리 동기화 실패')
    } finally {
      setSyncingCats(false)
    }
  }, [ext.extensionId])

  // 발행창을 열면: 캐시를 먼저 보여주고, 비어 있으면 확장이 네이버에 다녀와 자동으로 채운다.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    ;(async () => {
      let cached: NaverCategory[] = []
      try {
        const res = await publishQueueAPI.getCategories()
        cached = res.categories || []
      } catch { /* 캐시 없음 → 아래에서 자동 확보 */ }
      if (cancelled) return
      setCategories(cached)
      if (cached.length === 0) await syncCategories(true)
    })()
    return () => { cancelled = true }
  }, [open, syncCategories])

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []).filter((f) => f.type.startsWith('image/'))
    setImages((prev) => [...prev, ...files.map((file) => ({ file, preview: URL.createObjectURL(file) }))])
  }
  const removeImage = (index: number) => {
    setImages((prev) => {
      URL.revokeObjectURL(prev[index].preview)
      return prev.filter((_, i) => i !== index)
    })
  }

  const publish = async () => {
    if (!ext.connected || !ext.extensionId) {
      toast.error('확장 프로그램이 연결되지 않았습니다')
      return
    }
    let scheduleISO: string | null = null
    if (finalAction === 'schedule') {
      if (!scheduleDate || !scheduleTime) { toast.error('예약 날짜와 시간을 선택하세요'); return }
      const dt = new Date(`${scheduleDate}T${scheduleTime}`)
      if (isNaN(dt.getTime()) || dt.getTime() <= Date.now()) { toast.error('예약 시간은 현재 이후여야 합니다'); return }
      scheduleISO = `${scheduleDate}T${scheduleTime}`
    }

    setPublishing(true)
    const t = toast.loading('발행 준비 중...')
    try {
      const imageList: string[] = []
      if (images.length) {
        toast.loading('사진 처리 중...', { id: t })
        for (const img of images) imageList.push(await imageToCleanBase64(img.file))
      }
      const job = {
        title: post.title || post.suggested_titles?.[0] || '',
        content: post.generated_content || '',
        images: imageList,
        tags: post.seo_keywords || post.hashtags || [],
        options: { openType, search: true, category: category || null },
        finalAction,
        schedule: scheduleISO ? { datetime: scheduleISO } : null,
      }
      toast.loading('네이버 블로그로 전송 중...', { id: t })
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_JOB', job })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')

      const msg =
        finalAction === 'draft' ? { title: '임시저장을 시작했어요', desc: '새 탭에서 초안이 저장됩니다' }
          : finalAction === 'schedule' ? { title: '예약 발행을 등록했어요', desc: `${scheduleDate} ${scheduleTime} 예약` }
            : { title: '발행을 시작했어요', desc: '새 탭에서 자동으로 작성·발행됩니다' }
      toast.success(msg.title, { id: t, description: msg.desc })
      setOpen(false)
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e.message || '다시 시도해주세요' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <>
      <Button className="w-full bg-emerald-600 hover:bg-emerald-700 gap-2" size="lg" onClick={() => setOpen(true)}>
        <Send className="h-4 w-4" />
        네이버 블로그 발행
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-5 w-5 text-emerald-600" />
              네이버 블로그 발행
            </DialogTitle>
            <DialogDescription>사진과 발행 방식만 고르면 자동으로 작성됩니다</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* 실시간 연동 신호등 */}
            <ExtensionStatusCard />

            {/* 이미지 */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><ImageIcon className="h-4 w-4" />사진 추가 (선택)</Label>
              <input ref={fileInputRef} type="file" multiple accept="image/*" onChange={handleImageUpload} className="hidden" />
              <Button type="button" variant="outline" className="w-full" onClick={() => fileInputRef.current?.click()}>
                <Upload className="h-4 w-4 mr-2" />사진 선택 (촬영정보 자동 제거)
              </Button>
              {images.length > 0 && (
                <div className="grid grid-cols-4 gap-2 mt-2">
                  {images.map((img, index) => (
                    <div key={index} className="relative group">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.preview} alt="" className="w-full h-16 object-cover rounded border" />
                      <button onClick={() => removeImage(index)}
                        className="absolute -top-1 -right-1 bg-rose-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 발행 방식 */}
            <div className="space-y-2">
              <Label>발행 방식</Label>
              <div className="grid grid-cols-3 gap-2">
                {ACTIONS.map((opt) => {
                  const Icon = opt.icon
                  const active = finalAction === opt.key
                  return (
                    <button key={opt.key} onClick={() => setFinalAction(opt.key)}
                      className={`flex flex-col items-center gap-1 rounded-lg border p-2.5 transition ${
                        active ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500' : 'border-gray-200 hover:border-emerald-300'
                      }`}>
                      <Icon className={`w-4 h-4 ${active ? 'text-emerald-600' : 'text-gray-400'}`} />
                      <span className="text-xs font-medium">{opt.label}</span>
                    </button>
                  )
                })}
              </div>

              {finalAction === 'schedule' && (
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Input type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)} />
                  <Input type="time" step={600} value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} />
                  <p className="col-span-2 text-[11px] text-gray-500">※ 네이버 예약은 10분 단위 — 분은 자동 내림</p>
                </div>
              )}

              {finalAction !== 'draft' && (
                <div className="pt-1">
                  <Label className="text-xs text-gray-500">공개 범위</Label>
                  <select value={openType} onChange={(e) => setOpenType(e.target.value as OpenType)}
                    className="mt-1 w-full h-9 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="public">전체 공개</option>
                    <option value="neighbor">이웃 공개</option>
                    <option value="both">서로이웃 공개</option>
                    <option value="private">비공개</option>
                  </select>
                </div>
              )}

              {/* 카테고리 — 목록은 확장이 네이버 에디터에서 읽어와 서버에 캐시해 둔 것 */}
              {finalAction !== 'draft' && (
                <div className="pt-1">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-gray-500">카테고리</Label>
                    <button type="button" onClick={() => syncCategories(false)} disabled={syncingCats}
                      className="text-xs text-blue-600 hover:underline disabled:opacity-50">
                      {syncingCats ? '불러오는 중...' : '목록 새로고침'}
                    </button>
                  </div>
                  <select value={category} onChange={(e) => setCategory(e.target.value)}
                    disabled={syncingCats}
                    className="mt-1 w-full h-9 rounded-md border border-input bg-background px-3 text-sm disabled:opacity-60">
                    <option value="">네이버 기본 카테고리</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {syncingCats && categories.length === 0 && (
                    <p className="mt-1 text-[11px] text-gray-500">네이버에서 카테고리를 불러오는 중...</p>
                  )}
                  {!syncingCats && categories.length === 0 && (
                    <p className="mt-1 text-[11px] text-gray-500">
                      카테고리를 불러오지 못했습니다. 네이버 로그인 상태를 확인한 뒤 &lsquo;목록 새로고침&rsquo;을 눌러주세요.
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* 글 미리보기 */}
            <div className="p-3 bg-gray-50 rounded-lg space-y-1">
              <p className="text-sm font-medium truncate">{post.title || post.suggested_titles?.[0] || '제목 없음'}</p>
              <p className="text-xs text-gray-500">{(post.generated_content || '').slice(0, 100)}...</p>
            </div>

            <p className="text-[11px] text-muted-foreground text-center">
              브라우저에 네이버가 로그인되어 있어야 합니다(비밀번호 저장 안 함). 미로그인 시 로그인 창이 열립니다.
            </p>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>취소</Button>
            <Button className="bg-emerald-600 hover:bg-emerald-700 gap-2" onClick={publish} disabled={publishing || !ext.connected}>
              {publishing ? (
                <><Loader2 className="h-4 w-4 animate-spin" />발행 중...</>
              ) : (
                <><Send className="h-4 w-4" />
                  {finalAction === 'draft' ? '임시저장' : finalAction === 'schedule' ? '예약 발행' : '지금 발행'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
