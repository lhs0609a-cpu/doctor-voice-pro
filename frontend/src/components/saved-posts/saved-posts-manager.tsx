'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import {
  FileText,
  Trash2,
  Image as ImageIcon,
  Sparkles,
  Calendar,
  Send,
  Edit3,
  Loader2,
  CheckCircle2,
  Database,
  X,
  Clock,
  FileEdit,
  Zap,
  PlayCircle,
  Plus,
  Layers,
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import { ExtensionStatusBadge, ExtensionStatusCard, EXTENSION_DOWNLOAD_URL } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { PublishGuide } from './publish-guide'
import type { SavedPost } from '@/types'

// 샘플 글 (항상 유지)
const SAMPLE_POST: SavedPost = {
  id: 'sample-post-001',
  savedAt: '2025-01-01T00:00:00.000Z',
  suggested_titles: ['정기 검진을 받지 않으면 놓치는 위험은?'],
  generated_content: `안녕하세요, 여러분의 건강을 책임지는 닥터보이스입니다.

오늘은 정기 검진의 중요성에 대해 이야기해 볼까 합니다. 많은 분들이 "나는 건강하니까 괜찮아"라고 생각하시지만, 사실 대부분의 질병은 초기에 증상이 없는 경우가 많습니다.

특히 고혈압, 당뇨, 암 같은 질환들은 초기에 발견하면 치료가 훨씬 쉽고, 완치율도 높아집니다.

40대 이상이시라면 최소 1년에 한 번, 50대 이상이시라면 6개월에 한 번은 검진을 받으시는 것을 권장드립니다.

여러분의 건강한 내일을 응원합니다!`,
  seo_keywords: ['정기검진', '건강검진', '예방의학', '건강관리', '암검진'],
  original_content: '',
}

type FinalAction = 'draft' | 'publishNow' | 'schedule'
type OpenType = 'public' | 'neighbor' | 'both' | 'private'

const ACTION_OPTIONS: { key: FinalAction; label: string; desc: string; icon: any }[] = [
  { key: 'draft', label: '임시저장', desc: '네이버에 초안으로 저장', icon: FileEdit },
  { key: 'publishNow', label: '즉시 발행', desc: '지금 바로 공개 발행', icon: Zap },
  { key: 'schedule', label: '예약 발행', desc: '원하는 시간에 자동 발행', icon: Clock },
]

// 확장 프로그램에 메시지 (externally_connectable)
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

// 이미지 → EXIF 제거된 base64 (canvas 재인코딩)
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
      resolve(canvas.toDataURL('image/jpeg', quality)) // 재인코딩으로 메타데이터 제거
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

export function SavedPostsManager() {
  const router = useRouter()
  const ext = useExtensionStatus()

  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([])
  const [selectedPost, setSelectedPost] = useState<SavedPost | null>(null)
  const [uploadedImages, setUploadedImages] = useState<File[]>([])
  const [imagePreview, setImagePreview] = useState<string[]>([])

  const [finalAction, setFinalAction] = useState<FinalAction>('publishNow')
  const [openType, setOpenType] = useState<OpenType>('public')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)

  // 글 붙여넣어 추가
  const [addOpen, setAddOpen] = useState(false)
  const [newText, setNewText] = useState('')

  // 저장된 글 로드 (샘플 항상 포함)
  useEffect(() => {
    const load = () => {
      try {
        const saved = localStorage.getItem('saved-posts')
        let posts: SavedPost[] = saved ? JSON.parse(saved) : []
        if (!posts.some((p) => p.id === SAMPLE_POST.id)) {
          posts = [...posts, SAMPLE_POST]
          localStorage.setItem('saved-posts', JSON.stringify(posts))
        }
        setSavedPosts(posts)
        const selectId = localStorage.getItem('saved-posts-select')
        if (selectId) {
          const p = posts.find((x) => x.id === selectId)
          if (p) setSelectedPost(p)
          localStorage.removeItem('saved-posts-select')
        }
      } catch {
        setSavedPosts([SAMPLE_POST])
      }
    }
    load()
    window.addEventListener('storage', load)
    return () => window.removeEventListener('storage', load)
  }, [])

  const deletePost = (id: string) => {
    if (id === SAMPLE_POST.id) { toast.error('샘플 글은 삭제할 수 없습니다'); return }
    const updated = savedPosts.filter((p) => p.id !== id)
    setSavedPosts(updated)
    localStorage.setItem('saved-posts', JSON.stringify(updated))
    if (selectedPost?.id === id) setSelectedPost(null)
    toast.success('글이 삭제되었습니다')
  }

  // 붙여넣은 글 저장 (첫 줄 = 제목, 나머지 = 본문)
  const addPastedPost = () => {
    const lines = newText.replace(/\r\n/g, '\n').split('\n')
    const firstIdx = lines.findIndex((l) => l.trim())
    if (firstIdx < 0) { toast.error('내용을 입력하세요'); return }
    const title = lines[firstIdx].trim()
    const body = lines.slice(firstIdx + 1).join('\n').trim()
    const post: SavedPost = {
      id: `post-${Date.now()}`,
      savedAt: new Date().toISOString(),
      suggested_titles: [title],
      generated_content: body || title,
      seo_keywords: [],
      original_content: '',
    }
    const updated = [post, ...savedPosts]
    setSavedPosts(updated)
    localStorage.setItem('saved-posts', JSON.stringify(updated))
    setSelectedPost(post)
    setNewText('')
    setAddOpen(false)
    toast.success('글이 저장되었습니다', { description: '오른쪽에서 사진 추가 후 발행하세요' })
  }

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []).filter((f) => f.type.startsWith('image/'))
    if (files.length === 0) { toast.error('이미지 파일만 업로드 가능합니다'); return }
    setUploadedImages(files)
    setImagePreview(files.map((f) => URL.createObjectURL(f)))
    toast.success(`사진 ${files.length}장 준비 완료`)
  }

  const removeImage = (idx: number) => {
    setUploadedImages((prev) => prev.filter((_, i) => i !== idx))
    setImagePreview((prev) => {
      URL.revokeObjectURL(prev[idx])
      return prev.filter((_, i) => i !== idx)
    })
  }

  // ── 핵심: 확장 프로그램으로 발행 (세션 재사용, 로그인 정보 없음) ──
  const publish = async () => {
    if (!selectedPost) { toast.error('발행할 글을 먼저 선택하세요'); return }
    if (!ext.connected || !ext.extensionId) {
      toast.error('확장 프로그램이 연결되지 않았습니다', {
        description: '상단 안내에서 확장 프로그램을 설치/실행한 뒤 다시 시도하세요',
      })
      return
    }

    let scheduleISO: string | null = null
    if (finalAction === 'schedule') {
      if (!scheduleDate || !scheduleTime) { toast.error('예약 날짜와 시간을 선택하세요'); return }
      const dt = new Date(`${scheduleDate}T${scheduleTime}`)
      if (isNaN(dt.getTime()) || dt.getTime() <= Date.now()) {
        toast.error('예약 시간은 현재 이후여야 합니다'); return
      }
      scheduleISO = `${scheduleDate}T${scheduleTime}`
    }

    setPublishing(true)
    const t = toast.loading('발행 준비 중...')
    try {
      // 이미지 EXIF 제거 후 base64
      const images: string[] = []
      if (uploadedImages.length) {
        toast.loading('사진 처리 중...', { id: t })
        for (const f of uploadedImages) images.push(await imageToCleanBase64(f))
      }

      const job = {
        id: selectedPost.id || `post-${Date.now()}`,
        title: selectedPost.suggested_titles?.[0] || selectedPost.title || '',
        content: selectedPost.generated_content || selectedPost.content || '',
        images,
        tags: selectedPost.seo_keywords || selectedPost.hashtags || [],
        options: { openType, search: true },
        finalAction,
        schedule: scheduleISO ? { datetime: scheduleISO } : null,
      }

      toast.loading('네이버 블로그로 전송 중...', { id: t })
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_JOB', job })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')

      const msg =
        finalAction === 'draft' ? { title: '임시저장을 시작했어요', desc: '새 탭에서 자동으로 초안이 저장됩니다' }
          : finalAction === 'schedule' ? { title: '예약 발행을 등록했어요', desc: `${scheduleDate} ${scheduleTime} 예약으로 자동 발행됩니다` }
            : { title: '발행을 시작했어요', desc: '새 탭에서 자동으로 글이 작성·발행됩니다' }
      toast.success(msg.title, { id: t, description: msg.desc })
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e.message || '다시 시도해주세요' })
    } finally {
      setPublishing(false)
    }
  }

  const title = (p: SavedPost) => p.suggested_titles?.[0] || p.title || '제목 없음'
  const body = (p: SavedPost) => p.generated_content || p.content || ''
  const canPublish = !!selectedPost && ext.connected && !publishing

  return (
    <div className="container mx-auto p-6 space-y-5 max-w-6xl">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">네이버 블로그 자동 발행</h1>
          <p className="text-muted-foreground mt-1">글 선택 → 사진 → 발행 방식, 순서대로 3단계면 끝납니다</p>
        </div>
        <div className="flex items-center gap-2">
          <ExtensionStatusBadge />
          <Button onClick={() => setAddOpen(true)} className="gap-2 bg-emerald-600 hover:bg-emerald-700">
            <Plus className="w-4 h-4" />
            글 붙여넣어 추가
          </Button>
          <Button variant="outline" onClick={() => router.push('/dashboard/bulk')} className="gap-2">
            <Layers className="w-4 h-4" />
            대량 발행
          </Button>
          <Button variant="outline" onClick={() => setGuideOpen(true)} className="gap-2">
            <PlayCircle className="w-4 h-4" />
            발행 가이드
          </Button>
        </div>
      </div>

      {/* 실시간 연동 신호등 + 버전 + 자동 업데이트 */}
      <ExtensionStatusCard />

      {/* 본문: 좌 글목록 / 우 3단계 발행 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* STEP 1. 글 선택 */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <StepDot n={1} done={!!selectedPost} />
              발행할 글 선택
            </CardTitle>
            <CardDescription>저장된 글 {savedPosts.length}개</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[560px] overflow-y-auto">
            {savedPosts.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p>저장된 글이 없습니다</p>
              </div>
            ) : (
              savedPosts.map((post) => {
                const active = selectedPost?.id === post.id
                return (
                  <div
                    key={post.id}
                    onClick={() => setSelectedPost(post)}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      active ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500'
                        : 'border-gray-200 hover:border-emerald-300 hover:bg-emerald-50/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-sm line-clamp-2 flex-1">{title(post)}</h3>
                      {active && <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-none" />}
                      {post.sourceType === 'database' && !active && (
                        <span className="flex-none inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-medium rounded">
                          <Database className="w-2.5 h-2.5" />DB
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                      <Calendar className="w-3 h-3" />
                      {new Date(post.savedAt).toLocaleDateString('ko-KR')}
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2.5">
                      <Button size="sm" variant="outline" className="h-7 text-xs"
                        onClick={(e) => { e.stopPropagation(); router.push(`/dashboard/editor/${post.id}`) }}>
                        <Edit3 className="w-3 h-3 mr-1" />편집
                      </Button>
                      <Button size="sm" variant="destructive" className="h-7 text-xs px-2"
                        onClick={(e) => { e.stopPropagation(); deletePost(post.id) }}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        {/* STEP 2·3. 사진 + 발행 방식 */}
        <Card className="lg:col-span-3">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">발행 준비</CardTitle>
            <CardDescription>
              {selectedPost ? `선택됨: ${title(selectedPost)}` : '왼쪽에서 글을 먼저 선택하세요'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!selectedPost ? (
              <div className="text-center py-16 text-muted-foreground">
                <Sparkles className="w-14 h-14 mx-auto mb-3 opacity-40" />
                <p className="text-lg">글을 선택하면 발행 준비가 시작됩니다</p>
              </div>
            ) : (
              <>
                {/* 글 미리보기 */}
                <div className="rounded-lg bg-gray-50 p-4 max-h-40 overflow-y-auto">
                  <p className="text-sm whitespace-pre-line leading-relaxed text-gray-700">
                    {body(selectedPost).slice(0, 300)}{body(selectedPost).length > 300 ? '…' : ''}
                  </p>
                </div>

                {/* STEP 2. 사진 */}
                <section className="space-y-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <StepDot n={2} done={uploadedImages.length > 0} />
                    사진 추가 <span className="text-xs font-normal text-muted-foreground">(선택)</span>
                  </div>
                  <label className="flex items-center justify-center gap-2 h-11 rounded-lg border-2 border-dashed border-gray-300 cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/40 text-sm text-gray-600">
                    <ImageIcon className="w-4 h-4" />
                    사진 선택 (여러 장 가능 · 촬영정보 자동 제거)
                    <input type="file" multiple accept="image/*" onChange={handleImageUpload} className="hidden" />
                  </label>
                  {uploadedImages.length > 0 && (
                    <div className="grid grid-cols-5 gap-2">
                      {imagePreview.map((src, i) => (
                        <div key={i} className="relative group">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={src} alt="" className="w-full h-16 object-cover rounded-md border" />
                          <button onClick={() => removeImage(i)}
                            className="absolute -top-1.5 -right-1.5 bg-rose-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition">
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {/* STEP 3. 발행 방식 */}
                <section className="space-y-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <StepDot n={3} done={false} />
                    발행 방식 선택
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {ACTION_OPTIONS.map((opt) => {
                      const Icon = opt.icon
                      const active = finalAction === opt.key
                      return (
                        <button key={opt.key} onClick={() => setFinalAction(opt.key)}
                          className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition ${
                            active ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500'
                              : 'border-gray-200 hover:border-emerald-300'
                          }`}>
                          <Icon className={`w-5 h-5 ${active ? 'text-emerald-600' : 'text-gray-400'}`} />
                          <span className="text-sm font-medium">{opt.label}</span>
                          <span className="text-[11px] text-muted-foreground leading-tight">{opt.desc}</span>
                        </button>
                      )
                    })}
                  </div>

                  {/* 예약 시간 */}
                  {finalAction === 'schedule' && (
                    <div className="grid grid-cols-2 gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
                      <div>
                        <Label className="text-xs text-amber-800">날짜</Label>
                        <Input type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-800">시간</Label>
                        <Input type="time" step={600} value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} className="mt-1" />
                      </div>
                      <p className="col-span-2 text-[11px] text-amber-700">※ 네이버 예약은 10분 단위 — 분은 자동 내림 처리됩니다</p>
                    </div>
                  )}

                  {/* 공개 범위 (발행 계열) */}
                  {finalAction !== 'draft' && (
                    <div>
                      <Label className="text-xs text-muted-foreground">공개 범위</Label>
                      <select value={openType} onChange={(e) => setOpenType(e.target.value as OpenType)}
                        className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                        <option value="public">전체 공개</option>
                        <option value="neighbor">이웃 공개</option>
                        <option value="both">서로이웃 공개</option>
                        <option value="private">비공개</option>
                      </select>
                    </div>
                  )}
                </section>

                {/* 발행 버튼 */}
                <div className="pt-1">
                  <Button size="lg" disabled={!canPublish} onClick={publish}
                    className="w-full h-12 text-base gap-2 bg-emerald-600 hover:bg-emerald-700">
                    {publishing ? (
                      <><Loader2 className="w-5 h-5 animate-spin" />발행 중...</>
                    ) : (
                      <><Send className="w-5 h-5" />
                        {finalAction === 'draft' ? '임시저장하기' : finalAction === 'schedule' ? '예약 발행하기' : '지금 발행하기'}
                      </>
                    )}
                  </Button>
                  {!ext.connected && (
                    <p className="mt-2 text-center text-xs text-rose-600">
                      확장 프로그램이 연결되어야 발행할 수 있어요 —{' '}
                      <a href={EXTENSION_DOWNLOAD_URL} target="_blank" rel="noopener noreferrer" className="underline font-medium">
                        설치하기
                      </a>
                    </p>
                  )}
                  <p className="mt-2 text-center text-[11px] text-muted-foreground">
                    브라우저에 네이버가 로그인되어 있어야 합니다(비밀번호는 저장하지 않아요). 미로그인 시 로그인 창이 열립니다.
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 글 붙여넣어 추가 */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="w-5 h-5 text-emerald-600" /> 글 붙여넣어 추가
            </DialogTitle>
            <DialogDescription>
              다른 곳에서 쓴 글을 붙여넣으세요. <b>첫 줄이 제목</b>, 나머지가 본문이 됩니다.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            placeholder={'첫 줄 = 제목\n\n본문 내용을 붙여넣으세요...'}
            className="min-h-[240px] text-sm"
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            여러 글을 한 번에 예약하려면 상단의 <b>대량 발행</b>을 이용하세요.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>취소</Button>
            <Button onClick={addPastedPost} className="bg-emerald-600 hover:bg-emerald-700 gap-2">
              <CheckCircle2 className="w-4 h-4" /> 저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 실시간 발행 가이드 */}
      <PublishGuide
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
        onDownloadExtension={() => window.open(EXTENSION_DOWNLOAD_URL, '_blank')}
        hasExtension={ext.connected}
        hasSelectedPost={!!selectedPost}
        hasImages={uploadedImages.length > 0}
        onStartPublish={publish}
      />
    </div>
  )
}

function StepDot({ n, done }: { n: number; done: boolean }) {
  return (
    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
      done ? 'bg-emerald-600 text-white' : 'bg-gray-200 text-gray-600'
    }`}>
      {done ? <CheckCircle2 className="w-4 h-4" /> : n}
    </span>
  )
}

// 전역 저장 훅 (다른 컴포넌트에서 사용)
export function useSavePost() {
  const savePost = (post: Record<string, any>) => {
    const savedPost = { ...post, id: `post-${Date.now()}`, savedAt: new Date().toISOString() }
    try {
      const existing = localStorage.getItem('saved-posts')
      const posts = existing ? JSON.parse(existing) : []
      localStorage.setItem('saved-posts', JSON.stringify([savedPost, ...posts]))
      toast.success('글이 저장되었습니다', { description: '저장된 글 탭에서 확인하세요' })
      return true
    } catch {
      toast.error('글 저장에 실패했습니다')
      return false
    }
  }
  return { savePost }
}
