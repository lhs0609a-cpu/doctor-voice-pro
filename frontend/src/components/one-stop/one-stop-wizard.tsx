'use client'

import { cn } from '@/lib/utils'
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
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold">원스톱 자동화</h1>
        <p className="text-muted-foreground text-sm mt-1">
          키워드 분석부터 상위노출 판정, 글 자동작성, 예약발행까지 한 흐름으로.
        </p>
      </div>

      {/* 스텝 인디케이터 */}
      <ol className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <li key={s.n} className="flex items-center gap-2 flex-1">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold',
                  state.step === s.n
                    ? 'bg-primary text-primary-foreground'
                    : state.step > s.n
                    ? 'bg-green-500 text-white'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {state.step > s.n ? '✓' : s.n}
              </span>
              <span
                className={cn(
                  'text-sm hidden sm:inline',
                  state.step === s.n ? 'font-semibold' : 'text-muted-foreground',
                )}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="h-px flex-1 bg-border" />
            )}
          </li>
        ))}
      </ol>

      {state.step === 1 && (
        <Step1Keywords
          state={state}
          onCandidates={(c) => dispatch({ type: 'SET_CANDIDATES', candidates: c })}
          onNext={(selected) => {
            dispatch({ type: 'SET_SELECTED', selected })
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
