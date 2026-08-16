import { useState, type ReactNode, type RefObject } from 'react'
import type ReactECharts from 'echarts-for-react/lib/core'

import { csvFor, dimensionLabels, type ExploreRow } from '../lib/explore'
import { formatMeasure, measureMeta } from '../lib/measures'
import { percentileRank, summarize } from '../lib/stats'
import { chart } from '../theme/tokens'

export interface FrameProps {
  title: string
  subtitle?: string
  measure: string
  rows?: ExploreRow[]
  dimension?: string
  loading?: boolean
  /** Previous rows are still on screen while a new query resolves. */
  stale?: boolean
  suppressed?: string
  empty?: string
  onLineage?: (pin: string) => void
  onExport?: (kind: 'png' | 'csv' | 'table') => void
  /** Selecting a row drills into it, or opens its source when it is already atomic.
   * The table twin exposes the same action, so drill-down is keyboard-reachable. */
  onSelect?: (row: ExploreRow) => void
}

function download(name: string, href: string): void {
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = name
  anchor.click()
}

/** Card chrome shared by every chart: title, export actions, honest empty states,
 * and the table twin that makes each chart readable without colour or a pointer. */
export function ChartFrame({ children, chartRef, ...props }: FrameProps & { children: ReactNode; chartRef?: RefObject<ReactECharts> }) {
  const [showTable, setShowTable] = useState(false)
  const rows = props.rows ?? []
  const slug = props.title.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
  const savePng = () => {
    const url = chartRef?.current?.getEchartsInstance().getDataURL({ pixelRatio: 2, backgroundColor: chart.surface })
    if (!url) return
    download(`${slug}.png`, url)
    props.onExport?.('png')
  }
  const saveCsv = () => {
    const body = csvFor(rows, props.dimension ?? 'cohort', props.measure)
    download(`${slug}.csv`, `data:text/csv;charset=utf-8,${encodeURIComponent(body)}`)
    props.onExport?.('csv')
  }
  const toggleTable = () => {
    setShowTable(current => !current)
    if (!showTable) props.onExport?.('table')
  }
  const body = props.loading && !props.stale
    ? <div className="chart-state shimmer">Reading the governed materialisation…</div>
    : props.suppressed
      ? <div className="chart-state suppressed"><strong>Cohort protected</strong><span>{props.suppressed}</span></div>
      : !rows.length
        ? <div className="chart-state empty"><strong>No eligible result</strong><span>{props.empty ?? 'No governed value is available for this cohort yet.'}</span></div>
        : <div className={props.stale ? 'chart-body is-stale' : 'chart-body'}>{showTable ? <ResultTable rows={rows} measure={props.measure} dimension={props.dimension ?? 'cohort'} onLineage={props.onLineage} onSelect={props.onSelect}/> : children}</div>
  return <section className="chart-frame" aria-label={props.title}>
    <div className="chart-heading">
      <div><h3>{props.title}</h3>{props.subtitle && <p className="chart-subtitle">{props.subtitle}</p>}</div>
      <div className="chart-actions">
        <button className="text-button" onClick={toggleTable} aria-pressed={showTable} disabled={!rows.length}>{showTable ? 'Chart' : 'Table'}</button>
        <button className="text-button" onClick={saveCsv} disabled={!rows.length}>CSV</button>
        <button className="text-button" onClick={savePng} disabled={!chartRef || showTable || !rows.length}>PNG</button>
      </div>
    </div>
    {body}
  </section>
}

/** The WCAG-clean twin of every chart: the same numbers, plus the comparative
 * context a reader would otherwise have to infer from bar length. */
export function ResultTable({ rows, measure, dimension, onLineage, onSelect }: { rows: ExploreRow[]; measure: string; dimension: string; onLineage?: (pin: string) => void; onSelect?: (row: ExploreRow) => void }) {
  const summary = summarize(rows.map(row => row.value))
  const meta = measureMeta(measure)
  const values = rows.map(row => row.value)
  return <div className="result-table-scroll"><table className="result-table">
    <caption className="visually-hidden">{meta.label} by {dimensionLabels[dimension] ?? dimension}, with each row's distance from the cohort median.</caption>
    <thead><tr>
      <th scope="col">{dimensionLabels[dimension] ?? dimension}</th>
      <th scope="col" className="numeric">{meta.label}{meta.unit && meta.unit !== 'score' ? ` (${meta.unit})` : ''}</th>
      <th scope="col" className="numeric">vs median</th>
      <th scope="col" className="numeric">Percentile</th>
      <th scope="col" className="numeric">Companies</th>
      {onLineage && <th scope="col">Source</th>}
    </tr></thead>
    <tbody>{rows.map(row => {
      const delta = summary ? row.value - summary.median : null
      const rank = percentileRank(values, row.value)
      return <tr key={row.key} className={row.thin ? 'is-thin' : undefined}>
        <th scope="row">{onSelect ? <button className="row-select" onClick={() => onSelect(row)}>{row.label}</button> : row.label}{row.thin && <abbr title="Fewer companies than the published cohort minimum"> ·thin</abbr>}</th>
        <td className="numeric">{formatMeasure(row.value, measure)}</td>
        <td className="numeric">{delta === null ? '—' : `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${formatMeasure(Math.abs(delta), measure)}`}</td>
        <td className="numeric">{rank === null ? '—' : `${rank.toFixed(0)}th`}</td>
        <td className="numeric">{row.cohortN ?? '—'}</td>
        {onLineage && <td>{row.lineageKey ? <button className="text-button" onClick={() => onLineage(row.lineageKey as string)}>View source</button> : '—'}</td>}
      </tr>
    })}</tbody>
  </table></div>
}
