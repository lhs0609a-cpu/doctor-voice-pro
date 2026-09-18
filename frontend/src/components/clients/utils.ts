import type { ClientInput } from '@/lib/campaign-api'

/** axios 오류에서 사용자에게 보여줄 메시지를 뽑는다. */
export function errorMessage(e: unknown, fallback = '요청에 실패했습니다'): string {
  const err = e as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string }
    if (first?.msg) return first.msg
  }
  return err?.message || fallback
}

export const EMPTY_CLIENT: ClientInput = {
  name: '',
  short_name: '',
  specialty: '',
  diseases: [],
  treatments: [],
  regions: [],
  region_expand_level: 1,
  suffixes: [],
  min_volume_region: 20,
  min_volume_national: 100,
  forbidden_words: [],
  tone: '',
  facts: '',
  default_collection_id: null,
  sheet_url: '',
  sheet_blog_tab: '블로그',
  sheet_cafe_tab: '카페',
}
