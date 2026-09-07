'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'

type AxisDetail = {
  score: number
  max: number
  notes?: string[]
  why?: string
  fix?: string
  // 신뢰 축의 근거 인용 항목에만 붙는다
  citations?: string[]
  unverified_citations?: string[]
}

type Axis = {
  score: number
  max: number
  details: Record<string, AxisDetail>
}

type Violation = {
  severity: 'critical' | 'high' | 'medium'
  clause: string
  message: string
  fix: string
  samples: string[]
}

export type QualityReport = {
  total: number
  raw_total?: number
  grade: 'A' | 'B' | 'C' | 'D'
  capped_by_law: boolean
  score_cap: number
  judged_by_llm: boolean
  law: {
    passed: boolean
    violations: Violation[]
    counts: { critical: number; high: number; medium: number }
  }
  engagement: Axis
  understandability: Axis
  actionability: Axis
  trust: Axis
  differentiation: Axis
  naver_fit: Axis
  llm_judge: Axis | null
}

const AXIS_LABELS: Record<string, string> = {
  engagement: '몰입·공감',
  understandability: '이해도',
  actionability: '행동가능성',
  trust: '신뢰',
  differentiation: '차별화',
  naver_fit: '네이버 적합도',
  llm_judge: 'AI 심사',
}

const METRIC_LABELS: Record<string, string> = {
  // 몰입·공감
  hook: '첫 문단 후킹',
  self_reference: '독자 지목',
  narrative: '장면 전개',
  rhythm: '문체 리듬',
  // 이해도 (PEMAT)
  plain_language: '쉬운 말',
  active_voice: '능동태',
  chunking: '문장·문단 길이',
  informative_headers: '소제목 정보성',
  // 행동가능성 (PEMAT)
  concrete_actions: '구체적 행동',
  steps: '단계·빈도',
  when_to_visit: '병원 방문 기준',
  // 신뢰
  evidence: '근거 인용',
  two_sided: '한계 인정 + 대응',
  threat_efficacy: '위협/해결책 균형',
  naturalness: '자연스러움',
  // 네이버
  length: '분량',
  topic_focus: '주제 집중도',
  concreteness: '구체 정보',
  // AI 심사
  originality: '독창성',
  experience: '경험 디테일',
  intent: '검색 의도 충족',
  heading_fit: '소제목 정합',
  differentiation: '이 병원만의 것',
}

const SEVERITY_LABELS: Record<string, string> = {
  critical: '위반',
  high: '위반 소지 큼',
  medium: '지적 가능',
}

function gradeStyle(grade: string) {
  switch (grade) {
    case 'A':
      return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
    case 'B':
      return 'bg-sky-500/10 text-sky-600 border-sky-500/30'
    case 'C':
      return 'bg-amber-500/10 text-amber-600 border-amber-500/30'
    default:
      return 'bg-red-500/10 text-red-600 border-red-500/30'
  }
}

function barColor(ratio: number) {
  if (ratio >= 0.85) return 'bg-emerald-500'
  if (ratio >= 0.65) return 'bg-sky-500'
  if (ratio >= 0.45) return 'bg-amber-500'
  return 'bg-red-500'
}

function AxisBlock({ name, axis }: { name: string; axis: Axis }) {
  const ratio = axis.max > 0 ? axis.score / axis.max : 0
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{AXIS_LABELS[name] ?? name}</span>
        <span className="tabular-nums text-muted-foreground">
          {axis.score} / {axis.max}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full', barColor(ratio))} style={{ width: `${ratio * 100}%` }} />
      </div>
      <ul className="space-y-1.5 pl-1">
        {Object.entries(axis.details).map(([key, d]) => {
          const r = d.max > 0 ? d.score / d.max : 0
          const weak = r < 0.8
          return (
            <li key={key} className="text-xs">
              <div className="flex items-center justify-between">
                <span className={cn(weak ? 'text-foreground' : 'text-muted-foreground')}>
                  {METRIC_LABELS[key] ?? key}
                </span>
                <span className={cn('tabular-nums', weak ? 'text-amber-600' : 'text-muted-foreground')}>
                  {d.score}/{d.max}
                </span>
              </div>
              {(d.notes ?? []).map((n, i) => (
                <p key={i} className="mt-0.5 pl-2 text-[11px] leading-snug text-muted-foreground">
                  · {n}
                </p>
              ))}
              {d.why && (
                <p className="mt-0.5 pl-2 text-[11px] leading-snug text-muted-foreground">· {d.why}</p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function QualityScore({ report }: { report: QualityReport | null | undefined }) {
  const [open, setOpen] = useState(false)

  if (!report) return null

  const { law } = report
  const hasBlocking = law.counts.critical > 0 || law.counts.high > 0

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'flex h-14 w-14 flex-none flex-col items-center justify-center rounded-lg border',
            gradeStyle(report.grade)
          )}
        >
          <span className="text-lg font-bold leading-none tabular-nums">{Math.round(report.total)}</span>
          <span className="text-[10px] font-semibold leading-none opacity-80">{report.grade}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">원고 품질 점수</p>
          <p className="text-xs text-muted-foreground">
            {report.capped_by_law
              ? `의료광고법 위반으로 ${report.score_cap}점 상한이 걸렸습니다`
              : report.grade === 'A'
              ? '바로 발행해도 좋은 수준입니다'
              : report.grade === 'B'
              ? '무난합니다. 아래 감점 항목을 손보면 더 좋아집니다'
              : '감점 항목을 고쳐서 다시 생성하는 편이 낫습니다'}
          </p>
          {!report.judged_by_llm && (
            <p className="mt-0.5 text-[11px] text-amber-600">
              AI 심사를 못 해서 규칙 점수만 환산했습니다
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex-none rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
        >
          {open ? '접기' : '자세히'}
        </button>
      </div>

      {/* 의료광고법은 항상 보여준다 */}
      <div
        className={cn(
          'rounded-md border px-3 py-2 text-xs',
          hasBlocking
            ? 'border-red-500/30 bg-red-500/5'
            : law.counts.medium > 0
            ? 'border-amber-500/30 bg-amber-500/5'
            : 'border-emerald-500/30 bg-emerald-500/5'
        )}
      >
        <p className="font-medium">
          의료광고법 검사{' '}
          {law.violations.length === 0
            ? '통과'
            : `· 위반 ${law.counts.critical}건 / 소지 ${law.counts.high}건 / 지적 ${law.counts.medium}건`}
        </p>
        {law.violations.map((v, i) => (
          <div key={i} className="mt-1.5 leading-snug">
            <p>
              <span className="font-medium">[{SEVERITY_LABELS[v.severity]}]</span> {v.clause} — {v.message}
              {v.samples.length > 0 && (
                <span className="text-muted-foreground"> (예: {v.samples.join(', ')})</span>
              )}
            </p>
            <p className="text-muted-foreground">→ {v.fix}</p>
          </div>
        ))}
      </div>

      {/* 지어낸 출처는 발행 전에 반드시 확인해야 하므로 접힘 밖에 둔다 */}
      {(report.trust.details.evidence?.unverified_citations?.length ?? 0) > 0 && (
        <div className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs leading-snug">
          <p className="font-medium">발행 전 출처 확인이 필요합니다</p>
          <p className="mt-0.5 text-muted-foreground">
            원본 자료에 없던 기관·연구를 인용했습니다. AI가 지어냈을 수 있습니다. 사실이면 그대로
            두시고, 아니면 기관 이름을 빼고 일반론으로 바꾸세요.
          </p>
          <ul className="mt-1.5 space-y-1">
            {report.trust.details.evidence.unverified_citations!.map((c, i) => (
              <li key={i} className="text-foreground">
                · {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {open && (
        <div className="grid gap-4 pt-1 sm:grid-cols-2">
          <AxisBlock name="engagement" axis={report.engagement} />
          <AxisBlock name="understandability" axis={report.understandability} />
          <AxisBlock name="actionability" axis={report.actionability} />
          <AxisBlock name="trust" axis={report.trust} />
          <AxisBlock name="differentiation" axis={report.differentiation} />
          <AxisBlock name="naver_fit" axis={report.naver_fit} />
          {report.llm_judge && <AxisBlock name="llm_judge" axis={report.llm_judge} />}
        </div>
      )}
    </div>
  )
}
