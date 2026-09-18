'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/app-shell/page-header'
import { Pill, EmptyState, ListRow } from '@/components/app-shell/ui-kit'
import {
  Plus,
  Trash2,
  Loader2,
  ArrowLeft,
  MapPin,
  Bell,
  Users,
} from 'lucide-react'
import { reputationAPI } from '@/lib/api'
import type { MonitorProfile, AlertRule, ReputationCompetitor } from '@/types/reputation'
import { PLATFORM_LABELS } from '@/types/reputation'
import { toast } from 'sonner'


const PLATFORM_OPTIONS = [
  { value: 'naver_place', label: '네이버 플레이스' },
  { value: 'google_maps', label: '구글 지도' },
  { value: 'kakao_map', label: '카카오맵' },
  { value: 'naver_blog', label: '네이버 블로그' },
  { value: 'naver_cafe', label: '네이버 카페' },
  { value: 'dcinside', label: 'DC인사이드' },
  { value: 'fmkorea', label: 'FM코리아' },
  { value: 'theqoo', label: '더쿠' },
]

const BUSINESS_TYPES = [
  '병원/의원', '치과', '한의원', '피부과', '성형외과',
  '음식점', '카페', '미용실', '네일샵', '학원',
  '호텔/숙박', '기타',
]

const SEVERITY_LABELS: Record<string, string> = {
  critical: '긴급',
  warning: '주의',
  info: '정보',
}


export default function ReputationSettingsPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('profiles')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  // Profiles
  const [profiles, setProfiles] = useState<MonitorProfile[]>([])
  const [selectedProfile, setSelectedProfile] = useState<MonitorProfile | null>(null)
  const [isProfileDialogOpen, setIsProfileDialogOpen] = useState(false)

  // Alert Rules
  const [alertRules, setAlertRules] = useState<AlertRule[]>([])
  const [isAlertDialogOpen, setIsAlertDialogOpen] = useState(false)

  // Competitors
  const [competitors, setCompetitors] = useState<ReputationCompetitor[]>([])
  const [isCompetitorDialogOpen, setIsCompetitorDialogOpen] = useState(false)

  // Form states
  const [profileForm, setProfileForm] = useState({
    business_name: '',
    business_type: '',
    address: '',
    naver_place_id: '',
    google_place_id: '',
    kakao_place_id: '',
    keywords: '',
    negative_keywords: '',
    crawl_interval_minutes: 60,
    enabled_platforms: ['naver_place'] as string[],
    alert_email: '',
  })

  const [alertForm, setAlertForm] = useState({
    name: '',
    severity: 'warning',
    min_risk_score: 50,
    sentiment_filter: ['negative'],
    notify_email: true,
    notify_sms: false,
    notify_kakao: false,
    cooldown_minutes: 30,
  })

  const [competitorForm, setCompetitorForm] = useState({
    business_name: '',
    naver_place_id: '',
    address: '',
  })

  useEffect(() => {
    loadProfiles()
  }, [])

  useEffect(() => {
    if (selectedProfile) {
      loadAlertRules(selectedProfile.id)
      loadCompetitors(selectedProfile.id)
    }
  }, [selectedProfile])

  const loadProfiles = async () => {
    try {
      const data = await reputationAPI.getProfiles()
      setProfiles(data)
      if (data.length > 0) setSelectedProfile(data[0])
    } catch (error) {
      console.error('프로필 로드 실패:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadAlertRules = async (profileId: string) => {
    try {
      const data = await reputationAPI.getAlertRules(profileId)
      setAlertRules(data)
    } catch (error) {
      console.error('알림 규칙 로드 실패:', error)
    }
  }

  const loadCompetitors = async (profileId: string) => {
    try {
      const data = await reputationAPI.getCompetitors(profileId)
      setCompetitors(data)
    } catch (error) {
      console.error('경쟁사 로드 실패:', error)
    }
  }

  const handleSaveProfile = async () => {
    if (!profileForm.business_name) {
      toast.error('상호명을 입력해주세요.')
      return
    }

    setIsSaving(true)
    try {
      const payload = {
        ...profileForm,
        keywords: profileForm.keywords.split(',').map(k => k.trim()).filter(Boolean),
        negative_keywords: profileForm.negative_keywords.split(',').map(k => k.trim()).filter(Boolean),
      }

      await reputationAPI.createProfile(payload)
      toast.success('사업장이 등록되었습니다.')
      setIsProfileDialogOpen(false)
      loadProfiles()
      // Reset form
      setProfileForm({
        business_name: '', business_type: '', address: '',
        naver_place_id: '', google_place_id: '', kakao_place_id: '',
        keywords: '', negative_keywords: '',
        crawl_interval_minutes: 60, enabled_platforms: ['naver_place'],
        alert_email: '',
      })
    } catch (error) {
      toast.error('사업장 등록에 실패했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteProfile = async (profileId: string) => {
    if (!confirm('이 사업장을 삭제하시겠습니까? 수집된 모든 데이터가 삭제됩니다.')) return

    try {
      await reputationAPI.deleteProfile(profileId)
      toast.success('사업장이 삭제되었습니다.')
      loadProfiles()
    } catch (error) {
      toast.error('삭제에 실패했습니다.')
    }
  }

  const handleSaveAlertRule = async () => {
    if (!selectedProfile || !alertForm.name) {
      toast.error('알림 이름을 입력해주세요.')
      return
    }

    setIsSaving(true)
    try {
      await reputationAPI.createAlertRule(selectedProfile.id, alertForm)
      toast.success('알림 규칙이 생성되었습니다.')
      setIsAlertDialogOpen(false)
      loadAlertRules(selectedProfile.id)
      setAlertForm({
        name: '', severity: 'warning', min_risk_score: 50,
        sentiment_filter: ['negative'], notify_email: true,
        notify_sms: false, notify_kakao: false, cooldown_minutes: 30,
      })
    } catch (error) {
      toast.error('알림 규칙 생성에 실패했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteAlertRule = async (ruleId: string) => {
    try {
      await reputationAPI.deleteAlertRule(ruleId)
      toast.success('알림 규칙이 삭제되었습니다.')
      if (selectedProfile) loadAlertRules(selectedProfile.id)
    } catch (error) {
      toast.error('삭제에 실패했습니다.')
    }
  }

  const handleSaveCompetitor = async () => {
    if (!selectedProfile || !competitorForm.business_name) {
      toast.error('경쟁사명을 입력해주세요.')
      return
    }

    setIsSaving(true)
    try {
      await reputationAPI.addCompetitor(selectedProfile.id, competitorForm)
      toast.success('경쟁사가 추가되었습니다.')
      setIsCompetitorDialogOpen(false)
      loadCompetitors(selectedProfile.id)
      setCompetitorForm({ business_name: '', naver_place_id: '', address: '' })
    } catch (error) {
      toast.error('경쟁사 추가에 실패했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteCompetitor = async (competitorId: string) => {
    try {
      await reputationAPI.deleteCompetitor(competitorId)
      toast.success('경쟁사가 삭제되었습니다.')
      if (selectedProfile) loadCompetitors(selectedProfile.id)
    } catch (error) {
      toast.error('삭제에 실패했습니다.')
    }
  }

  const togglePlatform = (platform: string) => {
    setProfileForm(prev => ({
      ...prev,
      enabled_platforms: prev.enabled_platforms.includes(platform)
        ? prev.enabled_platforms.filter(p => p !== platform)
        : [...prev.enabled_platforms, platform],
    }))
  }

  const severityTone = (severity: string | null): 'danger' | 'warn' | 'muted' =>
    severity === 'critical' ? 'danger' : severity === 'warning' ? 'warn' : 'muted'

  return (
    <div className="space-y-6">
      <PageHeader
        title="평판 모니터링 설정"
        description="사업장, 알림 규칙, 경쟁사를 관리합니다."
        actions={
          <Button variant="outline" size="sm" onClick={() => router.push('/dashboard/reputation')}>
            <ArrowLeft className="h-4 w-4" />
            평판 홈
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="profiles">
            <MapPin className="mr-1 h-4 w-4" />
            사업장
          </TabsTrigger>
          <TabsTrigger value="alerts">
            <Bell className="mr-1 h-4 w-4" />
            알림 규칙
          </TabsTrigger>
          <TabsTrigger value="competitors">
            <Users className="mr-1 h-4 w-4" />
            경쟁사
          </TabsTrigger>
        </TabsList>

        {/* 사업장 관리 */}
        <TabsContent value="profiles">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div>
                <CardTitle>등록된 사업장</CardTitle>
                <CardDescription className="mt-1">모니터링 중인 사업장 목록입니다.</CardDescription>
              </div>
              <Button size="sm" onClick={() => setIsProfileDialogOpen(true)}>
                <Plus className="h-4 w-4" />
                사업장 추가
              </Button>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex justify-center py-16">
                  <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
                </div>
              ) : profiles.length === 0 ? (
                <EmptyState
                  icon={<MapPin className="h-8 w-8" />}
                  title="등록된 사업장이 없습니다"
                  description="첫 사업장을 등록하면 리뷰와 멘션 수집이 시작됩니다."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setIsProfileDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      첫 사업장 등록하기
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {profiles.map(profile => (
                    <div key={profile.id} className="rounded-lg border bg-muted/40 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-2">
                          <div>
                            <h3 className="text-sm font-semibold">{profile.business_name}</h3>
                            <p className="text-[13px] text-muted-foreground">
                              {profile.business_type || '업종 미지정'} | {profile.address || '주소 미지정'}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {(profile.enabled_platforms || []).map(p => (
                              <Pill key={p} tone="accent">
                                {PLATFORM_LABELS[p as keyof typeof PLATFORM_LABELS] || p}
                              </Pill>
                            ))}
                          </div>
                          {(profile.keywords || []).length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {(profile.keywords || []).map(kw => (
                                <Pill key={kw} tone="muted">{kw}</Pill>
                              ))}
                            </div>
                          )}
                          <p className="text-xs tabular-nums text-muted-foreground">
                            수집 주기: {profile.crawl_interval_minutes}분 |
                            상태: {profile.is_active ? '활성' : '비활성'}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="shrink-0 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDeleteProfile(profile.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 알림 규칙 */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div>
                <CardTitle>알림 규칙</CardTitle>
                <CardDescription className="mt-1">
                  {selectedProfile ? `${selectedProfile.business_name}의 알림 조건입니다.` : '위험 멘션이 감지되면 알림을 받습니다.'}
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setIsAlertDialogOpen(true)} disabled={!selectedProfile}>
                <Plus className="h-4 w-4" />
                규칙 추가
              </Button>
            </CardHeader>
            <CardContent>
              {!selectedProfile ? (
                <EmptyState
                  icon={<MapPin className="h-8 w-8" />}
                  title="먼저 사업장을 등록해주세요"
                  description="알림 규칙은 등록된 사업장에 연결됩니다."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setActiveTab('profiles')}>
                      사업장 탭으로 이동
                    </Button>
                  }
                />
              ) : alertRules.length === 0 ? (
                <EmptyState
                  icon={<Bell className="h-8 w-8" />}
                  title="등록된 알림 규칙이 없습니다"
                  description="부정적 리뷰가 감지되면 즉시 알림을 받아보세요."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setIsAlertDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      첫 규칙 추가하기
                    </Button>
                  }
                />
              ) : (
                <div className="rounded-lg border">
                  {alertRules.map(rule => (
                    <ListRow key={rule.id}>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-medium">{rule.name}</h3>
                          <Pill tone={severityTone(rule.severity)}>
                            {(rule.severity && SEVERITY_LABELS[rule.severity]) || rule.severity || '-'}
                          </Pill>
                          {!rule.is_active && <Pill tone="muted">비활성</Pill>}
                        </div>
                        <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                          위험도 {rule.min_risk_score}+ |
                          {rule.notify_email && ' 이메일'}
                          {rule.notify_sms && ' SMS'}
                          {rule.notify_kakao && ' 카카오'}
                          {' | 쿨다운 '}
                          {rule.cooldown_minutes}분
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDeleteAlertRule(rule.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </ListRow>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 경쟁사 관리 */}
        <TabsContent value="competitors">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
              <div>
                <CardTitle>경쟁사</CardTitle>
                <CardDescription className="mt-1">
                  {selectedProfile ? `${selectedProfile.business_name}과 비교할 경쟁사입니다.` : '평판을 비교할 경쟁사를 등록합니다.'}
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setIsCompetitorDialogOpen(true)} disabled={!selectedProfile}>
                <Plus className="h-4 w-4" />
                경쟁사 추가
              </Button>
            </CardHeader>
            <CardContent>
              {!selectedProfile ? (
                <EmptyState
                  icon={<MapPin className="h-8 w-8" />}
                  title="먼저 사업장을 등록해주세요"
                  description="경쟁사는 등록된 사업장에 연결됩니다."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setActiveTab('profiles')}>
                      사업장 탭으로 이동
                    </Button>
                  }
                />
              ) : competitors.length === 0 ? (
                <EmptyState
                  icon={<Users className="h-8 w-8" />}
                  title="등록된 경쟁사가 없습니다"
                  description="경쟁사를 추가하면 별점과 리뷰 수를 비교할 수 있습니다."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setIsCompetitorDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      첫 경쟁사 추가하기
                    </Button>
                  }
                />
              ) : (
                <div className="rounded-lg border">
                  {competitors.map(comp => (
                    <ListRow key={comp.id}>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium">{comp.business_name}</h3>
                        <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                          {comp.address || '주소 미지정'}
                          {comp.current_rating && ` | 별점 ${comp.current_rating}`}
                          {comp.review_count > 0 && ` | 리뷰 ${comp.review_count}건`}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDeleteCompetitor(comp.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </ListRow>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 사업장 등록 다이얼로그 */}
      <Dialog open={isProfileDialogOpen} onOpenChange={setIsProfileDialogOpen}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>사업장 등록</DialogTitle>
            <DialogDescription>모니터링할 사업장 정보를 입력하세요.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>상호명 *</Label>
              <Input
                value={profileForm.business_name}
                onChange={e => setProfileForm(f => ({ ...f, business_name: e.target.value }))}
                placeholder="예: 닥터보이스 의원"
              />
            </div>

            <div className="space-y-1.5">
              <Label>업종</Label>
              <Select
                value={profileForm.business_type}
                onValueChange={v => setProfileForm(f => ({ ...f, business_type: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="업종 선택" />
                </SelectTrigger>
                <SelectContent>
                  {BUSINESS_TYPES.map(t => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>주소</Label>
              <Input
                value={profileForm.address}
                onChange={e => setProfileForm(f => ({ ...f, address: e.target.value }))}
                placeholder="서울시 강남구..."
              />
            </div>

            <div className="space-y-1.5">
              <Label>네이버 플레이스 ID</Label>
              <Input
                value={profileForm.naver_place_id}
                onChange={e => setProfileForm(f => ({ ...f, naver_place_id: e.target.value }))}
                placeholder="숫자 ID (URL에서 확인)"
              />
            </div>

            <div className="space-y-1.5">
              <Label>구글 플레이스 ID</Label>
              <Input
                value={profileForm.google_place_id}
                onChange={e => setProfileForm(f => ({ ...f, google_place_id: e.target.value }))}
                placeholder="ChIJ..."
              />
            </div>

            <div className="space-y-1.5">
              <Label>모니터링 키워드 (쉼표로 구분)</Label>
              <Input
                value={profileForm.keywords}
                onChange={e => setProfileForm(f => ({ ...f, keywords: e.target.value }))}
                placeholder="상호명, 원장님이름, 대표메뉴"
              />
            </div>

            <div className="space-y-1.5">
              <Label>부정 키워드 알림 (쉼표로 구분)</Label>
              <Input
                value={profileForm.negative_keywords}
                onChange={e => setProfileForm(f => ({ ...f, negative_keywords: e.target.value }))}
                placeholder="불친절, 비위생, 사기"
              />
            </div>

            <div className="space-y-1.5">
              <Label>모니터링 플랫폼</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                {PLATFORM_OPTIONS.map(opt => {
                  const on = profileForm.enabled_platforms.includes(opt.value)
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => togglePlatform(opt.value)}
                      className={`pill cursor-pointer border transition-colors ${
                        on ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-muted-foreground hover:bg-muted'
                      }`}
                    >
                      {opt.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>수집 주기</Label>
              <Select
                value={String(profileForm.crawl_interval_minutes)}
                onValueChange={v => setProfileForm(f => ({ ...f, crawl_interval_minutes: Number(v) }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="30">30분</SelectItem>
                  <SelectItem value="60">1시간</SelectItem>
                  <SelectItem value="120">2시간</SelectItem>
                  <SelectItem value="360">6시간</SelectItem>
                  <SelectItem value="720">12시간</SelectItem>
                  <SelectItem value="1440">24시간</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>알림 이메일</Label>
              <Input
                type="email"
                value={profileForm.alert_email}
                onChange={e => setProfileForm(f => ({ ...f, alert_email: e.target.value }))}
                placeholder="alert@example.com"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsProfileDialogOpen(false)}>취소</Button>
            <Button onClick={handleSaveProfile} disabled={isSaving}>
              {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
              등록
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 알림 규칙 추가 다이얼로그 */}
      <Dialog open={isAlertDialogOpen} onOpenChange={setIsAlertDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>알림 규칙 추가</DialogTitle>
            <DialogDescription>위험 멘션 감지 시 알림을 받을 조건을 설정하세요.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>규칙 이름 *</Label>
              <Input
                value={alertForm.name}
                onChange={e => setAlertForm(f => ({ ...f, name: e.target.value }))}
                placeholder="예: 별점 2점 이하 즉시 알림"
              />
            </div>

            <div className="space-y-1.5">
              <Label>심각도</Label>
              <Select
                value={alertForm.severity}
                onValueChange={v => setAlertForm(f => ({ ...f, severity: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">긴급 (즉시 알림)</SelectItem>
                  <SelectItem value="warning">주의 (30분 내)</SelectItem>
                  <SelectItem value="info">정보 (다이제스트)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>최소 위험도 점수 (0-100)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={alertForm.min_risk_score}
                onChange={e => setAlertForm(f => ({ ...f, min_risk_score: Number(e.target.value) }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>쿨다운 (분)</Label>
              <Input
                type="number"
                min={5}
                value={alertForm.cooldown_minutes}
                onChange={e => setAlertForm(f => ({ ...f, cooldown_minutes: Number(e.target.value) }))}
              />
            </div>

            <div className="space-y-2">
              <Label>알림 채널</Label>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <Switch
                    checked={alertForm.notify_email}
                    onCheckedChange={v => setAlertForm(f => ({ ...f, notify_email: v }))}
                  />
                  이메일
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch
                    checked={alertForm.notify_sms}
                    onCheckedChange={v => setAlertForm(f => ({ ...f, notify_sms: v }))}
                  />
                  SMS
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch
                    checked={alertForm.notify_kakao}
                    onCheckedChange={v => setAlertForm(f => ({ ...f, notify_kakao: v }))}
                  />
                  카카오
                </label>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAlertDialogOpen(false)}>취소</Button>
            <Button onClick={handleSaveAlertRule} disabled={isSaving}>
              {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
              생성
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 경쟁사 추가 다이얼로그 */}
      <Dialog open={isCompetitorDialogOpen} onOpenChange={setIsCompetitorDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>경쟁사 추가</DialogTitle>
            <DialogDescription>평판을 비교할 경쟁사를 추가하세요.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>경쟁사명 *</Label>
              <Input
                value={competitorForm.business_name}
                onChange={e => setCompetitorForm(f => ({ ...f, business_name: e.target.value }))}
                placeholder="경쟁사 상호명"
              />
            </div>
            <div className="space-y-1.5">
              <Label>네이버 플레이스 ID</Label>
              <Input
                value={competitorForm.naver_place_id}
                onChange={e => setCompetitorForm(f => ({ ...f, naver_place_id: e.target.value }))}
                placeholder="숫자 ID"
              />
            </div>
            <div className="space-y-1.5">
              <Label>주소</Label>
              <Input
                value={competitorForm.address}
                onChange={e => setCompetitorForm(f => ({ ...f, address: e.target.value }))}
                placeholder="주소"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCompetitorDialogOpen(false)}>취소</Button>
            <Button onClick={handleSaveCompetitor} disabled={isSaving}>
              {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
              추가
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
