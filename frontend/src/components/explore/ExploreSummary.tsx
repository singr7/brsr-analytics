import { StatTile } from '../../charts/ChartKit'
import { describeCohort, leadingRow, type Insight } from '../../lib/insights'
import type { ExploreRow } from '../../lib/explore'
import { extremeNoun, formatMeasure, formatRange } from '../../lib/measures'
import { ratio, type Summary } from '../../lib/stats'

/** The five numbers that qualify every reading below them: how much data is in
 * the cohort, where its centre is, how wide it is, what leads it, and how much of
 * it is too thin to compare. */
export function MetricStrip({ rows, summary, measure, dimension, ascending }: { rows: ExploreRow[]; summary: Summary | null; measure: string; dimension: string; ascending: boolean }) {
  if (!summary) return null
  const leader = leadingRow(rows, ascending)
  const spread = ratio(summary.max, summary.min)
  const thin = rows.filter(row => row.thin).length
  return <div className="metric-strip">
    <StatTile label="Cohort" value={describeCohort(rows, dimension)}/>
    <StatTile label="Median" value={formatMeasure(summary.median, measure)} detail={`mean ${formatMeasure(summary.mean, measure)}`}/>
    <StatTile label="Middle half" value={formatRange(summary.q1, summary.q3, measure)} detail={`IQR ${formatMeasure(summary.iqr, measure)}`}/>
    <StatTile label={extremeNoun(measure) === 'largest reported' ? 'Largest reported' : 'Leading'} value={leader ? leader.label : '—'} detail={leader ? formatMeasure(leader.value, measure) : undefined} tone="accent"/>
    <StatTile
      label={thin ? 'Thin cohorts' : 'Full range'}
      value={thin ? `${thin} of ${rows.length}` : spread === null ? formatRange(summary.min, summary.max, measure) : `${spread >= 10 ? spread.toFixed(0) : spread.toFixed(1)}×`}
      detail={thin ? 'below the published minimum' : 'lowest to highest'}
      tone={thin ? 'caution' : 'plain'}/>
  </div>
}

export function InsightList({ insights }: { insights: Insight[] }) {
  if (!insights.length) return null
  return <ul className="insight-list">{insights.map(item => <li key={item.id} className={`tone-${item.tone}`}>
    <span>{item.label}</span><p>{item.text}</p>
  </li>)}</ul>
}
