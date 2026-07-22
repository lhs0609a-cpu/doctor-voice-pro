/**
 * 원스톱 마법사 상태머신 (프론트 인메모리, 백엔드 세션 불필요).
 *
 * 단계별 산출물이 다음 단계 입력으로 흐른다:
 *   step1 candidates → selected → step2 feasibility → approved → step3 생성 → step4 발행
 */
import { useReducer } from 'react'
import type { KeywordVolumeDTO, FeasibilityDTO } from '@/lib/api'

export type WizardStep = 1 | 2 | 3 | 4

export interface WizardState {
  step: WizardStep
  candidates: KeywordVolumeDTO[]      // step1: 실검색량 조회 결과
  selected: string[]                  // step1 → step2 로 넘길 키워드
  feasibility: Record<string, FeasibilityDTO> // step2: 키워드별 판정
  approved: string[]                  // step2 → step3: 실제 작성할 키워드
  generatedCount: number              // step3 성공 건수(진행 표시용)
}

const initialState: WizardState = {
  step: 1,
  candidates: [],
  selected: [],
  feasibility: {},
  approved: [],
  generatedCount: 0,
}

type Action =
  | { type: 'SET_CANDIDATES'; candidates: KeywordVolumeDTO[] }
  | { type: 'SET_SELECTED'; selected: string[] }
  | { type: 'SET_FEASIBILITY'; feasibility: FeasibilityDTO[] }
  | { type: 'SET_APPROVED'; approved: string[] }
  | { type: 'SET_GENERATED_COUNT'; count: number }
  | { type: 'GOTO'; step: WizardStep }
  | { type: 'RESET' }

function reducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case 'SET_CANDIDATES':
      return { ...state, candidates: action.candidates }
    case 'SET_SELECTED':
      return { ...state, selected: action.selected }
    case 'SET_FEASIBILITY': {
      const map: Record<string, FeasibilityDTO> = { ...state.feasibility }
      for (const f of action.feasibility) map[f.keyword] = f
      return { ...state, feasibility: map }
    }
    case 'SET_APPROVED':
      return { ...state, approved: action.approved }
    case 'SET_GENERATED_COUNT':
      return { ...state, generatedCount: action.count }
    case 'GOTO':
      return { ...state, step: action.step }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

export function useWizardState() {
  const [state, dispatch] = useReducer(reducer, initialState)
  return { state, dispatch }
}
