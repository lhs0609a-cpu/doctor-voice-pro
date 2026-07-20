'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const chrome: any

import { useState, useEffect, useRef } from 'react'
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
import { mediaPoolAPI, publishQueueAPI, type PoolCollectionItem, type NaverCategory } from '@/lib/api'
import { preparedStore, requestPersistentStorage, storageHeadroom } from '@/lib/prepared-store'
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

// 예약 준비함 항목 — 가벼운 메타데이터만 담는다.
// 사진 base64 는 IndexedDB(preparedStore)에 id 로 따로 보관하고, 확장이 그 글을
// 처리하기 직전에 한 건씩 꺼낸다. (예전엔 여기에 images 를 통째로 넣어 100건 = 400MB+ 가
// state 와 localStorage 에 동시에 올라가 탭이 죽거나 저장이 실패했다)
interface PreparedItem {
  id: string
  title: string
  content: string
  imageCount: number         // 실제 사진은 preparedStore 에
  hasFixed?: boolean         // 유니크화된 고정 하단 이미지 보유 여부
  tags: string[]
  emphasize: string[]
  openType: OpenType
  category?: string          // 네이버 카테고리 번호. 없으면 기본 카테고리
  scheduleISO: string
}

// ── 블로그별 저장소 ──
// 예약 기준·예약 현황·준비함은 블로그(네이버 계정)마다 완전히 분리해야 한다.
// 예전엔 전역 키 하나를 공유해서, 계정 A 로 잡아둔 기준이 계정 B 의 예약 계산에 그대로
// 쓰였고(→ B 블로그가 비어 있는데 엉뚱한 시각부터 잡힘), 반대로 B 가 A 의 기준을 덮어썼다.
const SCHED_KEYS = ['doctorvoice-last-schedule', 'doctorvoice-schedule-log', 'doctorvoice-prepared'] as const
const scopedKey = (base: string, blogId: string | null) => (blogId ? `${base}::${blogId}` : base)

// 마지막으로 확인된 블로그. 확장이 아직 안 붙었어도 이 값으로 예약 기준을 먼저 복원한다.
// 이게 없으면 확장 연결이 늦어지는 동안 blogId 가 null 이라 "예약이 하나도 없는" 화면이 뜨고,
// 그 상태에서 간격 예약을 걸면 기준이 지금 시각으로 리셋돼 기존 예약 위에 겹쳐 잡혔다.
const BLOGID_KEY = 'doctorvoice-last-blogid'

/**
 * 계정을 처음 확인한 시점에, 전역으로 남아 있던 예전 데이터를 그 블로그 것으로 넘긴다.
 * 스코프 키가 이미 있으면 '병합'한다 — 예전엔 덮어쓰기 없이 legacy 를 그냥 지워서,
 * blogId 확정 전에 담아둔 준비함·예약이 조용히 사라졌다.
 */
function migrateLegacyScope(blogId: string) {
  for (const base of SCHED_KEYS) {
    const legacy = localStorage.getItem(base)
    if (legacy === null) continue
    const scoped = scopedKey(base, blogId)
    const cur = localStorage.getItem(scoped)
    if (cur === null) {
      localStorage.setItem(scoped, legacy)
    } else if (base === 'doctorvoice-last-schedule') {
      // ISO 문자열 — 더 늦은 쪽이 기준(커서는 뒤로 물리면 안 된다)
      const a = new Date(cur).getTime(), b = new Date(legacy).getTime()
      if (!isNaN(b) && (isNaN(a) || b > a)) localStorage.setItem(scoped, legacy)
    } else {
      // 배열 — 합치고 id(준비함) 또는 at+title(예약 현황) 으로 중복 제거
      try {
        const arr = [...JSON.parse(cur), ...JSON.parse(legacy)]
        const seen = new Set<string>()
        const merged = arr.filter((x: any) => {
          const k = x?.id ?? `${x?.at}|${x?.title}`
          if (seen.has(k)) return false
          seen.add(k)
          return true
        })
        localStorage.setItem(scoped, JSON.stringify(merged))
      } catch { /* 깨진 값이면 기존 것을 지킨다 */ }
    }
    localStorage.removeItem(base) // 다른 블로그가 이 값을 물려받으면 안 된다
  }
}

// 준비함 목록 저장(가벼움 — 100건이어도 수십 KB)
function persistPreparedFor(blogId: string | null, items: PreparedItem[]) {
  try { localStorage.setItem(scopedKey('doctorvoice-prepared', blogId), JSON.stringify(items)) }
  catch { /* 메타데이터만이라 사실상 넘칠 일이 없다 */ }
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

// 본문을 문단으로 나눠 이미지를 고르게 끼운 블록(글-이미지-글-이미지)
function buildInterleavedBlocks(content: string, images: string[]): { type: 'text' | 'image'; content?: string; image?: string }[] {
  const text = (content || '').replace(/\r\n/g, '\n').trim()
  let paras = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)
  if (paras.length <= 1) paras = text.split(/\n/).map((p) => p.trim()).filter(Boolean)
  if (paras.length === 0) paras = [text || '']
  const n = images.length
  const blocks: { type: 'text' | 'image'; content?: string; image?: string }[] = []
  let imgIdx = 0
  for (let p = 0; p < paras.length; p++) {
    blocks.push({ type: 'text', content: paras[p] })
    const upto = Math.round(((p + 1) * n) / paras.length)
    while (imgIdx < upto) { blocks.push({ type: 'image', image: images[imgIdx] }); imgIdx++ }
  }
  while (imgIdx < n) { blocks.push({ type: 'image', image: images[imgIdx] }); imgIdx++ }
  return blocks
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

  // 고정 하단 이미지: 모든 글 맨 아래에 항상(유니크화되어) 들어감
  const [fixedImage, setFixedImage] = useState<string | null>(null)      // base64 data URL
  const [fixedSiblings, setFixedSiblings] = useState<string[]>([])        // 과거 변형 pHash(중복 회피)

  const [finalAction, setFinalAction] = useState<FinalAction>('publishNow')
  const [openType, setOpenType] = useState<OpenType>('public')

  // 네이버 카테고리: 확장이 에디터에서 읽어와 서버에 저장해 둔 목록으로 고른다.
  const [categories, setCategories] = useState<NaverCategory[]>([])
  const [category, setCategory] = useState('')      // '' = 네이버 기본 카테고리
  const [syncingCats, setSyncingCats] = useState(false)

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

  // 현재 로그인된 네이버 블로그. null = 확장으로 아직 확인 못 함
  const [blogId, setBlogId] = useState<string | null>(null)
  const [blogChecking, setBlogChecking] = useState(false)
  // 지난 세션에서 확인됐던 블로그(localStorage). 확장이 붙기 전의 임시 기준.
  const [cachedBlogId, setCachedBlogId] = useState<string | null>(null)
  const [scopeLoaded, setScopeLoaded] = useState(false) // 캐시 읽기를 시도했는가

  // 읽기·쓰기에 실제로 쓰는 스코프. 확장 확인값이 있으면 그게 우선, 없으면 캐시.
  const scopeId = blogId ?? cachedBlogId
  // 확장이 지금 이 순간 확인해 준 값인가. 간격 예약 허용 여부를 여기서 가른다.
  const blogConfirmed = !!blogId

  // 배치 결과 리스너는 deps [] 라 state 를 직접 읽으면 초기값(null)에 묶인다 → 거울 ref 로 읽는다.
  const blogIdRef = useRef<string | null>(null)
  useEffect(() => { blogIdRef.current = blogId }, [blogId])
  // 저장은 '읽을 때 쓰는 키'와 반드시 같아야 한다 → scopeId 를 따라간다.
  const scopeIdRef = useRef<string | null>(null)
  useEffect(() => { scopeIdRef.current = scopeId }, [scopeId])
  const lastSchedRef = useRef<string | null>(null)
  useEffect(() => { lastSchedRef.current = lastScheduledAt }, [lastScheduledAt])

  const persistPrepared = (items: PreparedItem[]) => persistPreparedFor(scopeIdRef.current, items)

  // 실패한 건의 사유 (준비함에 남겨두고 표시 → 다시 시도 가능)
  const [failedIds, setFailedIds] = useState<Record<string, string>>({})
  // 진행 중인 배치 상태 (총 건수/완료 건수)
  const [batchProgress, setBatchProgress] = useState<{ total: number; done: number; ok: number } | null>(null)

  // 이벤트 리스너에서 최신 준비함을 읽기 위한 거울 (stale closure 방지)
  const preparedRef = useRef<PreparedItem[]>([])
  useEffect(() => { preparedRef.current = prepared }, [prepared])

  // 배치 진행 카운터. 리스너가 매번 최신값을 봐야 하므로 ref.
  const batchRef = useRef<{ total: number; done: number; ok: number }>({ total: 0, done: 0, ok: 0 })
  // 결과가 한참 안 오면(탭 닫힘 등) 버튼이 영구히 잠기지 않도록 푸는 감시 타이머
  const stallTimerRef = useRef<any>(null)

  // 확장이 각 글을 처리하기 직전에 그 글의 payload 를 요청한다 → 그때 한 건만 만들어 넘긴다.
  // 미리 다 만들어두면 100건 × 4~5MB ≈ 500MB 가 탭 메모리에 한꺼번에 올라가 죽는다.
  useEffect(() => {
    const onRequest = async (e: any) => {
      const { id, token } = e.detail || {}
      const reply = (job: any) =>
        window.dispatchEvent(new CustomEvent('doctorvoice-job-payload', { detail: { token, job } }))
      try {
        const item = preparedRef.current.find((p) => p.id === id)
        if (!item) { reply(null); return }
        // 사진은 지금 IndexedDB 에서 꺼낸다 → 이 한 건만 잠깐 메모리에 올라간다.
        // get() 이 throw 하면 아래 catch 가 reply(null) → 확장은 이 건을 실패로 처리하고
        // 준비함에 그대로 남는다. 사진 없이 나가는 것보다 실패가 낫다.
        const payload = await preparedStore.get(id)
        const images = payload?.images || []

        // 담을 때 기록해 둔 장수와 대조한다. 어긋나면 사진이 유실된 것이므로 발행하지 않는다.
        // (예전엔 대조가 없어서, imageCount 12 인 글이 0장으로 나가도 '성공'으로 보고되고
        //  준비함 항목과 IndexedDB 사진이 함께 지워져 복구가 불가능했다)
        if (images.length !== item.imageCount) {
          throw new Error(`사진 유실: ${item.imageCount}장 중 ${images.length}장만 읽힘`)
        }
        if (item.hasFixed && !payload?.fixedImage) {
          throw new Error('고정 하단 이미지 유실')
        }

        const blocks = buildInterleavedBlocks(item.content, images)
        if (payload?.fixedImage) blocks.push({ type: 'image', image: payload.fixedImage })
        reply({
          id: item.id, title: item.title, content: item.content,
          // images 는 싣지 않는다 — 확장의 normalizeJob 이 blocks 에서 본문과 사진을
          // 모두 파생시키므로, 따로 보내면 같은 base64 가 두 번 실려 전송량만 2배가 된다.
          blocks,
          tags: item.tags, emphasize: item.emphasize,
          options: { openType: item.openType, search: true, category: item.category || null },
          finalAction: 'schedule', schedule: { datetime: item.scheduleISO },
          expectedBlogId: blogIdRef.current,
        })
      } catch (err: any) {
        // 왜 건너뛰었는지 남긴다 — 조용히 실패하면 사용자는 '왜 이 글만 안 올라갔지'만 남는다.
        console.error('[doctorvoice] payload 준비 실패', id, err)
        toast.error('사진을 준비하지 못해 이 글을 건너뛰었어요', {
          description: `${err?.message || '알 수 없는 오류'} — 준비함에 남겨뒀으니 다시 담아주세요.`,
        })
        reply(null)
      }
    }
    window.addEventListener('doctorvoice-job-request', onRequest)
    return () => window.removeEventListener('doctorvoice-job-request', onRequest)
  }, [])

  // 확장이 글 한 건을 끝낼 때마다 결과를 보낸다.
  // 성공한 건만 준비함에서 빼고, 실패한 건은 사유와 함께 남겨 다시 시도할 수 있게 한다.
  // (예전엔 전송 직후 준비함을 통째로 비워서 실패한 글이 흔적 없이 사라졌다)
  useEffect(() => {
    const onResult = (e: any) => {
      const { id, ok, message, uncertain } = e.detail || {}
      if (!id) return
      const b = batchRef.current
      if (!b.total) return // 이 화면이 시작한 배치가 아님

      b.done += 1
      if (ok) {
        b.ok += 1
        const item = preparedRef.current.find((p) => p.id === id)
        setPrepared((prev) => {
          const next = prev.filter((p) => p.id !== id)
          persistPrepared(next)
          return next
        })
        preparedStore.remove(id)
        if (item) {
          advanceCursor(item.scheduleISO)
          setScheduleLog((prev) => {
            const next = [...prev, { title: item.title || '(제목 없음)', at: item.scheduleISO }]
              .sort((a, b2) => a.at.localeCompare(b2.at)).slice(-200)
            localStorage.setItem(scopedKey('doctorvoice-schedule-log', scopeIdRef.current), JSON.stringify(next))
            return next
          })
        }
      } else if (uncertain) {
        // 시간 초과로 끝난 건 — 실제로는 발행됐을 수 있다. 그냥 다시 발행하면 중복 예약이 되므로
        // 사용자가 네이버에서 확인하고 판단하도록 따로 표시한다.
        setFailedIds((prev) => ({
          ...prev,
          [id]: '⚠️ 응답 시간 초과 — 네이버에 이미 예약됐을 수 있어요. 확인 후 다시 발행하세요(중복 주의)',
        }))
      } else {
        setFailedIds((prev) => ({ ...prev, [id]: message || '실패' }))
      }
      setBatchProgress({ total: b.total, done: b.done, ok: b.ok })
      try { localStorage.setItem(BATCH_KEY, JSON.stringify({ ...b, at: Date.now() })) } catch { /* noop */ }
      armStallTimer()

      if (b.done >= b.total) {
        const failed = b.total - b.ok
        if (failed > 0) {
          toast.warning(`예약 등록 완료 — ${b.ok}건 성공, ${failed}건 실패`, {
            description: '실패한 글은 준비함에 남겨뒀어요. 사유를 확인하고 다시 발행하세요.',
          })
        } else {
          toast.success(`${b.ok}건 모두 예약 등록했어요`)
        }
        endBatch()
      }
    }
    window.addEventListener('doctorvoice-job-result', onResult)
    return () => window.removeEventListener('doctorvoice-job-result', onResult)
  }, [])

  // 배치 시작/종료를 localStorage 에도 남긴다.
  // 발행 도중 새로고침하면 확장은 계속 도는데 이 화면이 결과를 무시해버려,
  // 이미 등록된 글이 준비함에 남고 사용자가 다시 눌러 중복 발행되는 문제가 있었다.
  const BATCH_KEY = 'doctorvoice-batch-active'

  const beginBatch = (total: number) => {
    batchRef.current = { total, done: 0, ok: 0 }
    setBatchProgress({ total, done: 0, ok: 0 })
    try { localStorage.setItem(BATCH_KEY, JSON.stringify({ total, done: 0, ok: 0, at: Date.now() })) } catch { /* noop */ }
    setPublishing(true)
    armStallTimer()
  }

  const endBatch = () => {
    batchRef.current = { total: 0, done: 0, ok: 0 }
    if (stallTimerRef.current) { clearTimeout(stallTimerRef.current); stallTimerRef.current = null }
    try { localStorage.removeItem(BATCH_KEY) } catch { /* noop */ }
    setBatchProgress(null)
    setPublishing(false)
  }

  // 새로고침 후 진행 중이던 배치 이어받기 (7분 넘게 조용했으면 죽은 것으로 보고 버린다)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(BATCH_KEY)
      if (!raw) return
      const s = JSON.parse(raw)
      if (!s?.total || Date.now() - (s.at || 0) > 7 * 60 * 1000) { localStorage.removeItem(BATCH_KEY); return }
      batchRef.current = { total: s.total, done: s.done || 0, ok: s.ok || 0 }
      setBatchProgress({ total: s.total, done: s.done || 0, ok: s.ok || 0 })
      setPublishing(true)
      armStallTimer()
    } catch { /* noop */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 한 건당 최대 3분(확장 가드) + 여유. 그 두 배 동안 아무 결과도 없으면 멈춘 것으로 본다.
  const armStallTimer = () => {
    if (stallTimerRef.current) clearTimeout(stallTimerRef.current)
    stallTimerRef.current = setTimeout(() => {
      const b = batchRef.current
      if (!b.total) return
      toast.error('발행이 응답하지 않아 중단했어요', {
        description: `${b.ok}건 완료. 남은 글은 준비함에 있으니 다시 발행하세요.`,
      })
      endBatch()
    }, 7 * 60 * 1000)
  }

  // 어느 블로그에 로그인돼 있는지 확장에 물어본다. 이게 정해져야 예약 기준을 계산할 수 있다.
  const detectBlog = async (silent = true) => {
    if (!ext.connected || !ext.extensionId) return null
    setBlogChecking(true)
    try {
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SYNC_BLOG' })
      if (res?.success && res.blogId) {
        setBlogId((prev) => {
          if (prev && prev !== res.blogId) {
            toast.info(`블로그가 '${res.blogId}' 로 바뀌었어요`, {
              description: '예약 기준과 준비함이 이 블로그 것으로 전환됩니다.',
            })
          }
          return res.blogId
        })
        // 다음 방문 때 확장이 붙기 전에도 이 블로그 기준으로 복원할 수 있게 기억해 둔다.
        try { localStorage.setItem(BLOGID_KEY, res.blogId) } catch { /* noop */ }
        return res.blogId as string
      }
      if (!silent) toast.error('블로그 확인 실패', { description: res?.error || '다시 시도해주세요' })
    } catch (e: any) {
      if (!silent) toast.error('블로그 확인 실패', { description: e.message })
    } finally {
      setBlogChecking(false)
    }
    return null
  }

  useEffect(() => { if (ext.connected) detectBlog(true) }, [ext.connected]) // eslint-disable-line react-hooks/exhaustive-deps

  // 확장 연결과 무관하게, 마지막으로 알던 블로그를 먼저 읽는다. 이게 있어야 복원이
  // 확장 연결 체인(ext.connected → SYNC_BLOG → 네이버 탭)에 묶이지 않는다.
  useEffect(() => {
    try { setCachedBlogId(localStorage.getItem(BLOGID_KEY)) } catch { /* noop */ }
    setScopeLoaded(true)
  }, [])

  // 스코프가 정해지면 그 블로그의 예약 기준·현황·준비함을 불러온다.
  // scopeId 가 null 이어도(= 한 번도 블로그를 확인한 적 없음) 비스코프 키에서 복원한다 —
  // 예전엔 여기서 조기 반환해, 데이터가 localStorage 에 멀쩡히 있어도 화면엔 안 나왔다.
  useEffect(() => {
    if (!scopeLoaded) return
    if (scopeId) migrateLegacyScope(scopeId)

    setLastScheduledAt(localStorage.getItem(scopedKey('doctorvoice-last-schedule', scopeId)))
    try {
      const log = JSON.parse(localStorage.getItem(scopedKey('doctorvoice-schedule-log', scopeId)) || '[]')
      setScheduleLog(Array.isArray(log) ? log : [])
    } catch { setScheduleLog([]) }

    // 준비함 복원. 예전 버전은 사진(images)까지 localStorage 에 넣었으므로 IndexedDB 로 옮긴다.
    ;(async () => {
      let prep: any[] = []
      try {
        const raw = JSON.parse(localStorage.getItem(scopedKey('doctorvoice-prepared', scopeId)) || '[]')
        if (Array.isArray(raw)) prep = raw
      } catch { /* noop */ }
      const items: PreparedItem[] = []
      for (const p of prep) {
        if (Array.isArray(p.images)) {
          // 구버전 항목 → 사진을 IndexedDB 로 이관하고 메타데이터만 남긴다
          try { await preparedStore.put(p.id, { images: p.images, fixedImage: p.fixedImage }) }
          catch { continue } // 옮기지 못한 건 버린다(사진 없이 발행되면 안 되므로)
          items.push({
            id: p.id, title: p.title, content: p.content,
            imageCount: p.images.length, hasFixed: !!p.fixedImage,
            tags: p.tags || [], emphasize: p.emphasize || [],
            openType: p.openType, category: p.category, scheduleISO: p.scheduleISO,
          })
        } else {
          items.push(p as PreparedItem)
        }
      }
      setPrepared(items)
      persistPreparedFor(scopeId, items)
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeId, scopeLoaded])

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
    // 예약 기준·현황·준비함은 블로그마다 다르므로 blogId 를 확인한 뒤 따로 불러온다(아래 효과).

    // 어느 블로그 준비함에도 없는 사진 찌꺼기 정리(발행 도중 탭이 닫힌 경우 등).
    // 블로그별로 지우면 다른 블로그 준비함의 사진까지 날아가므로 전체를 모아 한 번에 판단한다.
    try {
      const alive: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)
        if (!k || !k.startsWith('doctorvoice-prepared')) continue
        const arr = JSON.parse(localStorage.getItem(k) || '[]')
        if (Array.isArray(arr)) for (const it of arr) if (it?.id) alive.push(it.id)
      }
      preparedStore.prune(alive)
    } catch { /* noop */ }

    // 고정 하단 이미지는 서버에 보관한다.
    // (이 아래는 블로그와 무관한 항목들)
    // (localStorage 는 한도가 약 5MB 라 사진 base64 가 QuotaExceededError 로 저장에 실패했다
    //  → 등록은 된 것처럼 보이지만 새로고침하면 사라졌다.)
    mediaPoolAPI.getFixedImage()
      .then((r) => { if (r.image) setFixedImage(r.image) })
      .catch(() => { /* 미등록 */ })

    // 카테고리: 캐시를 먼저 보여주고, 없으면 확장이 네이버에 다녀와 자동으로 채운다.
    publishQueueAPI.getCategories()
      .then((r) => {
        if (r.categories?.length) setCategories(r.categories)
        else syncCategories(true)
      })
      .catch(() => { /* 캐시 없음 */ })
    try {
      const fs = JSON.parse(localStorage.getItem('doctorvoice-fixed-siblings') || '[]')
      if (Array.isArray(fs)) setFixedSiblings(fs)
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

  // 카테고리 목록 확보: 확장이 스스로 네이버 글쓰기를 열어 읽어오고 서버에 저장한다.
  // silent=true 는 첫 진입 자동 확보 — 실패해도 조용히 두고 사용자가 직접 누를 수 있게 한다.
  const syncCategories = async (silent = false) => {
    if (!ext.extensionId) {
      if (!silent) toast.error('확장 프로그램이 연결되어 있지 않습니다')
      return
    }
    setSyncingCats(true)
    try {
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SYNC_CATEGORIES' })
      if (!res?.success || !res.categories?.length) {
        if (!silent || res?.needLogin) toast.error(res?.error || '카테고리를 불러오지 못했습니다')
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
  }

  // 고정 하단 이미지 등록(원본 base64 저장 → 발행마다 유니크화해 맨 아래 삽입)
  const handleFixedImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = (e.target.files || [])[0]
    if (!f || !f.type.startsWith('image/')) { toast.error('이미지 파일을 선택하세요'); return }
    try {
      const b64 = await imageToCleanBase64(f)
      // 서버가 1280px JPEG 로 정규화해 보관하고, 정규화된 이미지를 돌려준다.
      const saved = await mediaPoolAPI.setFixedImage(b64, f.name)
      setFixedImage(saved.image)
      setFixedSiblings([])
      localStorage.setItem('doctorvoice-fixed-siblings', '[]')
      toast.success('고정 하단 이미지를 등록했어요', { description: '저장되어 다음에 열어도 그대로 있습니다' })
    } catch { toast.error('이미지 처리 실패') }
    e.target.value = ''
  }
  const removeFixedImage = async () => {
    try {
      await mediaPoolAPI.clearFixedImage()
    } catch { toast.error('해제 실패'); return }
    setFixedImage(null); setFixedSiblings([])
    localStorage.removeItem('doctorvoice-fixed-siblings')
    localStorage.removeItem('doctorvoice-fixed-image')   // 예전 버전이 남긴 값 정리
    toast.success('고정 이미지를 해제했어요')
  }
  // 고정 이미지를 유니크화해 반환(없으면 null). siblings 누적으로 글마다 다른 변형.
  const resolveFixedImage = async (): Promise<string | null> => {
    if (!fixedImage) return null
    try {
      const r = await mediaPoolAPI.uniquifyOne(fixedImage, fixedSiblings)
      // 회피셋 상한. 60이면 100건 준비 시 61번째부터 앞의 변형을 잊어버려
      // 뒷부분이 앞부분과 같은 변형으로 나왔다 → 100건 배치를 덮도록 넉넉히 잡는다.
      const nextSib = [...fixedSiblings, r.phash].slice(-300)
      setFixedSiblings(nextSib)
      localStorage.setItem('doctorvoice-fixed-siblings', JSON.stringify(nextSib))
      return r.image
    } catch (e: any) {
      // 예전엔 조용히 원본을 반환했다 — 100건 전부에 똑같은 이미지가 박혀
      // 네이버 중복 감지에 걸리는데도 사용자는 알 방법이 없었다. 담기를 실패시킨다.
      throw new Error(`고정 하단 이미지 유니크화 실패: ${e?.message || '알 수 없는 오류'}`)
    }
  }

  // 이 블로그에서 우리가 아는 '가장 늦은 예약' 시각(ms). 0 = 아는 예약 없음.
  //
  // 예전엔 doctorvoice-last-schedule 키 하나만 봤는데, 그 값은 '가장 늦은 예약'이 아니라
  // '가장 최근에 누른 예약'이라 수동 모드로 이전 날짜를 하나 잡으면 기준이 뒤로 후퇴했다.
  // → 그 다음 간격 예약이 이미 잡아둔 예약들 위에 겹쳐 잡혔다.
  // 이제 알고 있는 모든 출처의 최댓값을 쓴다.
  const knownLatestMs = (): number => {
    // 주의: 여기 없는 출처가 하나 있다 — 네이버에 직접(우리 앱을 거치지 않고) 잡아둔 예약.
    // 확장에 그걸 읽어오는 기능이 없어서 알 수 없다. 그래서 아래 knownLatest 는 어디까지나
    // '우리가 아는' 최댓값이고, 사용자가 네이버에서 직접 잡은 예약과는 겹칠 수 있다.
    const times = [
      lastScheduledAt,
      ...scheduleLog.map((s) => s.at),      // 우리가 등록한 예약 현황
      ...prepared.map((p) => p.scheduleISO), // 아직 발행 안 한 준비함(서로 겹치면 안 된다)
    ]
      .filter(Boolean)
      .map((s) => new Date(s as string).getTime())
      .filter((n) => !isNaN(n))
    return times.length ? Math.max(...times) : 0
  }

  // 간격 예약: (아는 가장 늦은 예약 or 지금) + intervalHours, 10분 내림
  const computeIntervalSlot = (): Date => {
    const now = Date.now()
    const base = Math.max(knownLatestMs(), now)
    const d = new Date(base + intervalHours * 3600_000)
    d.setMinutes(Math.floor(d.getMinutes() / 10) * 10, 0, 0)
    return d
  }

  // 간격 예약은 '이 블로그의 마지막 예약'을 알아야 성립한다. 스코프를 모르면
  // knownLatestMs() 가 0 이 되고 기준이 지금 시각으로 리셋돼 기존 예약 위에 겹쳐 잡힌다.
  // 조용히 틀리느니 막는다. (한 번이라도 블로그를 확인했으면 캐시로 복원되므로 통과)
  const intervalReady = !!scopeId
  const guardInterval = (): boolean => {
    if (intervalReady) return true
    toast.error('기준 블로그를 아직 확인하지 못했어요', {
      description: '확장 프로그램을 연결하고 네이버 블로그에 로그인한 뒤 "다시 확인"을 눌러주세요. 기준을 모르면 기존 예약과 겹칠 수 있어 막았습니다.',
    })
    return false
  }

  // 기준 커서는 앞으로만 간다. 뒤로 물리면 기존 예약과 겹친다.
  // (배치 결과 리스너에서도 불리므로 state 가 아니라 ref 를 읽는다)
  const advanceCursor = (iso: string) => {
    const next = new Date(iso).getTime()
    const curIso = lastSchedRef.current
    const cur = curIso ? new Date(curIso).getTime() : 0
    if (isNaN(next) || next <= cur) return
    lastSchedRef.current = iso
    localStorage.setItem(scopedKey('doctorvoice-last-schedule', scopeIdRef.current), iso)
    setLastScheduledAt(iso)
  }

  const resetSchedule = () => {
    localStorage.removeItem(scopedKey('doctorvoice-last-schedule', scopeId))
    localStorage.removeItem(scopedKey('doctorvoice-schedule-log', scopeId))
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
        if (!guardInterval()) return
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

      // 고정 하단 이미지(유니크화) — 맨 아래에 항상
      const fixedUniq = await resolveFixedImage()
      const blocks = buildInterleavedBlocks(finalBody || finalTitle, images)
      if (fixedUniq) blocks.push({ type: 'image', image: fixedUniq })
      const allImages = fixedUniq ? [...images, fixedUniq] : images

      const job = {
        id: savedId || `post-${Date.now()}`,
        title: finalTitle,
        content: finalBody || finalTitle,
        images: allImages,
        blocks, // 글-이미지-글-이미지 + 맨 아래 고정 이미지
        tags,
        emphasize: extractKeywords(finalBody || finalTitle), // 핵심 키워드 자동 굵게
        options: { openType, search: true, category: category || null },
        finalAction,
        schedule: scheduleISO ? { datetime: scheduleISO } : null,
        expectedBlogId: blogId, // 발행 직전 실제 로그인 계정과 대조 → 다르면 중단
      }

      toast.loading('네이버 블로그로 전송 중...', { id: t })
      const res = await sendMessageToExtension(ext.extensionId, { action: 'SUBMIT_JOB', job })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')

      // 예약이면 다음 글 간격 계산 기준으로 기억 + 예약 현황에 기록
      if (finalAction === 'schedule' && scheduleISO) {
        advanceCursor(scheduleISO)
        setScheduleLog((prev) => {
          const next = [...prev, { title: finalTitle || '(제목 없음)', at: scheduleISO! }]
            .sort((a, b) => a.at.localeCompare(b.at))
            .slice(-200)
          localStorage.setItem(scopedKey('doctorvoice-schedule-log', scopeId), JSON.stringify(next))
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
      if (!guardInterval()) return
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
        // 즉시발행(publish)에는 있던 검사가 여기엔 빠져 있었다 — 풀이 부족하거나 유니크화가
        // 전부 실패하면 서버가 200 + warnings 로 돌려주므로, 안 보면 사진 0장으로 조용히 담긴다.
        if (images.length === 0) {
          throw new Error('목록에서 사진을 가져오지 못했습니다. 목록에 사진이 있는지 확인하세요.')
        }
        if (images.length < collectionCount) {
          throw new Error(`사진이 부족합니다 — ${collectionCount}장 중 ${images.length}장만 배정됐어요. 목록에 사진을 더 넣거나 장수를 줄여주세요.`)
        }
        if (res.warnings?.length) {
          toast.warning('사진 배정에 유의사항이 있어요', { description: res.warnings[0] })
        }
      } else if (uploadedImages.length) {
        for (const f of uploadedImages) images.push(await imageToCleanBase64(f))
      }
      const fixedUniq = await resolveFixedImage()
      const itemId = savedId || `post-${Date.now()}`

      // 저장 여유가 바닥나면 put 이 성공해도 나중에 축출될 수 있다 → 미리 승격 요청하고 경고한다.
      await requestPersistentStorage()
      const headroom = await storageHeadroom()
      const need = images.reduce((n, s) => n + s.length, 0) + (fixedUniq?.length || 0)
      if (headroom !== null && headroom < need * 2) {
        throw new Error('브라우저 저장 공간이 부족해 사진을 안전하게 담을 수 없습니다. 준비함을 일부 발행하거나 비운 뒤 다시 시도하세요.')
      }

      // 사진은 IndexedDB 로 (한도가 사실상 없다). 저장에 실패하면 담기 자체를 실패시킨다 —
      // 조용히 넘어가면 발행 때 사진 없는 글이 나간다.
      await preparedStore.put(itemId, { images, fixedImage: fixedUniq || undefined })

      // 방금 쓴 걸 즉시 되읽어 확인한다. 여기서 걸리면 100건 돌린 뒤가 아니라 지금 알 수 있다.
      const verify = await preparedStore.get(itemId)
      if (!verify || verify.images.length !== images.length) {
        throw new Error('사진 저장을 확인하지 못했습니다. 다시 시도해주세요.')
      }
      const item: PreparedItem = {
        id: itemId,
        title: finalTitle, content: finalBody || finalTitle,
        imageCount: images.length, hasFixed: !!fixedUniq,
        tags, emphasize: extractKeywords(finalBody || finalTitle),
        openType, category: category || undefined, scheduleISO,
      }
      const nextCount = prepared.length + 1
      setPrepared((prev) => {
        const next = [...prev.filter((p) => p.id !== itemId), item]
          .sort((a, b) => a.scheduleISO.localeCompare(b.scheduleISO))
        persistPrepared(next)
        return next
      })
      // 다음 글이 겹치지 않도록 예약 기준 갱신(앞으로만 이동)
      advanceCursor(scheduleISO)
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
    setFailedIds({})
    const t = toast.loading(`준비한 ${prepared.length}건 예약 등록 시작...`)
    try {
      // 사진이 빠진 메타데이터만 보낸다(100건이어도 수십 KB).
      // 실제 payload 는 확장이 글을 처리하기 직전에 doctorvoice-job-request 로 한 건씩 받아간다.
      const metas = prepared.map((p) => ({
        id: p.id, title: p.title,
        options: { openType: p.openType, search: true, category: p.category || null },
        finalAction: 'schedule', schedule: { datetime: p.scheduleISO },
        expectedBlogId: blogId,
      }))
      const res = await sendMessageToExtension(ext.extensionId, {
        action: 'SUBMIT_BATCH', jobs: metas, expectedBlogId: blogId,
      })
      if (!res?.success) throw new Error(res?.error || '발행 전송 실패')

      // 준비함은 비우지 않는다 — 각 글의 결과를 받아 성공한 것만 하나씩 뺀다.
      beginBatch(metas.length)
      toast.success(`${metas.length}건 예약 등록을 시작했어요`, {
        id: t, description: '새 탭에서 순서대로 등록됩니다. 완료까지 이 창을 열어두세요.',
      })
    } catch (e: any) {
      toast.error('발행 실패', { id: t, description: e.message || '다시 시도해주세요' })
      endBatch()
    }
  }

  const removePrepared = (id: string) => {
    setPrepared((prev) => {
      const next = prev.filter((p) => p.id !== id)
      persistPrepared(next)
      return next
    })
    preparedStore.remove(id) // 사진도 같이 정리
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

              {/* 고정 하단 이미지 — 모든 글 맨 아래에 항상(유니크화되어) */}
              <div className="rounded-lg border border-dashed border-gray-300 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium flex items-center gap-1.5">
                    <ImageIcon className="w-4 h-4 text-emerald-600" /> 고정 하단 이미지 <span className="text-xs font-normal text-muted-foreground">(선택 · 모든 글 맨 아래)</span>
                  </div>
                  {fixedImage ? (
                    <button onClick={removeFixedImage} className="text-xs text-rose-500 hover:text-rose-600 underline">해제</button>
                  ) : (
                    <label className="text-xs text-emerald-600 hover:text-emerald-700 underline cursor-pointer">
                      등록
                      <input type="file" accept="image/*" onChange={handleFixedImageUpload} className="hidden" />
                    </label>
                  )}
                </div>
                {fixedImage ? (
                  <div className="flex items-center gap-2 mt-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={fixedImage} alt="고정" className="w-16 h-16 object-cover rounded border" />
                    <p className="text-xs text-muted-foreground">
                      등록됨 — 발행할 때마다 <b>유니크화(보정)</b>되어 본문 맨 아래에 자동으로 들어갑니다.
                    </p>
                  </div>
                ) : (
                  <p className="text-[11px] text-muted-foreground mt-1">
                    로고·연락처·안내 이미지 등을 등록하면, 랜덤 사진 외에 모든 글 하단에 항상 붙습니다(매번 다른 변형).
                  </p>
                )}
              </div>
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

                      {/* 어느 블로그 기준인지 — 계정마다 예약 기준이 따로 관리된다 */}
                      <div className="flex items-center justify-between rounded-md bg-white border border-amber-200 px-3 py-1.5 text-xs">
                        <span className="text-amber-900">
                          기준 블로그{' '}
                          {blogConfirmed ? (
                            <b className="font-semibold">{blogId}</b>
                          ) : cachedBlogId ? (
                            <>
                              <b className="font-semibold">{cachedBlogId}</b>
                              <span className="ml-1 text-amber-600">(지난 기록 · 확인 전)</span>
                            </>
                          ) : (
                            <span className="text-red-600">확인 안 됨 — 간격 예약을 쓸 수 없습니다</span>
                          )}
                        </span>
                        <button onClick={() => detectBlog(false)} disabled={blogChecking}
                          className="text-amber-700 underline underline-offset-2 disabled:opacity-50">
                          {blogChecking ? '확인 중...' : '다시 확인'}
                        </button>
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
                        {!intervalReady
                          ? '기준 블로그를 확인해야 간격 예약을 쓸 수 있어요. 기준을 모르면 이미 잡아둔 예약 위에 겹쳐 잡힙니다.'
                          : lastScheduledAt
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

              {/* 카테고리 (발행 계열) — 목록은 확장이 네이버 에디터에서 읽어온다 */}
              {finalAction !== 'draft' && (
                <div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">카테고리</Label>
                    <button type="button" onClick={() => syncCategories(false)} disabled={syncingCats}
                      className="text-xs text-emerald-700 hover:underline disabled:opacity-50">
                      {syncingCats ? '불러오는 중...' : '목록 새로고침'}
                    </button>
                  </div>
                  <select value={category} onChange={(e) => setCategory(e.target.value)}
                    disabled={syncingCats}
                    className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 text-sm disabled:opacity-60">
                    <option value="">네이버 기본 카테고리</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {!syncingCats && categories.length === 0 && (
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      카테고리를 불러오지 못했습니다. 네이버 로그인 상태를 확인한 뒤 &lsquo;목록 새로고침&rsquo;을 눌러주세요.
                    </p>
                  )}
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
                  {batchProgress && (
                    <div className="mb-2">
                      <div className="flex items-center justify-between text-[11px] text-amber-800 mb-1">
                        <span>등록 중… {batchProgress.done}/{batchProgress.total}건</span>
                        <span>성공 {batchProgress.ok}건{batchProgress.done > batchProgress.ok && ` · 실패 ${batchProgress.done - batchProgress.ok}건`}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-amber-100 overflow-hidden">
                        <div className="h-full bg-emerald-500 transition-all"
                          style={{ width: `${Math.round((batchProgress.done / batchProgress.total) * 100)}%` }} />
                      </div>
                    </div>
                  )}
                  <div className="max-h-52 overflow-y-auto divide-y divide-amber-100">
                    {prepared.map((p) => (
                      <div key={p.id} className="flex items-center gap-2 py-1.5 text-xs">
                        <span className="tabular-nums text-amber-800 w-36 shrink-0">{fmtKo(new Date(p.scheduleISO))}</span>
                        <span className="flex-1 truncate text-gray-700">{p.title || '(제목 없음)'}</span>
                        {failedIds[p.id] && (
                          <span className="text-[11px] text-rose-600 shrink-0 max-w-40 truncate" title={failedIds[p.id]}>
                            실패: {failedIds[p.id]}
                          </span>
                        )}
                        <span className="text-[11px] text-muted-foreground shrink-0">사진 {p.imageCount}</span>
                        <button onClick={() => removePrepared(p.id)} className="text-rose-500 hover:text-rose-600 shrink-0">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-amber-700">
                    담아둔 글은 여기 저장돼요(새로고침해도 유지). 다 모은 뒤 &lsquo;한번에 발행&rsquo;을 누르면 확장이 순서대로
                    네이버 예약발행에 등록하고, 등록에 성공한 글만 목록에서 빠집니다.
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
