'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill } from '@/components/app-shell/ui-kit'
import { profileAPI, industryAPI, Industry, MyIndustry } from '@/lib/api'
import {
  DifferentiatorsEditor,
  Differentiators,
  EMPTY_DIFFERENTIATORS,
} from '@/components/profile/differentiators-editor'
import type { IndustryProfileDefaults } from '@/types'
import { toast } from 'sonner'
import {
  Save,
  Sliders,
  MessageSquare,
  Users,
  FileText,
  Trash2,
  Plus,
  Info,
  Building2,
  Loader2,
  Sparkles,
} from 'lucide-react'

interface WritingStyle {
  formality: number
  friendliness: number
  technical_depth: number
  storytelling: number
  emotion: number
}

interface TargetAudience {
  age_range?: string
  gender?: string
  concerns: string[]
}

interface Profile {
  id: string
  user_id: string
  writing_style: WritingStyle | null
  signature_phrases: string[]
  differentiators: Differentiators | null
  sample_posts: string[]
  target_audience: TargetAudience | null
  preferred_structure: string
  learned_at: string | null
  profile_version: number
  created_at: string
  updated_at: string
}

export default function ProfilePage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)

  // Industry State (업종 설정)
  const [industries, setIndustries] = useState<Industry[]>([])
  const [selectedIndustry, setSelectedIndustry] = useState<string>('medical')
  const [businessName, setBusinessName] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [industryLoading, setIndustryLoading] = useState(false)
  const [industrySaving, setIndustrySaving] = useState(false)

  // Writing Style State
  const [formality, setFormality] = useState(5)
  const [friendliness, setFriendliness] = useState(5)
  const [technicalDepth, setTechnicalDepth] = useState(5)
  const [storytelling, setStorytelling] = useState(5)
  const [emotion, setEmotion] = useState(5)

  // Signature Phrases State
  const [signaturePhrases, setSignaturePhrases] = useState<string[]>([])
  const [differentiators, setDifferentiators] = useState<Differentiators>(EMPTY_DIFFERENTIATORS)
  const [newPhrase, setNewPhrase] = useState('')

  // Sample Posts State
  const [samplePosts, setSamplePosts] = useState<string[]>([])
  const [newSamplePost, setNewSamplePost] = useState('')

  // Target Audience State
  const [ageRange, setAgeRange] = useState('')
  const [gender, setGender] = useState('')
  const [concerns, setConcerns] = useState<string[]>([])
  const [newConcern, setNewConcern] = useState('')

  // Preferred Structure State
  const [preferredStructure, setPreferredStructure] = useState('story_problem_solution')

  // Industry Profile Defaults State (업종별 추천 기본값)
  const [profileDefaults, setProfileDefaults] = useState<IndustryProfileDefaults | null>(null)

  // Get current industry config
  const currentIndustry = industries.find(i => i.value === selectedIndustry)

  useEffect(() => {
    loadProfile()
    loadIndustryData()
  }, [])

  const loadIndustryData = async () => {
    setIndustryLoading(true)
    try {
      // Load all industries
      const industriesData = await industryAPI.getAll()
      setIndustries(industriesData.industries)

      // Load my industry setting
      const myIndustry = await industryAPI.getMyIndustry()
      setSelectedIndustry(myIndustry.industry_type)
      setBusinessName(myIndustry.business_name || '')
      setSpecialty(myIndustry.specialty || '')

      // Load profile defaults for current industry
      try {
        const defaults = await industryAPI.getProfileDefaults(myIndustry.industry_type)
        setProfileDefaults(defaults)
      } catch (err) {
        console.error('Failed to load profile defaults:', err)
      }
    } catch (error) {
      console.error('Failed to load industry data:', error)
    } finally {
      setIndustryLoading(false)
    }
  }

  const handleSaveIndustry = async () => {
    setIndustrySaving(true)
    try {
      await industryAPI.updateMyIndustry({
        industry_type: selectedIndustry,
        business_name: businessName || undefined,
        specialty: specialty || undefined,
      })
      toast.success('업종 설정이 저장되었습니다.')
    } catch (error) {
      console.error('Failed to save industry:', error)
      toast.error('업종 설정 저장 중 오류가 발생했습니다.')
    } finally {
      setIndustrySaving(false)
    }
  }

  const loadProfile = async () => {
    try {
      const data = await profileAPI.get() as Profile
      setProfile(data)

      // Load writing style
      if (data.writing_style) {
        setFormality(data.writing_style.formality)
        setFriendliness(data.writing_style.friendliness)
        setTechnicalDepth(data.writing_style.technical_depth)
        setStorytelling(data.writing_style.storytelling)
        setEmotion(data.writing_style.emotion)
      }

      // Load other fields
      setSignaturePhrases(data.signature_phrases || [])
      setDifferentiators({
        philosophy: data.differentiators?.philosophy || '',
        items: data.differentiators?.items || [],
      })
      setSamplePosts(data.sample_posts || [])
      setPreferredStructure(data.preferred_structure || 'story_problem_solution')

      // Load target audience
      if (data.target_audience) {
        setAgeRange(data.target_audience.age_range || '')
        setGender(data.target_audience.gender || '')
        setConcerns(data.target_audience.concerns || [])
      }
    } catch (error) {
      console.error('Failed to load profile:', error)
      toast.error('프로필을 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await profileAPI.update({
        writing_style: {
          formality,
          friendliness,
          technical_depth: technicalDepth,
          storytelling,
          emotion,
          humor: 5,
          question_usage: 5,
          metaphor_usage: 5,
          sentence_length: 5,
        },
        signature_phrases: signaturePhrases,
        differentiators: {
          philosophy: differentiators.philosophy.trim(),
          items: differentiators.items.filter((it) => it.text.trim()),
        },
        sample_posts: samplePosts,
        target_audience: {
          age_range: ageRange || undefined,
          gender: gender || undefined,
          concerns,
        },
        preferred_structure: preferredStructure,
      })

      toast.success('프로필이 저장되었습니다.')
      loadProfile()
    } catch (error) {
      console.error('Failed to save profile:', error)
      toast.error('프로필 저장 중 오류가 발생했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const addPhrase = () => {
    if (newPhrase.trim()) {
      setSignaturePhrases([...signaturePhrases, newPhrase.trim()])
      setNewPhrase('')
    }
  }

  const removePhrase = (index: number) => {
    setSignaturePhrases(signaturePhrases.filter((_, i) => i !== index))
  }

  const addSamplePost = () => {
    if (newSamplePost.trim()) {
      setSamplePosts([...samplePosts, newSamplePost.trim()])
      setNewSamplePost('')
    }
  }

  const removeSamplePost = (index: number) => {
    setSamplePosts(samplePosts.filter((_, i) => i !== index))
  }

  const addConcern = () => {
    if (newConcern.trim()) {
      setConcerns([...concerns, newConcern.trim()])
      setNewConcern('')
    }
  }

  const removeConcern = (index: number) => {
    setConcerns(concerns.filter((_, i) => i !== index))
  }

  const SliderWithValue = ({
    label,
    value,
    onChange,
    description,
  }: {
    label: string
    value: number
    onChange: (value: number) => void
    description: string
  }) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-[13px] font-medium text-muted-foreground">{label}</Label>
        <span className="text-sm font-semibold tabular-nums text-primary">{value}</span>
      </div>
      <input
        type="range"
        min="1"
        max="10"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary"
      />
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  )

  const CardIcon = ({ icon: Icon }: { icon: typeof Save }) => (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
      <Icon className="h-4 w-4" />
    </div>
  )

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="프로필 설정"
        description="AI가 내 글쓰기 스타일을 학습하도록 프로필을 설정하세요."
        actions={
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? '저장 중...' : '프로필 저장'}
          </Button>
        }
      />

      {/* Industry Selection - 업종 설정 */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={Building2} />
            <div>
              <CardTitle>업종 설정</CardTitle>
              <CardDescription className="mt-1">
                업종에 맞는 AI 프롬프트와 전문 용어가 자동으로 적용됩니다
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {industryLoading ? (
            <div className="flex justify-center py-8">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
            </div>
          ) : (
            <>
              {/* Industry Type Selection */}
              <div className="space-y-2">
                <Label className="text-[13px] font-medium text-muted-foreground">업종 선택</Label>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                  {industries.map((industry) => {
                    const selected = selectedIndustry === industry.value
                    return (
                      <button
                        key={industry.value}
                        type="button"
                        onClick={async () => {
                          setSelectedIndustry(industry.value)
                          setSpecialty('') // Reset specialty when industry changes
                          // 업종별 프로필 기본값 로드
                          try {
                            const defaults = await industryAPI.getProfileDefaults(industry.value)
                            setProfileDefaults(defaults)
                          } catch (err) {
                            console.error('Failed to load profile defaults:', err)
                          }
                        }}
                        className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                          selected
                            ? 'border-primary bg-accent ring-1 ring-primary'
                            : 'bg-card hover:bg-muted/40'
                        }`}
                      >
                        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-lg ${selected ? 'bg-card' : 'bg-muted'}`}>
                          {industry.icon}
                        </div>
                        <div className={`text-sm font-medium ${selected ? 'text-primary' : ''}`}>{industry.name}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Business Name */}
              {currentIndustry && (
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="business-name" className="text-[13px] font-medium text-muted-foreground">
                      {currentIndustry.business_name_label}
                    </Label>
                    <Input
                      id="business-name"
                      placeholder={`예: ${
                        selectedIndustry === 'medical' ? '○○병원' :
                        selectedIndustry === 'legal' ? '○○법률사무소' :
                        selectedIndustry === 'restaurant' ? '○○맛집' :
                        '○○업체'
                      }`}
                      value={businessName}
                      onChange={(e) => setBusinessName(e.target.value)}
                    />
                  </div>

                  {/* Specialty */}
                  <div className="space-y-2">
                    <Label htmlFor="specialty" className="text-[13px] font-medium text-muted-foreground">
                      {currentIndustry.specialty_label}
                    </Label>
                    <Select
                      value={specialty || '_none'}
                      onValueChange={(val) => setSpecialty(val === '_none' ? '' : val)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="선택하세요" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="_none">선택하세요</SelectItem>
                        {currentIndustry.specialty_options.map((opt) => (
                          <SelectItem key={opt} value={opt}>
                            {opt}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              {/* Industry Info */}
              {currentIndustry && (
                <div className="rounded-lg border bg-muted/40 p-3">
                  <div className="flex items-start gap-2">
                    <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                    <div className="text-sm">
                      <p className="mb-1 font-medium">
                        {currentIndustry.name} 업종 AI 설정
                      </p>
                      <p className="text-xs text-muted-foreground">
                        추천 글 주제: {currentIndustry.sample_topics.slice(0, 3).join(', ')}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Save Industry Button */}
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveIndustry}
                  disabled={industrySaving}
                >
                  {industrySaving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {industrySaving ? '저장 중...' : '업종 설정 저장'}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Writing Style */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <CardIcon icon={Sliders} />
              <div>
                <CardTitle>글쓰기 스타일</CardTitle>
                <CardDescription className="mt-1">
                  AI가 생성할 글의 스타일을 세밀하게 조정합니다 (1-10)
                </CardDescription>
              </div>
            </div>
            {profileDefaults && (
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => {
                  const ws = profileDefaults.writing_style
                  setFormality(ws.formality)
                  setFriendliness(ws.friendliness)
                  setTechnicalDepth(ws.technical_depth)
                  setStorytelling(ws.storytelling)
                  setEmotion(ws.emotion)
                  setPreferredStructure(profileDefaults.recommended_structure)
                  toast.success('업종 추천 스타일이 적용되었습니다')
                }}
              >
                <Sparkles className="h-4 w-4" />
                업종 추천 스타일 적용
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <SliderWithValue
            label="격식 (Formality)"
            value={formality}
            onChange={setFormality}
            description="1: 친근한 반말 → 10: 격식있는 존댓말"
          />
          <SliderWithValue
            label="친근함 (Friendliness)"
            value={friendliness}
            onChange={setFriendliness}
            description="1: 전문적이고 거리감 있음 → 10: 따뜻하고 친근함"
          />
          <SliderWithValue
            label="전문성 (Technical Depth)"
            value={technicalDepth}
            onChange={setTechnicalDepth}
            description="1: 일반인도 이해 쉬움 → 10: 전문적이고 깊이있음"
          />
          <SliderWithValue
            label="스토리텔링 (Storytelling)"
            value={storytelling}
            onChange={setStorytelling}
            description="1: 팩트 중심 설명 → 10: 이야기와 사례 중심"
          />
          <SliderWithValue
            label="감정 표현 (Emotion)"
            value={emotion}
            onChange={setEmotion}
            description="1: 담백하고 중립적 → 10: 감정적이고 공감적"
          />
        </CardContent>
      </Card>

      {/* 이 병원만의 것 */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={Sparkles} />
            <div>
              <CardTitle>이 병원만의 것</CardTitle>
              <CardDescription className="mt-1">
                글을 읽은 사람이 &quot;여기는 다르네&quot; 하고 느낄 재료입니다
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <DifferentiatorsEditor value={differentiators} onChange={setDifferentiators} />
        </CardContent>
      </Card>

      {/* Signature Phrases */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={MessageSquare} />
            <div>
              <CardTitle>자주 쓰는 표현</CardTitle>
              <CardDescription className="mt-1">
                자주 사용하는 표현이나 문구를 추가하세요
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder='예: "환자분들께 말씀드리는데요", "제 경험상"'
              value={newPhrase}
              onChange={(e) => setNewPhrase(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addPhrase()}
            />
            <Button variant="outline" onClick={addPhrase} size="sm" className="h-10 shrink-0">
              <Plus className="h-4 w-4" />
              추가
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {signaturePhrases.map((phrase, index) => (
              <Pill key={index} tone="muted" className="gap-1.5 pr-1.5">
                {phrase}
                <button
                  type="button"
                  onClick={() => removePhrase(index)}
                  className="rounded p-0.5 text-muted-foreground transition-colors hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Pill>
            ))}
            {signaturePhrases.length === 0 && (
              <p className="text-sm text-muted-foreground">
                추가된 표현이 없습니다
              </p>
            )}
          </div>
          {profileDefaults && profileDefaults.recommended_phrases.length > 0 && (
            <div className="space-y-2">
              <Label className="flex items-center gap-1 text-[13px] font-medium text-primary">
                <Sparkles className="h-3 w-3" />
                업종 추천 표현 (클릭하여 추가)
              </Label>
              <div className="flex flex-wrap gap-2">
                {profileDefaults.recommended_phrases
                  .filter(phrase => !signaturePhrases.includes(phrase))
                  .map((phrase, index) => (
                    <button
                      key={index}
                      type="button"
                      className="pill cursor-pointer border border-dashed border-primary/40 bg-card text-primary transition-colors hover:bg-accent"
                      onClick={() => {
                        setSignaturePhrases([...signaturePhrases, phrase])
                        toast.success(`"${phrase}" 추가됨`)
                      }}
                    >
                      + {phrase}
                    </button>
                  ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sample Posts */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={FileText} />
            <div>
              <CardTitle>샘플 글</CardTitle>
              <CardDescription className="mt-1">
                직접 작성한 글의 샘플을 추가하면 AI가 문체를 학습합니다
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Textarea
              placeholder="과거에 작성한 블로그 글이나 칼럼의 내용을 붙여넣으세요"
              value={newSamplePost}
              onChange={(e) => setNewSamplePost(e.target.value)}
              rows={4}
            />
            <Button variant="outline" onClick={addSamplePost} size="sm">
              <Plus className="h-4 w-4" />
              샘플 추가
            </Button>
          </div>
          <div className="space-y-2">
            {samplePosts.map((post, index) => (
              <div
                key={index}
                className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3"
              >
                <div className="flex-1 text-sm">
                  {post.substring(0, 150)}
                  {post.length > 150 && '...'}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeSamplePost(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {samplePosts.length === 0 && (
              <p className="text-sm text-muted-foreground">
                추가된 샘플이 없습니다
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Target Audience */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={Users} />
            <div>
              <CardTitle>타겟 독자</CardTitle>
              <CardDescription className="mt-1">
                주요 타겟 독자층을 설정하면 맞춤형 콘텐츠를 생성합니다
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="age-range" className="text-[13px] font-medium text-muted-foreground">연령대</Label>
              <div className="flex gap-2">
                <Input
                  id="age-range"
                  placeholder="예: 30-50"
                  value={ageRange}
                  onChange={(e) => setAgeRange(e.target.value)}
                />
                {profileDefaults && profileDefaults.target_audience.age_range && !ageRange && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-10 shrink-0 text-xs text-primary"
                    onClick={() => {
                      setAgeRange(profileDefaults.target_audience.age_range)
                      toast.success('추천 연령대 적용됨')
                    }}
                  >
                    추천: {profileDefaults.target_audience.age_range}
                  </Button>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="gender" className="text-[13px] font-medium text-muted-foreground">성별</Label>
              <div className="flex gap-2">
                <Select value={gender || 'all'} onValueChange={(val) => setGender(val === 'all' ? '' : val)}>
                  <SelectTrigger>
                    <SelectValue placeholder="선택" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">전체</SelectItem>
                    <SelectItem value="male">남성</SelectItem>
                    <SelectItem value="female">여성</SelectItem>
                  </SelectContent>
                </Select>
                {profileDefaults && profileDefaults.target_audience.gender && !gender && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-10 shrink-0 text-xs text-primary"
                    onClick={() => {
                      setGender(profileDefaults.target_audience.gender)
                      toast.success('추천 성별 적용됨')
                    }}
                  >
                    추천: {profileDefaults.target_audience.gender === 'female' ? '여성' : profileDefaults.target_audience.gender === 'male' ? '남성' : '전체'}
                  </Button>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-[13px] font-medium text-muted-foreground">주요 관심사 / 고민</Label>
            <div className="flex gap-2">
              <Input
                placeholder='예: "무릎 통증", "관절염", "스포츠 부상"'
                value={newConcern}
                onChange={(e) => setNewConcern(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addConcern()}
              />
              <Button variant="outline" onClick={addConcern} size="sm" className="h-10 shrink-0">
                <Plus className="h-4 w-4" />
                추가
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {concerns.map((concern, index) => (
                <Pill key={index} tone="muted" className="gap-1.5 pr-1.5">
                  {concern}
                  <button
                    type="button"
                    onClick={() => removeConcern(index)}
                    className="rounded p-0.5 text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Pill>
              ))}
              {concerns.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  추가된 관심사가 없습니다
                </p>
              )}
            </div>
            {profileDefaults && profileDefaults.target_audience.recommended_concerns.length > 0 && (
              <div className="mt-2 space-y-2">
                <Label className="flex items-center gap-1 text-[13px] font-medium text-primary">
                  <Sparkles className="h-3 w-3" />
                  업종 추천 관심사 (클릭하여 추가)
                </Label>
                <div className="flex flex-wrap gap-2">
                  {profileDefaults.target_audience.recommended_concerns
                    .filter(concern => !concerns.includes(concern))
                    .map((concern, index) => (
                      <button
                        key={index}
                        type="button"
                        className="pill cursor-pointer border border-dashed border-primary/40 bg-card text-primary transition-colors hover:bg-accent"
                        onClick={() => {
                          setConcerns([...concerns, concern])
                          toast.success(`"${concern}" 추가됨`)
                        }}
                      >
                        + {concern}
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Preferred Structure */}
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <CardIcon icon={FileText} />
            <div>
              <CardTitle>선호하는 글 구조</CardTitle>
              <CardDescription className="mt-1">
                포스팅의 기본 구조를 선택하세요
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <Select
            value={preferredStructure}
            onValueChange={setPreferredStructure}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="story_problem_solution">
                스토리 → 문제 → 해결책
              </SelectItem>
              <SelectItem value="aida">
                AIDA (주목 → 관심 → 욕구 → 행동)
              </SelectItem>
              <SelectItem value="pas">
                PAS (문제 → 공감 → 해결책)
              </SelectItem>
              <SelectItem value="qa">질문 → 답변</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex gap-2 rounded-lg bg-accent p-3">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
            <p className="text-xs text-accent-foreground">
              {preferredStructure === 'story_problem_solution' &&
                '실제 사례로 시작해서 독자의 문제를 정의하고 해결책을 제시합니다'}
              {preferredStructure === 'aida' &&
                '주목을 끌고 관심을 유도한 뒤 욕구를 자극하여 행동을 유도합니다'}
              {preferredStructure === 'pas' &&
                '문제를 제시하고 공감을 얻은 후 해결책을 제시합니다'}
              {preferredStructure === 'qa' &&
                '독자의 질문을 먼저 던지고 답변하는 형식입니다'}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button (secondary, bottom of long form; primary lives in PageHeader) */}
      <div className="flex justify-end gap-2 pb-8">
        <Button
          variant="outline"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? '저장 중...' : '프로필 저장'}
        </Button>
      </div>
    </div>
  )
}

function X(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  )
}
