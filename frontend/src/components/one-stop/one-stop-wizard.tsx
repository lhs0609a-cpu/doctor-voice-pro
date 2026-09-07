'use client'

import { blogIndexAPI } from '@/lib/blog-index-api'

import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/app-shell/page-header'
import { useWizardState, type WizardStep } from './use-wizard-state'
import { Step1Keywords } from './step1-keywords'
import { Step2Feasibility } from './step2-feasibility'
import { Step3Generate } from './step3-generate'
import { Step4Publish } from './step4-publish'

const STEPS: { n: WizardStep; label: string }[] = [
  { n: 1, label: '키워드·검색량' },
  { n: 2, label: '상위노출 가능성' },
  { n: 3, label: '글 자동작성' },
  { n: 4, label: '예약발행' },
]

export function OneStopWizard() {
  const { state, dispatch } = useWizardState()

  return (
    <div className="space-y-6">
      <PageHeader
        title="원스톱 자동화"
        description="키워드를 넣으면 검색량 확인, 상위노출 판정, 글 작성, 예약발행까지 순서대로 진행합니다."
      />

      {/* 스텝 인디케이터 */}
      <ol className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const active = state.step === s.n
          const done = state.step > s.n
          return (
            <li key={s.n} className={cn('flex items-center gap-2', i < STEPS.length - 1 && 'flex-1')}>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold tabular-nums',
                    active
                      ? 'bg-primary text-primary-foreground'
                      : done
                      ? 'bg-success-soft text-success'
                      : 'bg-muted text-muted-foreground',
                  )}
                >
                  {done ? <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> : s.n}
                </span>
                <span
                  className={cn(
                    'hidden text-[13px] sm:inline',
                    active ? 'font-semibold text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {s.label}
                </span>
              </div>
              {i < STEPS.length - 1 && <div className="h-px flex-1 bg-border" />}
            </li>
          )
        })}
      </ol>

      {state.step === 1 && (
        <Step1Keywords
          state={state}
          onCandidates={(c) => dispatch({ type: 'SET_CANDIDATES', candidates: c })}
          onNext={(selected) => {
            dispatch({ type: 'SET_SELECTED', selected })
            // 2단계 판정이 캐시 히트로 끝나도록, 넘어가는 순간 경쟁 블로그를 뒤에서 미리 채점한다
            blogIndexAPI.prewarm(selected).catch(() => { /* 실패해도 판정은 그대로 동작 */ })
            dispatch({ type: 'GOTO', step: 2 })
          }}
        />
      )}

      {state.step === 2 && (
        <Step2Feasibility
          state={state}
          onFeasibility={(f) => dispatch({ type: 'SET_FEASIBILITY', feasibility: f })}
          onBack={() => dispatch({ type: 'GOTO', step: 1 })}
          onNext={(approved) => {
            dispatch({ type: 'SET_APPROVED', approved })
            dispatch({ type: 'GOTO', step: 3 })
          }}
        />
      )}

      {state.step === 3 && (
        <Step3Generate
          state={state}
          onBack={() => dispatch({ type: 'GOTO', step: 2 })}
          onDone={(count) => {
            dispatch({ type: 'SET_GENERATED_COUNT', count })
            dispatch({ type: 'GOTO', step: 4 })
          }}
        />
      )}

      {state.step === 4 && (
        <Step4Publish
          state={state}
          onBack={() => dispatch({ type: 'GOTO', step: 3 })}
          onRestart={() => dispatch({ type: 'RESET' })}
        />
      )}
    </div>
  )
}
