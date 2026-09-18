'use client'

import { DIACRANKAnalysis } from '@/types'
import { TrendingUp, Award, Info } from 'lucide-react'
import { Pill } from '@/components/app-shell/ui-kit'

interface DIACRANKScoreProps {
  analysis: DIACRANKAnalysis
}

const getScoreTextColor = (score: number) => {
  if (score >= 80) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

const getGradeTone = (grade: string): 'ok' | 'warn' | 'accent' | 'muted' => {
  if (grade === 'S' || grade === 'A+' || grade === 'A') return 'accent'
  if (grade === 'B+' || grade === 'B') return 'ok'
  return 'muted'
}

export function DIACRANKScore({ analysis }: DIACRANKScoreProps) {
  return (
    <div className="space-y-6">
      {/* 전체 등급 */}
      <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/40 p-4">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2">
            <Award className="h-4 w-4 text-primary" />
            <span className="text-[13px] font-medium text-muted-foreground">전체 등급</span>
          </div>
          <p className="text-sm text-foreground">{analysis.summary}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Pill tone={getGradeTone(analysis.overall_grade)} className="px-3 py-1 text-lg font-semibold">
            {analysis.overall_grade}
          </Pill>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            {analysis.estimated_ranking}
          </div>
        </div>
      </div>

      {/* DIA 점수 */}
      <div>
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <span>DIA 점수</span>
          <span className={`text-base font-semibold tabular-nums ${getScoreTextColor(analysis.dia_score.total)}`}>
            {analysis.dia_score.total}점
          </span>
        </h4>
        <div className="space-y-3">
          {/* 경험 정보 */}
          <ScoreItem
            label="경험 정보"
            score={analysis.dia_score.experience.score}
            analysis={analysis.dia_score.experience.analysis}
            suggestions={analysis.dia_score.experience.suggestions}
          />
          {/* 정보성 */}
          <ScoreItem
            label="정보성"
            score={analysis.dia_score.information.score}
            analysis={analysis.dia_score.information.analysis}
            suggestions={analysis.dia_score.information.suggestions}
          />
          {/* 독창성 */}
          <ScoreItem
            label="독창성"
            score={analysis.dia_score.originality.score}
            analysis={analysis.dia_score.originality.analysis}
            suggestions={analysis.dia_score.originality.suggestions}
          />
          {/* 적시성 */}
          <ScoreItem
            label="적시성"
            score={analysis.dia_score.timeliness.score}
            analysis={analysis.dia_score.timeliness.analysis}
            suggestions={analysis.dia_score.timeliness.suggestions}
          />
        </div>
      </div>

      {/* CRANK 점수 */}
      <div>
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <span>C-RANK 점수</span>
          <span className={`text-base font-semibold tabular-nums ${getScoreTextColor(analysis.crank_score.total)}`}>
            {analysis.crank_score.total}점
          </span>
        </h4>
        <div className="space-y-3">
          {/* Context */}
          <ScoreItem
            label="Context (주제 집중도)"
            score={analysis.crank_score.context.score}
            analysis={analysis.crank_score.context.analysis}
            suggestions={analysis.crank_score.context.suggestions}
          />
          {/* Content */}
          <ScoreItem
            label="Content (콘텐츠 품질)"
            score={analysis.crank_score.content.score}
            analysis={analysis.crank_score.content.analysis}
            suggestions={analysis.crank_score.content.suggestions}
          />
          {/* Chain */}
          <ScoreItem
            label="Chain (참여도)"
            score={analysis.crank_score.chain.score}
            analysis={analysis.crank_score.chain.analysis}
            suggestions={analysis.crank_score.chain.suggestions}
          />
          {/* Creator */}
          <ScoreItem
            label="Creator (작성자 신뢰도)"
            score={analysis.crank_score.creator.score}
            analysis={analysis.crank_score.creator.analysis}
            suggestions={analysis.crank_score.creator.suggestions}
          />
        </div>
      </div>
    </div>
  )
}

interface ScoreItemProps {
  label: string
  score: number
  analysis: string
  suggestions: string[]
}

function ScoreItem({ label, score, analysis, suggestions }: ScoreItemProps) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
        <span className={`text-sm font-semibold tabular-nums ${getScoreTextColor(score)}`}>{score}점</span>
      </div>
      <div className="relative mb-2 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-all duration-300"
          style={{ width: `${score}%` }}
        />
      </div>
      <p className="mb-2 text-xs text-muted-foreground">{analysis}</p>
      {suggestions.length > 0 && (
        <div className="mt-2 border-t pt-2">
          <div className="flex items-start gap-1.5">
            <Info className="mt-0.5 h-3 w-3 flex-shrink-0 text-primary" />
            <div className="space-y-1 text-xs text-muted-foreground">
              {suggestions.map((suggestion, idx) => (
                <div key={idx}>• {suggestion}</div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
