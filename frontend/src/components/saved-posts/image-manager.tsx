/**
 * ImageManager Component
 * 이미지 업로드, 관리, 배치 설정
 */

import React, { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { toast } from 'sonner'
import { Upload, Trash2, Image as ImageIcon, Grid, List } from 'lucide-react'
import {
  saveImage,
  getImagesByPostId,
  deleteImage,
  updateImagePosition,
  isIndexedDBSupported,
  type ImageRecord,
} from '@/lib/indexeddb'
import {
  validateImageFiles,
  formatBase64Size,
} from '@/lib/image-utils'

interface ImageManagerProps {
  postId: string
  onImagesChange: (images: ImageRecord[]) => void
}

export const ImageManager: React.FC<ImageManagerProps> = ({ postId, onImagesChange }) => {
  const [images, setImages] = useState<ImageRecord[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [positionStrategy, setPositionStrategy] = useState<'between' | 'even'>('between')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // IndexedDB 지원 여부 확인
  const [isSupported, setIsSupported] = useState(true)

  useEffect(() => {
    setIsSupported(isIndexedDBSupported())
    if (!isIndexedDBSupported()) {
      toast.error('브라우저가 IndexedDB를 지원하지 않습니다.')
    }
  }, [])

  // 글 ID 변경 시 이미지 로드
  useEffect(() => {
    if (postId && isSupported) {
      loadImages()
    }
  }, [postId, isSupported])

  /**
   * 이미지 로드
   */
  const loadImages = async () => {
    setIsLoading(true)
    try {
      const loadedImages = await getImagesByPostId(postId)
      // 업로드 시간 순 정렬
      const sorted = loadedImages.sort((a, b) => a.uploadedAt - b.uploadedAt)
      setImages(sorted)
      onImagesChange(sorted)
    } catch (error: any) {
      console.error('Load images error:', error)
      toast.error('이미지를 불러오는데 실패했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * 파일 선택 핸들러
   */
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    await handleUpload(Array.from(files))

    // input 초기화 (같은 파일 재선택 가능하도록)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  /**
   * 이미지 업로드
   */
  const handleUpload = async (files: File[]) => {
    if (!isSupported) {
      toast.error('IndexedDB가 지원되지 않습니다.')
      return
    }

    // 파일 검증
    const { valid, invalid } = validateImageFiles(files, 10)

    if (invalid.length > 0) {
      invalid.forEach(({ file, reason }) => {
        toast.error(`${file.name}: ${reason}`)
      })
    }

    if (valid.length === 0) {
      return
    }

    setIsLoading(true)
    setUploadProgress(0)

    try {
      const total = valid.length
      const newImages: ImageRecord[] = []

      for (let i = 0; i < total; i++) {
        const file = valid[i]

        // IndexedDB에 저장
        const imageId = await saveImage(postId, file)

        // 저장된 이미지 정보 조회
        const savedImages = await getImagesByPostId(postId)
        const savedImage = savedImages.find((img) => img.id === imageId)

        if (savedImage) {
          newImages.push(savedImage)
        }

        // 진행률 업데이트
        setUploadProgress(Math.round(((i + 1) / total) * 100))
      }

      // 이미지 목록 업데이트
      const updatedImages = [...images, ...newImages]
      setImages(updatedImages)
      onImagesChange(updatedImages)

      toast.success(`${valid.length}개의 이미지가 업로드되었습니다.`)
    } catch (error: any) {
      console.error('Upload error:', error)
      toast.error('이미지 업로드에 실패했습니다.')
    } finally {
      setIsLoading(false)
      setUploadProgress(0)
    }
  }

  /**
   * 이미지 삭제
   */
  const handleDelete = async (imageId: string) => {
    if (!confirm('이미지를 삭제하시겠습니까?')) {
      return
    }

    try {
      await deleteImage(imageId)

      const updatedImages = images.filter((img) => img.id !== imageId)
      setImages(updatedImages)
      onImagesChange(updatedImages)

      toast.success('이미지가 삭제되었습니다.')
    } catch (error: any) {
      console.error('Delete error:', error)
      toast.error('이미지 삭제에 실패했습니다.')
    }
  }

  /**
   * 이미지 위치 업데이트
   */
  const handlePositionChange = async (imageId: string, position: number) => {
    try {
      await updateImagePosition(imageId, position)

      const updatedImages = images.map((img) =>
        img.id === imageId ? { ...img, position } : img
      )
      setImages(updatedImages)
      onImagesChange(updatedImages)
    } catch (error: any) {
      console.error('Position update error:', error)
      toast.error('위치 업데이트에 실패했습니다.')
    }
  }

  /**
   * 배치 전략 변경
   */
  const handleStrategyChange = (strategy: 'between' | 'even') => {
    setPositionStrategy(strategy)
  }

  // IndexedDB 미지원 시
  if (!isSupported) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            이미지 관리
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            현재 브라우저는 IndexedDB를 지원하지 않습니다.
            <br />
            Chrome, Firefox, Edge 등 최신 브라우저를 사용해주세요.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            이미지 관리
            {images.length > 0 && (
              <span className="text-sm font-normal text-muted-foreground">
                ({images.length}개)
              </span>
            )}
          </div>

          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            size="sm"
            className="gap-2"
          >
            <Upload className="h-4 w-4" />
            이미지 업로드
          </Button>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 파일 입력 (숨김) */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* 업로드 진행률 */}
        {isLoading && uploadProgress > 0 && (
          <div className="space-y-2">
            <Progress value={uploadProgress} />
            <p className="text-xs text-center text-muted-foreground">
              업로드 중... {uploadProgress}%
            </p>
          </div>
        )}

        {/* 배치 전략 선택 */}
        <div className="space-y-2">
          <Label>이미지 배치 전략</Label>
          <Select value={positionStrategy} onValueChange={handleStrategyChange}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="between">
                <div className="flex items-center gap-2">
                  <List className="h-4 w-4" />
                  <span>문단 사이 (2-3 문단마다)</span>
                </div>
              </SelectItem>
              <SelectItem value="even">
                <div className="flex items-center gap-2">
                  <Grid className="h-4 w-4" />
                  <span>균등 분포</span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {positionStrategy === 'between'
              ? '이미지를 2-3 문단 사이에 배치합니다.'
              : '이미지를 전체 문단에 균등하게 배치합니다.'}
          </p>
        </div>

        {/* 이미지 갤러리 */}
        {images.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {images.map((image, index) => (
              <div
                key={image.id}
                className="relative group border rounded-lg overflow-hidden bg-muted"
              >
                {/* 썸네일 */}
                <img
                  src={image.thumbnail}
                  alt={`Image ${index + 1}`}
                  className="w-full h-32 object-cover"
                />

                {/* 순서 표시 */}
                <div className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                  #{index + 1}
                </div>

                {/* 삭제 버튼 */}
                <Button
                  onClick={() => handleDelete(image.id)}
                  variant="destructive"
                  size="icon"
                  className="absolute top-2 right-2 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>

                {/* 정보 */}
                <div className="p-2 bg-background/95 backdrop-blur">
                  <p className="text-xs text-muted-foreground truncate">
                    {formatBase64Size(image.thumbnail)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed rounded-lg">
            <ImageIcon className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-sm font-medium mb-2">이미지가 없습니다</p>
            <p className="text-xs text-muted-foreground mb-4">
              이미지를 업로드하여 글에 삽입하세요
            </p>
            <Button
              onClick={() => fileInputRef.current?.click()}
              variant="outline"
              size="sm"
              className="gap-2"
            >
              <Upload className="h-4 w-4" />
              이미지 선택
            </Button>
          </div>
        )}

        {/* 안내 메시지 */}
        {images.length > 0 && (
          <div className="pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              💡 이미지는 선택한 배치 전략에 따라 자동으로 본문에 삽입됩니다.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
