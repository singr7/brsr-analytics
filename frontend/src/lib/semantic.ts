import { useQuery } from '@tanstack/react-query'

import { accessToken } from './auth'
import { apiUrl } from './api'

export type Shape = 'distribution' | 'ranking' | 'timeseries' | 'comparison' | 'single'
export interface SemanticFilter { dimension: string; operator: 'eq' | 'in' | 'gte' | 'lte' | 'between' | 'score_band'; value: string | number | Array<string | number> }
export interface SemanticDSL {
  measures: string[]
  dimensions: string[]
  filters: SemanticFilter[]
  shape: Shape
  sort?: { by: string; direction: 'asc' | 'desc' }
  limit?: number
}
export interface PolicyNotice { code: string; message: string; measure?: string }
export interface SemanticResponse {
  data: Array<Record<string, unknown>>
  lineage_refs: Record<string, Array<{ pin_id: string; filing_id?: string; field_key?: string; source_page?: number }>>
  applied_policy: PolicyNotice[]
  catalog_version: string
  cache_hit: boolean
}
export async function runSemanticQuery(dsl: SemanticDSL): Promise<SemanticResponse> {
  const token = accessToken()
  const response = await fetch(`${apiUrl}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(dsl),
  })
  if (!response.ok) throw new Error(`Query failed (${response.status})`)
  return response.json() as Promise<SemanticResponse>
}

export function useSemanticQuery(dsl: SemanticDSL, enabled = true) {
  return useQuery({
    queryKey: ['semantic', dsl],
    queryFn: () => runSemanticQuery(dsl),
    staleTime: 300_000,
    enabled,
    // Refining a filter holds the previous result on screen at reduced opacity
    // rather than collapsing the layout into a skeleton.
    placeholderData: previous => previous,
  })
}

export function consolidatePolicyNotices(notices: PolicyNotice[] = []): PolicyNotice[] {
  return [...new Map(notices.map(item => [item.code, item])).values()]
}

export function encodeQueryState(dsl: SemanticDSL): string {
  return new URLSearchParams({ q: JSON.stringify(dsl) }).toString()
}

export function decodeQueryState(search: string, fallback: SemanticDSL): SemanticDSL {
  const raw = new URLSearchParams(search).get('q')
  if (!raw) return fallback
  try { return JSON.parse(raw) as SemanticDSL } catch { return fallback }
}

export function replaceQueryState(dsl: SemanticDSL): void {
  window.history.replaceState(null, '', `${window.location.pathname}?${encodeQueryState(dsl)}`)
}
