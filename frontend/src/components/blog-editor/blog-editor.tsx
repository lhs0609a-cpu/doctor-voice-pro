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
import type { SavedPost } from '@/types'

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

  // 이미지 업로드 핸들러 - 자동으로 문단 사이에 배치 + 전체 스타일링
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const imageFiles = files.filter(file => /\.(jpg|jpeg|png|gif|webp)$/i.test(file.name))

    if (imageFiles.length === 0) return

    // 이미지를 라이브러리에 추가
    const newImages = imageFiles.map(file => ({
      id: `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      url: URL.createObjectURL(file),
      file
    }))
    setUploadedImages(prev => [...prev, ...newImages])

    // 자동 스타일링 적용 (이미지 배치 + 인용구 + 색상강조 + 구분선)
    autoStyleContent(newImages)

    toast.success(`${imageFiles.length}개 이미지 + 자동 스타일링 적용!`, {
      description: '인용구, 색상 강조, 구분선이 자동 추가되었습니다'
    })
  }

  // 전체 콘텐츠 자동 스타일링
  const autoStyleContent = (images: { id: string; url: string; file: File }[]) => {
    setBlocks(prevBlocks => {
      // 텍스트 블록만 필터링
      const textBlocks = prevBlocks.filter(b => b.type === 'text')
      const textBlockCount = textBlocks.length

      if (textBlockCount === 0) {
        // 텍스트 블록이 없으면 이미지만 추가
        return images.map((img, i) => ({
          id: `block-${Date.now()}-img-${i}`,
          type: 'image' as BlockType,
          content: '',
          imageUrl: img.url,
          imageFile: img.file,
        }))
      }

      // 스타일링된 새 블록 배열 생성
      let styledBlocks: EditorBlock[] = []
      let textIndex = 0
      let imageIndex = 0

      // 이미지 배치 간격 계산
      const imageInterval = Math.max(1, Math.floor(textBlockCount / (images.length + 1)))

      // 강조할 문단 패턴 감지 함수들
      const isQuoteWorthy = (text: string): boolean => {
        // 인용구로 만들기 좋은 패턴
        const quotePatterns = [
          /^["'「『]/,  // 따옴표로 시작
          /["'」』]$/,  // 따옴표로 끝
          /^.{0,5}(말씀|의하면|따르면|연구|조사|결과)/,  // ~에 의하면, ~에 따르면
          /(핵심|포인트|중요한|기억|명심)/i,  // 핵심 문구
          /^(TIP|팁|참고|주의|알림|💡|📌|⚠️|✨)/i,  // 팁/참고 문구
          /(하세요|합시다|해보세요|추천|권장)[\.\!]?$/,  // 권유형 문장
        ]
        return quotePatterns.some(pattern => pattern.test(text.trim()))
      }

      const isHighlightWorthy = (text: string): boolean => {
        // 색상 강조할 패턴
        const highlightPatterns = [
          /(중요|핵심|필수|꼭|반드시|주의|경고)/,
          /(효과|장점|이점|혜택|결과)/,
          /(방법|비결|노하우|팁|비법)/,
          /(첫째|둘째|셋째|1\.|2\.|3\.)/,
          /(\d+%|\d+원|\d+만원|\d+명)/,  // 숫자 강조
          /(추천|인기|베스트|최고)/,
        ]
        return highlightPatterns.some(pattern => pattern.test(text.trim()))
      }

      const shouldAddDivider = (index: number, total: number): boolean => {
        // 전체 콘텐츠의 1/3, 2/3 지점에 구분선 추가
        const oneThird = Math.floor(total / 3)
        const twoThirds = Math.floor((total * 2) / 3)
        return index === oneThird || index === twoThirds
      }

      // 배경색 배열 (순환 사용)
      const highlightColors = ['#fef9c3', '#dcfce7', '#dbeafe', '#f3e8ff', '#fce7f3']
      let colorIndex = 0
      let quoteCount = 0
      let highlightCount = 0
      const maxQuotes = 3  // 최대 인용구 개수
      const maxHighlights = 4  // 최대 하이라이트 개수

      prevBlocks.forEach((block, blockIndex) => {
        // 텍스트 블록인 경우 스타일링 적용
        if (block.type === 'text' && block.content.trim()) {
          const text = block.content.trim()
          textIndex++

          // 구분선 추가 (1/3, 2/3 지점)
          if (shouldAddDivider(textIndex, textBlockCount)) {
            styledBlocks.push({
              id: `block-${Date.now()}-divider-${textIndex}`,
              type: 'divider' as BlockType,
              content: '',
            })
          }

          // 인용구로 변환할지 결정
          if (isQuoteWorthy(text) && quoteCount < maxQuotes) {
            styledBlocks.push({
              ...block,
              id: `block-${Date.now()}-quote-${textIndex}`,
              type: 'quote' as BlockType,
            })
            quoteCount++
          }
          // 색상 강조할지 결정
          else if (isHighlightWorthy(text) && highlightCount < maxHighlights) {
            styledBlocks.push({
              ...block,
              style: {
                ...block.style,
                backgroundColor: highlightColors[colorIndex % highlightColors.length],
              },
            })
            colorIndex++
            highlightCount++
          }
          // 일반 텍스트
          else {
            styledBlocks.push(block)
          }

          // 이미지 삽입 (간격마다)
          if (imageIndex < images.length && textIndex % imageInterval === 0 && textIndex < textBlockCount) {
            const img = images[imageIndex]
            styledBlocks.push({
              id: `block-${Date.now()}-img-${imageIndex}`,
              type: 'image' as BlockType,
              content: '',
              imageUrl: img.url,
              imageFile: img.file,
            })
            imageIndex++
          }
        } else {
          // 텍스트가 아닌 블록은 그대로 유지
          styledBlocks.push(block)
        }
      })

      // 남은 이미지 추가
      while (imageIndex < images.length) {
        const img = images[imageIndex]
        styledBlocks.push({
          id: `block-${Date.now()}-img-${imageIndex}-end`,
          type: 'image' as BlockType,
          content: '',
          imageUrl: img.url,
          imageFile: img.file,
        })
        imageIndex++
      }

      return styledBlocks
    })
  }

  // 이미지를 문단 사이에 자동 배치
  const autoDistributeImages = (images: { id: string; url: string; file: File }[]) => {
    setBlocks(prevBlocks => {
      // 텍스트 블록만 필터링
      const textBlocks = prevBlocks.filter(b => b.type === 'text')
      const textBlockCount = textBlocks.length

      if (textBlockCount === 0) {
        // 텍스트 블록이 없으면 맨 뒤에 이미지 추가
        const imageBlocks = images.map((img, i) => ({
          id: `block-${Date.now()}-img-${i}`,
          type: 'image' as BlockType,
          content: '',
          imageUrl: img.url,
          imageFile: img.file,
        }))
        return [...prevBlocks, ...imageBlocks]
      }

      // 이미지를 균등하게 배치할 간격 계산
      // 예: 텍스트 10개, 이미지 3개 -> 2, 5, 8번째 텍스트 뒤에 배치
      const interval = Math.max(1, Math.floor(textBlockCount / (images.length + 1)))

      const newBlocks: EditorBlock[] = []
      let imageIndex = 0
      let textIndex = 0

      prevBlocks.forEach(block => {
        newBlocks.push(block)

        if (block.type === 'text') {
          textIndex++
          // 매 interval번째 텍스트 블록 뒤에 이미지 삽입
          if (imageIndex < images.length && textIndex % interval === 0 && textIndex < textBlockCount) {
            const img = images[imageIndex]
            newBlocks.push({
              id: `block-${Date.now()}-img-${imageIndex}`,
              type: 'image' as BlockType,
              content: '',
              imageUrl: img.url,
              imageFile: img.file,
            })
            imageIndex++
          }
        }
      })

      // 남은 이미지가 있으면 마지막에 추가
      while (imageIndex < images.length) {
        const img = images[imageIndex]
        newBlocks.push({
          id: `block-${Date.now()}-img-${imageIndex}-end`,
          type: 'image' as BlockType,
          content: '',
          imageUrl: img.url,
          imageFile: img.file,
        })
        imageIndex++
      }

      return newBlocks
    })
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

  // 블로그 포스팅 - HTML 복사 후 네이버 블로그로 이동
  const handleBlogPosting = async () => {
    const loadingToast = toast.loading('포스팅 준비 중...')

    try {
      // 이미지를 Base64로 변환한 HTML 생성
      const html = await generateHTMLWithBase64Images()
      const plainText = `${title}\n\n${blocksToContent(blocks)}`

      // 클립보드에 HTML 복사
      try {
        await navigator.clipboard.write([
          new ClipboardItem({
            'text/html': new Blob([html], { type: 'text/html' }),
            'text/plain': new Blob([plainText], { type: 'text/plain' }),
          }),
        ])
      } catch (clipboardError) {
        console.warn('ClipboardItem 실패, 대체 방법 시도:', clipboardError)
        await navigator.clipboard.writeText(plainText)
      }

      // saved-posts 업데이트
      const saved = localStorage.getItem('saved-posts')
      const posts = saved ? JSON.parse(saved) : []
      const postIndex = posts.findIndex((p: SavedPost) => p.id === post.id)

      if (postIndex !== -1) {
        posts[postIndex] = {
          ...posts[postIndex],
          title,
          suggested_titles: [title],
          generated_content: blocksToContent(blocks),
        }
        localStorage.setItem('saved-posts', JSON.stringify(posts))
      }

      // 확장 프로그램용 데이터 저장
      const postData = {
        title,
        content: blocksToContent(blocks),
        html,
      }

      try {
        localStorage.setItem('pendingPost', JSON.stringify(postData))
        localStorage.setItem('autoPasteEnabled', 'true')
      } catch (e) {
        console.warn('localStorage 저장 실패:', e)
      }

      toast.success('클립보드에 복사 완료!', {
        id: loadingToast,
        description: '네이버 블로그로 이동합니다...',
      })

      // 네이버 블로그 글쓰기 페이지로 이동
      setTimeout(() => {
        window.open('https://blog.naver.com/GoBlogWrite.naver', '_blank')
      }, 500)

    } catch (error) {
      console.error('블로그 포스팅 오류:', error)
      toast.error('포스팅 준비 실패', {
        id: loadingToast,
        description: '다시 시도해주세요',
      })
    }
  }

  // 이미지를 Base64로 포함한 HTML 생성
  const generateHTMLWithBase64Images = async () => {
    let html = `<h2 style="font-size: 24px; font-weight: bold; margin-bottom: 16px;">${title}</h2>\n\n`

    for (const block of blocks) {
      if (block.type === 'text') {
        const style = []
        if (block.style?.backgroundColor) {
          style.push(`background-color: ${block.style.backgroundColor}; padding: 16px; border-radius: 8px; margin: 8px 0;`)
        }
        if (block.style?.textAlign) {
          style.push(`text-align: ${block.style.textAlign};`)
        }
        if (block.style?.bold) style.push('font-weight: bold;')
        if (block.style?.italic) style.push('font-style: italic;')
        if (block.style?.underline) style.push('text-decoration: underline;')

        const styleAttr = style.length > 0 ? ` style="${style.join(' ')}"` : ''
        const content = block.content.replace(/\n/g, '<br>')
        html += `<p${styleAttr}>${content}</p>\n\n`
      } else if (block.type === 'image') {
        // 이미지를 Base64로 변환
        let imgSrc = block.imageUrl || ''
        if (block.imageFile) {
          try {
            imgSrc = await imageToBase64(block.imageFile)
          } catch (e) {
            console.warn('이미지 변환 실패:', e)
          }
        }
        if (imgSrc) {
          html += `<p style="text-align: center; margin: 16px 0;"><img src="${imgSrc}" style="max-width: 100%; height: auto; border-radius: 8px;" /></p>\n\n`
        }
      } else if (block.type === 'quote') {
        html += `<blockquote style="border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 16px 0; background-color: #f8fafc; color: #4b5563; font-style: italic;">${block.content}</blockquote>\n\n`
      } else if (block.type === 'divider') {
        html += `<hr style="margin: 24px 0; border: none; border-top: 2px solid #e5e7eb;" />\n\n`
      }
    }

    return html
  }

  // 크롬 확장 프로그램으로 전송 (레거시 - 호환성 유지)
  const sendToExtension = async () => {
    await handleBlogPosting()
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
      {/* 헤더 - P1 Fix: 모바일 UX 개선 */}
      <div className="sticky top-0 z-50 bg-white border-b shadow-sm">
        <div className="container mx-auto px-2 sm:px-4 py-2 sm:py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              <Button variant="ghost" size="sm" onClick={() => router.push('/dashboard/saved')} className="px-2 sm:px-3">
                <ArrowLeft className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">돌아가기</span>
              </Button>
              <div className="h-6 w-px bg-gray-300 hidden sm:block" />
              {/* P1 Fix: 모바일에서도 제목 표시 (짧게) */}
              <h1 className="font-semibold text-sm sm:text-base truncate">
                <span className="sm:hidden">에디터</span>
                <span className="hidden sm:inline">블로그 에디터</span>
              </h1>
            </div>

            {/* P1 Fix: 모바일에서 버튼 간격 및 터치 영역 개선 */}
            <div className="flex items-center gap-1.5 sm:gap-2">
              <Button
                variant={previewMode ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPreviewMode(!previewMode)}
                className="px-2.5 sm:px-3 min-w-[40px] sm:min-w-0"
                title={previewMode ? '편집 모드' : '미리보기'}
              >
                <Eye className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">{previewMode ? '편집' : '미리보기'}</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={copyToClipboard}
                className="px-2.5 sm:px-3 min-w-[40px] sm:min-w-0"
                title="복사"
              >
                <Copy className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">복사</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSave}
                className="px-2.5 sm:px-3 min-w-[40px] sm:min-w-0"
                title="저장"
              >
                <Save className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">저장</span>
              </Button>
              <Button
                size="sm"
                className="bg-green-600 hover:bg-green-700 px-2.5 sm:px-3 min-w-[40px] sm:min-w-0"
                onClick={sendToExtension}
                title="블로그에 포스팅"
              >
                <Send className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">포스팅</span>
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

      <div className="container mx-auto px-2 sm:px-4 py-4 sm:py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6">
          {/* 왼쪽: 이미지 패널 (모바일에서는 에디터 다음에 표시) */}
          <div className="lg:col-span-1 space-y-4 order-2 lg:order-1">
            <Card>
              <CardHeader className="pb-2 sm:pb-3">
                <CardTitle className="text-xs sm:text-sm flex items-center gap-2">
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
                {/* P1 Fix: 모바일 패딩 정상화 */}
                <Button
                  variant="outline"
                  className="w-full py-2.5 sm:py-2"
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
              <CardHeader className="pb-2 sm:pb-3">
                <CardTitle className="text-xs sm:text-sm">블록 추가</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {/* 모바일: 가로 배열, 데스크탑: 세로 배열 */}
                <div className="flex lg:flex-col gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 lg:w-full justify-center lg:justify-start py-3 sm:py-2"
                    onClick={() => addBlock('text', selectedBlockId || undefined)}
                  >
                    <Type className="h-4 w-4 lg:mr-2" />
                    <span className="hidden lg:inline">텍스트</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 lg:w-full justify-center lg:justify-start py-3 sm:py-2"
                    onClick={() => addBlock('quote', selectedBlockId || undefined)}
                  >
                    <Quote className="h-4 w-4 lg:mr-2" />
                    <span className="hidden lg:inline">인용구</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 lg:w-full justify-center lg:justify-start py-3 sm:py-2"
                    onClick={() => addBlock('divider', selectedBlockId || undefined)}
                  >
                    <span className="lg:mr-2">—</span>
                    <span className="hidden lg:inline">구분선</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 가운데: 에디터 영역 (모바일에서 최상단) */}
          <div className="lg:col-span-2 order-1 lg:order-2">
            <Card>
              <CardContent className="p-3 sm:p-6">
                {/* 제목 */}
                <Input
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="제목을 입력하세요"
                  className="text-lg sm:text-2xl font-bold border-none shadow-none focus-visible:ring-0 px-0 mb-4 sm:mb-6"
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
                      {/* 블록 컨트롤 - 모바일에서는 상단에 표시 */}
                      {!previewMode && (
                        <>
                          {/* 데스크탑: 왼쪽에 표시 */}
                          <div className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity hidden lg:flex flex-col gap-1">
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
                          {/* 모바일: 선택 시 상단 툴바 표시 */}
                          {selectedBlockId === block.id && (
                            <div className="lg:hidden flex items-center gap-1 mb-2 p-1 bg-gray-100 rounded-lg">
                              <button
                                onClick={e => {
                                  e.stopPropagation()
                                  moveBlock(block.id, 'up')
                                }}
                                className="p-2 hover:bg-white rounded disabled:opacity-30"
                                disabled={index === 0}
                              >
                                <MoveUp className="h-4 w-4" />
                              </button>
                              <button
                                onClick={e => {
                                  e.stopPropagation()
                                  moveBlock(block.id, 'down')
                                }}
                                className="p-2 hover:bg-white rounded disabled:opacity-30"
                                disabled={index === blocks.length - 1}
                              >
                                <MoveDown className="h-4 w-4" />
                              </button>
                              <div className="flex-1" />
                              <button
                                onClick={e => {
                                  e.stopPropagation()
                                  deleteBlock(block.id)
                                }}
                                className="p-2 text-red-500 hover:bg-red-50 rounded"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          )}
                        </>
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
                            // P1 Fix: 모바일에서 더 작은 min-height (세로 공간 절약)
                            className="w-full min-h-[60px] sm:min-h-[80px] p-2 sm:p-3 bg-transparent border-none resize-none focus:outline-none text-sm sm:text-base"
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
                          <div className="border-l-4 border-blue-500 pl-3 sm:pl-4 py-2">
                            <textarea
                              value={block.content}
                              onChange={e => updateBlockContent(block.id, e.target.value)}
                              placeholder="인용구를 입력하세요..."
                              className="w-full min-h-[60px] sm:min-h-[40px] bg-transparent border-none resize-none focus:outline-none text-gray-600 italic text-sm sm:text-base"
                              disabled={previewMode}
                            />
                          </div>
                        )}

                        {block.type === 'divider' && (
                          <hr className="my-4 border-gray-300" />
                        )}
                      </div>

                      {/* 삭제 버튼 (데스크탑만) */}
                      {!previewMode && (
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            deleteBlock(block.id)
                          }}
                          className="absolute -right-8 top-1/2 -translate-y-1/2 p-1 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50 rounded hidden lg:block"
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
                      className="w-full py-6 sm:py-4 border-2 border-dashed border-gray-200 rounded-lg text-gray-400 hover:border-blue-400 hover:text-blue-500 active:bg-blue-50 transition-colors flex items-center justify-center gap-2"
                    >
                      <Plus className="h-5 w-5 sm:h-4 sm:w-4" />
                      블록 추가
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 오른쪽: 스타일 패널 (모바일에서 마지막) */}
          <div className="lg:col-span-1 order-3">
            {selectedBlock && selectedBlock.type !== 'divider' && selectedBlock.type !== 'image' && !previewMode && (
              <Card>
                <CardHeader className="pb-2 sm:pb-3">
                  <CardTitle className="text-xs sm:text-sm flex items-center gap-2">
                    <Palette className="h-4 w-4" />
                    블록 스타일
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 sm:space-y-4">
                  {/* 텍스트 스타일 */}
                  {selectedBlock.type === 'text' && (
                    <>
                      <div>
                        <Label className="text-xs">텍스트 스타일</Label>
                        <div className="flex gap-1 mt-2">
                          <Button
                            variant={selectedBlock.style?.bold ? 'default' : 'outline'}
                            size="sm"
                            className="flex-1 sm:flex-none py-3 sm:py-2"
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
                            className="flex-1 sm:flex-none py-3 sm:py-2"
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
                            className="flex-1 sm:flex-none py-3 sm:py-2"
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
                            className="flex-1 sm:flex-none py-3 sm:py-2"
                            onClick={() =>
                              updateBlockStyle(selectedBlock.id, { textAlign: 'left' })
                            }
                          >
                            <AlignLeft className="h-4 w-4" />
                          </Button>
                          <Button
                            variant={selectedBlock.style?.textAlign === 'center' ? 'default' : 'outline'}
                            size="sm"
                            className="flex-1 sm:flex-none py-3 sm:py-2"
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
                          className={`h-10 sm:h-8 rounded border-2 transition-all active:scale-95 ${
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
