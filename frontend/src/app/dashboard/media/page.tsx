'use client'

import { useState, useEffect, useRef } from 'react'
import { DashboardNav } from '@/components/dashboard-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Image as ImageIcon,
  Upload,
  Trash2,
  Loader2,
  Wand2,
  Download,
  CheckCircle2,
  AlertTriangle,
  ImageOff,
} from 'lucide-react'
import {
  mediaPoolAPI,
  type PoolImageItem,
  type AssignedImage,
} from '@/lib/api'
import { toast } from 'sonner'

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

  useEffect(() => {
    loadPool()
  }, [])

  const loadPool = async () => {
    try {
      const data = await mediaPoolAPI.list()
      setImages(data.images)
    } catch (err) {
      console.error(err)
      toast.error('사진 풀을 불러오지 못했습니다')
    } finally {
      setIsLoading(false)
    }
  }

  const handleFilesSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    const arr = Array.from(files)
    setIsUploading(true)
    try {
      const res = await mediaPoolAPI.upload(arr)
      if (res.uploaded > 0) {
        toast.success(`${res.uploaded}장 업로드 완료${res.failed ? ` (실패 ${res.failed}장)` : ''}`)
      } else {
        toast.error(`업로드 실패 (${res.failed}장). 풀 상한(${MAX_POOL_SIZE}장) 또는 파일 형식을 확인하세요.`)
      }
      await loadPool()
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
      const res = await mediaPoolAPI.assign({ count: assignCount })
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

  return (
    <div className="min-h-screen bg-background">
      <DashboardNav />
      <main className="container mx-auto px-4 py-8 max-w-6xl">
        {/* 헤더 */}
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-primary/10">
            <ImageIcon className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">사진 풀</h1>
            <p className="text-sm text-muted-foreground">
              사진을 미리 올려두면 글마다 자동으로 배정 + 유니크화해 네이버 중복사진 인식을 피합니다
            </p>
          </div>
        </div>

        {/* 업로드 */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span className="flex items-center gap-2">
                <Upload className="h-4 w-4" />
                사진 업로드
              </span>
              <Badge variant="secondary">
                {images.length} / {MAX_POOL_SIZE}장
              </Badge>
            </CardTitle>
            <CardDescription>
              JPG/PNG 여러 장을 한 번에 올릴 수 있습니다. 원본은 서버에 보관되고, 글 배정 시마다 새로운 변형이 생성됩니다.
            </CardDescription>
          </CardHeader>
          <CardContent>
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
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  업로드 중...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  사진 선택
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* 자동 배정 미리보기 */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wand2 className="h-4 w-4" />
              자동 배정 미리보기
            </CardTitle>
            <CardDescription>
              가장 적게 쓴 사진을 골라 각각 유니크화합니다. 통과(passed)는 원본·과거 변형과 pHash 거리가 임계 이상임을 뜻합니다.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <Label htmlFor="assignCount">장수</Label>
                <Input
                  id="assignCount"
                  type="number"
                  min={1}
                  max={20}
                  value={assignCount}
                  onChange={(e) => setAssignCount(Math.max(1, Number(e.target.value) || 1))}
                  className="w-24"
                />
              </div>
              <Button onClick={handleAssign} disabled={isAssigning || images.length === 0}>
                {isAssigning ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    유니크화 중...
                  </>
                ) : (
                  <>
                    <Wand2 className="h-4 w-4 mr-2" />
                    배정 + 유니크화
                  </>
                )}
              </Button>
              {assigned.length > 0 && (
                <Button variant="outline" onClick={downloadAll}>
                  <Download className="h-4 w-4 mr-2" />
                  전체 다운로드
                </Button>
              )}
            </div>

            {assignWarnings.length > 0 && (
              <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 space-y-1">
                {assignWarnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400">
                    <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {assigned.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {assigned.map((a, idx) => (
                  <div key={idx} className="border rounded-lg overflow-hidden group relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={a.image} alt={a.filename || `assigned-${idx}`} className="w-full aspect-square object-cover" />
                    <div className="p-2 space-y-1">
                      <div className="flex items-center gap-1">
                        {a.passed ? (
                          <Badge variant="secondary" className="gap-1 text-green-700 dark:text-green-400">
                            <CheckCircle2 className="h-3 w-3" /> 통과
                          </Badge>
                        ) : (
                          <Badge variant="destructive" className="gap-1">
                            <AlertTriangle className="h-3 w-3" /> 미달
                          </Badge>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-tight">
                        {a.frame_style} · 거리 {a.min_distance} · SSIM {a.ssim.toFixed(3)}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full h-7 text-xs"
                        onClick={() => downloadAssigned(a, idx)}
                      >
                        <Download className="h-3 w-3 mr-1" /> 저장
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 풀 목록 */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">보관된 사진</CardTitle>
            <CardDescription>배정 시 사용 횟수가 적은 사진부터 우선 사용됩니다</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                불러오는 중...
              </div>
            ) : images.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <ImageOff className="h-10 w-10 mb-2 opacity-50" />
                <p>아직 사진이 없습니다. 위에서 업로드하세요.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {images.map((img) => (
                  <div key={img.id} className="border rounded-lg overflow-hidden group relative">
                    {img.thumbnail ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={img.thumbnail} alt={img.filename || img.id} className="w-full aspect-square object-cover" />
                    ) : (
                      <div className="w-full aspect-square bg-muted flex items-center justify-center">
                        <ImageOff className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                    <Button
                      variant="destructive"
                      size="icon"
                      className="absolute top-1 right-1 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => handleDelete(img.id)}
                      disabled={deletingId === img.id}
                    >
                      {deletingId === img.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <div className="p-2">
                      <p className="text-[11px] truncate text-muted-foreground" title={img.filename || ''}>
                        {img.filename || '이름 없음'}
                      </p>
                      <div className="flex items-center justify-between mt-1">
                        <Badge variant="outline" className="text-[10px] px-1.5">
                          사용 {img.use_count}회
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">{formatSize(img.size_bytes)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
