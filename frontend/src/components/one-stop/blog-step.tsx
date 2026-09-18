'use client'

// 2단계 블로그 — 이 자리에서 고르고, 추가하고, (원하면) 네이버 계정을 넣는다. 다른 화면으로 보내지 않는다.
// 네이버 계정을 넣어 두면 실행기가 알아서 로그인하고, 안 넣으면 처음 올릴 때 실행기가 띄운 크롬 창에서 한 번 로그인한다.

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pill } from '@/components/app-shell/ui-kit'
import { campaignAPI, type BlogAccount, type BlogInput, type Campaign, type Client } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'

const STATUS: Record<string, { label: string; tone: 'ok' | 'warn' | 'muted' }> = {
  active: { label: '정상', tone: 'ok' },
  captcha: { label: '보안문자 필요', tone: 'warn' },
  login_required: { label: '로그인 필요', tone: 'warn' },
}

/** 블로그 수정은 전체 값을 보낸다. 비밀번호를 비우면 서버가 기존 값을 유지한다. */
function blogBody(blog: BlogAccount, extra: Partial<BlogInput> = {}): BlogInput {
  return {
    blog_id: blog.blog_id, label: blog.label ?? null, login_id: blog.login_id ?? null, login_pw: null, proxy_url: null,
    daily_limit: blog.daily_limit, window_start: blog.window_start, window_end: blog.window_end,
    min_gap_minutes: blog.min_gap_minutes, default_category: blog.default_category ?? null, open_type: blog.open_type,
    ...extra,
  }
}

/** 주소를 통째로 붙여 넣어도 아이디만 뽑는다. blog.naver.com/abc123?x=1 → abc123 */
export function naverBlogId(raw: string): string {
  return raw.trim()
    .replace(/^https?:\/\//i, '')
    .replace(/^(m\.)?blog\.naver\.com\//i, '')
    .split(/[/?#]/)[0]
}

export function BlogStep({ campaign, client, setCampaign, onChanged }: {
  campaign: Campaign
  client: Client
  setCampaign: (campaign: Campaign) => void
  onChanged: () => void
}) {
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [newBlog, setNewBlog] = useState('')
  const [creds, setCreds] = useState<Record<string, { id: string; pw: string }>>({})
  const [proxies, setProxies] = useState<Record<string, string>>({})

  const linked = client.blogs.filter(b => campaign.blog_ids.includes(b.id))
  const troubled = linked.filter(b => ['captcha', 'login_required'].includes(b.status))

  const run = async (key: string, work: () => Promise<string>) => {
    setBusy(key); setError(''); setMessage('')
    try { setMessage(await work()) } catch (e) { setError(errMsg(e)) } finally { setBusy('') }
  }

  const toggle = (blog: BlogAccount) => run(`toggle-${blog.id}`, async () => {
    const on = campaign.blog_ids.includes(blog.id)
    const next = on ? campaign.blog_ids.filter(id => id !== blog.id) : [...campaign.blog_ids, blog.id]
    setCampaign(await campaignAPI.patchCampaign(campaign.id, { blog_ids: next }))
    return on ? `${blog.label || blog.blog_id} 블로그를 뺐습니다` : `${blog.label || blog.blog_id} 블로그에 올립니다`
  })

  const saveCreds = (blog: BlogAccount) => run(`creds-${blog.id}`, async () => {
    const value = creds[blog.id] || { id: '', pw: '' }
    if (!value.id.trim() && !value.pw) throw new Error('네이버 아이디나 비밀번호를 넣어 주세요')
    await campaignAPI.updateBlog(blog.id, blogBody(blog, { login_id: value.id.trim() || blog.login_id || null, login_pw: value.pw || null }))
    setCreds(c => ({ ...c, [blog.id]: { id: '', pw: '' } }))
    onChanged()
    return '저장했습니다. 실행기가 이 계정으로 알아서 로그인합니다'
  })

  const saveProxy = (blog: BlogAccount) => run(`proxy-${blog.id}`, async () => {
    const value = (proxies[blog.id] || '').trim()
    if (!value) throw new Error('프록시 주소를 넣어 주세요 (지우려면 - 한 글자)')
    await campaignAPI.updateBlog(blog.id, blogBody(blog, { proxy_url: value }))
    setProxies(p => ({ ...p, [blog.id]: '' }))
    onChanged()
    return value === '-' ? '프록시를 지웠습니다. 이 블로그는 PC 회선으로 나갑니다'
      : '저장했습니다. 실행기를 다시 켜면 이 블로그만 이 IP로 나갑니다'
  })

  const add = () => run('add', async () => {
    const id = naverBlogId(newBlog)
    if (!/^[A-Za-z0-9_-]+$/.test(id)) throw new Error('블로그 아이디는 영어·숫자로 된 부분만 넣어 주세요 (예: abc123)')
    const blog = await campaignAPI.addBlog(client.id, {
      blog_id: id, daily_limit: 2, window_start: '09:00', window_end: '21:00', min_gap_minutes: 120, open_type: 'public',
    })
    setCampaign(await campaignAPI.patchCampaign(campaign.id, { blog_ids: [...campaign.blog_ids, blog.id] }))
    setNewBlog('')
    onChanged()
    return `${id} 블로그를 추가했습니다`
  })

  return <div className="space-y-5">
    {/* ① 올릴 블로그 */}
    <div className="space-y-2">
      <p className="text-sm font-medium">① 올릴 블로그에 체크</p>
      {client.blogs.length === 0
        ? <p className="text-sm text-muted-foreground">아래 ③에서 블로그를 추가하세요.</p>
        : <ul className="space-y-1.5">{client.blogs.map(b => {
          const status = STATUS[b.status] || { label: b.status, tone: 'muted' as const }
          return <li key={b.id}>
            <label className="flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm hover:bg-muted/40">
              <input type="checkbox" className="h-4 w-4" checked={campaign.blog_ids.includes(b.id)} disabled={!!busy} onChange={() => toggle(b)} />
              <span className="min-w-0 flex-1 truncate">{b.label || b.blog_id}{b.label && <span className="text-muted-foreground"> ({b.blog_id})</span>}</span>
              <Pill tone={status.tone}>{status.label}</Pill>
            </label>
          </li>
        })}</ul>}
    </div>

    {troubled.length > 0 && <div className="flex items-start gap-2 rounded-lg bg-warning-soft p-3 text-sm">
      <span aria-hidden className="shrink-0 font-bold text-warning motion-safe:animate-bounce">▶</span>
      <p>실행기가 띄운 <b>크롬 창</b>에서 네이버에 로그인하세요(<b>로그인 상태 유지</b> 체크). 1분 안에 &lsquo;정상&rsquo;으로 바뀝니다.</p>
    </div>}

    {/* ② 네이버 계정 */}
    {linked.length > 0 && <div className="space-y-2">
      <p className="text-sm font-medium">② 네이버 아이디·비밀번호 <span className="font-normal text-muted-foreground">(선택 — 넣어 두면 자동 로그인)</span></p>
      {linked.map(b => {
        const value = creds[b.id] || { id: '', pw: '' }
        return <div key={b.id} className="space-y-1.5 rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{b.label || b.blog_id}</span>
            {b.has_password ? <Pill tone="ok">자동 로그인 준비됨{b.login_id ? ` · ${b.login_id}` : ''}</Pill> : <Pill tone="muted">계정 안 넣음</Pill>}
          </div>
          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <Input placeholder={b.login_id ? `네이버 아이디 (지금: ${b.login_id})` : '네이버 아이디'} value={value.id} disabled={!!busy}
              autoComplete="off" onChange={e => setCreds(c => ({ ...c, [b.id]: { ...value, id: e.target.value } }))} />
            <Input type="password" placeholder={b.has_password ? '비밀번호 (바꿀 때만 입력)' : '네이버 비밀번호'} value={value.pw} disabled={!!busy}
              autoComplete="new-password" onChange={e => setCreds(c => ({ ...c, [b.id]: { ...value, pw: e.target.value } }))} />
            <Button size="sm" className="h-9" disabled={!!busy || (!value.id.trim() && !value.pw)} onClick={() => saveCreds(b)}>
              {busy === `creds-${b.id}` ? '저장 중…' : '저장'}
            </Button>
          </div>
        </div>
      })}
    </div>}

    {/* ③ 블로그별 고정 IP */}
    {linked.length > 0 && <div className="space-y-2">
      <p className="text-sm font-medium">③ 블로그별 고정 IP <span className="font-normal text-muted-foreground">(선택 — 여러 병원을 한 PC에서 운영할 때)</span></p>
      <p className="text-xs leading-relaxed text-muted-foreground">
        블로그마다 <b>고정된</b> 주소를 넣으세요. 계속 바꾸면 같은 계정이 여기저기서 접속하는 꼴이라
        로그인이 자꾸 풀립니다. 예) <code>123.45.67.89:8080</code> 또는 <code>http://아이디:비밀번호@123.45.67.89:8080</code>
      </p>
      {linked.map(b => {
        const value = proxies[b.id] ?? ''
        return <div key={b.id} className="space-y-1.5 rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{b.label || b.blog_id}</span>
            {b.proxy_label ? <Pill tone="ok">{b.proxy_label}</Pill> : <Pill tone="muted">PC 회선 그대로</Pill>}
          </div>
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <Input placeholder={b.proxy_label ? '바꿀 때만 입력 (지우려면 -)' : '123.45.67.89:8080'} value={value} disabled={!!busy}
              autoComplete="off" onChange={e => setProxies(p => ({ ...p, [b.id]: e.target.value }))} />
            <Button size="sm" className="h-9" disabled={!!busy || !value.trim()} onClick={() => saveProxy(b)}>
              {busy === `proxy-${b.id}` ? '저장 중…' : '저장'}
            </Button>
          </div>
        </div>
      })}
    </div>}

    {/* ④ 블로그 추가 */}
    <div className="space-y-2">
      <p className="text-sm font-medium">④ 블로그 추가 <span className="font-normal text-muted-foreground">(주소를 붙여 넣어도 됩니다)</span></p>
      <div className="flex gap-2">
        <Input placeholder="abc123 또는 블로그 주소" value={newBlog} disabled={!!busy} onChange={e => setNewBlog(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && newBlog.trim()) void add() }} />
        <Button disabled={!!busy || !newBlog.trim()} onClick={add}>{busy === 'add' ? '추가 중…' : '추가'}</Button>
      </div>
    </div>

    {message && <p role="status" className="text-sm text-success">{message}</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </div>
}
