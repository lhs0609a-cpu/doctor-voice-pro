'use client'

import { Button } from '@/components/ui/button'
import { FileDown, FileText, Sparkles, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useState } from 'react'

interface ExportButtonsProps {
  content: string
  title?: string
  keywords?: string[]
  emphasisPhrases?: string[]
  images?: Array<{ url: string; caption?: string }>  // P3: 직접 이미지 전달 옵션
  onExportSuccess?: () => void
}

// P3 Fix: 콘텐츠에서 이미지 URL 추출 함수
function extractImagesFromContent(content: string): Array<{ url: string; caption: string; position: number }> {
  const images: Array<{ url: string; caption: string; position: number }> = []

  // 마크다운 이미지 패턴: ![alt](url)
  const markdownRegex = /!\[([^\]]*)\]\(([^)]+)\)/g
  let match
  while ((match = markdownRegex.exec(content)) !== null) {
    images.push({
      caption: match[1] || '',
      url: match[2],
      position: match.index,
    })
  }

  // HTML 이미지 패턴: <img src="url" alt="caption">
  const htmlRegex = /<img[^>]+src=["']([^"']+)["'][^>]*(?:alt=["']([^"']*)["'])?[^>]*>/gi
  while ((match = htmlRegex.exec(content)) !== null) {
    // 이미 마크다운으로 추출된 URL이 아닌 경우만 추가
    const url = match[1]
    if (!images.some(img => img.url === url)) {
      images.push({
        url: url,
        caption: match[2] || '',
        position: match.index,
      })
    }
  }

  return images
}

export function ExportButtons({
  content,
  title = '',
  keywords = [],
  emphasisPhrases = [],
  images: providedImages,
  onExportSuccess,
}: ExportButtonsProps) {
  const [exporting, setExporting] = useState(false)
  const [autoExporting, setAutoExporting] = useState(false)

  const exportToDocx = async () => {
    setExporting(true)
    try {
      // P3 Fix: 콘텐츠에서 이미지 추출 또는 제공된 이미지 사용
      const extractedImages = providedImages || extractImagesFromContent(content)

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/docx`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          title,
          keywords,
          emphasis_phrases: emphasisPhrases,
          images: extractedImages,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '알 수 없는 오류' }))
        console.error('서버 에러 상세:', errorData)
        throw new Error(errorData.detail || '워드 문서 생성에 실패했습니다')
      }

      // 파일 다운로드
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title || 'blog_post'}.docx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast.success('워드 문서가 다운로드되었습니다', {
        description: '파일을 열어서 전체 선택 후 블로그에 붙여넣기 하세요',
      })

      onExportSuccess?.()
    } catch (error) {
      console.error('Export error:', error)
      toast.error('워드 문서 생성 실패', {
        description: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다',
      })
    } finally {
      setExporting(false)
    }
  }

  const exportToHtml = async () => {
    setExporting(true)
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/html`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          title,
          keywords,
          emphasis_phrases: emphasisPhrases,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '알 수 없는 오류' }))
        console.error('서버 에러 상세:', errorData)
        throw new Error(errorData.detail || 'HTML 생성에 실패했습니다')
      }

      const data = await response.json()

      // HTML을 클립보드에 복사
      await navigator.clipboard.writeText(data.html)

      toast.success('HTML이 클립보드에 복사되었습니다', {
        description: '블로그 HTML 모드에서 붙여넣기 하세요',
      })

      onExportSuccess?.()
    } catch (error) {
      console.error('Export error:', error)
      toast.error('HTML 생성 실패', {
        description: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다',
      })
    } finally {
      setExporting(false)
    }
  }

  const autoExport = async () => {
    setAutoExporting(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/export/auto-export?content=${encodeURIComponent(content)}&title=${encodeURIComponent(title)}`,
        {
          method: 'POST',
        }
      )

      if (!response.ok) {
        throw new Error('자동 내보내기에 실패했습니다')
      }

      // 파일 다운로드
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title || 'blog_post'}_auto.docx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast.success('AI 자동 스타일링 완료', {
        description: 'AI가 중요 키워드를 분석하여 강조했습니다',
      })

      onExportSuccess?.()
    } catch (error) {
      console.error('Auto export error:', error)
      toast.error('자동 내보내기 실패', {
        description: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다',
      })
    } finally {
      setAutoExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm font-semibold">블로그 복붙용 다운로드</p>
        <p className="text-xs text-muted-foreground">
          워드 문서(.docx)를 내려받아 블로그에 붙여넣으면 색상, 강조, 인용구가 그대로 유지됩니다
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {/* 워드 다운로드 (추천) */}
        <Button
          onClick={exportToDocx}
          disabled={exporting || !content}
          variant="default"
          className="w-full"
        >
          {exporting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              생성 중...
            </>
          ) : (
            <>
              <FileDown className="h-4 w-4" />
              워드 다운로드 (추천)
            </>
          )}
        </Button>

        {/* HTML 복사 */}
        <Button
          onClick={exportToHtml}
          disabled={exporting || !content}
          variant="outline"
          className="w-full"
        >
          <FileText className="h-4 w-4" />
          HTML 복사
        </Button>

        {/* AI 자동 스타일링 */}
        <Button
          onClick={autoExport}
          disabled={autoExporting || !content}
          variant="outline"
          className="w-full"
        >
          {autoExporting ? (
            <>
              <Sparkles className="h-4 w-4 animate-pulse" />
              AI 분석 중...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              AI 자동 강조
            </>
          )}
        </Button>
      </div>

      {/* 사용 가이드 */}
      <div className="space-y-2 rounded-lg border bg-muted/40 p-4">
        <p className="text-[13px] font-medium text-muted-foreground">사용 방법</p>
        <ol className="list-inside list-decimal space-y-1 text-xs text-muted-foreground">
          <li>워드 다운로드 버튼 클릭</li>
          <li>다운로드된 .docx 파일 열기</li>
          <li>전체 선택 (Ctrl+A 또는 Cmd+A)</li>
          <li>복사 (Ctrl+C 또는 Cmd+C)</li>
          <li>네이버/티스토리 블로그 에디터에 붙여넣기 (Ctrl+V)</li>
        </ol>
        <p className="text-xs text-foreground">
          모든 스타일(색상, 강조, 인용구)이 그대로 유지됩니다.
        </p>
      </div>
    </div>
  )
}
