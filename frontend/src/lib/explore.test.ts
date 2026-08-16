import { applyDrill, csvFor, drillTarget, filterValue, primaryDimension, readDrill, toRows, withFilter } from './explore'
import { formatCompact, formatMeasure } from './measures'
import type { SemanticDSL, SemanticResponse } from './semantic'

const base: SemanticDSL = {
  measures: ['completeness'], dimensions: ['sector'],
  filters: [{ dimension: 'fy', operator: 'eq', value: 2025 }],
  shape: 'distribution', sort: { by: 'value', direction: 'desc' }, limit: 20,
}

const response = (data: Array<Record<string, unknown>>): SemanticResponse =>
  ({ data, lineage_refs: {}, applied_policy: [], catalog_version: '1', cache_hit: false })

test('rows keep cohort depth, thinness, and lineage from the governed payload', () => {
  const rows = toRows(response([
    { sector: 'Energy', value: 78, cohort_n: 9, measure: 'completeness' },
    { sector: 'Metals', value: 61, cohort_n: 2, thin_cohort: true, lineage_key: 'pin-1', measure: 'completeness' },
    { sector: 'Retail', value: null, measure: 'completeness' },
  ]), 'sector', 'completeness')
  expect(rows).toHaveLength(2)
  expect(rows[1]).toMatchObject({ key: 'Metals', value: 61, cohortN: 2, thin: true, lineageKey: 'pin-1' })
})

test('rows for one measure ignore the other measures in a multi-measure result', () => {
  const rows = toRows(response([
    { sector: 'Energy', value: 78, measure: 'completeness' },
    { sector: 'Energy', value: 44, measure: 'substance' },
  ]), 'sector', 'substance')
  expect(rows).toEqual([expect.objectContaining({ label: 'Energy', value: 44 })])
})

test('an anonymised bottom ranking falls back to the cohort column', () => {
  const anonymised = [{ cohort: 'anonymised lower-performing cohort', value: 31 }]
  expect(primaryDimension({ ...base, dimensions: ['company'] }, anonymised)).toBe('cohort')
})

test('drilling re-targets the query at companies and keeps the untouched filters', () => {
  const drilled = applyDrill(base, [{ dimension: 'sector', value: 'Energy' }])
  expect(drilled.dimensions).toEqual(['company'])
  expect(drilled.shape).toBe('ranking')
  expect(drilled.filters).toEqual([
    { dimension: 'fy', operator: 'eq', value: 2025 },
    { dimension: 'sector', operator: 'eq', value: 'Energy' },
  ])
  expect(applyDrill(base, [])).toBe(base)
})

test('only aggregate dimensions offer a drill-down', () => {
  expect(drillTarget('sector')).toBe('company')
  expect(drillTarget('mcap_band')).toBe('company')
  expect(drillTarget('company')).toBeNull()
  expect(drillTarget('fy')).toBeNull()
})

test('a malformed drill parameter is ignored rather than thrown', () => {
  expect(readDrill('?drill=not-json')).toEqual([])
  expect(readDrill('?drill=[{"dimension":"sector"}]')).toEqual([])
  expect(readDrill('?drill=[{"dimension":"sector","value":"Energy"}]')).toEqual([{ dimension: 'sector', value: 'Energy' }])
})

test('a filter is replaced in place and cleared by an empty value', () => {
  const withSector = withFilter(base, 'sector', 'Energy')
  expect(filterValue(withSector, 'sector')).toBe('Energy')
  expect(withFilter(withSector, 'sector', null).filters).toHaveLength(1)
  expect(withFilter(withSector, 'fy', 2024).filters).toContainEqual({ dimension: 'fy', operator: 'eq', value: 2024 })
})

test('the CSV twin carries cohort depth and escapes separators in labels', () => {
  const csv = csvFor([{ key: 'Oil, gas', label: 'Oil, gas', value: 61.25, measure: 'completeness', cohortN: 3, thin: true }], 'sector', 'completeness')
  expect(csv.split('\n')[1]).toBe('"Oil, gas",61.25,3,true')
})

test('values carry their catalog unit into prose and shorten only on axes', () => {
  expect(formatMeasure(74.25, 'completeness')).toBe('74.3 / 100')
  expect(formatMeasure(1234567, 'p6.e1.energy_total_gj')).toBe('12,34,567 GJ')
  expect(formatMeasure(3.456, 'normalized.energy_gj_per_inr_crore')).toBe('3.46 GJ / INR crore')
  expect(formatCompact(1234567, 'p6.e1.energy_total_gj')).toBe('1.2M')
  expect(formatCompact(74.25, 'completeness')).toBe('74.3')
})
