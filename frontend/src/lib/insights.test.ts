import { staticRows, type ExploreRow } from './explore'
import { buildInsights, leadingRow } from './insights'

const scores = staticRows([['Energy', 78], ['Metals', 71], ['Automotive', 67], ['Consumer', 52]], 'completeness')

test('the leading row follows the sort direction, not the largest value', () => {
  expect(leadingRow(scores, false)?.label).toBe('Energy')
  expect(leadingRow(scores, true)?.label).toBe('Consumer')
  expect(leadingRow([], false)).toBeNull()
})

test('a score cohort gets a headline, a spread, and a range — never a total', () => {
  const insights = buildInsights({ rows: scores, measure: 'completeness', dimension: 'sector', ascending: false, shape: 'distribution' })
  const ids = insights.map(item => item.id)
  expect(ids).toContain('leader')
  expect(ids).toContain('spread')
  expect(ids).not.toContain('concentration')
  expect(insights[0].text).toContain('Energy')
  expect(insights[0].text).toContain('69.0 / 100')
})

test('an absolute measure is described as scale and gets a concentration reading', () => {
  const rows = staticRows([['A', 900], ['B', 500], ['C', 300], ['D', 100], ['E', 50]], 'p6.e1.energy_total_gj')
  const insights = buildInsights({ rows, measure: 'p6.e1.energy_total_gj', dimension: 'company', ascending: false, shape: 'ranking' })
  const ids = insights.map(item => item.id)
  expect(ids).toContain('concentration')
  expect(ids).toContain('polarity')
  expect(insights.find(item => item.id === 'concentration')?.text).toContain('92%')
  expect(insights.find(item => item.id === 'leader')?.text).toContain('largest value')
})

test('a lower-is-better measure reads the gap in the favourable direction', () => {
  const rows = staticRows([['A', 20], ['B', 40], ['C', 60]], 'normalized.energy_gj_per_inr_crore')
  const insights = buildInsights({ rows, measure: 'normalized.energy_gj_per_inr_crore', dimension: 'company', ascending: true, shape: 'ranking' })
  expect(insights[0].text).toContain('A sits at the favourable end')
  expect(insights[0].text).toContain('2.0× below')
})

test('thin cohorts raise a caution that names how many rows are affected', () => {
  const rows: ExploreRow[] = scores.map((row, index) => ({ ...row, thin: index < 2, cohortN: index < 2 ? 2 : 9 }))
  const insights = buildInsights({ rows, measure: 'completeness', dimension: 'sector', ascending: false, shape: 'distribution' })
  const caution = insights.find(item => item.id === 'thin')
  expect(caution?.tone).toBe('caution')
  expect(caution?.text).toContain('2 of 4 rows')
})

test('a single row supports no derived statement at all', () => {
  expect(buildInsights({ rows: scores.slice(0, 1), measure: 'completeness', dimension: 'sector', ascending: false, shape: 'ranking' })).toEqual([])
})
