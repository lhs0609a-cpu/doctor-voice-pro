'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  Plus,
  Trash2,
  Target,
  Mail,
  Clock,
  Filter,
  X,
} from 'lucide-react'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill } from '@/components/app-shell/ui-kit'
import { outreachAPI, type OutreachEmailTemplate } from '@/lib/api'
import { toast } from 'sonner'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'muted'

const LEAD_GRADES: { value: string; label: string; tone: Tone }[] = [
  { value: 'A', label: 'A등급 (80+점)', tone: 'ok' },
  { value: 'B', label: 'B등급 (60-79점)', tone: 'accent' },
  { value: 'C', label: 'C등급 (40-59점)', tone: 'warn' },
  { value: 'D', label: 'D등급 (0-39점)', tone: 'muted' },
]

const BLOG_CATEGORIES = [
  { value: 'beauty', label: '뷰티/패션' },
  { value: 'food', label: '맛집/카페' },
  { value: 'travel', label: '여행' },
  { value: 'parenting', label: '육아/교육' },
  { value: 'living', label: '리빙/인테리어' },
  { value: 'health', label: '건강/의료' },
  { value: 'it', label: 'IT/테크' },
  { value: 'finance', label: '재테크/금융' },
  { value: 'lifestyle', label: '라이프스타일' },
]

const WEEKDAYS = [
  { value: 1, label: '월' },
  { value: 2, label: '화' },
  { value: 3, label: '수' },
  { value: 4, label: '목' },
  { value: 5, label: '금' },
  { value: 6, label: '토' },
  { value: 7, label: '일' },
]

interface TemplateSequence {
  template_id: string
  delay_days: number
}

const TOGGLE_ON = 'border-primary bg-accent text-primary'
const TOGGLE_OFF = 'border-border text-muted-foreground hover:bg-muted/40'

export default function NewCampaignPage() {
  const router = useRouter()
  const [saving, setSaving] = useState(false)
  const [templates, setTemplates] = useState<OutreachEmailTemplate[]>([])

  // Form state
  const [form, setForm] = useState({
    name: '',
    description: '',
    target_grades: ['A', 'B'] as string[],
    target_categories: [] as string[],
    target_keywords: [] as string[],
    min_score: 60,
    max_contacts: 100,
    daily_limit: 50,
    sending_hours_start: 9,
    sending_hours_end: 18,
    sending_days: [1, 2, 3, 4, 5] as number[],
  })

  const [templateSequence, setTemplateSequence] = useState<TemplateSequence[]>([
    { template_id: '', delay_days: 0 }
  ])

  const [newKeyword, setNewKeyword] = useState('')

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    try {
      const data = await outreachAPI.getTemplates()
      setTemplates(data.templates)
    } catch (error) {
      console.error('Templates load error:', error)
    }
  }

  const handleGradeToggle = (grade: string) => {
    setForm(prev => ({
      ...prev,
      target_grades: prev.target_grades.includes(grade)
        ? prev.target_grades.filter(g => g !== grade)
        : [...prev.target_grades, grade]
    }))
  }

  const handleCategoryToggle = (category: string) => {
    setForm(prev => ({
      ...prev,
      target_categories: prev.target_categories.includes(category)
        ? prev.target_categories.filter(c => c !== category)
        : [...prev.target_categories, category]
    }))
  }

  const handleDayToggle = (day: number) => {
    setForm(prev => ({
      ...prev,
      sending_days: prev.sending_days.includes(day)
        ? prev.sending_days.filter(d => d !== day)
        : [...prev.sending_days, day].sort()
    }))
  }

  const handleAddKeyword = () => {
    if (newKeyword.trim() && !form.target_keywords.includes(newKeyword.trim())) {
      setForm(prev => ({
        ...prev,
        target_keywords: [...prev.target_keywords, newKeyword.trim()]
      }))
      setNewKeyword('')
    }
  }

  const handleRemoveKeyword = (keyword: string) => {
    setForm(prev => ({
      ...prev,
      target_keywords: prev.target_keywords.filter(k => k !== keyword)
    }))
  }

  const handleAddTemplate = () => {
    setTemplateSequence(prev => [
      ...prev,
      { template_id: '', delay_days: 3 }
    ])
  }

  const handleRemoveTemplate = (index: number) => {
    if (templateSequence.length > 1) {
      setTemplateSequence(prev => prev.filter((_, i) => i !== index))
    }
  }

  const handleTemplateChange = (index: number, field: keyof TemplateSequence, value: any) => {
    setTemplateSequence(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    ))
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('캠페인 이름을 입력하세요')
      return
    }

    if (templateSequence.some(t => !t.template_id)) {
      toast.error('모든 템플릿을 선택하세요')
      return
    }

    if (form.target_grades.length === 0) {
      toast.error('최소 하나의 타겟 등급을 선택하세요')
      return
    }

    setSaving(true)
    try {
      const result = await outreachAPI.createCampaign({
        name: form.name,
        description: form.description,
        target_grades: form.target_grades,
        target_categories: form.target_categories.length > 0 ? form.target_categories : undefined,
        target_keywords: form.target_keywords.length > 0 ? form.target_keywords : undefined,
        min_score: form.min_score,
        max_contacts: form.max_contacts,
        templates: templateSequence,
        daily_limit: form.daily_limit,
        sending_hours_start: form.sending_hours_start,
        sending_hours_end: form.sending_hours_end,
        sending_days: form.sending_days,
      })

      if (result.success) {
        toast.success('캠페인이 생성되었습니다')
        router.push('/dashboard/outreach?tab=campaigns')
      } else {
        toast.error('캠페인 생성 실패')
      }
    } catch (error) {
      toast.error('캠페인 생성 실패')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <Button variant="ghost" size="sm" className="-ml-2 tracking-normal" asChild>
            <Link href="/dashboard/outreach?tab=campaigns">
              <ArrowLeft className="h-4 w-4" />
              캠페인 목록
            </Link>
          </Button>
        }
        title="새 캠페인 만들기"
        description="타겟 블로그를 정하고, 이메일 순서와 발송 시간을 설정하세요."
      />

      <div className="space-y-4">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-muted-foreground" />
              기본 정보
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>캠페인 이름 *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="예: 뷰티 블로거 협찬 제안"
                className="mt-1"
              />
            </div>
            <div>
              <Label>설명</Label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="캠페인에 대한 설명..."
                className="mt-1"
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        {/* Target Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              타겟 설정
            </CardTitle>
            <CardDescription>이메일을 보낼 블로그 조건을 정합니다</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Target Grades */}
            <div>
              <Label className="mb-3 block">타겟 등급 *</Label>
              <div className="flex flex-wrap gap-2">
                {LEAD_GRADES.map((grade) => (
                  <button
                    key={grade.value}
                    type="button"
                    onClick={() => handleGradeToggle(grade.value)}
                    className={`rounded-lg border px-3 py-2 transition-colors ${
                      form.target_grades.includes(grade.value) ? TOGGLE_ON : TOGGLE_OFF
                    }`}
                  >
                    <Pill tone={grade.tone}>{grade.label}</Pill>
                  </button>
                ))}
              </div>
            </div>

            {/* Target Categories */}
            <div>
              <Label className="mb-3 block">카테고리 (선택사항)</Label>
              <div className="flex flex-wrap gap-2">
                {BLOG_CATEGORIES.map((category) => (
                  <button
                    key={category.value}
                    type="button"
                    onClick={() => handleCategoryToggle(category.value)}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                      form.target_categories.includes(category.value) ? TOGGLE_ON : TOGGLE_OFF
                    }`}
                  >
                    {category.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Keywords */}
            <div>
              <Label className="mb-3 block">키워드 필터 (선택사항)</Label>
              <div className="mb-2 flex gap-2">
                <Input
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                  placeholder="키워드 입력"
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddKeyword())}
                />
                <Button type="button" variant="outline" size="icon" onClick={handleAddKeyword}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {form.target_keywords.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {form.target_keywords.map((keyword) => (
                    <Pill key={keyword} tone="muted" className="gap-1">
                      {keyword}
                      <button type="button" onClick={() => handleRemoveKeyword(keyword)} className="hover:text-foreground">
                        <X className="h-3 w-3" />
                      </button>
                    </Pill>
                  ))}
                </div>
              )}
            </div>

            {/* Min Score & Max Contacts */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>최소 점수</Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={form.min_score}
                  onChange={(e) => setForm({ ...form, min_score: parseInt(e.target.value) || 0 })}
                  className="mt-1"
                />
              </div>
              <div>
                <Label>최대 발송 수</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.max_contacts}
                  onChange={(e) => setForm({ ...form, max_contacts: parseInt(e.target.value) || 100 })}
                  className="mt-1"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Template Sequence */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              이메일 시퀀스
            </CardTitle>
            <CardDescription>보낼 이메일 템플릿과 순서를 정합니다</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {templateSequence.map((item, index) => (
              <div key={index} className="flex items-center gap-4 rounded-lg border bg-muted/40 p-4">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-primary tabular-nums">
                  {index + 1}
                </div>
                <div className="grid flex-1 grid-cols-2 gap-4">
                  <div>
                    <Label className="text-[13px] font-medium text-muted-foreground">템플릿</Label>
                    <Select
                      value={item.template_id}
                      onValueChange={(v) => handleTemplateChange(index, 'template_id', v)}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="템플릿 선택" />
                      </SelectTrigger>
                      <SelectContent>
                        {templates.map((template) => (
                          <SelectItem key={template.id} value={template.id}>
                            {template.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {index > 0 && (
                    <div>
                      <Label className="text-[13px] font-medium text-muted-foreground">이전 발송 후 대기 일수</Label>
                      <Input
                        type="number"
                        min={1}
                        value={item.delay_days}
                        onChange={(e) => handleTemplateChange(index, 'delay_days', parseInt(e.target.value) || 1)}
                        className="mt-1"
                      />
                    </div>
                  )}
                </div>
                {index > 0 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveTemplate(index)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <Button variant="outline" onClick={handleAddTemplate} className="w-full">
              <Plus className="h-4 w-4" />
              팔로업 이메일 추가
            </Button>
          </CardContent>
        </Card>

        {/* Schedule Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              발송 스케줄
            </CardTitle>
            <CardDescription>이메일을 보낼 시간과 빈도를 정합니다</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Daily Limit */}
            <div>
              <Label>일일 발송 한도</Label>
              <Input
                type="number"
                min={1}
                max={200}
                value={form.daily_limit}
                onChange={(e) => setForm({ ...form, daily_limit: parseInt(e.target.value) || 50 })}
                className="mt-1 max-w-xs"
              />
            </div>

            {/* Sending Hours */}
            <div>
              <Label className="mb-3 block">발송 시간대</Label>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={form.sending_hours_start}
                    onChange={(e) => setForm({ ...form, sending_hours_start: parseInt(e.target.value) || 9 })}
                    className="w-20"
                  />
                  <span className="text-sm text-muted-foreground">시</span>
                </div>
                <span className="text-muted-foreground">~</span>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={form.sending_hours_end}
                    onChange={(e) => setForm({ ...form, sending_hours_end: parseInt(e.target.value) || 18 })}
                    className="w-20"
                  />
                  <span className="text-sm text-muted-foreground">시</span>
                </div>
              </div>
            </div>

            {/* Sending Days */}
            <div>
              <Label className="mb-3 block">발송 요일</Label>
              <div className="flex gap-2">
                {WEEKDAYS.map((day) => (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => handleDayToggle(day.value)}
                    className={`h-10 w-10 rounded-full border text-sm font-medium transition-colors ${
                      form.sending_days.includes(day.value) ? TOGGLE_ON : TOGGLE_OFF
                    }`}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" asChild>
            <Link href="/dashboard/outreach?tab=campaigns">취소</Link>
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? '생성 중...' : '캠페인 생성'}
          </Button>
        </div>
      </div>
    </div>
  )
}
