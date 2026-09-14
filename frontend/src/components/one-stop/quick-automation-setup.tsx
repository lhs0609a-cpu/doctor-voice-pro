'use client'

import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { campaignAPI, type Campaign, type Client } from '@/lib/campaign-api'
import { mediaPoolAPI } from '@/lib/api'
import { errMsg } from '@/components/campaign/common'
import { naverBlogId } from './blog-step'

export function QuickAutomationSetup({ clients, onCreated, onCancel }: {
  clients: Client[]; onCreated: (campaign: Campaign) => void; onCancel?: () => void
}) {
  const [clientId, setClientId] = useState(clients[0]?.id || '')
  const [name, setName] = useState('')
  const [subjects, setSubjects] = useState('')
  const [region, setRegion] = useState('')
  const [blogId, setBlogId] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  // Keep successful intermediate records if a later upload fails, so retry does not create duplicates.
  const saved = useRef<{ client?: Client; campaign?: Campaign; blog?: string; collection?: string; uploaded?: boolean }>({})
  const hospital = clients.find(c => c.id === clientId)
  const hasBlogs = hospital?.blogs.some(b => b.status === 'active')

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (busy) return
    // 주소를 통째로 붙여 넣어도 아이디만 쓴다. 그대로 저장하면 실행기가 없는 블로그로 간다.
    const cleanBlogId = naverBlogId(blogId)
    if (!hasBlogs && !saved.current.blog && !/^[A-Za-z0-9_-]{2,50}$/.test(cleanBlogId)) {
      setError('네이버 블로그 아이디는 blog.naver.com/ 뒤의 영어·숫자 부분입니다 (예: abc123)')
      return
    }
    setBlogId(cleanBlogId)
    setBusy(true); setError('')
    try {
      let client = saved.current.client || hospital
      if (!client) {
        setMessage('병원 정보를 저장합니다')
        client = await campaignAPI.createClient({ name: name.trim(), diseases: subjects.split(',').map(s => s.trim()).filter(Boolean),
          treatments: [], regions: region.split(',').map(s => s.trim()).filter(Boolean), region_expand_level: 1,
          suffixes: [], min_volume_region: 20, min_volume_national: 100, forbidden_words: [] })
        saved.current.client = client
      }
      let blogs = client.blogs.filter(b => b.status === 'active').map(b => b.id)
      if (!blogs.length) {
        if (!saved.current.blog) {
          setMessage('블로그를 등록합니다')
          const blog = await campaignAPI.addBlog(client.id, { blog_id: cleanBlogId, daily_limit: 2,
            window_start: '09:00', window_end: '21:00', min_gap_minutes: 120, open_type: 'public' })
          saved.current.blog = blog.id
        }
        blogs = [saved.current.blog]
      }
      if (!saved.current.campaign) {
        setMessage('자동 운영 공간을 만듭니다')
        saved.current.campaign = await campaignAPI.createCampaign(client.id, `${client.name} 자동 운영`)
      }
      if (files.length && !saved.current.uploaded) {
        if (!saved.current.collection) {
          saved.current.collection = (await mediaPoolAPI.createCollection(`${client.name} 운영 사진`)).id
        }
        setMessage(`사진 ${files.length}장을 업로드합니다. 이 화면을 잠시 유지해 주세요.`)
        const uploaded = await mediaPoolAPI.upload(files, saved.current.collection)
        if (uploaded.failed || uploaded.uploaded < files.length) {
          const names = uploaded.images.map(image => image.filename)
          setFiles(files.filter(file => {
            const index = names.indexOf(file.name)
            if (index < 0) return true
            names.splice(index, 1)
            return false
          }))
          throw new Error(uploaded.message || `사진 ${uploaded.uploaded}장 저장, 일부 업로드 실패. 남은 사진을 다시 시도하세요.`)
        }
        saved.current.uploaded = true
      }
      setMessage('설정을 연결합니다')
      const campaign = await campaignAPI.patchCampaign(saved.current.campaign.id, {
        blog_ids: blogs, collection_id: saved.current.collection || client.default_collection_id || null,
      })
      onCreated(campaign)
    } catch (e) { setError(errMsg(e)) }
    finally { setBusy(false); setMessage('') }
  }

  return <Card className="mx-auto max-w-2xl p-6 sm:p-8">
    <form className="space-y-5" onSubmit={submit}>
      <div><p className="text-xs font-medium text-primary">처음 한 번만 설정</p><h2 className="mt-2 text-xl font-semibold">어떤 병원의 블로그를 운영할까요?</h2><p className="mt-2 text-sm text-muted-foreground">키워드와 원고 형식은 진료 항목에 맞춰 자동으로 준비합니다.</p></div>
      {!!clients.length && <div><Label htmlFor="setup-client">병원 선택</Label><select id="setup-client" className="mt-1 h-11 w-full rounded-lg border bg-background px-3" disabled={busy || !!saved.current.campaign || !!saved.current.client} value={clientId}
        onChange={e => { setClientId(e.target.value); saved.current = {} }}><option value="">새 병원 등록</option>{clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>}
      {!hospital && <>
        <div><Label htmlFor="setup-name">병원 이름</Label><Input id="setup-name" required maxLength={100} placeholder="예: 서울봄의원" value={name} disabled={busy || !!saved.current.client} onChange={e => setName(e.target.value)} /></div>
        <div><Label htmlFor="setup-subjects">진료 항목</Label><Input id="setup-subjects" required placeholder="예: 아토피, 습진, 여드름" value={subjects} disabled={busy || !!saved.current.client} onChange={e => setSubjects(e.target.value)} /><p className="mt-1 text-xs text-muted-foreground">쉼표로 구분하세요. 글의 주제를 찾는 기준으로 사용합니다.</p></div>
        <div><Label htmlFor="setup-region">지역</Label><Input id="setup-region" placeholder="예: 강남, 역삼" value={region} disabled={busy || !!saved.current.client} onChange={e => setRegion(e.target.value)} /></div>
      </>}
      {!hasBlogs && <div><Label htmlFor="setup-blog">네이버 블로그 아이디</Label><Input id="setup-blog" required placeholder="예: abc123 또는 블로그 주소" value={blogId} disabled={busy || !!saved.current.blog} onChange={e => setBlogId(e.target.value)} /><p className="mt-1 text-xs text-muted-foreground">blog.naver.com/ 뒤에 있는 영어 아이디입니다. 블로그 주소를 통째로 붙여 넣어도 됩니다.</p></div>}
      {hasBlogs && <p className="rounded-lg bg-primary/5 p-3 text-sm">등록된 정상 상태 블로그 {hospital?.blogs.filter(b => b.status === 'active').length}개를 연결합니다. 다음 화면에서 변경할 수 있습니다.</p>}
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}<br />저장된 단계는 유지됩니다. 다시 시도하면 이어서 진행합니다.</p>}
      {message && <p role="status" className="text-sm">{message}</p>}
      <div className="flex flex-wrap gap-3"><Button type="submit" className="h-11 flex-1" disabled={busy}>{busy ? '설정 저장 중…' : '저장하기'}</Button>{onCancel && <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>돌아가기</Button>}</div>
      <p className="text-xs text-muted-foreground">저장만 합니다. 글은 아직 쓰지 않습니다. 저장하면 아래 3번(사진)과 4번(글 쓰기)이 열립니다.</p>
    </form>
  </Card>
}
