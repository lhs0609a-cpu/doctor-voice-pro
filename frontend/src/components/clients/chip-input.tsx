'use client'

import { useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface ChipInputProps {
  value: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}

/** 입력 후 Enter 또는 쉼표로 항목을 추가하고, x 로 제거하는 칩 입력. */
export function ChipInput({ value, onChange, placeholder, className, disabled }: ChipInputProps) {
  const [text, setText] = useState('')

  const commit = () => {
    const items = text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .filter((s) => !value.includes(s))
    if (items.length) onChange([...value, ...items])
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      commit()
    } else if (e.key === 'Backspace' && !text && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div className={cn('rounded-lg border border-input bg-card px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring', className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        {value.map((item) => (
          <span key={item} className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground">
            {item}
            {!disabled && (
              <button
                type="button"
                className="rounded-full text-muted-foreground hover:text-foreground"
                onClick={() => onChange(value.filter((v) => v !== item))}
                aria-label={`${item} 제거`}
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))}
        <Input
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={commit}
          placeholder={value.length ? '' : placeholder}
          className="h-7 min-w-[120px] flex-1 border-0 px-1 shadow-none focus-visible:ring-0"
        />
      </div>
    </div>
  )
}
