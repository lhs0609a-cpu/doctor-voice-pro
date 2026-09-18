'use client'

import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import {
  Upload,
  Trash2,
  Loader2,
  Wand2,
  Download,
  CheckCircle2,
  AlertTriangle,
  ImageOff,
  FolderPlus,
  Folder,
  Pencil,
  Check,
  X,
  Tag,
} from 'lucide-react'
import {
  mediaPoolAPI,
  type PoolImageItem,
  type AssignedImage,
  type PoolCollectionItem,
} from '@/lib/api'
import { campaignAPI, pollTask, type PhotoMeta } from '@/lib/campaign-api'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const MAX_POOL_SIZE = 200

export default function MediaPoolPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [images, setImages] = useState<PoolImageItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 자동 배정 미리보기
  const [assignCount, setAssignCount] = useState(5)
  const [isAssigning, setIsAssigning] = useState(false)
  const [assigned, setAssigned] = useState<AssignedImage[]>([])
  const [assignWarnings, setAssignWarnings] = useState<string[]>([])

  // 목록(앨범)
  const [collections, setCollections] = useState<PoolCollectionItem[]>([])
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)
  const [newCollectionName, setNewCollectionName] = useState('')
  const [creatingCollection, setCreatingCollection] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  // AI 사진 인식(태깅) — 사진 id → 메타
  const [photoMeta, setPhotoMeta] = useState<Record<string, PhotoMeta>>({})
  const [tagging, setTagging] = useState<{ progress: number; total: number } | null>(null)

  useEffect(() => {
    loadPool()
    loadCollections()
  }, [])

  // 선택 목록이 바뀌면 그 목록의 사진만 로드(없으면 전체)
  useEffect(() => {
    loadPool(selectedCollectionId)
    loadPhotoMeta(selectedCollectionId)
  }, [selectedCollectionId])

  const loadPhotoMeta = async (collectionId?: string | null) => {
    try {
      const list = await campaignAPI.listPhotos(collectionId || undefined)
      const map: Record<string, PhotoMeta> = {}
      list.forEach((p) => { map[p.id] = p })
      setPhotoMeta(map)
    } catch {
      // 캠페인 API 를 못 쓰는 환경이면 배지만 생략
    }
  }

  const handleTagPhotos = async () => {
    if (images.length === 0) { toast.error('먼저 사진을 업로드하세요'); return }
    setTagging({ progress: 0, total: images.length })
    try {
      const task = await campaignAPI.tagPhotos(selectedCollectionId)
      const done = await pollTask(task.id, (t) => setTagging({ progress: t.progress, total: t.total || images.length }))
      if (done.status === 'done') {
        toast.success('AI 사진 인식이 끝났습니다', { description: done.message || undefined })
      } else {
        toast.error('AI 사진 인식 실패', { description: done.error || done.message || undefined })
      }
      await loadPhotoMeta(selectedCollectionId)
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      toast.error('AI 사진 인식 실패', { description: e?.response?.data?.detail || e?.message })
    } finally {
      setTagging(null)
    }
  }

  const metaTitle = (m?: PhotoMeta) => {
    if (!m || !m.tagged) return '아직 AI 태깅되지 않은 사진'
    const parts = [m.caption, m.scene && `장면: ${m.scene}`, m.tags?.length ? `태그: ${m.tags.join(', ')}` : null]
    return parts.filter(Boolean).join('\n')
  }

  const loadPool = async (collectionId?: string | null) => {
    try {
      const data = await mediaPoolAPI.list(collectionId || undefined)
      setImages(data.images)
    } catch (err) {
      console.error(err)
      toast.error('사진 풀을 불러오지 못했습니다')
    } finally {
      setIsLoading(false)
    }
  }

  const loadCollections = async () => {
    try {
      const data = await mediaPoolAPI.listCollections()
      setCollections(data.collections)
    } catch (err) {
      console.error(err)
    }
  }

  const handleCreateCollection = async () => {
    const name = newCollectionName.trim()
    if (!name) { toast.error('목록 이름을 입력하세요'); return }
    setCreatingCollection(true)
    try {
      const col = await mediaPoolAPI.createCollection(name)
      setNewCollectionName('')
      await loadCollections()
      setSelectedCollectionId(col.id)
      toast.success(`'${name}' 목록을 만들었어요. 이제 사진을 올리면 이 목록에 담깁니다`)
    } catch (err) {
      console.error(err)
      toast.error('목록 생성 실패')
    } finally {
      setCreatingCollection(false)
    }
  }

  const handleRenameCollection = async (id: string) => {
    const name = renameValue.trim()
    if (!name) { toast.error('이름을 입력하세요'); return }
    try {
      await mediaPoolAPI.renameCollection(id, name)
      setRenamingId(null)
      await loadCollections()
      toast.success('이름을 변경했어요')
    } catch (err) {
      console.error(err)
      toast.error('이름 변경 실패')
    }
  }

  const handleDeleteCollection = async (id: string, name: string) => {
    if (!confirm(`'${name}' 목록을 삭제할까요? (사진 원본은 풀에 남습니다)`)) return
    try {
      await mediaPoolAPI.deleteCollection(id)
      if (selectedCollectionId === id) setSelectedCollectionId(null)
      await loadCollections()
      toast.success('목록을 삭제했어요')
    } catch (err) {
      console.error(err)
      toast.error('삭제 실패')
    }
  }

  const handleFilesSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    const arr = Array.from(files)
    setIsUploading(true)
    try {
      const res = await mediaPoolAPI.upload(arr, selectedCollectionId || undefined)
      if (res.uploaded > 0) {
        const where = selectedCollectionId
          ? ` → '${collections.find(c => c.id === selectedCollectionId)?.name || '목록'}'`
          : ''
        toast.success(`${res.uploaded}장 업로드 완료${where}${res.failed ? ` (실패 ${res.failed}장)` : ''}`, {
          description: res.message || undefined,
        })
      } else {
        toast.error(
          res.message ||
          `업로드 실패 (${res.failed}장). 풀 상한(${MAX_POOL_SIZE}장) 또는 파일 형식을 확인하세요.`
        )
      }
      await loadPool(selectedCollectionId)
      await loadCollections()
    } catch (err) {
      console.error(err)
      toast.error('업로드 중 오류가 발생했습니다')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await mediaPoolAPI.remove(id)
      setImages(prev => prev.filter(i => i.id !== id))
      toast.success('사진을 풀에서 제거했습니다')
    } catch (err) {
      console.error(err)
      toast.error('삭제 중 오류가 발생했습니다')
    } finally {
      setDeletingId(null)
    }
  }

  const handleAssign = async () => {
    if (images.length === 0) {
      toast.error('먼저 사진을 업로드하세요')
      return
    }
    setIsAssigning(true)
    setAssigned([])
    setAssignWarnings([])
    try {
      const res = await mediaPoolAPI.assign({
        count: assignCount,
        collection_id: selectedCollectionId || undefined,
      })
      setAssigned(res.images)
      setAssignWarnings(res.warnings)
      if (res.all_passed) {
        toast.success(`${res.returned}장 유니크화 완료 (전부 통과)`)
      } else {
        toast.warning(`${res.returned}장 배정 — 일부 임계 미달, 경고를 확인하세요`)
      }
      await loadPool() // use_count 갱신
    } catch (err) {
      console.error(err)
      toast.error('자동 배정 중 오류가 발생했습니다')
    } finally {
      setIsAssigning(false)
    }
  }

  const downloadAssigned = (a: AssignedImage, idx: number) => {
    const link = document.createElement('a')
    link.href = a.image
    link.download = `uniquified_${idx + 1}.jpg`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const downloadAll = () => {
    assigned.forEach((a, i) => downloadAssigned(a, i))
    toast.success(`${assigned.length}장 다운로드`)
  }

  const formatSize = (bytes: number | null) => {
    if (!bytes) return '-'
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const selectedCollectionName = collections.find(c => c.id === selectedCollectionId)?.name
  const taggedCount = images.filter(i => photoMeta[i.id]?.tagged).length

  return (
    <div className="space-y-6">
      <PageHeader
        title="사진 풀"
        description="사진을 미리 올려두면 글마다 자동으로 배정하고 유니크화해 네이버 중복 사진 인식을 피합니다."
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handleFilesSelected}
            />
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || images.length >= MAX_POOL_SIZE}
            >
              {isUploading ? <Loader2 className="animate-spin" /> : <Upload />}
              {isUploading ? '업로드 중...' : '사진 올리기'}
            </Button>
          </>
        }
      />

      {/* 목록(앨범) */}
      <Card>
        <CardHeader>
          <CardTitle>사진 목록</CardTitle>
          <CardDescription>
            사진을 목록으로 묶어두면(예: &apos;1목록&apos; 40장) 글 발행 시 그 목록을 선택해 자동으로 사진이 들어갑니다.
            목록을 고른 상태로 업로드하면 그 목록에 담깁니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 새 목록 만들기 */}
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-[200px] flex-1 space-y-1">
              <Label htmlFor="newCollection" className="text-[13px] font-medium text-muted-foreground">새 목록 만들기</Label>
              <Input
                id="newCollection"
                placeholder="예: 1목록, 병원외경, 시술후기"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreateCollection() }}
              />
            </div>
            <Button variant="outline" onClick={handleCreateCollection} disabled={creatingCollection}>
              {creatingCollection ? <Loader2 className="animate-spin" /> : <FolderPlus />}
              목록 추가
            </Button>
          </div>

          {/* 목록 칩 */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCollectionId(null)}
              className={cn(
                'rounded-full border px-3 py-1.5 text-sm transition-colors',
                selectedCollectionId === null
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-input bg-card hover:bg-muted'
              )}
            >
              전체 사진 <span className="tabular-nums">({images.length && selectedCollectionId === null ? images.length : '·'})</span>
            </button>
            {collections.map((c) => (
              <div key={c.id} className="flex items-center">
                {renamingId === c.id ? (
                  <div className="flex items-center gap-1">
                    <Input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleRenameCollection(c.id) }}
                      className="h-8 w-32"
                      autoFocus
                    />
                    <Button size="sm" variant="ghost" className="w-8 px-0" onClick={() => handleRenameCollection(c.id)}>
                      <Check />
                    </Button>
                    <Button size="sm" variant="ghost" className="w-8 px-0" onClick={() => setRenamingId(null)}>
                      <X />
                    </Button>
                  </div>
                ) : (
                  <div
                    className={cn(
                      'group flex cursor-pointer items-center gap-1.5 rounded-full border py-1.5 pl-3 pr-1.5 text-sm transition-colors',
                      selectedCollectionId === c.id
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-input bg-card hover:bg-muted'
                    )}
                    onClick={() => setSelectedCollectionId(c.id)}
                  >
                    <Folder className="h-3.5 w-3.5" />
                    <span>{c.name}</span>
                    <span className={cn(
                      'rounded-full px-1.5 text-[11px] tabular-nums',
                      selectedCollectionId === c.id ? 'bg-primary-foreground/20' : 'bg-muted text-muted-foreground'
                    )}>{c.count}</span>
                    <button
                      className="p-0.5 opacity-60 hover:opacity-100"
                      onClick={(e) => { e.stopPropagation(); setRenamingId(c.id); setRenameValue(c.name) }}
                      title="이름 변경"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      className="p-0.5 opacity-60 hover:opacity-100"
                      onClick={(e) => { e.stopPropagation(); handleDeleteCollection(c.id, c.name) }}
                      title="목록 삭제"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {collections.length === 0 && (
            <p className="text-sm text-muted-foreground">
              아직 목록이 없습니다. 위에서 목록을 만들면 사진을 그룹으로 관리할 수 있어요.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 풀 목록 */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                보관된 사진
                {selectedCollectionName && <Pill tone="accent"><Folder className="h-3 w-3" /> {selectedCollectionName}</Pill>}
              </CardTitle>
              <CardDescription>
                {selectedCollectionId
                  ? '업로드하면 선택한 목록에 담깁니다. 전체 풀에 담으려면 위에서 ‘전체 사진’을 선택하세요.'
                  : 'JPG/PNG 여러 장을 한 번에 올릴 수 있습니다. 배정 시 사용 횟수가 적은 사진부터 먼저 씁니다.'}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Pill tone="muted" className="tabular-nums">{images.length} / {MAX_POOL_SIZE}장</Pill>
              {images.length > 0 && (
                <Pill tone={taggedCount === images.length ? 'ok' : 'muted'} className="tabular-nums">
                  태그됨 {taggedCount} / {images.length}
                </Pill>
              )}
              <Button size="sm" variant="outline" onClick={handleTagPhotos} disabled={!!tagging || images.length === 0}>
                {tagging ? <Loader2 className="animate-spin" /> : <Tag />}
                {tagging ? `인식 중 ${tagging.progress}/${tagging.total}` : 'AI 사진 인식'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              불러오는 중...
            </div>
          ) : images.length === 0 ? (
            <EmptyState
              icon={<ImageOff className="h-10 w-10" />}
              title="아직 사진이 없습니다"
              description="사진을 올려두면 글마다 자동으로 배정됩니다. AI 사진 인식을 켜면 문맥에 맞는 사진이 배치됩니다."
              action={
                <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
                  <Upload /> 사진 올리기
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {images.map((img) => (
                <div key={img.id} className="group relative overflow-hidden rounded-lg border" title={metaTitle(photoMeta[img.id])}>
                  <span className="absolute left-1 top-1 z-10">
                    <Pill tone={photoMeta[img.id]?.tagged ? 'ok' : 'muted'} className="text-[10px]">
                      {photoMeta[img.id]?.tagged ? '태그됨' : '미태깅'}
                    </Pill>
                  </span>
                  {img.thumbnail ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={img.thumbnail} alt={img.filename || img.id} className="aspect-square w-full object-cover" />
                  ) : (
                    <div className="flex aspect-square w-full items-center justify-center bg-muted">
                      <ImageOff className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                  <Button
                    variant="destructive"
                    size="sm"
                    className="absolute right-1 top-1 h-7 w-7 px-0 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleDelete(img.id)}
                    disabled={deletingId === img.id}
                  >
                    {deletingId === img.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                  </Button>
                  <div className="p-2">
                    <p className="truncate text-[11px] text-muted-foreground" title={img.filename || ''}>
                      {img.filename || '이름 없음'}
                    </p>
                    <div className="mt-1 flex items-center justify-between text-[11px] tabular-nums text-muted-foreground">
                      <span>사용 {img.use_count}회</span>
                      <span>{formatSize(img.size_bytes)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 자동 배정 미리보기 */}
      <Card>
        <CardHeader>
          <CardTitle>자동 배정 미리보기</CardTitle>
          <CardDescription>
            가장 적게 쓴 사진을 골라 각각 유니크화합니다. 통과(passed)는 원본·과거 변형과 pHash 거리가 임계 이상임을 뜻합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="assignCount" className="text-[13px] font-medium text-muted-foreground">장수</Label>
              <Input
                id="assignCount"
                type="number"
                min={1}
                max={20}
                value={assignCount}
                onChange={(e) => setAssignCount(Math.max(1, Number(e.target.value) || 1))}
                className="w-24 tabular-nums"
              />
            </div>
            <Button variant="outline" onClick={handleAssign} disabled={isAssigning || images.length === 0}>
              {isAssigning ? <Loader2 className="animate-spin" /> : <Wand2 />}
              {isAssigning ? '유니크화 중...' : '배정 + 유니크화'}
            </Button>
            {assigned.length > 0 && (
              <Button variant="ghost" onClick={downloadAll}>
                <Download />
                전체 다운로드
              </Button>
            )}
          </div>

          {assignWarnings.length > 0 && (
            <div className="space-y-1 rounded-lg bg-warning-soft p-3">
              {assignWarnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-warning">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {assigned.length > 0 && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
              {assigned.map((a, idx) => (
                <div key={idx} className="group relative overflow-hidden rounded-lg border">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={a.image} alt={a.filename || `assigned-${idx}`} className="aspect-square w-full object-cover" />
                  <div className="space-y-1.5 p-2">
                    <div>
                      {a.passed ? (
                        <Pill tone="ok"><CheckCircle2 className="h-3 w-3" /> 통과</Pill>
                      ) : (
                        <Pill tone="danger"><AlertTriangle className="h-3 w-3" /> 미달</Pill>
                      )}
                    </div>
                    <p className="text-[11px] leading-tight tabular-nums text-muted-foreground">
                      {a.frame_style} · 거리 {a.min_distance} · SSIM {a.ssim.toFixed(3)}
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => downloadAssigned(a, idx)}
                    >
                      <Download /> 저장
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
