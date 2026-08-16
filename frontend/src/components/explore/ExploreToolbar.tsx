import { filterValue, withFilter, type DrillStep } from '../../lib/explore'
import { defaultCompare, measureMeta, measures } from '../../lib/measures'
import type { SemanticDSL } from '../../lib/semantic'

export interface ToolbarProps {
  dsl: SemanticDSL
  onChange: (next: SemanticDSL) => void
  sectors: string[]
  compare: string | null
  onCompare: (measure: string | null) => void
  drill: DrillStep[]
  onDrillTo: (depth: number) => void
}

const MCAP_BANDS = [['', 'All bands'], ['large', 'Large cap'], ['mid', 'Mid cap'], ['small', 'Small cap']]
const TOP_N = [10, 15, 25, 50]

/** One control row above everything it scopes. Every control writes straight into
 * the semantic DSL, so the URL, the charts, and the export stay the same query. */
export function ExploreToolbar({ dsl, onChange, sectors, compare, onCompare, drill, onDrillTo }: ToolbarProps) {
  const measure = dsl.measures[0]
  const meta = measureMeta(measure)
  const direction = dsl.sort?.direction ?? 'desc'
  const drilled = drill.length > 0
  return <div className="explore-toolbar">
    <div className="toolbar-row">
      <label>Measure
        <select value={measure} onChange={event => {
          const next = event.target.value
          onChange({ ...dsl, measures: [next] })
          onCompare(defaultCompare(next))
        }}>{Object.values(measures).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
      </label>
      <label>Financial year
        <select value={filterValue(dsl, 'fy') || '2025'} onChange={event => onChange(withFilter(dsl, 'fy', Number(event.target.value)))}>
          <option value="2025">FY 2025</option><option value="2024">FY 2024</option>
        </select>
      </label>
      <label>Sector
        <select value={filterValue(dsl, 'sector')} onChange={event => onChange(withFilter(dsl, 'sector', event.target.value || null))} disabled={drilled}>
          <option value="">All sectors</option>
          {sectors.map(item => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
      <label>Market cap
        <select value={filterValue(dsl, 'mcap_band')} onChange={event => onChange(withFilter(dsl, 'mcap_band', event.target.value || null))}>
          {MCAP_BANDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label>Show
        <select value={String(dsl.limit ?? 25)} onChange={event => onChange({ ...dsl, limit: Number(event.target.value) })}>
          {TOP_N.map(item => <option key={item} value={item}>Top {item}</option>)}
        </select>
      </label>
      <label>Order
        <select value={direction} onChange={event => onChange({ ...dsl, sort: { by: 'value', direction: event.target.value as 'asc' | 'desc' } })}>
          <option value="desc">Highest first</option><option value="asc">Lowest first</option>
        </select>
      </label>
      <label>Compare with
        <select value={compare ?? ''} onChange={event => onCompare(event.target.value || null)}>
          <option value="">No second measure</option>
          {Object.values(measures).filter(item => item.key !== measure).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      </label>
    </div>
    <p className="toolbar-note"><strong>{meta.label}</strong> · {meta.note}</p>
    {drilled && <nav className="drill-crumbs" aria-label="Drill-down path">
      <button onClick={() => onDrillTo(0)}>All cohorts</button>
      {drill.map((step, index) => <span key={`${step.dimension}-${step.value}`}>
        <i aria-hidden="true">›</i>
        <button onClick={() => onDrillTo(index + 1)} aria-current={index === drill.length - 1 ? 'page' : undefined}>{step.value}</button>
      </span>)}
      <button className="crumb-clear" onClick={() => onDrillTo(0)}>Clear drill-down ×</button>
    </nav>}
  </div>
}
