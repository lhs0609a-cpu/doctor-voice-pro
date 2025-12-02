'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Slider } from '@/components/ui/slider'
import type { CafeReviewInput, CafeReviewStyle } from '@/types'
import { ReviewStyleConfig } from './review-style-config'
import { Loader2, Sparkles, Coffee, FileDown, FileText, Copy, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'
import { postsAPI } from '@/lib/api'
import { Document, Paragraph, TextRun, Packer } from 'docx'
import { saveAs } from 'file-saver'

export function CafeReviewCreator() {
  const [loading, setLoading] = useState(false)
  const [reviewInput, setReviewInput] = useState<CafeReviewInput>({
    hospital_name: '',
    visit_purpose: '',
    experience_content: '',
    emphasis_points: '',
    target_length: 800,
  })
  const [generateCount, setGenerateCount] = useState(1)
  const [generatedReviews, setGeneratedReviews] = useState<string[]>([])
  const [selectedReviewIndex, setSelectedReviewIndex] = useState(0)
  const [reviewStyle, setReviewStyle] = useState<CafeReviewStyle>({
    friendliness: 8,
    emotion: 7,
    humor: 6,
    colloquial: 8,
    emoji_usage: 5,
    detail_level: 7,
    honesty: 6,
  })
  const [writingPerspective, setWritingPerspective] = useState('1인칭')
  const [generatedReview, setGeneratedReview] = useState<string>('')
  const [copied, setCopied] = useState(false)
  // AI 제공자 및 모델 선택 (GPT만 사용)
  const [aiProvider] = useState('gpt')
  const [aiModel, setAiModel] = useState('gpt-4o-mini')

  const handleGenerate = async () => {
    // 입력 검증 (최소 글자수 제한 제거, 간단한 키워드만 있어도 OK)
    if (!reviewInput.hospital_name.trim()) {
      toast.error('병원 이름을 입력해주세요')
      return
    }
    if (!reviewInput.visit_purpose.trim()) {
      toast.error('방문 목적을 입력해주세요')
      return
    }
    if (!reviewInput.experience_content.trim() || reviewInput.experience_content.length < 10) {
      toast.error('경험 내용을 최소 10자 이상 입력해주세요 (짧아도 괜찮습니다!)')
      return
    }

    setLoading(true)
    const loadingToast = toast.loading(`AI가 카페 바이럴 후기 ${generateCount}개를 생성하고 있습니다... (0/${generateCount})`)

    try {
      const results: string[] = []

      // 배치 처리 (3개씩)
      const BATCH_SIZE = 3
      for (let batchStart = 0; batchStart < generateCount; batchStart += BATCH_SIZE) {
        const batchEnd = Math.min(batchStart + BATCH_SIZE, generateCount)
        const batchSize = batchEnd - batchStart

        toast.loading(`AI가 카페 바이럴 후기를 생성하고 있습니다... (${batchStart}/${generateCount})`, {
          id: loadingToast,
        })

        // 현재 배치의 요청들을 병렬로 실행
        const batchPromises = Array.from({ length: batchSize }, async (_, i) => {
          const globalIndex = batchStart + i

          // 백엔드 API 호출
          const cafeReviewPrompt = buildCafeReviewPrompt()

          const post = await postsAPI.create({
            original_content: cafeReviewPrompt,
            persuasion_level: Math.min(5, Math.max(1, Math.round((reviewStyle.emotion + reviewStyle.friendliness) / 2))),
            framework: '경험공유형',
            target_length: reviewInput.target_length || 800,
            writing_perspective: writingPerspective,
            ai_provider: aiProvider,
            ai_model: aiModel,
            writing_style: {
              formality: 10 - reviewStyle.friendliness,
              friendliness: reviewStyle.friendliness,
              technical_depth: 3,
              storytelling: reviewStyle.detail_level,
              emotion: reviewStyle.emotion,
              humor: reviewStyle.humor,
              question_usage: 5,
              metaphor_usage: 4,
              sentence_length: reviewStyle.colloquial > 7 ? 4 : 6,
            },
            requirements: {
              common: [
                '🔥 실제 카페 회원이 급하게 쓴 것처럼 자연스럽고 비격식적으로 작성',
                '의료법 준수 (효과 과장 금지)',
                '개인적인 경험과 느낌을 구어체로 표현',
                '❌ 절대 소제목 사용 금지 (예: "왜 이런 증상이 생길까요?", "어떻게 관리하면 좋을까요?" 같은 제목 형식 절대 사용하지 말 것)',
                '❌ 문단 구분이나 섹션 나누기 없이 자연스럽게 흐름대로 작성',
                '이모티콘 적극 사용: ㅋㅋ, ㅎㅎ, ㅠㅠ, ^^, ㅜㅜ, !! 등을 문장 곳곳에 자연스럽게 배치',
                '말줄임표(...) 자주 사용하여 생각하는 느낌 표현',
                '느낌표(!!)를 과도하게 사용해서 감정 표현',
                reviewStyle.honesty > 6 ? '작은 단점이나 아쉬움도 솔직하게 언급 (근데... 이건 좀 아쉬웠어요ㅠㅠ)' : '긍정적인 면 강조하되 과장은 금지',
                '구어체 표현 적극 사용: "진짜", "완전", "대박", "헐", "와", "짱", "엄청", "개" 등',
                '띄어쓰기가 일부 불규칙하거나 붙여쓰기도 자연스럽게',
                '자연스러운 오타 1-2개 포함 (예: "넘 좋아요", "안됬어요" → "안됐어요" 대신 오타, "됬다" 등)',
                '문장이 완벽하게 끝나지 않고 말을 흐리는 표현도 사용',
                '구체적인 디테일 포함 (시간, 장소, 대화 등)',
                '사용자가 입력한 간단한 키워드나 내용을 풍부하게 확장하여 작성',
              ],
              individual: `진짜 카페에 급하게 올리는 바이럴 후기 스타일로 작성. 절대 소제목이나 구조화된 형식 사용하지 말고, 그냥 이야기하듯이 쭉 이어서 쓰기. 너무 정제되거나 진지하지 않게, 친구한테 얘기하듯이 편하게 쓰기. ${reviewInput.emphasis_points ? `특히 강조할 점: ${reviewInput.emphasis_points}` : ''}`,
            },
          })

          if (!post.generated_content) {
            throw new Error('후기 생성 실패')
          }

          // 이모티콘 추가 처리
          let finalContent = post.generated_content
          if (reviewStyle.emoji_usage > 7) {
            finalContent = addEmojisToContent(finalContent)
          }

          toast.loading(`AI가 카페 바이럴 후기를 생성하고 있습니다... (${globalIndex + 1}/${generateCount})`, {
            id: loadingToast,
          })

          return finalContent
        })

        const batchResults = await Promise.all(batchPromises)
        results.push(...batchResults)

        // 다음 배치 전에 짧은 딜레이
        if (batchEnd < generateCount) {
          await new Promise(resolve => setTimeout(resolve, 1000))
        }
      }

      setGeneratedReviews(results)
      setGeneratedReview(results[0])
      setSelectedReviewIndex(0)

      toast.success(`카페 바이럴 후기 ${generateCount}개 생성 완료!`, { id: loadingToast })
    } catch (error: any) {
      console.error('Generation error:', error)
      toast.error('후기 생성 실패', {
        id: loadingToast,
        description: error.message || error.response?.data?.detail || '오류가 발생했습니다'
      })
    } finally {
      setLoading(false)
    }
  }

  const buildCafeReviewPrompt = () => {
    return `
[카페 바이럴 후기 작성 요청]

병원명: ${reviewInput.hospital_name}
방문 목적: ${reviewInput.visit_purpose}

[나의 경험 (간단한 키워드/메모)]
${reviewInput.experience_content}

${reviewInput.emphasis_points ? `[특히 강조하고 싶은 점]\n${reviewInput.emphasis_points}` : ''}

**🔥 핵심 스타일 가이드**:
- 네이버 카페나 맘카페에 올리는 실제 후기처럼 작성
- 너무 정제되거나 문법이 완벽하면 안됨! 급하게 쓴 느낌으로
- ❌ **절대 소제목 사용 금지!** ("왜 이런 증상이 생길까요?", "어떻게 관리하면 좋을까요?" 같은 제목 형식 절대 안됨)
- ❌ **문단 구분이나 섹션 나누지 말고 쭉 이어서 작성**
- 이모티콘 필수 사용: ㅋㅋ, ㅎㅎ, ㅠㅠ, ^^, ㅜㅜ, !!, ... 등
- 구어체 적극 사용: "진짜", "완전", "대박", "헐", "와", "짱", "넘", "엄청" 등
- 자연스러운 오타 1-2개 포함 (예: "됬어요", "넘좋아요", "되게" → "되게" 등)
- 띄어쓰기 일부러 틀리거나 붙여쓰기
- 말줄임표(...) 자주 사용
- 느낌표 과다 사용(!!!)
- 문장이 완벽하게 끝나지 않고 흐려지는 표현도 OK

**작성 방법**:
1. 실제 방문 경험처럼 구체적인 디테일 추가 (시간, 위치, 대화 내용 등)
2. 감정 변화를 솔직하게 표현 (처음엔 걱정했는데... 근데 가보니까...!)
3. 친구한테 얘기하듯이 편하고 자연스럽게
4. 완벽한 문장 구조보다는 생각나는대로 쓴 느낌으로

위 가이드를 반드시 따라서 진짜 사람이 급하게 쓴 것 같은 자연스러운 카페 후기를 작성해주세요.
    `.trim()
  }

  const addEmojisToContent = (content: string): string => {
    // 간단한 이모티콘 추가 로직 (감정 표현 위치에)
    const emojiMap: Record<string, string[]> = {
      '좋': ['👍', '😊', '💕'],
      '만족': ['😍', '🥰', '✨'],
      '추천': ['👏', '💯', '⭐'],
      '감사': ['🙏', '💖', '😌'],
      '놀라': ['😲', '🤩', '✨'],
    }

    let result = content
    for (const [keyword, emojis] of Object.entries(emojiMap)) {
      const regex = new RegExp(`(${keyword}[^\\s]{0,3})`, 'g')
      let count = 0
      result = result.replace(regex, (match) => {
        if (count++ % 3 === 0) { // 3번에 1번만 추가
          const randomEmoji = emojis[Math.floor(Math.random() * emojis.length)]
          return `${match} ${randomEmoji}`
        }
        return match
      })
    }
    return result
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(generatedReview)
      setCopied(true)
      toast.success('클립보드에 복사되었습니다')
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      toast.error('복사 실패')
    }
  }

  const handleDownloadText = () => {
    try {
      const blob = new Blob([generatedReview], { type: 'text/plain;charset=utf-8' })
      const fileName = `카페후기_${reviewInput.hospital_name}_${new Date().toISOString().slice(0, 10)}.txt`
      saveAs(blob, fileName)
      toast.success('텍스트 파일 다운로드 완료')
    } catch (error) {
      toast.error('텍스트 파일 다운로드 실패')
    }
  }

  const handleDownloadWord = async () => {
    try {
      const paragraphs = generatedReview.split('\n').map(para =>
        new Paragraph({
          children: [new TextRun({ text: para || ' ', size: 22 })],
          spacing: { after: 200 },
        })
      )

      const doc = new Document({
        sections: [{
          properties: {},
          children: [
            new Paragraph({
              children: [new TextRun({
                text: `${reviewInput.hospital_name} 방문 후기`,
                bold: true,
                size: 32
              })],
              spacing: { after: 400 },
            }),
            ...paragraphs
          ],
        }],
      })

      const blob = await Packer.toBlob(doc)
      const fileName = `카페후기_${reviewInput.hospital_name}_${new Date().toISOString().slice(0, 10)}.docx`
      saveAs(blob, fileName)
      toast.success('Word 파일 다운로드 완료')
    } catch (error) {
      toast.error('Word 파일 다운로드 실패')
    }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      {/* 입력 섹션 */}
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Coffee className="h-5 w-5 text-amber-600" />
              카페 바이럴 후기 정보
            </CardTitle>
            <CardDescription>
              실제 경험을 바탕으로 입력하세요
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="hospital_name">병원 이름 *</Label>
              <Input
                id="hospital_name"
                placeholder="예: ○○피부과의원"
                value={reviewInput.hospital_name}
                onChange={(e) => setReviewInput({ ...reviewInput, hospital_name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="visit_purpose">방문 목적 (치료/시술) *</Label>
              <Input
                id="visit_purpose"
                placeholder="예: 아토피 치료, 레이저 시술, 피부 관리 등"
                value={reviewInput.visit_purpose}
                onChange={(e) => setReviewInput({ ...reviewInput, visit_purpose: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="experience_content">
                경험 내용 * (간단히 적어도 OK!)
              </Label>
              <Textarea
                id="experience_content"
                placeholder="간단한 키워드나 메모만 적어도 됩니다! AI가 자동으로 풍부하게 확장합니다.

예시 (간단히):
- 피부 건조, 가려움 심함
- 지인 추천으로 방문
- 선생님 꼼꼼한 진료, 생활습관 조언
- 2주 후 많이 좋아짐

또는 (상세히):
피부가 너무 건조하고 가려워서 고민하다가 지인 추천으로 방문했어요. 처음엔 걱정했는데, 선생님이 꼼꼼하게 진료해주시고 생활 습관까지 알려주셔서 좋았어요. 치료 받은 지 2주 정도 됐는데 확실히 좋아진 게 느껴져요."
                className="min-h-[200px] resize-none"
                value={reviewInput.experience_content}
                onChange={(e) => setReviewInput({ ...reviewInput, experience_content: e.target.value })}
              />
              <div className="text-sm text-muted-foreground">
                {reviewInput.experience_content.length}자 / 최소 10자 (짧아도 괜찮습니다!)
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="emphasis_points">강조하고 싶은 포인트 (선택)</Label>
              <Input
                id="emphasis_points"
                placeholder="예: 의료진 친절함, 깨끗한 시설, 합리적 가격 등"
                value={reviewInput.emphasis_points}
                onChange={(e) => setReviewInput({ ...reviewInput, emphasis_points: e.target.value })}
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>목표 글자수</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={300}
                    max={2500}
                    step={50}
                    value={reviewInput.target_length}
                    onChange={(e) => {
                      const value = parseInt(e.target.value) || 300
                      const clampedValue = Math.max(300, Math.min(2500, value))
                      setReviewInput({ ...reviewInput, target_length: clampedValue })
                    }}
                    className="w-24 h-8 text-sm"
                  />
                  <span className="text-sm text-muted-foreground">자</span>
                </div>
              </div>
              <Slider
                value={[reviewInput.target_length || 800]}
                onValueChange={(value) => setReviewInput({ ...reviewInput, target_length: value[0] })}
                min={300}
                max={2500}
                step={50}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>300자 (짧게)</span>
                <span>1400자 (보통)</span>
                <span>2500자 (길게)</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>작성 시점</Label>
              <div className="grid grid-cols-3 gap-2">
                {['1인칭', '3인칭', '대화형'].map((perspective) => (
                  <Button
                    key={perspective}
                    variant={writingPerspective === perspective ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setWritingPerspective(perspective)}
                  >
                    {perspective}
                  </Button>
                ))}
              </div>
            </div>

            {/* GPT 모델 선택 */}
            <div className="space-y-2 pt-4 border-t">
              <Label>GPT 모델 선택</Label>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant={aiModel === 'gpt-4o-mini' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAiModel('gpt-4o-mini')}
                >
                  GPT-4o Mini (빠름)
                </Button>
                <Button
                  variant={aiModel === 'gpt-4o' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAiModel('gpt-4o')}
                >
                  GPT-4o (고품질)
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>생성 개수 (다양한 버전 생성)</Label>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((count) => (
                  <Button
                    key={count}
                    variant={generateCount === count ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setGenerateCount(count)}
                  >
                    {count}개
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                여러 버전을 생성하여 가장 마음에 드는 후기를 선택하세요
              </p>
            </div>

            <Button
              className="w-full gap-2"
              size="lg"
              onClick={handleGenerate}
              disabled={loading || !reviewInput.hospital_name || !reviewInput.visit_purpose || reviewInput.experience_content.length < 10}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  AI 생성 중... ({generateCount}개)
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  카페 후기 {generateCount}개 생성하기
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        <ReviewStyleConfig value={reviewStyle} onChange={setReviewStyle} />
      </div>

      {/* 출력 섹션 */}
      <div className="space-y-6">
        {!generatedReview ? (
          <Card className="border-dashed">
            <CardContent className="pt-6">
              <div className="text-center py-12 text-muted-foreground">
                <Coffee className="h-12 w-12 mx-auto mb-3 text-amber-300" />
                <p>정보를 입력하고 생성하기를 눌러주세요</p>
                <p className="text-sm mt-2">AI가 자연스러운 카페 후기를 작성합니다</p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* 여러 버전 선택 UI */}
            {generatedReviews.length > 1 && (
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Label className="text-sm font-medium">생성된 버전 선택</Label>
                    <span className="text-xs text-muted-foreground">({generatedReviews.length}개)</span>
                  </div>
                  <div className="grid grid-cols-5 gap-2">
                    {generatedReviews.map((_, index) => (
                      <Button
                        key={index}
                        variant={selectedReviewIndex === index ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => {
                          setSelectedReviewIndex(index)
                          setGeneratedReview(generatedReviews[index])
                        }}
                      >
                        버전 {index + 1}
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  생성된 카페 후기
                  {generatedReviews.length > 1 && (
                    <span className="text-sm font-normal text-muted-foreground">
                      (버전 {selectedReviewIndex + 1}/{generatedReviews.length})
                    </span>
                  )}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopy}
                      className="gap-2"
                    >
                      {copied ? (
                        <>
                          <CheckCircle2 className="h-4 w-4" />
                          복사됨
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4" />
                          복사
                        </>
                      )}
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
              <div className="prose prose-sm max-w-none">
                <div className="whitespace-pre-wrap text-sm leading-relaxed max-h-[500px] overflow-y-auto border rounded-md p-4 bg-amber-50">
                  {generatedReview}
                </div>
              </div>

              <div className="text-xs text-muted-foreground pt-2">
                글자수: {generatedReview.length}자
              </div>

              <div className="grid grid-cols-2 gap-2 pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={handleDownloadWord}
                  className="gap-2"
                >
                  <FileDown className="h-4 w-4" />
                  Word 저장
                </Button>
                <Button
                  variant="outline"
                  onClick={handleDownloadText}
                  className="gap-2"
                >
                  <FileText className="h-4 w-4" />
                  텍스트 저장
                </Button>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-xs space-y-1">
                <p className="font-medium text-blue-900">💡 카페 게시 팁</p>
                <ul className="text-blue-700 space-y-0.5 pl-4">
                  <li>• 제목은 짧고 흥미롭게 (예: "○○피부과 다녀왔어요!")</li>
                  <li>• 사진이 있으면 신뢰도가 훨씬 높아집니다</li>
                  <li>• 댓글에 친절하게 답변하면 더 자연스러워요</li>
                  <li>• 의료법 위반 표현이 없는지 한 번 더 확인하세요</li>
                </ul>
              </div>
            </CardContent>
          </Card>
          </>
        )}
      </div>
    </div>
  )
}
