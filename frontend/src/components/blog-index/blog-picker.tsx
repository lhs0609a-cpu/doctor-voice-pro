'use client'

/**
 * "내 블로그" 입력. ID 또는 URL 을 직접 적거나, 등록된 블로그 계정 중에서 고른다.
 * 마지막 값은 localStorage(doctorvoice-my-blog-id)에 기억한다.
 */
import { useEffect, useMemo, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { campaignAPI, type Client } from '@/lib/campaign-api'
import { cn } from '@/lib/utils'

export const MY_BLOG_STORAGE_KEY = 'doctorvoice-my-blog-id'

/** URL(blog.naver.com/xxx, m.blog.naver.com/xxx/123, ?blogId=xxx) 또는 생 ID → 블로그 ID */
export function normalizeBlogId(raw: string): string {
  const s = (raw || '').trim()
  if (!s) return ''
  const m = s.match(/blog\.naver\.com\/(?:PostList\.naver\?blogId=)?([A-Za-z0-9_-]+)/i)
  if (m) return m[1]
  const q = s.match(/[?&]blogId=([A-Za-z0-9_-]+)/i)
  if (q) return q[1]
  return s.replace(/^@/, '').split(/[/?#\s]/)[0]
}

export function readRememberedBlogId(): string {
  try { return localStorage.getItem(MY_BLOG_STORAGE_KEY) || '' } catch { return '' }
}

export function rememberBlogId(id: string) {
  try { if (id) localStorage.setItem(MY_BLOG_STORAGE_KEY, id) } catch { /* noop */ }
}

export interface BlogOption {
  blog_id: string
  label: string        // "병원명 · 별칭 (blog_id)"
  client_id: string
  client_name: string
  alias?: string | null
}

/** 모든 병원의 블로그 계정을 선택지로 편다. preferClientId 의 것을 앞에 둔다. */
export function clientsToBlogOptions(clients: Client[], preferClientId?: string): BlogOption[] {
  const out: BlogOption[] = []
  const seen = new Set<string>()
  const ordered = [...clients].sort((a, b) => (a.id === preferClientId ? -1 : b.id === preferClientId ? 1 : 0))
  for (const c of ordered) {
    for (const b of c.blogs || []) {
      if (!b.blog_id || seen.has(b.blog_id)) continue
      seen.add(b.blog_id)
      const name = c.short_name || c.name
      out.push({
        blog_id: b.blog_id,
        alias: b.label,
        client_id: c.id,
        client_name: name,
        label: `${name}${b.label ? ` · ${b.label}` : ''} (${b.blog_id})`,
      })
    }
  }
  return out
}

interface Props {
  value: string
  onChange: (blogId: string) => void
  /** 이 병원의 블로그를 드롭다운 맨 앞에 둔다 */
  preferClientId?: string
  /** 값이 비어 있으면 기억해 둔 마지막 블로그를 자동으로 채운다(기본 true) */
  autoRestore?: boolean
  disabled?: boolean
  className?: string
}

export function BlogPicker({ value, onChange, preferClientId, autoRestore = true, disabled, className }: Props) {
  const [text, setText] = useState(value)
  const [options, setOptions] = useState<BlogOption[]>([])
  const [loadingOpts, setLoadingOpts] = useState(true)

  // 바깥에서 값이 바뀌면 입력칸도 맞춘다
  useEffect(() => { setText(value) }, [value])

  // 등록 블로그 목록
  useEffect(() => {
    let alive = true
    campaignAPI.listClients()
      .then((cs) => { if (alive) setOptions(clientsToBlogOptions(cs, preferClientId)) })
      .catch(() => { /* 목록이 없어도 직접 입력은 된다 */ })
      .finally(() => { if (alive) setLoadingOpts(false) })
    return () => { alive = false }
  }, [preferClientId])

  // 마지막 값 복원
  useEffect(() => {
    if (!autoRestore || value) return
    const remembered = readRememberedBlogId()
    if (remembered) onChange(remembered)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 값이 정해지면 기억
  useEffect(() => { if (value) rememberBlogId(value) }, [value])

  const commit = (raw: string) => {
    const id = normalizeBlogId(raw)
    setText(id)
    if (id !== value) onChange(id)
  }

  const matched = useMemo(() => options.find((o) => o.blog_id === value), [options, value])

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={text}
          disabled={disabled}
          placeholder="블로그 ID 또는 주소 (예: blog.naver.com/myhospital)"
          onChange={(e) => {
            setText(e.target.value)
            const id = normalizeBlogId(e.target.value)
            if (id !== value) onChange(id)
          }}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit((e.target as HTMLInputElement).value) } }}
          className="sm:flex-1"
          autoComplete="off"
          spellCheck={false}
        />
        <Select
          value={matched ? matched.blog_id : ''}
          onValueChange={(v) => { setText(v); onChange(v) }}
          disabled={disabled || options.length === 0}
        >
          <SelectTrigger className="sm:w-72">
            <SelectValue placeholder={loadingOpts ? '등록 블로그 불러오는 중…' : options.length ? '등록된 블로그에서 고르기' : '등록된 블로그 없음'} />
          </SelectTrigger>
          <SelectContent>
            {options.map((o) => (
              <SelectItem key={o.blog_id} value={o.blog_id}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {value && (
        <p className="text-xs text-muted-foreground">
          {matched ? <>{matched.client_name}{matched.alias ? ` · ${matched.alias}` : ''} · </> : null}
          <span className="font-mono">{value}</span>
        </p>
      )}
    </div>
  )
}
