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

/** 실행기가 남긴 사유에서 '지금 로그인된 블로그' 아이디를 뽑는다.
 *  예: "로그인된 블로그가 다릅니다(예상 'lhs0609c', 현재 'platonmarketing')." → platonmarketing */
function loggedInBlogId(reason?: string | null): string {
  const hit = /현재\s*'([A-Za-z0-9_-]{2,50})'/.exec(reason || '')
  return hit ? hit[1] : ''
}

/** 블로그 수정은 전체 값을 보낸다. 비밀번호를 비우면 서버가 기존 값을 유지한다.
 *  글 끝에 붙는 링크(홈페이지·플레이스)까지 반드시 실어야 한다 — 빼면 서버가 '지웠다'로 읽어
 *  계정이나 카테고리만 저장해도 링크가 사라진다(2026-09-28). */
export function blogBody(blog: BlogAccount, extra: Partial<BlogInput> = {}): BlogInput {
  return {
    blog_id: blog.blog_id, label: blog.label ?? null, login_id: blog.login_id ?? null, login_pw: null, proxy_url: null,
    daily_limit: blog.daily_limit, window_start: blog.window_start, window_end: blog.window_end,
    min_gap_minutes: blog.min_gap_minutes, default_category: blog.default_category ?? null, open_type: blog.open_type,
    footer_link_url: blog.footer_link_url ?? null, footer_link_label: blog.footer_link_label ?? null,
    place_url: blog.place_url ?? null, place_label: blog.place_label ?? null,
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
  const [links, setLinks] = useState<Record<string, { site: string; siteLabel: string; place: string; placeLabel: string }>>({})

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

  // 카테고리는 '앞으로 올릴 글 전부'에 대한 선택이다. 서버가 아직 안 올린 예약건의
  // 카테고리까지 같이 바꿔 준다 — 그래야 지금 걸려 있는 예약도 이 칸으로 올라간다.
  const saveCategory = (blog: BlogAccount, value: string) => run(`cat-${blog.id}`, async () => {
    await campaignAPI.updateBlog(blog.id, blogBody(blog, { default_category: value.trim() || null }))
    onChanged()
    const picked = (blog.categories || []).find(c => c.id === value.trim())
    return value.trim()
      ? `'${picked?.name || value.trim()}' 카테고리로 올립니다. 걸려 있는 예약도 함께 바꿨습니다.`
      : '네이버 기본 카테고리로 올립니다.'
  })

  // 이 블로그로 올리는 **모든 글** 끝에 들어가는 링크. 한 번 넣으면 100건을 예약해도 전부 들어간다.
  // 네이버는 주소가 한 줄로 있으면 알아서 카드(플레이스면 지도 카드)로 만들어 준다.
  const saveLinks = (blog: BlogAccount) => run(`links-${blog.id}`, async () => {
    const value = links[blog.id] || { site: '', siteLabel: '', place: '', placeLabel: '' }
    const body = blogBody(blog, {
      footer_link_url: value.site.trim() || null,
      footer_link_label: value.siteLabel.trim() || null,
      place_url: value.place.trim() || null,
      place_label: value.placeLabel.trim() || null,
    })
    await campaignAPI.updateBlog(blog.id, body)
    onChanged()
    const kept = [body.place_url && '플레이스 지도', body.footer_link_url && '홈페이지·예약 링크'].filter(Boolean).join(' · ')
    return kept ? `${kept}를 이 블로그의 모든 글 끝에 넣습니다.` : '글 끝 링크를 지웠습니다.'
  })

  // 카테고리는 네이버 글쓰기 화면 안에만 있다. 블로그에서 새로 만들었으면 사람이 눌러
  // 바로 가져올 수 있어야 한다 — 일주일마다 자동으로 다시 읽는 것만으로는 늦다.
  const rescanCategories = (blog: BlogAccount) => run(`catscan-${blog.id}`, async () => {
    await campaignAPI.rescanCategories(blog.id)
    onChanged()
    return '실행기가 다음 차례에 이 블로그의 카테고리를 읽어 옵니다(보통 1~2분). 다 읽으면 아래 목록에 뜹니다.'
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

    {troubled.length > 0 && <div className="space-y-2 rounded-lg bg-warning-soft p-3 text-sm">
      <div className="flex items-start gap-2">
        <span aria-hidden className="shrink-0 font-bold text-warning motion-safe:animate-bounce">▶</span>
        <p>실행기가 띄운 <b>크롬 창</b>에서 네이버에 로그인하세요(<b>로그인 상태 유지</b> 체크). 보통 1분 안에 &lsquo;정상&rsquo;으로 바뀝니다.</p>
      </div>

      {/* 실행기가 남긴 진짜 사유. 감추면 '로그인했는데 왜 안 풀리지'가 된다 —
          아이디가 어긋난 경우가 특히 그렇다(로그인 문제가 아니다). */}
      {troubled.filter(b => b.status_reason).map(b => {
        const now = loggedInBlogId(b.status_reason)
        return <div key={`why-${b.id}`} className="space-y-2 rounded-lg bg-card p-2 text-xs">
          <p className="text-muted-foreground">{b.status_reason}</p>
          {!!now && now !== b.blog_id && <Button size="sm" variant="outline" disabled={busy === `swap-${b.id}`}
            onClick={() => run(`swap-${b.id}`, async () => {
              await campaignAPI.updateBlog(b.id, blogBody(b, { blog_id: now }))
              await campaignAPI.setBlogStatus(b.id, 'active', '사용자가 로그인된 블로그로 바꿨습니다')
              onChanged()
              return `이 블로그를 ${now} 로 바꿨습니다. 예약한 글이 그리로 올라갑니다.`
            })}>
            {busy === `swap-${b.id}` ? '바꾸는 중…' : `지금 로그인된 ${now} 로 바꾸기`}
          </Button>}
        </div>
      })}
      {/* 실행기가 다시 확인할 때까지 기다리지 않아도 되게 — 이미 로그인한 사람이 직접 푼다.
          잘못 눌러도 다음 발행 때 실행기가 다시 판정하므로 되돌릴 수 없는 일이 아니다. */}
      <div className="flex flex-wrap items-center gap-2">
        {troubled.map(b => (
          <Button key={b.id} size="sm" variant="outline" disabled={busy === `ok-${b.id}`}
            onClick={() => run(`ok-${b.id}`, async () => {
              await campaignAPI.setBlogStatus(b.id, 'active', '사용자가 네이버 로그인을 확인')
              onChanged()
              return `${b.label || b.blog_id}: 정상으로 바꿨습니다. 이제 예약한 글이 올라갑니다.`
            })}>
            {busy === `ok-${b.id}` ? '바꾸는 중…' : `${b.label || b.blog_id} — 로그인했어요`}
          </Button>
        ))}
      </div>
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

    {/* ③ 올릴 카테고리 */}
    {linked.length > 0 && <div className="space-y-2">
      <p className="text-sm font-medium">③ 올릴 카테고리 <span className="font-normal text-muted-foreground">(선택 — 안 고르면 네이버 기본 카테고리)</span></p>
      {linked.map(b => {
        const list = b.categories || []
        const current = b.default_category ?? ''
        const chosen = list.find(c => c.id === current)
        return <div key={b.id} className="space-y-1.5 rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{b.label || b.blog_id}</span>
            {current
              ? <Pill tone="ok">{chosen?.name || `번호 ${current}`}</Pill>
              : <Pill tone="muted">네이버 기본 카테고리</Pill>}
            {b.categories_pending && (b.status === 'active'
              ? <Pill tone="warn">읽어 오는 중</Pill>
              : <Pill tone="warn">로그인 확인 먼저</Pill>)}
            <Button size="sm" variant="outline" className="ml-auto h-7" disabled={!!busy}
              onClick={() => rescanCategories(b)}>
              {busy === `catscan-${b.id}` ? '요청 중…' : list.length ? '카테고리 새로 읽기' : '카테고리 가져오기'}
            </Button>
          </div>
          {list.length > 0
            ? <select className="h-9 w-full rounded-md border bg-background px-2 text-sm" value={current} disabled={!!busy}
                aria-label={`${b.label || b.blog_id} 카테고리`}
                onChange={e => saveCategory(b, e.target.value)}>
                <option value="">네이버 기본 카테고리</option>
                {list.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            : <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">
                  카테고리는 네이버 글쓰기 화면 안에만 있습니다. 실행기를 켜 둔 채 위의 <b>[카테고리 가져오기]</b>를 누르면
                  1~2분 안에 목록이 여기에 뜹니다. 그 전에는 번호를 직접 넣어도 됩니다.
                  {b.status !== 'active' && <> 이 블로그는 <b>로그인 확인이 먼저</b>입니다 — 로그인이 풀려 있으면 목록을 읽어 올 수 없습니다.</>}
                </p>
                <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                  <Input placeholder="카테고리 번호 (예: 24)" defaultValue={current} disabled={!!busy}
                    onKeyDown={e => { if (e.key === 'Enter') saveCategory(b, (e.target as HTMLInputElement).value) }}
                    onBlur={e => { if (e.target.value.trim() !== current) saveCategory(b, e.target.value) }} />
                  <Button size="sm" className="h-9" disabled={!!busy} onClick={() => saveCategory(b, current)}>
                    {busy === `cat-${b.id}` ? '저장 중…' : '저장'}
                  </Button>
                </div>
              </div>}
        </div>
      })}
    </div>}

    {/* ④ 글 끝에 늘 들어갈 링크 */}
    {linked.length > 0 && <div className="space-y-2">
      <p className="text-sm font-medium">④ 글 끝에 늘 들어갈 링크 <span className="font-normal text-muted-foreground">(플레이스 지도 · 홈페이지)</span></p>
      <p className="text-xs leading-relaxed text-muted-foreground">
        한 번 넣어 두면 이 블로그로 올리는 <b>모든 글</b>(대량 예약 100건도) 끝에 들어갑니다.
        네이버가 주소 한 줄을 알아서 카드로 만들어 줍니다 — 플레이스 주소는 지도 카드가 됩니다.
        원고 본문에 이미 그 주소가 있으면 두 번 넣지 않습니다.
      </p>
      {linked.map(b => {
        const value = links[b.id] || {
          site: b.footer_link_url ?? '', siteLabel: b.footer_link_label ?? '',
          place: b.place_url ?? '', placeLabel: b.place_label ?? '',
        }
        const set = (patch: Partial<typeof value>) => setLinks(l => ({ ...l, [b.id]: { ...value, ...patch } }))
        return <div key={b.id} className="space-y-1.5 rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{b.label || b.blog_id}</span>
            {b.place_url ? <Pill tone="ok">지도 카드</Pill> : <Pill tone="muted">지도 없음</Pill>}
            {b.footer_link_url ? <Pill tone="ok">링크 카드</Pill> : <Pill tone="muted">링크 없음</Pill>}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input placeholder="플레이스 지도 주소 (naver.me/… 또는 map.naver.com/…)" value={value.place} disabled={!!busy}
              autoComplete="off" onChange={e => set({ place: e.target.value })} />
            <Input placeholder="지도 앞에 붙일 한 줄 (예: 오시는 길)" value={value.placeLabel} disabled={!!busy}
              autoComplete="off" onChange={e => set({ placeLabel: e.target.value })} />
            <Input placeholder="홈페이지·예약 주소 (https://…)" value={value.site} disabled={!!busy}
              autoComplete="off" onChange={e => set({ site: e.target.value })} />
            <Input placeholder="링크 앞에 붙일 한 줄 (예: 예약은 여기서)" value={value.siteLabel} disabled={!!busy}
              autoComplete="off" onChange={e => set({ siteLabel: e.target.value })} />
          </div>
          <Button size="sm" className="h-9" disabled={!!busy} onClick={() => saveLinks(b)}>
            {busy === `links-${b.id}` ? '저장 중…' : '저장'}
          </Button>
        </div>
      })}
    </div>}

    {/* ⑤ 블로그별 고정 IP */}
    {linked.length > 0 && <div className="space-y-2">
      <p className="text-sm font-medium">⑤ 블로그별 고정 IP <span className="font-normal text-muted-foreground">(선택 — 여러 병원을 한 PC에서 운영할 때)</span></p>
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
      <p className="text-sm font-medium">⑥ 블로그 추가 <span className="font-normal text-muted-foreground">(주소를 붙여 넣어도 됩니다)</span></p>
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
