'use client'

import { useState } from 'react'
import { BarChart3, Loader2, Pencil, Plus, Trash2, Pause, Play } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Pill, EmptyState } from '@/components/app-shell/ui-kit'
import { campaignAPI, BLOG_STATUS_LABEL, type BlogAccount, type BlogInput } from '@/lib/campaign-api'
import { analyzeAndWait, indexTone } from '@/components/blog-index/blog-index-card'
import { errorMessage } from '@/components/clients/utils'

interface BlogAccountsProps {
  clientId: string
  blogs: BlogAccount[]
  onChanged: () => Promise<void> | void
}

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const STATUS_TONE: Record<string, Tone> = {
  active: 'ok',
  paused: 'muted',
  captcha: 'warn',
  login_required: 'warn',
  disabled: 'danger',
}

const OPEN_TYPE_LABEL: Record<string, string> = {
  public: '전체 공개',
  neighbor: '이웃 공개',
  private: '비공개',
}

const EMPTY_BLOG: BlogInput = {
  blog_id: '',
  label: '',
  login_id: '',
  login_pw: '',
  daily_limit: 2,
  window_start: '09:00',
  window_end: '21:00',
  min_gap_minutes: 120,
  default_category: '',
  open_type: 'public',
}

function toInput(b: BlogAccount): BlogInput {
  return {
    blog_id: b.blog_id,
    label: b.label ?? '',
    login_id: b.login_id ?? '',
    login_pw: '',
    daily_limit: b.daily_limit,
    window_start: b.window_start,
    window_end: b.window_end,
    min_gap_minutes: b.min_gap_minutes,
    default_category: b.default_category ?? '',
    open_type: b.open_type,
  }
}

const TH = 'py-2.5 pr-4 text-left text-[12px] font-medium uppercase tracking-wide text-muted-foreground'
const TD = 'py-2.5 pr-4 align-middle'

export function BlogAccounts({ clientId, blogs, onChanged }: BlogAccountsProps) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<BlogAccount | null>(null)
  const [form, setForm] = useState<BlogInput>(EMPTY_BLOG)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [indexingId, setIndexingId] = useState<string | null>(null)

  const set = <K extends keyof BlogInput>(key: K, value: BlogInput[K]) => setForm((f) => ({ ...f, [key]: value }))

  const openAdd = () => { setEditing(null); setForm(EMPTY_BLOG); setOpen(true) }
  const openEdit = (b: BlogAccount) => { setEditing(b); setForm(toInput(b)); setOpen(true) }

  const save = async () => {
    if (!form.blog_id.trim()) { toast.error('블로그 ID를 입력하세요'); return }
    if (form.daily_limit < 1) { toast.error('하루 한도는 1 이상이어야 합니다'); return }
    setSaving(true)
    try {
      const body: BlogInput = {
        ...form,
        blog_id: form.blog_id.trim(),
        label: form.label?.trim() || null,
        login_id: form.login_id?.trim() || null,
        // 비워두면 기존 비밀번호 유지
        login_pw: form.login_pw ? form.login_pw : null,
        default_category: form.default_category?.trim() || null,
      }
      if (editing) {
        await campaignAPI.updateBlog(editing.id, body)
        toast.success('블로그 계정을 수정했습니다')
      } else {
        await campaignAPI.addBlog(clientId, body)
        toast.success('블로그 계정을 추가했습니다')
      }
      setOpen(false)
      await onChanged()
    } catch (e) {
      toast.error(editing ? '수정 실패' : '추가 실패', { description: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async (b: BlogAccount, status: 'active' | 'paused') => {
    setBusyId(b.id)
    try {
      await campaignAPI.setBlogStatus(b.id, status, status === 'paused' ? '사용자가 일시정지' : undefined)
      toast.success(status === 'active' ? '정상 상태로 바꿨습니다' : '일시정지했습니다')
      await onChanged()
    } catch (e) {
      toast.error('상태 변경 실패', { description: errorMessage(e) })
    } finally {
      setBusyId(null)
    }
  }

  const analyzeIndex = async (b: BlogAccount) => {
    setIndexingId(b.id)
    try {
      const r = await analyzeAndWait(b.blog_id, false)
      if (!r.success) throw new Error(r.error_message || r.error_code || '블로그를 읽을 수 없습니다')
      const score = r.index?.total_score
      toast.success(score == null ? '지수를 분석했지만 점수는 측정 불가입니다' : `지수 ${score.toLocaleString('ko-KR', { maximumFractionDigits: 1 })} · ${r.index?.grade || ''}`)
      await onChanged()
    } catch (e) {
      toast.error('지수 분석 실패', { description: errorMessage(e) })
    } finally {
      setIndexingId(null)
    }
  }

  const remove = async (b: BlogAccount) => {
    if (!confirm(`'${b.label || b.blog_id}' 계정을 삭제할까요? 예약된 발행이 있으면 함께 취소될 수 있습니다.`)) return
    setBusyId(b.id)
    try {
      await campaignAPI.deleteBlog(b.id)
      toast.success('블로그 계정을 삭제했습니다')
      await onChanged()
    } catch (e) {
      toast.error('삭제 실패', { description: errorMessage(e) })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>블로그 계정</CardTitle>
            <CardDescription>이 병원 원고를 발행할 네이버 블로그입니다. 하루 한도와 시간대에 맞춰 자동 분배됩니다.</CardDescription>
          </div>
          <Button size="sm" variant="outline" onClick={openAdd}>
            <Plus /> 계정 추가
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {blogs.length === 0 ? (
          <EmptyState
            title="아직 블로그 계정이 없습니다"
            description="계정을 추가해야 예약 발행이 가능합니다."
            action={<Button size="sm" variant="outline" onClick={openAdd}><Plus /> 계정 추가</Button>}
            className="py-8"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className={TH}>별칭</th>
                  <th className={TH}>블로그 ID</th>
                  <th className={TH}>로그인 ID</th>
                  <th className={`${TH} text-right`}>하루 한도</th>
                  <th className={TH}>시간대</th>
                  <th className={TH}>상태</th>
                  <th className={TH}>지수</th>
                  <th className={`${TH} pr-0 text-right`}>관리</th>
                </tr>
              </thead>
              <tbody>
                {blogs.map((b) => (
                  <tr key={b.id} className="border-b last:border-0 hover:bg-muted/40">
                    <td className={`${TD} font-medium`}>{b.label || '-'}</td>
                    <td className={`${TD} font-mono text-xs`}>{b.blog_id}</td>
                    <td className={`${TD} text-xs`}>
                      {b.login_id || '-'}
                      {b.has_password && <span className="ml-1 text-[10px] text-muted-foreground">(비밀번호 저장됨)</span>}
                    </td>
                    <td className={`${TD} text-right tabular-nums`}>{b.daily_limit}개</td>
                    <td className={`${TD} text-xs tabular-nums`}>{b.window_start}–{b.window_end} · {b.min_gap_minutes}분 간격</td>
                    <td className={TD}>
                      <Pill tone={STATUS_TONE[b.status] || 'muted'} className="cursor-default" >
                        <span title={b.status_reason || undefined}>{BLOG_STATUS_LABEL[b.status] || b.status}</span>
                      </Pill>
                    </td>
                    <td className={TD}>
                      <div className="flex items-center gap-1.5">
                        {b.index_score != null ? (
                          <Pill tone={indexTone(b.index_level)} className="tabular-nums">
                            <span title={b.index_at ? `측정 ${b.index_at.slice(0, 16).replace('T', ' ')}` : undefined}>
                              지수 {b.index_score.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}{b.index_grade ? ` · ${b.index_grade}` : ''}
                            </span>
                          </Pill>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" disabled={indexingId === b.id} onClick={() => analyzeIndex(b)} title="블로그 지수 분석 (20~60초)">
                          {indexingId === b.id ? <Loader2 className="animate-spin" /> : <BarChart3 />} {b.index_score != null ? '다시' : '지수 분석'}
                        </Button>
                      </div>
                    </td>
                    <td className={`${TD} pr-0`}>
                      <div className="flex justify-end gap-1">
                        {b.status === 'active' ? (
                          <Button variant="ghost" size="sm" disabled={busyId === b.id} onClick={() => changeStatus(b, 'paused')} title="일시정지">
                            <Pause /> 일시정지
                          </Button>
                        ) : (
                          <Button variant="ghost" size="sm" disabled={busyId === b.id} onClick={() => changeStatus(b, 'active')} title="정상으로">
                            <Play /> 정상으로
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" className="w-8 px-0" onClick={() => openEdit(b)} title="편집">
                          <Pencil />
                        </Button>
                        <Button variant="ghost" size="sm" className="w-8 px-0 text-danger hover:text-danger" disabled={busyId === b.id} onClick={() => remove(b)} title="삭제">
                          {busyId === b.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? '블로그 계정 편집' : '블로그 계정 추가'}</DialogTitle>
            <DialogDescription>발행에 쓸 네이버 블로그 정보와 하루 한도를 정합니다.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="b-blog">블로그 ID *</Label>
                <Input id="b-blog" value={form.blog_id} onChange={(e) => set('blog_id', e.target.value)} placeholder="blog.naver.com/ 뒤의 ID" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="b-label">별칭</Label>
                <Input id="b-label" value={form.label ?? ''} onChange={(e) => set('label', e.target.value)} placeholder="예: 로담 메인" />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="b-login">로그인 ID</Label>
                <Input id="b-login" value={form.login_id ?? ''} onChange={(e) => set('login_id', e.target.value)} autoComplete="off" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="b-pw">비밀번호</Label>
                <Input
                  id="b-pw"
                  type="password"
                  value={form.login_pw ?? ''}
                  onChange={(e) => set('login_pw', e.target.value)}
                  autoComplete="new-password"
                  placeholder={editing?.has_password ? '비워두면 기존 비밀번호 유지' : ''}
                />
              </div>
            </div>
            <p className="-mt-2 text-xs text-muted-foreground">비밀번호는 암호화 저장, 자동 로그인에만 사용합니다.</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="b-limit">하루 한도</Label>
                <Input id="b-limit" type="number" min={1} max={20} value={form.daily_limit} onChange={(e) => set('daily_limit', Math.max(0, Number(e.target.value) || 0))} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="b-ws">시작 시각</Label>
                <Input id="b-ws" type="time" value={form.window_start} onChange={(e) => set('window_start', e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="b-we">종료 시각</Label>
                <Input id="b-we" type="time" value={form.window_end} onChange={(e) => set('window_end', e.target.value)} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="b-gap">최소 간격(분)</Label>
                <Input id="b-gap" type="number" min={0} step={10} value={form.min_gap_minutes} onChange={(e) => set('min_gap_minutes', Math.max(0, Number(e.target.value) || 0))} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="b-cat">기본 카테고리</Label>
                <Input id="b-cat" value={form.default_category ?? ''} onChange={(e) => set('default_category', e.target.value)} placeholder="블로그 카테고리명" />
              </div>
              <div className="space-y-1">
                <Label>공개 범위</Label>
                <Select value={form.open_type} onValueChange={(v) => set('open_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(OPEN_TYPE_LABEL).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>취소</Button>
            <Button onClick={save} disabled={saving}>
              {saving && <Loader2 className="animate-spin" />}
              {editing ? '저장' : '추가'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
