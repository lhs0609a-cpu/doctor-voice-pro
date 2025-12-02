'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Save,
  Eye,
  Image as ImageIcon,
  Type,
  Quote,
  Palette,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  List,
  Trash2,
  MoveUp,
  MoveDown,
  Plus,
  Upload,
  Copy,
  Download,
  Send,
  X,
  GripVertical,
} from 'lucide-react'

interface SavedPost {
  id: string
  savedAt: string
  suggested_titles?: string[]
  generated_content?: string
  seo_keywords?: string[]
  original_content?: string
  title?: string
  hashtags?: string[]
}

// 에디터 블록 타입
type BlockType = 'text' | 'image' | 'quote' | 'divider'

interface EditorBlock {
  id: string
  type: BlockType
  content: string
  style?: {
    backgroundColor?: string
    textAlign?: 'left' | 'center' | 'right'
    bold?: boolean
    italic?: boolean
    underline?: boolean
    fontSize?: 'small' | 'medium' | 'large'
  }
  imageUrl?: string
  imageFile?: File
}

interface BlogEditorProps {
  post: SavedPost
  onSave: (post: SavedPost) => void
}

// 문단을 블록으로 변환
function contentToBlocks(content: string): EditorBlock[] {
  const paragraphs = content.split('\n').filter(p => p.trim())
  return paragraphs.map((text, index) => ({
    id: `block-${Date.now()}-${index}`,
    type: 'text' as BlockType,
    content: text,
    style: {
      textAlign: 'left' as const,
    },
  }))
}

// 블록을 텍스트로 변환
function blocksToContent(blocks: EditorBlock[]): string {
  return blocks
    .filter(b => b.type === 'text')
    .map(b => b.content)
    .join('\n\n')
}

export function BlogEditor({ post, onSave }: BlogEditorProps) {
  const router = useRouter()
  const [title, setTitle] = useState(post.suggested_titles?.[0] || post.title || '')
  const [blocks, setBlocks] = useState<EditorBlock[]>(() =>
    contentToBlocks(post.generated_content || '')
  )
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [previewMode, setPreviewMode] = useState(false)
  const [uploadedImages, setUploadedImages] = useState<{ id: string; url: string; file: File }[]>([])
  const [dragOverBlockId, setDragOverBlockId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  // 선택된 블록
  const selectedBlock = blocks.find(b => b.id === selectedBlockId)

  // 블록 추가
  const addBlock = (type: BlockType, afterId?: string) => {
    const newBlock: EditorBlock = {
      id: `block-${Date.now()}`,
      type,
      content: type === 'divider' ? '' : '',
      style: {
        textAlign: 'left',
      },
    }

    setBlocks(prev => {
      if (afterId) {
        const index = prev.findIndex(b => b.id === afterId)
        return [...prev.slice(0, index + 1), newBlock, ...prev.slice(index + 1)]
      }
      return [...prev, newBlock]
    })

    if (type !== 'divider') {
      setSelectedBlockId(newBlock.id)
    }
  }

  // 블록 삭제
  const deleteBlock = (id: string) => {
    setBlocks(prev => prev.filter(b => b.id !== id))
    if (selectedBlockId === id) {
      setSelectedBlockId(null)
    }
  }

  // 블록 이동
  const moveBlock = (id: string, direction: 'up' | 'down') => {
    setBlocks(prev => {
      const index = prev.findIndex(b => b.id === id)
      if (
        (direction === 'up' && index === 0) ||
        (direction === 'down' && index === prev.length - 1)
      ) {
        return prev
      }

      const newBlocks = [...prev]
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      ;[newBlocks[index], newBlocks[targetIndex]] = [newBlocks[targetIndex], newBlocks[index]]
      return newBlocks
    })
  }

  // 블록 내용 업데이트
  const updateBlockContent = (id: string, content: string) => {
    setBlocks(prev =>
      prev.map(b => (b.id === id ? { ...b, content } : b))
    )
  }

  // 블록 스타일 업데이트
  const updateBlockStyle = (id: string, style: Partial<EditorBlock['style']>) => {
    setBlocks(prev =>
      prev.map(b => (b.id === id ? { ...b, style: { ...b.style, ...style } } : b))
    )
  }

  // 이미지 업로드 핸들러
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const imageFiles = files.filter(file => /\.(jpg|jpeg|png|gif|webp)$/i.test(file.name))

    imageFiles.forEach(file => {
      const url = URL.createObjectURL(file)
      const id = `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      setUploadedImages(prev => [...prev, { id, url, file }])
    })

    if (imageFiles.length > 0) {
      toast.success(`${imageFiles.length}개 이미지 업로드됨`)
    }
  }

  // 이미지를 블록에 삽입
  const insertImageToBlock = (imageId: string, afterBlockId?: string) => {
    const image = uploadedImages.find(img => img.id === imageId)
    if (!image) return

    const newBlock: EditorBlock = {
      id: `block-${Date.now()}`,
      type: 'image',
      content: '',
      imageUrl: image.url,
      imageFile: image.file,
    }

    setBlocks(prev => {
      if (afterBlockId) {
        const index = prev.findIndex(b => b.id === afterBlockId)
        return [...prev.slice(0, index + 1), newBlock, ...prev.slice(index + 1)]
      }
      return [...prev, newBlock]
    })
  }

  // 드래그 앤 드롭
  const handleDragOver = (e: React.DragEvent, blockId: string) => {
    e.preventDefault()
    setDragOverBlockId(blockId)
  }

  const handleDrop = (e: React.DragEvent, blockId: string) => {
    e.preventDefault()
    setDragOverBlockId(null)

    const imageId = e.dataTransfer.getData('imageId')
    if (imageId) {
      insertImageToBlock(imageId, blockId)
    }

    // 파일 드롭
    const files = Array.from(e.dataTransfer.files)
    const imageFiles = files.filter(file => file.type.startsWith('image/'))

    imageFiles.forEach(file => {
      const url = URL.createObjectURL(file)
      const newBlock: EditorBlock = {
        id: `block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        type: 'image',
        content: '',
        imageUrl: url,
        imageFile: file,
      }

      setBlocks(prev => {
        const index = prev.findIndex(b => b.id === blockId)
        return [...prev.slice(0, index + 1), newBlock, ...prev.slice(index + 1)]
      })
    })

    if (imageFiles.length > 0) {
      toast.success(`${imageFiles.length}개 이미지 삽입됨`)
    }
  }

  // 전체 영역 드래그 앤 드롭
  const handleGlobalDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleGlobalDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleGlobalDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    const imageFiles = files.filter(file => file.type.startsWith('image/'))

    imageFiles.forEach(file => {
      const url = URL.createObjectURL(file)
      const id = `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      setUploadedImages(prev => [...prev, { id, url, file }])
    })

    if (imageFiles.length > 0) {
      toast.success(`${imageFiles.length}개 이미지 업로드됨 - 원하는 위치에 드래그하세요`)
    }
  }

  // 저장
  const handleSave = () => {
    const updatedPost: SavedPost = {
      ...post,
      title,
      suggested_titles: [title],
      generated_content: blocksToContent(blocks),
    }
    onSave(updatedPost)
  }

  // 클립보드 복사 (HTML 형식)
  const copyToClipboard = async () => {
    const html = generateHTML()
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([blocksToContent(blocks)], { type: 'text/plain' }),
        }),
      ])
      toast.success('클립보드에 복사됨', {
        description: '네이버 블로그에 Ctrl+V로 붙여넣기 하세요',
      })
    } catch (error) {
      // Fallback
      const textarea = document.createElement('textarea')
      textarea.value = blocksToContent(blocks)
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      toast.success('텍스트가 복사됨')
    }
  }

  // HTML 생성
  const generateHTML = () => {
    let html = `<h2>${title}</h2>\n\n`

    blocks.forEach(block => {
      if (block.type === 'text') {
        const style = []
        if (block.style?.backgroundColor) {
          style.push(`background-color: ${block.style.backgroundColor}; padding: 16px; border-radius: 8px;`)
        }
        if (block.style?.textAlign) {
          style.push(`text-align: ${block.style.textAlign};`)
        }
        if (block.style?.bold) style.push('font-weight: bold;')
        if (block.style?.italic) style.push('font-style: italic;')
        if (block.style?.underline) style.push('text-decoration: underline;')

        const styleAttr = style.length > 0 ? ` style="${style.join(' ')}"` : ''
        html += `<p${styleAttr}>${block.content}</p>\n\n`
      } else if (block.type === 'image' && block.imageUrl) {
        html += `<p><img src="${block.imageUrl}" style="max-width: 100%;" /></p>\n\n`
      } else if (block.type === 'quote') {
        html += `<blockquote style="border-left: 4px solid #3b82f6; padding-left: 16px; margin: 16px 0; color: #4b5563;">${block.content}</blockquote>\n\n`
      } else if (block.type === 'divider') {
        html += `<hr style="margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;" />\n\n`
      }
    })

    return html
  }

  // 이미지를 Base64로 변환
  const imageToBase64 = async (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  // 크롬 확장 프로그램으로 전송
  const sendToExtension = async () => {
    const loadingToast = toast.loading('포스팅 데이터 준비 중...')

    try {
      // 블록에서 이미지 추출 및 Base64 변환
      const imageBlocks = blocks.filter(b => b.type === 'image' && b.imageFile)
      const imageBase64List: string[] = []

      for (const block of imageBlocks) {
        if (block.imageFile) {
          const base64 = await imageToBase64(block.imageFile)
          imageBase64List.push(base64)
        }
      }

      // 업로드된 이미지도 Base64로 변환
      for (const img of uploadedImages) {
        if (img.file) {
          const base64 = await imageToBase64(img.file)
          if (!imageBase64List.includes(base64)) {
            imageBase64List.push(base64)
          }
        }
      }

      // 블록 순서대로 콘텐츠 생성 (이미지 위치 정보 포함)
      const contentWithImageMarkers = blocks.map((block, index) => {
        if (block.type === 'text') {
          return { type: 'text', content: block.content, style: block.style }
        } else if (block.type === 'image') {
          return { type: 'image', index: imageBlocks.indexOf(block) }
        } else if (block.type === 'quote') {
          return { type: 'quote', content: block.content }
        } else if (block.type === 'divider') {
          return { type: 'divider' }
        }
        return null
      }).filter(Boolean)

      const postData = {
        title,
        content: blocksToContent(blocks),
        blocks: contentWithImageMarkers,
        html: generateHTML(),
        keywords: post.seo_keywords || [],
        images: imageBase64List,
      }

      // saved-posts 업데이트 (이미지는 저장하지 않음 - 용량 초과 방지)
      const saved = localStorage.getItem('saved-posts')
      const posts = saved ? JSON.parse(saved) : []
      const postIndex = posts.findIndex((p: SavedPost) => p.id === post.id)

      if (postIndex !== -1) {
        posts[postIndex] = {
          ...posts[postIndex],
          title,
          suggested_titles: [title],
          generated_content: blocksToContent(blocks),
          // 이미지는 저장하지 않음 (용량 초과 방지)
        }
        localStorage.setItem('saved-posts', JSON.stringify(posts))
      }

      // 확장 프로그램용 데이터는 별도 키에 저장 (이미지 포함)
      // IndexedDB 사용하여 대용량 데이터 저장
      try {
        await saveToIndexedDB('doctorvoice-pending-post', postData)
        console.log('IndexedDB에 저장 완료')
      } catch (dbError) {
        console.warn('IndexedDB 저장 실패, localStorage 시도:', dbError)
        // localStorage 용량 초과 시 이미지 제외하고 저장
        const lightPostData = { ...postData, images: [] }
        localStorage.setItem('doctorvoice-pending-post', JSON.stringify(lightPostData))
      }

      window.postMessage({
        type: 'DOCTORVOICE_POST_DATA',
        data: postData,
      }, '*')

      toast.success('포스팅 데이터 준비 완료!', {
        id: loadingToast,
        description: '크롬 확장 프로그램 아이콘을 클릭하여 포스팅을 시작하세요',
      })
    } catch (error) {
      console.error('sendToExtension error:', error)
      toast.error('데이터 준비 실패', {
        id: loadingToast,
        description: '다시 시도해주세요',
      })
    }
  }

  // IndexedDB에 대용량 데이터 저장
  const saveToIndexedDB = (key: string, data: any): Promise<void> => {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('DoctorVoiceDB', 1)

      request.onerror = () => reject(request.error)

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        if (!db.objectStoreNames.contains('posts')) {
          db.createObjectStore('posts')
        }
      }

      request.onsuccess = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        const transaction = db.transaction(['posts'], 'readwrite')
        const store = transaction.objectStore('posts')

        const putRequest = store.put(data, key)
        putRequest.onsuccess = () => resolve()
        putRequest.onerror = () => reject(putRequest.error)
      }
    })
  }

  // 배경색 옵션
  const backgroundColors = [
    { name: '없음', value: '' },
    { name: '연노랑', value: '#fef9c3' },
    { name: '연초록', value: '#dcfce7' },
    { name: '연파랑', value: '#dbeafe' },
    { name: '연보라', value: '#f3e8ff' },
    { name: '연분홍', value: '#fce7f3' },
    { name: '연회색', value: '#f3f4f6' },
  ]

  return (
    <div
      className="min-h-screen"
      onDragOver={handleGlobalDragOver}
      onDragLeave={handleGlobalDragLeave}
      onDrop={handleGlobalDrop}
    >
      {/* 헤더 */}
      <div className="sticky top-0 z-50 bg-white border-b shadow-sm">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={() => router.push('/dashboard/saved')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                돌아가기
              </Button>
              <div className="h-6 w-px bg-gray-300" />
              <h1 className="font-semibold">블로그 에디터</h1>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={previewMode ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPreviewMode(!previewMode)}
              >
                <Eye className="h-4 w-4 mr-2" />
                {previewMode ? '편집모드' : '미리보기'}
              </Button>
              <Button variant="outline" size="sm" onClick={copyToClipboard}>
                <Copy className="h-4 w-4 mr-2" />
                복사
              </Button>
              <Button variant="outline" size="sm" onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                저장
              </Button>
              <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={sendToExtension}>
                <Send className="h-4 w-4 mr-2" />
                블로그 포스팅
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* 드래그 오버레이 */}
      {isDragging && (
        <div className="fixed inset-0 z-40 bg-blue-500/20 flex items-center justify-center pointer-events-none">
          <div className="bg-white p-8 rounded-lg shadow-lg text-center">
            <Upload className="h-12 w-12 mx-auto mb-4 text-blue-600" />
            <p className="text-lg font-semibold">이미지를 여기에 드롭하세요</p>
          </div>
        </div>
      )}

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 왼쪽: 이미지 패널 */}
          <div className="lg:col-span-1 space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <ImageIcon className="h-4 w-4" />
                  이미지 라이브러리
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-4 w-4 mr-2" />
                  이미지 업로드
                </Button>

                {uploadedImages.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">
                      이미지를 드래그해서 원하는 위치에 놓으세요
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {uploadedImages.map(img => (
                        <div
                          key={img.id}
                          draggable
                          onDragStart={e => {
                            e.dataTransfer.setData('imageId', img.id)
                          }}
                          className="relative group cursor-move"
                        >
                          <img
                            src={img.url}
                            alt=""
                            className="w-full h-20 object-cover rounded border hover:border-blue-500 transition-colors"
                          />
                          <button
                            onClick={() => {
                              setUploadedImages(prev => prev.filter(i => i.id !== img.id))
                            }}
                            className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 text-center py-4">
                    업로드된 이미지가 없습니다
                  </p>
                )}
              </CardContent>
            </Card>

            {/* 블록 추가 */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">블록 추가</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => addBlock('text', selectedBlockId || undefined)}
                >
                  <Type className="h-4 w-4 mr-2" />
                  텍스트
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => addBlock('quote', selectedBlockId || undefined)}
                >
                  <Quote className="h-4 w-4 mr-2" />
                  인용구
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => addBlock('divider', selectedBlockId || undefined)}
                >
                  <span className="mr-2">—</span>
                  구분선
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* 가운데: 에디터 영역 */}
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-6">
                {/* 제목 */}
                <Input
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="제목을 입력하세요"
                  className="text-2xl font-bold border-none shadow-none focus-visible:ring-0 px-0 mb-6"
                  disabled={previewMode}
                />

                {/* 블록 목록 */}
                <div className="space-y-3">
                  {blocks.map((block, index) => (
                    <div
                      key={block.id}
                      className={`relative group ${
                        dragOverBlockId === block.id ? 'ring-2 ring-blue-500' : ''
                      }`}
                      onDragOver={e => handleDragOver(e, block.id)}
                      onDrop={e => handleDrop(e, block.id)}
                      onClick={() => !previewMode && setSelectedBlockId(block.id)}
                    >
                      {/* 블록 컨트롤 */}
                      {!previewMode && (
                        <div className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-1">
                          <button
                            onClick={e => {
                              e.stopPropagation()
                              moveBlock(block.id, 'up')
                            }}
                            className="p-1 hover:bg-gray-100 rounded"
                            disabled={index === 0}
                          >
                            <MoveUp className="h-3 w-3" />
                          </button>
                          <button
                            onClick={e => {
                              e.stopPropagation()
                              moveBlock(block.id, 'down')
                            }}
                            className="p-1 hover:bg-gray-100 rounded"
                            disabled={index === blocks.length - 1}
                          >
                            <MoveDown className="h-3 w-3" />
                          </button>
                        </div>
                      )}

                      {/* 블록 내용 */}
                      <div
                        className={`rounded-lg transition-all ${
                          selectedBlockId === block.id && !previewMode
                            ? 'ring-2 ring-blue-500'
                            : 'hover:bg-gray-50'
                        }`}
                        style={{
                          backgroundColor: block.style?.backgroundColor || undefined,
                        }}
                      >
                        {block.type === 'text' && (
                          <textarea
                            value={block.content}
                            onChange={e => updateBlockContent(block.id, e.target.value)}
                            placeholder="텍스트를 입력하세요..."
                            className="w-full min-h-[60px] p-3 bg-transparent border-none resize-none focus:outline-none"
                            style={{
                              textAlign: block.style?.textAlign,
                              fontWeight: block.style?.bold ? 'bold' : undefined,
                              fontStyle: block.style?.italic ? 'italic' : undefined,
                              textDecoration: block.style?.underline ? 'underline' : undefined,
                            }}
                            disabled={previewMode}
                          />
                        )}

                        {block.type === 'image' && block.imageUrl && (
                          <div className="p-2">
                            <img
                              src={block.imageUrl}
                              alt=""
                              className="max-w-full rounded-lg mx-auto"
                            />
                          </div>
                        )}

                        {block.type === 'quote' && (
                          <div className="border-l-4 border-blue-500 pl-4 py-2">
                            <textarea
                              value={block.content}
                              onChange={e => updateBlockContent(block.id, e.target.value)}
                              placeholder="인용구를 입력하세요..."
                              className="w-full min-h-[40px] bg-transparent border-none resize-none focus:outline-none text-gray-600 italic"
                              disabled={previewMode}
                            />
                          </div>
                        )}

                        {block.type === 'divider' && (
                          <hr className="my-4 border-gray-300" />
                        )}
                      </div>

                      {/* 삭제 버튼 */}
                      {!previewMode && (
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            deleteBlock(block.id)
                          }}
                          className="absolute -right-8 top-1/2 -translate-y-1/2 p-1 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50 rounded"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  ))}

                  {/* 블록 추가 버튼 */}
                  {!previewMode && (
                    <button
                      onClick={() => addBlock('text')}
                      className="w-full py-4 border-2 border-dashed border-gray-200 rounded-lg text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors flex items-center justify-center gap-2"
                    >
                      <Plus className="h-4 w-4" />
                      블록 추가
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 오른쪽: 스타일 패널 */}
          <div className="lg:col-span-1">
            {selectedBlock && selectedBlock.type !== 'divider' && selectedBlock.type !== 'image' && !previewMode && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Palette className="h-4 w-4" />
                    블록 스타일
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 텍스트 스타일 */}
                  {selectedBlock.type === 'text' && (
                    <>
                      <div>
                        <Label className="text-xs">텍스트 스타일</Label>
                        <div className="flex gap-1 mt-2">
                          <Button
                            variant={selectedBlock.style?.bold ? 'default' : 'outline'}
                            size="sm"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, {
                                bold: !selectedBlock.style?.bold,
                              })
                            }
                          >
                            <Bold className="h-4 w-4" />
                          </Button>
                          <Button
                            variant={selectedBlock.style?.italic ? 'default' : 'outline'}
                            size="sm"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, {
                                italic: !selectedBlock.style?.italic,
                              })
                            }
                          >
                            <Italic className="h-4 w-4" />
                          </Button>
                          <Button
                            variant={selectedBlock.style?.underline ? 'default' : 'outline'}
                            size="sm"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, {
                                underline: !selectedBlock.style?.underline,
                              })
                            }
                          >
                            <Underline className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      <div>
                        <Label className="text-xs">정렬</Label>
                        <div className="flex gap-1 mt-2">
                          <Button
                            variant={selectedBlock.style?.textAlign === 'left' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, { textAlign: 'left' })
                            }
                          >
                            <AlignLeft className="h-4 w-4" />
                          </Button>
                          <Button
                            variant={selectedBlock.style?.textAlign === 'center' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, { textAlign: 'center' })
                            }
                          >
                            <AlignCenter className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </>
                  )}

                  {/* 배경색 */}
                  <div>
                    <Label className="text-xs">배경색</Label>
                    <div className="grid grid-cols-4 gap-2 mt-2">
                      {backgroundColors.map(color => (
                        <button
                          key={color.name}
                          onClick={() =>
                            updateBlockStyle(selectedBlock.id, {
                              backgroundColor: color.value,
                            })
                          }
                          className={`h-8 rounded border-2 transition-all ${
                            selectedBlock.style?.backgroundColor === color.value
                              ? 'border-blue-500 scale-110'
                              : 'border-gray-200 hover:border-gray-400'
                          }`}
                          style={{ backgroundColor: color.value || '#fff' }}
                          title={color.name}
                        />
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 키워드 */}
            {post.seo_keywords && post.seo_keywords.length > 0 && (
              <Card className="mt-4">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">SEO 키워드</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-1">
                    {post.seo_keywords.map((keyword, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 해시태그 */}
            {post.hashtags && post.hashtags.length > 0 && (
              <Card className="mt-4">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">해시태그</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-1">
                    {post.hashtags.slice(0, 10).map((tag, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
