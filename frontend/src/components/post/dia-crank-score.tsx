'use client'

import { DIACRANKAnalysis } from '@/types'
import { TrendingUp, Award, Info } from 'lucide-react'

interface DIACRANKScoreProps {
  analysis: DIACRANKAnalysis
}

export function DIACRANKScore({ analysis }: DIACRANKScoreProps) {
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600'
    if (score >= 80) return 'text-blue-600'
    if (score >= 70) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getGradeColor = (grade: string) => {
    if (grade === 'S' || grade === 'A+') return 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
    if (grade === 'A') return 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white'
    if (grade === 'B+' || grade === 'B') return 'bg-gradient-to-r from-green-600 to-emerald-600 text-white'
    return 'bg-gray-500 text-white'
  }

  return (
    <div className="space-y-6">
      {/* 전체 등급 */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg border border-blue-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Award className="h-5 w-5 text-purple-600" />
            <span className="text-sm font-semibold text-gray-700">전체 등급</span>
          </div>
          <p className="text-xs text-gray-600">{analysis.summary}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className={`px-4 py-2 rounded-full font-bold text-2xl ${getGradeColor(analysis.overall_grade)}`}>
            {analysis.overall_grade}
          </div>
          <div className="text-xs text-gray-600 flex items-center gap-1">
            <TrendingUp className="h-3 w-3" />
            {analysis.estimated_ranking}
          </div>
        </div>
      </div>

      {/* DIA 점수 */}
      <div>
        <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <span className="text-blue-600">📊 DIA 점수</span>
          <span className={`text-lg font-bold ${getScoreColor(analysis.dia_score.total)}`}>
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
        <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <span className="text-purple-600">📈 C-RANK 점수</span>
          <span className={`text-lg font-bold ${getScoreColor(analysis.crank_score.total)}`}>
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
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'bg-green-500'
    if (score >= 80) return 'bg-blue-500'
    if (score >= 70) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getTextColor = (score: number) => {
    if (score >= 90) return 'text-green-600'
    if (score >= 80) return 'text-blue-600'
    if (score >= 70) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-bold ${getTextColor(score)}`}>{score}점</span>
      </div>
      <div className="relative w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full ${getScoreColor(score)} transition-all duration-300`}
          style={{ width: `${score}%` }}
        />
      </div>
      <p className="text-xs text-gray-600 mb-2">{analysis}</p>
      {suggestions.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-200">
          <div className="flex items-start gap-1">
            <Info className="h-3 w-3 text-blue-500 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-gray-600 space-y-1">
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
