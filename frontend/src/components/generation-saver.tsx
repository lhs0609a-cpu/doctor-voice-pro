'use client'

import { useEffect } from 'react'
import { toast } from 'sonner'
import { onGenResult, splitTitleBody, appendSavedPosts } from '@/lib/keyword-batch'

/**
 * 키워드 대량 생성 결과를 '저장된 글'에 저장하는 전역 리스너.
 *
 * 대시보드 레이아웃에 상시 마운트되어, 사용자가 어느 페이지에 있든
 * (생성 중 실시간으로 보려고 '저장된 글'로 넘어가도) 결과가 유실되지 않는다.
 * 예전에는 이 로직이 키워드 생성 페이지 안에만 있어, 페이지를 벗어나면
 * 리스너가 사라져 이후 글이 통째로 저장되지 않았다.
 */
export function GenerationSaver() {
  useEffect(() => {
    let notifiedFull = false
    const off = onGenResult((r) => {
      if (r.done || r.fatal || !r.ok || !r.text) return
      try {
        const { title, content } = splitTitleBody(r.text)
        appendSavedPosts([{ keyword: r.keyword, title, content }])
      } catch (e) {
        // 저장 공간 부족 등은 한 번만 알린다(매 건 토스트가 쏟아지지 않게).
        if (!notifiedFull) {
          notifiedFull = true
          toast.error(e instanceof Error ? e.message : '저장 공간이 부족합니다')
        }
      }
    })
    return off
  }, [])

  return null
}
