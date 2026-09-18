'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */

import { useState, useRef, useEffect } from 'react'
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
import { LauncherCard, TargetBlogSelect, useTargetBlog } from '@/components/launcher/launcher-card'
import { buildInterleavedBlocks, extractKeywords } from '@/lib/post-blocks'
import { publishQueueAPI, type NaverCategory } from '@/lib/api'
import type { Post } from '@/types'
import { cn } from '@/lib/utils'

type FinalAction = 'draft' | 'publishNow' | 'schedule'
type OpenType = 'public' | 'neighbor' | 'both' | 'private'

const ACTIONS: { key: FinalAction; label: string; icon: any }[] = [
  { key: 'draft', label: '임시저장', icon: FileEdit },
  { key: 'publishNow', label: '즉시 발행', icon: Zap },
  { key: 'schedule', label: '예약 발행', icon: Clock },
]

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

const LABEL = 'text-[13px] font-medium text-muted-foreground'
const SELECT = 'mt-1 h-9 w-full rounded-lg border border-input bg-card px-3 text-sm disabled:opacity-60'

export function OneClickPublish({ post }: OneClickPublishProps) {
  const target = useTargetBlog()
  const [open, setOpen] = useState(false)
  const [images, setImages] = useState<{ file: File; preview: string }[]>([])
  const [finalAction, setFinalAction] = useState<FinalAction>('publishNow')
  const [openType, setOpenType] = useState<OpenType>('public')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [categories, setCategories] = useState<NaverCategory[]>([])
  const [category, setCategory] = useState('')        // '' = 네이버 기본 카테고리
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 카테고리 목록은 PC 실행기가 네이버 에디터에서 읽어 서버에 저장해 둔다.
  // 아직 한 번도 돌지 않았으면 비어 있고, 그때는 네이버 기본 카테고리로 나간다.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await publishQueueAPI.getCategories()
        if (!cancelled) setCategories(res.categories || [])
      } catch { /* 캐시 없음 — 기본 카테고리로 발행 */ }
    })()
    return () => { cancelled = true }
  }, [open])

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
    if (!target.blogRefId) {
      toast.error('발행할 블로그를 먼저 고르세요', { description: '원스톱 자동화의 연결 설정에서 네이버 블로그를 등록할 수 있습니다' })
      return
    }
    let scheduleISO: string | null = null
    if (finalAction === 'schedule') {
      if (!scheduleDate || !scheduleTime) { toast.error('예약 날짜와 시간을 선택하세요'); return }
      const dt = new Date(`${scheduleDate}T${scheduleTime}`)
      // 실행기가 에디터를 열 시간이 필요하다. 서버도 같은 기준으로 거른다.
      if (isNaN(dt.getTime()) || dt.getTime() <= Date.now() + 5 * 60 * 1000) {
        toast.error('예약 시간은 지금부터 5분 뒤 이후여야 합니다'); return
      }
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
      const title = post.title || post.suggested_titles?.[0] || ''
      const content = post.generated_content || ''
      toast.loading('PC 실행기에 넘길 준비 중...', { id: t })
      await publishQueueAPI.enqueueJob({
        title,
        blocks: buildInterleavedBlocks(content || title, imageList),
        tags: post.seo_keywords || post.hashtags || [],
        emphasize: extractKeywords(content || title),
        scheduled_at: scheduleISO,
        final_action: finalAction === 'publishNow' ? 'publish' : finalAction,
        open_type: openType,
        search: true,
        category: category || null,
        blog_ref_id: target.blogRefId,
      })

      const where = target.selected?.label || target.blogId
      const msg =
        finalAction === 'draft' ? { title: '임시저장을 맡겼어요', desc: `${where} · 실행기가 초안으로 저장합니다` }
          : finalAction === 'schedule' ? { title: '예약 발행을 맡겼어요', desc: `${where} · ${scheduleDate} ${scheduleTime} 예약으로 등록합니다` }
            : { title: '발행을 맡겼어요', desc: `${where} · 실행기가 바로 작성·발행합니다` }
      toast.success(msg.title, { id: t, description: msg.desc + '. 이 창을 닫아도 됩니다.' })
      setOpen(false)
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e?.response?.data?.detail || e.message || '다시 시도해주세요' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <>
      <Button className="w-full" size="lg" onClick={() => setOpen(true)}>
        <Send />
        네이버 블로그 발행
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-md overflow-y-auto">
          <DialogHeader>
            <DialogTitle>네이버 블로그 발행</DialogTitle>
            <DialogDescription>사진과 발행 방식만 고르면 자동으로 작성됩니다</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* 어느 블로그로 보낼지 + 실행기 안내 */}
            <div className="space-y-2">
              <Label className={LABEL}>발행할 블로그</Label>
              <TargetBlogSelect
                blogs={target.blogs} value={target.blogRefId} onChange={target.choose}
                loading={target.loading} onRefresh={target.refresh}
              />
            </div>
            <LauncherCard compact />

            {/* 이미지 */}
            <div className="space-y-2">
              <Label className={cn(LABEL, 'flex items-center gap-2')}><ImageIcon className="h-4 w-4" />사진 추가 (선택)</Label>
              <input ref={fileInputRef} type="file" multiple accept="image/*" onChange={handleImageUpload} className="hidden" />
              <Button type="button" variant="outline" className="w-full" onClick={() => fileInputRef.current?.click()}>
                <Upload />사진 선택 (촬영정보 자동 제거)
              </Button>
              {images.length > 0 && (
                <div className="mt-2 grid grid-cols-4 gap-2">
                  {images.map((img, index) => (
                    <div key={index} className="group relative">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.preview} alt="" className="h-16 w-full rounded-md border object-cover" />
                      <button onClick={() => removeImage(index)}
                        className="absolute -right-1 -top-1 rounded-full bg-destructive p-0.5 text-destructive-foreground opacity-0 transition group-hover:opacity-100">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 발행 방식 */}
            <div className="space-y-2">
              <Label className={LABEL}>발행 방식</Label>
              <div className="grid grid-cols-3 gap-2">
                {ACTIONS.map((opt) => {
                  const Icon = opt.icon
                  const active = finalAction === opt.key
                  return (
                    <button key={opt.key} onClick={() => setFinalAction(opt.key)}
                      className={cn(
                        'flex flex-col items-center gap-1 rounded-lg border p-2.5 transition-colors',
                        active ? 'border-primary bg-accent text-accent-foreground' : 'hover:bg-muted'
                      )}>
                      <Icon className={cn('h-4 w-4', active ? 'text-primary' : 'text-muted-foreground')} />
                      <span className="text-xs font-medium">{opt.label}</span>
                    </button>
                  )
                })}
              </div>

              {finalAction === 'schedule' && (
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Input type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)} />
                  <Input type="time" step={600} value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} />
                  <p className="col-span-2 text-[11px] text-muted-foreground">※ 네이버 예약은 10분 단위 — 분은 자동 내림</p>
                </div>
              )}

              {finalAction !== 'draft' && (
                <div className="pt-1">
                  <Label className={LABEL}>공개 범위</Label>
                  <select value={openType} onChange={(e) => setOpenType(e.target.value as OpenType)} className={SELECT}>
                    <option value="public">전체 공개</option>
                    <option value="neighbor">이웃 공개</option>
                    <option value="both">서로이웃 공개</option>
                    <option value="private">비공개</option>
                  </select>
                </div>
              )}

              {/* 카테고리 — 목록은 PC 실행기가 네이버 에디터에서 읽어와 서버에 캐시해 둔 것 */}
              {finalAction !== 'draft' && (
                <div className="pt-1">
                  <Label className={LABEL}>카테고리</Label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className={SELECT}>
                    <option value="">네이버 기본 카테고리</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {categories.length === 0 && (
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      카테고리 목록은 PC 실행기가 처음 한 번 네이버에 다녀오면 채워집니다. 그전까지는 기본 카테고리로 발행됩니다.
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* 글 미리보기 */}
            <div className="space-y-1 rounded-lg bg-muted p-3">
              <p className="truncate text-sm font-medium">{post.title || post.suggested_titles?.[0] || '제목 없음'}</p>
              <p className="text-xs text-muted-foreground">{(post.generated_content || '').slice(0, 100)}...</p>
            </div>

            <p className="text-center text-[11px] text-muted-foreground">
              PC 실행기가 켜져 있어야 등록됩니다. 네이버 로그인은 실행기가 연 크롬 창에서 한 번만 하면 유지됩니다.
            </p>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>취소</Button>
            <Button onClick={publish} disabled={publishing || !target.blogRefId}>
              {publishing ? (
                <><Loader2 className="animate-spin" />발행 중...</>
              ) : (
                <><Send />
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
