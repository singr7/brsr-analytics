import type { SemanticDSL, SemanticFilter, SemanticResponse } from './semantic'

/** One plotted result, normalised out of the semantic response's loose row shape. */
export interface ExploreRow {
  /** Stable identity for colour and selection — the dimension value, not the rank. */
  key: string
  label: string
  value: number
  measure: string
  /** Companies behind an aggregate row; absent on company-level rows. */
  cohortN?: number
  /** The row rests on fewer companies than the catalog minimum. */
  thin?: boolean
  lineageKey?: string
}

const DIMENSION_KEYS = ['company', 'sector', 'industry', 'mcap_band', 'fy', 'cohort'] as const

export const dimensionLabels: Record<string, string> = {
  sector: 'Sector', industry: 'Industry', mcap_band: 'Market-cap band',
  fy: 'Financial year', company: 'Company', cohort: 'Cohort', assurance_status: 'Assurance status',
}

/** The dimension a row set is keyed on, preferring the query's own first dimension. */
export function primaryDimension(dsl: SemanticDSL, rows: Array<Record<string, unknown>> = []): string {
  const first = dsl.dimensions[0]
  if (first && rows.some(row => row[first] !== undefined)) return first
  // A bottom-ranked query has its company column replaced by an anonymised cohort.
  return DIMENSION_KEYS.find(key => rows.some(row => row[key] !== undefined)) ?? first ?? 'cohort'
}

export function toRows(response: SemanticResponse | undefined, dimension: string, measure: string): ExploreRow[] {
  if (!response) return []
  return response.data
    .filter(row => row.value !== null && row.value !== undefined && (row.measure === undefined || row.measure === measure))
    .map((row, index) => {
      const raw = row[dimension]
      const label = raw === undefined || raw === null ? `Cohort ${index + 1}` : String(raw)
      return {
        key: label,
        label,
        value: Number(row.value),
        measure: String(row.measure ?? measure),
        cohortN: row.cohort_n === undefined || row.cohort_n === null ? undefined : Number(row.cohort_n),
        thin: row.thin_cohort === true,
        lineageKey: row.lineage_key ? String(row.lineage_key) : undefined,
      }
    })
    .filter(row => Number.isFinite(row.value))
}

/** Where a click on this dimension leads, or null when the row is already atomic. */
export function drillTarget(dimension: string): string | null {
  return ['sector', 'industry', 'mcap_band', 'assurance_status'].includes(dimension) ? 'company' : null
}

export interface DrillStep { dimension: string; value: string }

export function readDrill(search: string): DrillStep[] {
  const raw = new URLSearchParams(search).get('drill')
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is DrillStep =>
      typeof item === 'object' && item !== null && typeof (item as DrillStep).dimension === 'string' && typeof (item as DrillStep).value === 'string')
  } catch { return [] }
}

/** Re-target a query at the companies inside a drilled cohort.
 *
 * Ranking is the only shape the backend accepts for the company dimension, and it
 * keeps the base query's sort direction — so a "lower is better" question drills
 * into the same anonymised-cohort policy the ranked view already applies.
 */
export function applyDrill(base: SemanticDSL, steps: DrillStep[]): SemanticDSL {
  if (!steps.length) return base
  const drilled: SemanticFilter[] = steps.map(step => ({ dimension: step.dimension, operator: 'eq', value: step.value }))
  const kept = base.filters.filter(filter => !steps.some(step => step.dimension === filter.dimension))
  return { ...base, dimensions: ['company'], shape: 'ranking', filters: [...kept, ...drilled] }
}

/** Replace a single-value filter, or drop it when `value` is empty. */
export function withFilter(dsl: SemanticDSL, dimension: string, value: string | number | null): SemanticDSL {
  const rest = dsl.filters.filter(item => item.dimension !== dimension)
  return { ...dsl, filters: value === null || value === '' ? rest : [...rest, { dimension, operator: 'eq', value }] }
}

export function filterValue(dsl: SemanticDSL, dimension: string): string {
  const found = dsl.filters.find(item => item.dimension === dimension)?.value
  return found === undefined || Array.isArray(found) ? '' : String(found)
}

/** Build rows from literal label/value pairs — illustrative and internal surfaces
 * that are not backed by a semantic query. */
export function staticRows(entries: Array<[string, number]>, measure: string): ExploreRow[] {
  return entries.map(([label, value]) => ({ key: label, label, value, measure }))
}

export function csvFor(rows: ExploreRow[], dimension: string, measure: string): string {
  const header = [dimensionLabels[dimension] ?? dimension, measure, 'cohort_n', 'below_minimum_cohort']
  const body = rows.map(row => [row.label, row.value, row.cohortN ?? '', row.thin ? 'true' : 'false'])
  return [header, ...body]
    .map(line => line.map(cell => (/[",\n]/.test(String(cell)) ? `"${String(cell).replaceAll('"', '""')}"` : String(cell))).join(','))
    .join('\n')
}
