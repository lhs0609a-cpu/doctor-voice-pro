"use client"

import * as React from "react"
import * as SliderPrimitive from "@radix-ui/react-slider"

import { cn } from "@/lib/utils"

/**
 * P1 Fix: 모바일 터치 UX 개선
 * - 터치 타겟 크기 증가 (모바일: 44px, 데스크톱: 20px)
 * - 트랙 높이 증가 (모바일: 8px, 데스크톱: 8px)
 * - 터치 영역 확대를 위한 pseudo-element 추가
 */
const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex w-full touch-none select-none items-center py-2",
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-2 sm:h-2 w-full grow overflow-hidden rounded-full bg-secondary">
      <SliderPrimitive.Range className="absolute h-full bg-primary" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      className={cn(
        "block rounded-full border-2 border-primary bg-background ring-offset-background transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        // P1 Fix: 모바일에서 더 큰 터치 타겟 (44x44px 권장 가이드라인)
        "h-7 w-7 sm:h-5 sm:w-5",
        // 터치 영역 확대
        "before:absolute before:inset-[-8px] before:content-['']"
      )}
    />
  </SliderPrimitive.Root>
))
Slider.displayName = SliderPrimitive.Root.displayName

export { Slider }
