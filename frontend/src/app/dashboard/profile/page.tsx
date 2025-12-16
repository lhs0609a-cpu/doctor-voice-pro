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
import { Badge } from '@/components/ui/badge'
import { profileAPI } from '@/lib/api'
import {
  Save,
  Sliders,
  MessageSquare,
  Users,
  FileText,
  Trash2,
  Plus,
  Info,
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

  // Writing Style State
  const [formality, setFormality] = useState(5)
  const [friendliness, setFriendliness] = useState(5)
  const [technicalDepth, setTechnicalDepth] = useState(5)
  const [storytelling, setStorytelling] = useState(5)
  const [emotion, setEmotion] = useState(5)

  // Signature Phrases State
  const [signaturePhrases, setSignaturePhrases] = useState<string[]>([])
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

  useEffect(() => {
    loadProfile()
  }, [])

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
      alert('프로필을 불러올 수 없습니다.')
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
        },
        signature_phrases: signaturePhrases,
        sample_posts: samplePosts,
        target_audience: {
          age_range: ageRange || undefined,
          gender: gender || undefined,
          concerns,
        },
        preferred_structure: preferredStructure,
      })

      alert('프로필이 저장되었습니다.')
      loadProfile()
    } catch (error) {
      console.error('Failed to save profile:', error)
      alert('프로필 저장 중 오류가 발생했습니다.')
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
        <Label>{label}</Label>
        <span className="text-sm font-semibold text-blue-600">{value}</span>
      </div>
      <input
        type="range"
        min="1"
        max="10"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-muted-foreground">로딩 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">프로필 설정</h1>
        <p className="text-muted-foreground">
          AI가 당신의 스타일을 학습하도록 프로필을 설정하세요
        </p>
      </div>

      {/* Writing Style */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sliders className="h-5 w-5" />
            <CardTitle>글쓰기 스타일</CardTitle>
          </div>
          <CardDescription>
            AI가 생성할 글의 스타일을 세밀하게 조정합니다 (1-10)
          </CardDescription>
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

      {/* Signature Phrases */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            <CardTitle>자주 쓰는 표현</CardTitle>
          </div>
          <CardDescription>
            당신이 자주 사용하는 표현이나 문구를 추가하세요
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder='예: "환자분들께 말씀드리는데요", "제 경험상"'
              value={newPhrase}
              onChange={(e) => setNewPhrase(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addPhrase()}
            />
            <Button onClick={addPhrase} size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              추가
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {signaturePhrases.map((phrase, index) => (
              <Badge key={index} variant="secondary" className="gap-2">
                {phrase}
                <button
                  onClick={() => removePhrase(index)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            {signaturePhrases.length === 0 && (
              <p className="text-sm text-muted-foreground">
                추가된 표현이 없습니다
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Sample Posts */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            <CardTitle>샘플 글</CardTitle>
          </div>
          <CardDescription>
            당신이 작성한 글의 샘플을 추가하여 AI가 학습하도록 하세요
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Textarea
              placeholder="과거에 작성한 블로그 글이나 칼럼의 내용을 붙여넣으세요..."
              value={newSamplePost}
              onChange={(e) => setNewSamplePost(e.target.value)}
              rows={4}
            />
            <Button onClick={addSamplePost} size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              샘플 추가
            </Button>
          </div>
          <div className="space-y-2">
            {samplePosts.map((post, index) => (
              <div
                key={index}
                className="flex items-start gap-2 p-3 bg-muted rounded-lg"
              >
                <div className="flex-1 text-sm">
                  {post.substring(0, 150)}
                  {post.length > 150 && '...'}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeSamplePost(index)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
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
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            <CardTitle>타겟 독자</CardTitle>
          </div>
          <CardDescription>
            주요 타겟 독자층을 설정하여 맞춤형 콘텐츠를 생성합니다
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="age-range">연령대</Label>
              <Input
                id="age-range"
                placeholder="예: 30-50"
                value={ageRange}
                onChange={(e) => setAgeRange(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gender">성별</Label>
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
            </div>
          </div>

          <div className="space-y-2">
            <Label>주요 관심사 / 고민</Label>
            <div className="flex gap-2">
              <Input
                placeholder='예: "무릎 통증", "관절염", "스포츠 부상"'
                value={newConcern}
                onChange={(e) => setNewConcern(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addConcern()}
              />
              <Button onClick={addConcern} size="sm" className="gap-2">
                <Plus className="h-4 w-4" />
                추가
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {concerns.map((concern, index) => (
                <Badge key={index} variant="secondary" className="gap-2">
                  {concern}
                  <button
                    onClick={() => removeConcern(index)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              {concerns.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  추가된 관심사가 없습니다
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preferred Structure */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            <CardTitle>선호하는 글 구조</CardTitle>
          </div>
          <CardDescription>
            포스팅의 기본 구조를 선택하세요
          </CardDescription>
        </CardHeader>
        <CardContent>
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
          <div className="mt-2 p-3 bg-blue-50 rounded-lg flex gap-2">
            <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-blue-900">
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

      {/* Save Button */}
      <div className="flex justify-end gap-2 pb-8">
        <Button
          size="lg"
          onClick={handleSave}
          disabled={saving}
          className="gap-2"
        >
          <Save className="h-4 w-4" />
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
