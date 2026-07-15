'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import {
  FileText,
  Trash2,
  Image as ImageIcon,
  Save,
  Send,
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
  Folder,
  Upload,
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import { ExtensionStatusBadge, ExtensionStatusCard, EXTENSION_DOWNLOAD_URL } from '@/components/extension-status'
import { useExtensionStatus } from '@/lib/use-extension-status'
import { PublishGuide } from './publish-guide'
import { mediaPoolAPI, type PoolCollectionItem } from '@/lib/api'
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
type ScheduleMode = 'manual' | 'interval'

// 예약 준비함 항목 (이미지는 base64로 확정 저장 → 나중에 한 번에 발행)
interface PreparedItem {
  id: string
  title: string
  content: string
  images: string[]
  tags: string[]
  emphasize: string[]
  openType: OpenType
  scheduleISO: string
}

const ACTION_OPTIONS: { key: FinalAction; label: string; desc: string; icon: any }[] = [
  { key: 'draft', label: '임시저장', desc: '네이버에 초안으로 저장', icon: FileEdit },
  { key: 'publishNow', label: '즉시 발행', desc: '지금 바로 공개 발행', icon: Zap },
  { key: 'schedule', label: '예약 발행', desc: '원하는 시간에 자동 발행', icon: Clock },
]

const INTERVAL_PRESETS = [2, 3, 4, 6]

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

// 본문에서 자동 강조할 키워드(반복 단어) 추출 — 조사 제거 + 불용어 제외 + 빈도순
const _JOSA = ['으로써','으로서','이라고','라고','에서는','에서도','으로','에서','에게','한테','부터','까지','처럼','같이','마다','조차','밖에','이나','라도','이란','은','는','이','가','을','를','에','와','과','도','만','의','로']
const _STOP = new Set(['그리고','그러나','하지만','그래서','또한','또는','그런데','때문','위해','통해','대해','경우','정도','우리','여러분','있습니다','합니다','입니다','습니다','됩니다','있는','하는','되는','매우','정말','너무','아주','가장','모든','다양한','오늘','안녕하세요','감사합니다'])
function stripJosa(w: string): string {
  if (!/[가-힣]$/.test(w)) return w
  for (const j of _JOSA) if (w.endsWith(j) && w.length - j.length >= 2) return w.slice(0, -j.length)
  return w
}
function extractKeywords(text: string, topN = 6): string[] {
  const counts = new Map<string, number>()
  const words = (text || '').match(/[가-힣A-Za-z0-9]+/g) || []
  for (const raw of words) {
    const w = stripJosa(raw)
    if (w.length < 2 || _STOP.has(w) || /^[0-9]+$/.test(w)) continue
    counts.set(w, (counts.get(w) || 0) + 1)
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1])
  const repeated = sorted.filter(([, c]) => c >= 2).map(([w]) => w)
  return repeated.slice(0, topN)
}

// 텍스트에서 첫 비어있지 않은 줄
function firstLine(text: string): string {
  const line = text.replace(/\r\n/g, '\n').split('\n').find((l) => l.trim())
  return (line || '').trim()
}

// 제목/본문 분리: 제목칸이 비면 본문 첫 줄을 제목으로 올린다
function splitTitleBody(rawTitle: string, rawBody: string): { title: string; body: string } {
  const t = rawTitle.trim()
  if (t) return { title: t, body: rawBody.trim() || t }
  const lines = rawBody.replace(/\r\n/g, '\n').split('\n')
  const idx = lines.findIndex((l) => l.trim())
  if (idx < 0) return { title: '', body: '' }
  const title = lines[idx].trim()
  const body = lines.slice(idx + 1).join('\n').trim()
  return { title, body: body || title }
}

// Date → <input datetime> 로컬 문자열 (YYYY-MM-DDTHH:mm)
function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

function fmtKo(d: Date): string {
  return d.toLocaleString('ko-KR', {
    month: 'long', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export function SavedPostsManager() {
  const router = useRouter()
  const ext = useExtensionStatus()

  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([])

  // 인라인 에디터(글 따로/사진 따로 없이 한 화면)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftBody, setDraftBody] = useState('')

  const [uploadedImages, setUploadedImages] = useState<File[]>([])
  const [imagePreview, setImagePreview] = useState<string[]>([])

  // 사진 소스: 직접 업로드 | 저장된 목록
  const [photoMode, setPhotoMode] = useState<'upload' | 'collection'>('upload')
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)
  const [collectionCount, setCollectionCount] = useState(12) // 이 글에 넣을 장수(기억됨)

  const [finalAction, setFinalAction] = useState<FinalAction>('publishNow')
  const [openType, setOpenType] = useState<OpenType>('public')

  // 예약 발행: 직접 지정 | 간격 예약
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>('manual')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [intervalHours, setIntervalHours] = useState(3)
  const [lastScheduledAt, setLastScheduledAt] = useState<string | null>(null)
  const [scheduleLog, setScheduleLog] = useState<{ title: string; at: string }[]>([]) // 잡아둔 예약 기록

  const [publishing, setPublishing] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)

  // 예약 준비함: 발행하지 않고 담아뒀다가 나중에 한 번에 처리
  const [prepared, setPrepared] = useState<PreparedItem[]>([])
  const [preparing, setPreparing] = useState(false)

  // 저장된 글 로드 (샘플 항상 포함) + 선택 요청 반영
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
          if (p) {
            setSelectedId(p.id)
            setDraftTitle(p.suggested_titles?.[0] || p.title || '')
            setDraftBody(p.generated_content || p.content || '')
          }
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

  // 사진 목록 로드 + 저장해둔 장수/선택 목록/예약 설정 복원
  useEffect(() => {
    const savedCount = Number(localStorage.getItem('doctorvoice-collection-count'))
    if (savedCount >= 1) setCollectionCount(savedCount)
    const savedCol = localStorage.getItem('doctorvoice-collection-id')
    const savedInterval = Number(localStorage.getItem('doctorvoice-schedule-interval'))
    if (savedInterval >= 1) setIntervalHours(savedInterval)
    const lastSched = localStorage.getItem('doctorvoice-last-schedule')
    if (lastSched) setLastScheduledAt(lastSched)
    try {
      const log = JSON.parse(localStorage.getItem('doctorvoice-schedule-log') || '[]')
      if (Array.isArray(log)) setScheduleLog(log)
    } catch { /* noop */ }
    try {
      const prep = JSON.parse(localStorage.getItem('doctorvoice-prepared') || '[]')
      if (Array.isArray(prep)) setPrepared(prep)
    } catch { /* noop */ }
    mediaPoolAPI.listCollections().then((data) => {
      setCollections(data.collections)
      if (savedCol && data.collections.some((c) => c.id === savedCol)) {
        setSelectedCollectionId(savedCol)
        setPhotoMode('collection')
      }
    }).catch(() => {})
  }, [])

  // 장수/선택 목록/간격은 다음에도 쓰도록 기억
  useEffect(() => {
    localStorage.setItem('doctorvoice-collection-count', String(collectionCount))
  }, [collectionCount])
  useEffect(() => {
    if (selectedCollectionId) localStorage.setItem('doctorvoice-collection-id', selectedCollectionId)
  }, [selectedCollectionId])
  useEffect(() => {
    localStorage.setItem('doctorvoice-schedule-interval', String(intervalHours))
  }, [intervalHours])

  // ── 에디터로 글 불러오기 / 새 글 ──
  const loadPost = (post: SavedPost) => {
    setSelectedId(post.id)
    setDraftTitle(post.suggested_titles?.[0] || post.title || '')
    setDraftBody(post.generated_content || post.content || '')
  }
  const newDraft = () => {
    setSelectedId(null)
    setDraftTitle('')
    setDraftBody('')
  }

  const persist = (posts: SavedPost[]) => {
    setSavedPosts(posts)
    localStorage.setItem('saved-posts', JSON.stringify(posts))
  }

  const deletePost = (id: string) => {
    if (id === SAMPLE_POST.id) { toast.error('샘플 글은 삭제할 수 없습니다'); return }
    persist(savedPosts.filter((p) => p.id !== id))
    if (selectedId === id) newDraft()
    toast.success('글이 삭제되었습니다')
  }

  // 현재 에디터 내용을 목록에 저장(신규 or 수정). 반환: 저장된 id
  const saveDraft = (silent = false): string | null => {
    const { title, body } = splitTitleBody(draftTitle, draftBody)
    if (!title && !body) { if (!silent) toast.error('제목이나 본문을 입력하세요'); return null }

    let id = selectedId
    if (id && id !== SAMPLE_POST.id && savedPosts.some((p) => p.id === id)) {
      persist(savedPosts.map((p) => (p.id === id
        ? { ...p, suggested_titles: [title], generated_content: body || title }
        : p)))
    } else {
      id = `post-${Date.now()}`
      const post: SavedPost = {
        id, savedAt: new Date().toISOString(),
        suggested_titles: [title], generated_content: body || title,
        seo_keywords: [], original_content: '',
      }
      persist([post, ...savedPosts])
    }
    setSelectedId(id)
    if (!silent) toast.success('글을 저장했습니다', { description: '왼쪽 목록에서 다시 쓸 수 있어요' })
    return id
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

  // 간격 예약: (마지막 예약 or 지금) + intervalHours, 10분 내림, 과거면 지금 기준
  const computeIntervalSlot = (): Date => {
    const now = Date.now()
    const base = lastScheduledAt ? new Date(lastScheduledAt).getTime() : now
    let t = base + intervalHours * 3600_000
    if (t <= now) t = now + intervalHours * 3600_000
    const d = new Date(t)
    d.setMinutes(Math.floor(d.getMinutes() / 10) * 10, 0, 0)
    return d
  }

  const resetSchedule = () => {
    localStorage.removeItem('doctorvoice-last-schedule')
    localStorage.removeItem('doctorvoice-schedule-log')
    setLastScheduledAt(null)
    setScheduleLog([])
    toast.success('예약 기준과 현황을 초기화했어요')
  }

  // 지나간(과거) 예약은 현황에서 정리
  const upcomingLog = scheduleLog.filter((x) => new Date(x.at).getTime() > Date.now())

  // ── 핵심: 확장 프로그램으로 발행 (세션 재사용, 로그인 정보 없음) ──
  const publish = async () => {
    const { title: finalTitle, body: finalBody } = splitTitleBody(draftTitle, draftBody)
    if (!finalBody && !finalTitle) { toast.error('발행할 글을 입력하세요'); return }
    if (!ext.connected || !ext.extensionId) {
      toast.error('확장 프로그램이 연결되지 않았습니다', {
        description: '상단 안내에서 확장 프로그램을 설치/실행한 뒤 다시 시도하세요',
      })
      return
    }

    let scheduleISO: string | null = null
    if (finalAction === 'schedule') {
      let dt: Date
      if (scheduleMode === 'interval') {
        dt = computeIntervalSlot()
      } else {
        if (!scheduleDate || !scheduleTime) { toast.error('예약 날짜와 시간을 선택하세요'); return }
        dt = new Date(`${scheduleDate}T${scheduleTime}`)
      }
      if (isNaN(dt.getTime()) || dt.getTime() <= Date.now()) {
        toast.error('예약 시간은 현재 이후여야 합니다'); return
      }
      scheduleISO = toLocalInput(dt)
    }

    // 발행 시 목록에도 자동 저장(다시 쓰기 편하게)
    const savedId = saveDraft(true)
    const src = savedPosts.find((p) => p.id === selectedId)
    const tags = src?.seo_keywords || src?.hashtags || []

    setPublishing(true)
    const t = toast.loading('발행 준비 중...')
    try {
      // 이미지 준비: 저장된 목록에서 유니크화 배정 or 직접 업로드(EXIF 제거)
      const images: string[] = []
      if (photoMode === 'collection' && selectedCollectionId) {
        toast.loading('목록에서 사진을 유니크화하는 중...', { id: t })
        const res = await mediaPoolAPI.assign({
          count: collectionCount,
          collection_id: selectedCollectionId,
          post_id: savedId || undefined,
        })
        for (const a of res.images) images.push(a.image)
        if (images.length === 0) throw new Error('목록에서 사진을 가져오지 못했습니다. 목록에 사진이 있는지 확인하세요.')
        if (res.warnings?.length) {
          toast.warning(`사진 ${res.returned}장 배정 (일부 유의)`, { description: res.warnings[0] })
        }
      } else if (uploadedImages.length) {
        toast.loading('사진 처리 중...', { id: t })
        for (const f of uploadedImages) images.push(await imageToCleanBase64(f))
      }

      const job = {
        id: savedId || `post-${Date.now()}`,
        title: finalTitle,
        content: finalBody || finalTitle,
        images,
        tags,
        emphasize: extractKeywords(finalBody || finalTitle), // 핵심 키워드 자동 굵게
        options: { openType, search: true },
        finalAction,
        schedule: scheduleISO ? { datetime: scheduleISO } : null,
      }

      toast.loading('네이버 블로그로 전송 중...', { id: t })
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_JOB', job })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')

      // 예약이면 다음 글 간격 계산 기준으로 기억 + 예약 현황에 기록
      if (finalAction === 'schedule' && scheduleISO) {
        localStorage.setItem('doctorvoice-last-schedule', scheduleISO)
        setLastScheduledAt(scheduleISO)
        setScheduleLog((prev) => {
          const next = [...prev, { title: finalTitle || '(제목 없음)', at: scheduleISO! }]
            .sort((a, b) => a.at.localeCompare(b.at))
            .slice(-50) // 최근 50건만 유지
          localStorage.setItem('doctorvoice-schedule-log', JSON.stringify(next))
          return next
        })
      }

      const when = scheduleISO ? scheduleISO.replace('T', ' ') : ''
      const msg =
        finalAction === 'draft' ? { title: '임시저장을 시작했어요', desc: '새 탭에서 자동으로 초안이 저장됩니다' }
          : finalAction === 'schedule' ? { title: '예약 발행을 등록했어요', desc: `${when} 예약으로 자동 발행됩니다` }
            : { title: '발행을 시작했어요', desc: '새 탭에서 자동으로 글이 작성·발행됩니다' }
      toast.success(msg.title, { id: t, description: msg.desc })
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e.message || '다시 시도해주세요' })
    } finally {
      setPublishing(false)
    }
  }

  // 현재 편집 중인 글을 '예약 준비함'에 담기 (발행하지 않음)
  const preparePost = async () => {
    const { title: finalTitle, body: finalBody } = splitTitleBody(draftTitle, draftBody)
    if (!finalBody && !finalTitle) { toast.error('담을 글을 입력하세요'); return }
    let dt: Date
    if (scheduleMode === 'interval') {
      dt = computeIntervalSlot()
    } else {
      if (!scheduleDate || !scheduleTime) { toast.error('예약 날짜와 시간을 선택하세요'); return }
      dt = new Date(`${scheduleDate}T${scheduleTime}`)
    }
    if (isNaN(dt.getTime()) || dt.getTime() <= Date.now()) { toast.error('예약 시간은 현재 이후여야 합니다'); return }
    const scheduleISO = toLocalInput(dt)

    const savedId = saveDraft(true)
    const src = savedPosts.find((p) => p.id === selectedId)
    const tags = src?.seo_keywords || src?.hashtags || []

    setPreparing(true)
    const t = toast.loading('준비함에 담는 중... (사진 처리 포함)')
    try {
      const images: string[] = []
      if (photoMode === 'collection' && selectedCollectionId) {
        const res = await mediaPoolAPI.assign({
          count: collectionCount, collection_id: selectedCollectionId, post_id: savedId || undefined,
        })
        for (const a of res.images) images.push(a.image)
      } else if (uploadedImages.length) {
        for (const f of uploadedImages) images.push(await imageToCleanBase64(f))
      }
      const item: PreparedItem = {
        id: savedId || `post-${Date.now()}`,
        title: finalTitle, content: finalBody || finalTitle,
        images, tags, emphasize: extractKeywords(finalBody || finalTitle),
        openType, scheduleISO,
      }
      const nextCount = prepared.length + 1
      setPrepared((prev) => {
        const next = [...prev, item].sort((a, b) => a.scheduleISO.localeCompare(b.scheduleISO))
        try { localStorage.setItem('doctorvoice-prepared', JSON.stringify(next)) }
        catch { toast.warning('저장 공간 부족 — 사진이 많으면 사진 풀(목록)을 쓰는 걸 권장해요') }
        return next
      })
      // 다음 글이 겹치지 않도록 예약 기준 갱신
      localStorage.setItem('doctorvoice-last-schedule', scheduleISO)
      setLastScheduledAt(scheduleISO)
      toast.success('예약 준비함에 담았어요', { id: t, description: `${fmtKo(dt)} 예약 · 준비 ${nextCount}건` })
      newDraft() // 다음 글 작성 준비
    } catch (e: any) {
      toast.error('담기 실패', { id: t, description: e.message || '다시 시도해주세요' })
    } finally {
      setPreparing(false)
    }
  }

  // 준비함의 모든 글을 확장으로 한 번에 예약 발행
  const publishAllPrepared = async () => {
    if (!ext.connected || !ext.extensionId) { toast.error('확장 프로그램이 연결되지 않았습니다'); return }
    if (prepared.length === 0) return
    setPublishing(true)
    const t = toast.loading(`준비한 ${prepared.length}건 예약 등록 시작...`)
    try {
      const jobs = prepared.map((p) => ({
        id: p.id, title: p.title, content: p.content, images: p.images,
        tags: p.tags, emphasize: p.emphasize,
        options: { openType: p.openType, search: true },
        finalAction: 'schedule', schedule: { datetime: p.scheduleISO },
      }))
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_BATCH', jobs })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')
      // 준비함 → 예약 기록으로 이동
      setScheduleLog((prev) => {
        const next = [...prev, ...prepared.map((p) => ({ title: p.title, at: p.scheduleISO }))]
          .sort((a, b) => a.at.localeCompare(b.at)).slice(-50)
        localStorage.setItem('doctorvoice-schedule-log', JSON.stringify(next))
        return next
      })
      setPrepared([]); localStorage.removeItem('doctorvoice-prepared')
      toast.success(`${jobs.length}건 예약 등록을 시작했어요`, {
        id: t, description: '새 탭에서 순차적으로 네이버 예약발행됩니다. 완료까지 창을 열어두세요.',
      })
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e.message || '다시 시도해주세요' })
    } finally {
      setPublishing(false)
    }
  }

  const removePrepared = (id: string) => {
    setPrepared((prev) => {
      const next = prev.filter((p) => p.id !== id)
      localStorage.setItem('doctorvoice-prepared', JSON.stringify(next))
      return next
    })
  }

  const listTitle = (p: SavedPost) => p.suggested_titles?.[0] || p.title || '제목 없음'
  const hasContent = !!(draftTitle.trim() || draftBody.trim())
  const canPublish = hasContent && ext.connected && !publishing
  const intervalSlot = computeIntervalSlot()

  return (
    <div className="container mx-auto p-6 space-y-5 max-w-6xl">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">네이버 블로그 자동 발행</h1>
          <p className="text-muted-foreground mt-1">글을 붙여넣고 사진을 더한 뒤 바로 발행 — 한 화면에서 끝납니다</p>
        </div>
        <div className="flex items-center gap-2">
          <ExtensionStatusBadge />
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

      {/* 본문: 좌 저장 목록(재사용) / 우 인라인 작성+발행 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* 왼쪽: 저장된 글(재사용 라이브러리) */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="w-4 h-4 text-emerald-600" />
              저장된 글
            </CardTitle>
            <CardDescription>글 {savedPosts.length}개 · 클릭하면 오른쪽에서 바로 수정·발행</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[620px] overflow-y-auto">
            {savedPosts.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p>저장된 글이 없습니다</p>
              </div>
            ) : (
              savedPosts.map((post) => {
                const active = selectedId === post.id
                return (
                  <div
                    key={post.id}
                    onClick={() => loadPost(post)}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      active ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500'
                        : 'border-gray-200 hover:border-emerald-300 hover:bg-emerald-50/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-sm line-clamp-2 flex-1">{listTitle(post)}</h3>
                      {active ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-none" />
                      ) : post.sourceType === 'database' ? (
                        <span className="flex-none inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-medium rounded">
                          <Database className="w-2.5 h-2.5" />DB
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-muted-foreground">
                        {new Date(post.savedAt).toLocaleDateString('ko-KR')}
                      </span>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50"
                        onClick={(e) => { e.stopPropagation(); deletePost(post.id) }}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        {/* 오른쪽: 인라인 작성 → 사진 → 발행 (한 화면) */}
        <Card className="lg:col-span-3">
          <CardHeader className="pb-3 flex flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle className="text-base">발행 준비</CardTitle>
              <CardDescription>
                {selectedId ? '불러온 글을 수정할 수 있어요' : '여기에 글을 붙여넣고 바로 발행하세요'}
              </CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={newDraft} className="gap-1.5 flex-none">
              <Plus className="w-3.5 h-3.5" /> 새 글
            </Button>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* STEP 1. 글 작성/붙여넣기 (인라인) */}
            <section className="space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <StepDot n={1} done={hasContent} />
                글 작성 · 붙여넣기
              </div>
              <Input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                placeholder="제목 (비우면 본문 첫 줄이 제목이 됩니다)"
                className="font-medium"
              />
              <Textarea
                value={draftBody}
                onChange={(e) => setDraftBody(e.target.value)}
                placeholder={'본문을 붙여넣거나 작성하세요...\n다른 곳에서 쓴 글을 그대로 붙여넣어도 됩니다.'}
                className="min-h-[200px] text-sm leading-relaxed"
              />
            </section>

            {/* STEP 2. 사진 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2 font-semibold">
                <StepDot n={2} done={photoMode === 'collection' ? !!selectedCollectionId : uploadedImages.length > 0} />
                사진 추가 <span className="text-xs font-normal text-muted-foreground">(선택)</span>
              </div>

              {/* 소스 토글 */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setPhotoMode('upload')}
                  className={`flex items-center justify-center gap-2 h-10 rounded-lg border text-sm transition ${
                    photoMode === 'upload'
                      ? 'border-emerald-500 bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500'
                      : 'border-gray-200 text-gray-600 hover:border-emerald-300'
                  }`}
                >
                  <Upload className="w-4 h-4" /> 직접 업로드
                </button>
                <button
                  onClick={() => setPhotoMode('collection')}
                  className={`flex items-center justify-center gap-2 h-10 rounded-lg border text-sm transition ${
                    photoMode === 'collection'
                      ? 'border-emerald-500 bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500'
                      : 'border-gray-200 text-gray-600 hover:border-emerald-300'
                  }`}
                >
                  <Folder className="w-4 h-4" /> 저장된 목록에서
                </button>
              </div>

              {photoMode === 'upload' ? (
                <>
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
                </>
              ) : (
                <div className="space-y-3">
                  {collections.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-500 text-center">
                      저장된 목록이 없습니다.{' '}
                      <button
                        onClick={() => router.push('/dashboard/media')}
                        className="text-emerald-600 underline underline-offset-2"
                      >
                        사진 페이지
                      </button>
                      에서 목록을 만들고 사진을 담아주세요.
                    </div>
                  ) : (
                    <>
                      {/* 목록 선택 칩 */}
                      <div className="flex flex-wrap gap-2">
                        {collections.map((c) => (
                          <button
                            key={c.id}
                            onClick={() => setSelectedCollectionId(c.id)}
                            className={`flex items-center gap-1.5 pl-3 pr-2 py-1.5 rounded-full text-sm border transition ${
                              selectedCollectionId === c.id
                                ? 'border-emerald-500 bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500'
                                : 'border-gray-200 text-gray-600 hover:border-emerald-300'
                            }`}
                          >
                            <Folder className="w-3.5 h-3.5" />
                            {c.name}
                            <span className="text-[11px] text-muted-foreground">{c.count}장</span>
                          </button>
                        ))}
                      </div>
                      {/* 장수 입력(기억됨) + 빠른 선택 */}
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Label htmlFor="colCount" className="text-sm text-gray-600">이 글에 넣을 사진 수</Label>
                          <Input
                            id="colCount"
                            type="number"
                            min={1}
                            max={30}
                            value={collectionCount}
                            onChange={(e) => setCollectionCount(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                            className="w-20 h-9"
                          />
                          <span className="text-xs text-muted-foreground">장</span>
                          <div className="flex gap-1">
                            {[8, 10, 12, 15].map((n) => (
                              <button
                                key={n}
                                onClick={() => setCollectionCount(n)}
                                className={`px-2.5 h-8 rounded-md text-xs border transition ${
                                  collectionCount === n
                                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                                    : 'border-gray-200 text-gray-600 hover:border-emerald-300'
                                }`}
                              >
                                {n}
                              </button>
                            ))}
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          발행할 때마다 &lsquo;적게 쓴 사진&rsquo;부터 골라 자동 유니크화 — 40~60장 담아두면 글마다 알아서 다른 사진이 들어갑니다.
                        </p>
                      </div>
                      {selectedCollectionId && (
                        <p className="text-xs text-emerald-700 bg-emerald-50 rounded-md px-3 py-2">
                          &lsquo;{collections.find((c) => c.id === selectedCollectionId)?.name}&rsquo; 목록에서{' '}
                          {collectionCount}장이 유니크화되어 자동으로 들어갑니다.
                        </p>
                      )}
                    </>
                  )}
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

              {/* 예약 발행 상세 */}
              {finalAction === 'schedule' && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-3">
                  {/* 방식 토글: 직접 지정 / 간격 예약 */}
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setScheduleMode('manual')}
                      className={`h-9 rounded-md border text-sm transition ${
                        scheduleMode === 'manual'
                          ? 'border-amber-500 bg-white text-amber-800 ring-1 ring-amber-400'
                          : 'border-amber-200 text-amber-700 hover:bg-white/60'
                      }`}
                    >
                      날짜·시간 직접 지정
                    </button>
                    <button
                      onClick={() => setScheduleMode('interval')}
                      className={`h-9 rounded-md border text-sm transition ${
                        scheduleMode === 'interval'
                          ? 'border-amber-500 bg-white text-amber-800 ring-1 ring-amber-400'
                          : 'border-amber-200 text-amber-700 hover:bg-white/60'
                      }`}
                    >
                      간격으로 예약
                    </button>
                  </div>

                  {scheduleMode === 'manual' ? (
                    <div className="grid grid-cols-2 gap-2">
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
                  ) : (
                    <div className="space-y-2.5">
                      {/* 간격 프리셋 + 커스텀 */}
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs text-amber-800">발행 간격</span>
                        {INTERVAL_PRESETS.map((h) => (
                          <button
                            key={h}
                            onClick={() => setIntervalHours(h)}
                            className={`px-2.5 h-8 rounded-full text-sm border transition ${
                              intervalHours === h
                                ? 'border-amber-500 bg-amber-500 text-white'
                                : 'border-amber-300 bg-white text-amber-700 hover:bg-amber-100'
                            }`}
                          >
                            {h}시간
                          </button>
                        ))}
                        <span className="mx-1 text-amber-300">|</span>
                        <Input
                          type="number"
                          min={1}
                          max={48}
                          value={intervalHours}
                          onChange={(e) => setIntervalHours(Math.max(1, Math.min(48, Number(e.target.value) || 1)))}
                          className="w-16 h-8 bg-white"
                        />
                        <span className="text-xs text-amber-800">시간마다</span>
                      </div>

                      {/* 다음 예약 시각 */}
                      <div className="flex items-center justify-between rounded-md bg-white border border-amber-200 px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-amber-600" />
                          <span className="text-sm font-medium text-amber-900">
                            예약 시각 {fmtKo(intervalSlot)}
                          </span>
                        </div>
                        {lastScheduledAt && (
                          <button onClick={resetSchedule} className="text-xs text-amber-700 underline underline-offset-2">
                            기준 초기화
                          </button>
                        )}
                      </div>

                      <p className="text-[11px] text-amber-700">
                        {lastScheduledAt
                          ? `마지막 예약(${fmtKo(new Date(lastScheduledAt))}) 기준 ${intervalHours}시간 뒤로 잡힙니다. 발행할 때마다 다음 글이 자동으로 ${intervalHours}시간씩 밀려요.`
                          : `첫 예약이에요. 지금부터 ${intervalHours}시간 뒤로 잡히고, 이후 글은 자동으로 ${intervalHours}시간 간격이 됩니다.`}
                      </p>

                      {/* 예약 현황 — 이미 잡아둔 예약들(중복 방지 확인용) */}
                      {upcomingLog.length > 0 && (
                        <div className="rounded-md bg-white border border-amber-200 p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-amber-900">
                              예약 대기 {upcomingLog.length}건
                            </span>
                            <span className="text-[11px] text-amber-600">다음 글은 맨 아래 예약 다음으로 잡힙니다</span>
                          </div>
                          <div className="max-h-40 overflow-y-auto divide-y divide-amber-50">
                            {upcomingLog.map((x, i) => (
                              <div key={i} className="flex items-center gap-2 py-1.5 text-xs">
                                <span className="tabular-nums text-amber-800 w-40 shrink-0">{fmtKo(new Date(x.at))}</span>
                                <span className="truncate text-gray-700">{x.title}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
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

            {/* 저장 + 발행 */}
            <div className="pt-1">
              <div className="flex gap-2">
                <Button size="lg" variant="outline" onClick={() => saveDraft(false)} disabled={!hasContent}
                  className="h-12 gap-2">
                  <Save className="w-4 h-4" /> 저장
                </Button>
                <Button size="lg" disabled={!canPublish} onClick={publish}
                  className="flex-1 h-12 text-base gap-2 bg-emerald-600 hover:bg-emerald-700">
                  {publishing ? (
                    <><Loader2 className="w-5 h-5 animate-spin" />발행 중...</>
                  ) : (
                    <><Send className="w-5 h-5" />
                      {finalAction === 'draft' ? '임시저장하기' : finalAction === 'schedule' ? '예약 발행하기' : '지금 발행하기'}
                    </>
                  )}
                </Button>
              </div>

              {/* 예약 준비함에 담기 (지금 발행하지 않고 모아두기) */}
              {finalAction === 'schedule' && (
                <Button variant="outline" onClick={preparePost} disabled={!hasContent || preparing}
                  className="w-full mt-2 h-11 gap-2 border-amber-300 text-amber-700 hover:bg-amber-50">
                  {preparing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                  예약 준비함에 담기 (지금 발행 안 함)
                </Button>
              )}

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

              {/* 예약 준비함 — 모아둔 글을 한 번에 발행 */}
              {prepared.length > 0 && (
                <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50/60 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-amber-900 flex items-center gap-1.5">
                      <Layers className="w-4 h-4" /> 예약 준비함 {prepared.length}건
                    </span>
                    <Button size="sm" onClick={publishAllPrepared} disabled={!ext.connected || publishing}
                      className="h-8 gap-1.5 bg-emerald-600 hover:bg-emerald-700">
                      {publishing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      준비한 {prepared.length}건 한번에 발행
                    </Button>
                  </div>
                  <div className="max-h-52 overflow-y-auto divide-y divide-amber-100">
                    {prepared.map((p) => (
                      <div key={p.id} className="flex items-center gap-2 py-1.5 text-xs">
                        <span className="tabular-nums text-amber-800 w-36 shrink-0">{fmtKo(new Date(p.scheduleISO))}</span>
                        <span className="flex-1 truncate text-gray-700">{p.title || '(제목 없음)'}</span>
                        <span className="text-[11px] text-muted-foreground shrink-0">사진 {p.images.length}</span>
                        <button onClick={() => removePrepared(p.id)} className="text-rose-500 hover:text-rose-600 shrink-0">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-amber-700">
                    담아둔 글은 여기 저장돼요. 다 모은 뒤 &lsquo;한번에 발행&rsquo;을 누르면 확장이 순서대로 네이버 예약발행에 등록합니다.
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 실시간 발행 가이드 */}
      <PublishGuide
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
        onDownloadExtension={() => window.open(EXTENSION_DOWNLOAD_URL, '_blank')}
        hasExtension={ext.connected}
        hasSelectedPost={hasContent}
        hasImages={photoMode === 'collection' ? !!selectedCollectionId : uploadedImages.length > 0}
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
