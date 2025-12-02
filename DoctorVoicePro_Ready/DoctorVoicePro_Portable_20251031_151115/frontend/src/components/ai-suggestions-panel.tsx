'use client'

import { useState } from 'react'
import { postsAPIExtended } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { Sparkles, Loader2, ThumbsUp, AlertTriangle, Lightbulb } from 'lucide-react'

interface AISuggestionsProps {
  postId: string
}

interface Suggestion {
  overall_assessment: string
  strengths: string[]
  improvements: Array<{ title: string; description: string }>
  tone_suggestions: string
  seo_suggestions: string[]
}

export function AISuggestionsPanel({ postId }: AISuggestionsProps) {
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<Suggestion | null>(null)

  const loadSuggestions = async () => {
    try {
      setLoading(true)
      const data = await postsAPIExtended.getSuggestions(postId)
      setSuggestions(data)
    } catch (error) {
      toast.error('AI 제안 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  if (!suggestions && !loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <Sparkles className="h-12 w-12 mx-auto mb-4 text-blue-500" />
            <h3 className="text-lg font-semibold mb-2">AI 개선 제안</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Claude AI가 포스팅을 분석하여 개선 제안을 제공합니다
            </p>
            <Button onClick={loadSuggestions} className="gap-2">
              <Sparkles className="h-4 w-4" />
              제안 받기
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-12">
            <Loader2 className="h-12 w-12 mx-auto mb-4 animate-spin text-blue-500" />
            <p className="text-sm text-muted-foreground">
              AI가 포스팅을 분석하고 있습니다...
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Overall Assessment */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-600" />
            전체 평가
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{suggestions?.overall_assessment}</p>
        </CardContent>
      </Card>

      {/* Strengths */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ThumbsUp className="h-5 w-5 text-green-600" />
            강점
          </CardTitle>
          <CardDescription>이 포스팅의 우수한 점들</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {suggestions?.strengths.map((strength, index) => (
              <li key={index} className="flex items-start gap-2">
                <Badge variant="outline" className="mt-0.5">
                  {index + 1}
                </Badge>
                <span className="text-sm flex-1">{strength}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Improvements */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            개선 사항
          </CardTitle>
          <CardDescription>더 나은 포스팅을 위한 제안</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {suggestions?.improvements.map((improvement, index) => (
            <div key={index} className="border-l-4 border-orange-500 pl-4 py-2">
              <h4 className="font-semibold text-sm mb-1">{improvement.title}</h4>
              <p className="text-sm text-muted-foreground">{improvement.description}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Tone Suggestions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-yellow-600" />
            어조 & 스타일 제안
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{suggestions?.tone_suggestions}</p>
        </CardContent>
      </Card>

      {/* SEO Suggestions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-blue-600" />
            SEO 개선 제안
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {suggestions?.seo_suggestions.map((suggestion, index) => (
              <li key={index} className="flex items-start gap-2">
                <Badge variant="outline" className="mt-0.5">
                  {index + 1}
                </Badge>
                <span className="text-sm flex-1">{suggestion}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Button variant="outline" onClick={loadSuggestions} className="w-full gap-2">
        <Sparkles className="h-4 w-4" />
        새로 분석하기
      </Button>
    </div>
  )
}
