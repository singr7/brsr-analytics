import type { ExploreRow } from './explore'
import { formatMeasure, measureMeta } from './measures'
import { change, concentration, percentileRank, ratio, summarize, type Summary } from './stats'

/** A statement the interface is prepared to defend from the rows on screen.
 *
 * `tone` is editorial weight, never a verdict on a company:
 *   'lead'    — the headline reading
 *   'context' — spread, shape, and scale that qualify the headline
 *   'caution' — a reason to distrust a comparative reading of this view
 */
export interface Insight { id: string; label: string; text: string; tone: 'lead' | 'context' | 'caution' }

export interface InsightInput {
  rows: ExploreRow[]
  measure: string
  dimension: string
  /** Ascending sort means the favourable end is the smallest value. */
  ascending: boolean
  shape: string
}

function multiple(value: number): string {
  return value >= 10 ? `${value.toFixed(0)}×` : `${value.toFixed(1)}×`
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

/** The row at the favourable end of the current sort — not necessarily the largest. */
export function leadingRow(rows: ExploreRow[], ascending: boolean): ExploreRow | null {
  if (!rows.length) return null
  return rows.reduce((best, row) => (ascending ? row.value < best.value : row.value > best.value) ? row : best)
}

export function describeCohort(rows: ExploreRow[], dimension: string): string {
  const unit = dimension === 'company' ? 'company' : dimension === 'fy' ? 'year' : `${dimension.replaceAll('_', ' ')} cohort`
  return plural(rows.length, unit)
}

/** Build the insight list for a result set. Order is presentation order. */
export function buildInsights(input: InsightInput): Insight[] {
  const { rows, measure, dimension, ascending } = input
  const summary = summarize(rows.map(row => row.value))
  if (!summary || rows.length < 2) return []
  const meta = measureMeta(measure)
  const leader = leadingRow(rows, ascending)
  const insights: Insight[] = []

  if (leader) {
    const versus = ratio(leader.value, summary.median)
    const direction = meta.polarity === 'neutral' ? 'reports the largest value in this view' : 'sits at the favourable end of this view'
    const gap = versus === null || !Number.isFinite(versus) ? '' :
      ascending
        ? ` — ${multiple(1 / versus)} below the ${formatMeasure(summary.median, measure)} median.`
        : ` — ${multiple(versus)} the ${formatMeasure(summary.median, measure)} median.`
    insights.push({
      id: 'leader',
      label: 'Headline',
      tone: 'lead',
      text: `${leader.label} ${direction} at ${formatMeasure(leader.value, measure)}${gap || '.'}`,
    })
  }

  insights.push({
    id: 'spread',
    label: 'Spread',
    tone: 'context',
    text: `The middle half of ${describeCohort(rows, dimension)} falls between ${formatMeasure(summary.q1, measure)} and ${formatMeasure(summary.q3, measure)}, around a ${formatMeasure(summary.median, measure)} median.`,
  })

  const span = ratio(summary.max, summary.min)
  if (span !== null && summary.min > 0 && span >= 1.5) {
    insights.push({
      id: 'range',
      label: 'Range',
      tone: 'context',
      text: `The full range runs ${formatMeasure(summary.min, measure)} to ${formatMeasure(summary.max, measure)}, a ${multiple(span)} difference across the visible cohort.`,
    })
  }

  if (meta.additive) {
    const share = concentration(rows.map(row => row.value), 3)
    if (share !== null) {
      insights.push({
        id: 'concentration',
        label: 'Concentration',
        tone: 'context',
        text: `The three largest reporters account for ${share.toFixed(0)}% of the ${formatMeasure(summary.total, measure)} total on screen. Reported volume tracks company scale.`,
      })
    }
  }

  if (input.shape === 'timeseries') {
    const movement = change(rows.map(row => row.value))
    if (movement && movement.percent !== null) {
      const verb = movement.absolute === 0 ? 'is unchanged' : movement.absolute > 0 ? 'rose' : 'fell'
      insights.push({
        id: 'trend',
        label: 'Movement',
        tone: 'context',
        text: `Across ${rows[0].label} to ${rows[rows.length - 1].label} the value ${verb} by ${formatMeasure(Math.abs(movement.absolute), measure)} (${Math.abs(movement.percent).toFixed(0)}%).`,
      })
    }
  }

  const thin = rows.filter(row => row.thin).length
  if (thin) {
    insights.push({
      id: 'thin',
      label: 'Cohort depth',
      tone: 'caution',
      text: `${thin} of ${rows.length} rows rest on fewer companies than the published minimum. They are shown as ingested, but will not support a comparative claim.`,
    })
  }

  if (meta.polarity === 'neutral') {
    insights.push({
      id: 'polarity',
      label: 'How to read this',
      tone: 'caution',
      text: 'This is an absolute quantity, so the order reflects company size and sector as much as disclosure or performance. Use the turnover-normalised view to compare intensity.',
    })
  }

  return insights
}

/** Per-row context for tooltips and the table view. */
export interface RowContext { deltaToMedian: number; percentile: number | null; shareOfTotal: number | null }

export function rowContext(row: ExploreRow, rows: ExploreRow[], measure: string, summary: Summary): RowContext {
  const values = rows.map(item => item.value)
  return {
    deltaToMedian: row.value - summary.median,
    percentile: percentileRank(values, row.value),
    shareOfTotal: measureMeta(measure).additive && summary.total > 0 ? (row.value / summary.total) * 100 : null,
  }
}
