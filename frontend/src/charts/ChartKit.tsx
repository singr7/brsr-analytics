import ReactECharts from 'echarts-for-react/lib/core'
import { useRef } from 'react'

import type { ExploreRow } from '../lib/explore'
import { formatCompact, formatMeasure, measureMeta } from '../lib/measures'
import { histogram, summarize } from '../lib/stats'
import { chart } from '../theme/tokens'
import { ChartFrame, type FrameProps } from './ChartFrame'
import { echarts } from './echarts'

export type ChartDatum = ExploreRow

export interface PlotProps extends FrameProps {
  /** Key of the row drawn in the emphasis hue; everything else recedes. */
  selected?: string
  /** Reads "Click a bar to see the companies inside it" under the title. */
  drillHint?: string
}

const AXIS = { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: chart.label, fontSize: 11 } }
const GRID_LINE = { lineStyle: { color: chart.grid, width: 1, type: 'solid' as const } }
const TOOLTIP = {
  trigger: 'item' as const, backgroundColor: chart.surface, borderColor: chart.grid, borderWidth: 1,
  textStyle: { color: '#17231e', fontSize: 12 }, extraCssText: 'box-shadow:0 6px 18px #17231e18;border-radius:2px;',
}

function rowTooltip(row: ExploreRow, measure: string, median: number | null): string {
  const delta = median === null ? null : row.value - median
  const lines = [
    `<strong>${row.label}</strong>`,
    `${measureMeta(measure).label}: ${formatMeasure(row.value, measure)}`,
    delta === null ? '' : `${delta >= 0 ? '+' : '−'}${formatMeasure(Math.abs(delta), measure)} vs cohort median`,
    row.cohortN === undefined ? '' : `${row.cohortN} ${row.cohortN === 1 ? 'company' : 'companies'}${row.thin ? ' · below the published minimum' : ''}`,
  ]
  return lines.filter(Boolean).join('<br/>')
}

/** Ordered magnitude across nominal categories: one hue for the series, the
 * emphasis hue for the selected row, and a median rule for the comparison the
 * reader is actually making. Thin cohorts recede rather than taking a second hue. */
export function RankedBar(props: PlotProps) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const summary = summarize(rows.map(row => row.value))
  const labelled = rows.length <= 16
  const height = Math.max(220, rows.length * 27 + 54)
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: labelled ? 92 : 30, top: 8, bottom: 26, containLabel: true },
    xAxis: { type: 'value' as const, ...AXIS, splitLine: GRID_LINE, axisLabel: { ...AXIS.axisLabel, formatter: (value: number) => formatCompact(value, props.measure) } },
    yAxis: { type: 'category' as const, inverse: true, data: rows.map(row => row.label), ...AXIS, splitLine: { show: false }, axisLabel: { ...AXIS.axisLabel, width: 150, overflow: 'truncate' as const } },
    tooltip: { ...TOOLTIP, formatter: (item: { dataIndex: number }) => rowTooltip(rows[item.dataIndex], props.measure, summary?.median ?? null) },
    series: [{
      type: 'bar' as const,
      barWidth: 15,
      data: rows.map(row => ({
        value: row.value,
        itemStyle: {
          color: props.selected && row.key === props.selected ? chart.series[1] : chart.accent,
          opacity: row.thin ? 0.45 : 1,
          borderRadius: [0, 4, 4, 0] as [number, number, number, number],
        },
      })),
      label: labelled ? { show: true, position: 'right' as const, color: chart.label, fontSize: 11, formatter: (item: { dataIndex: number }) => formatCompact(rows[item.dataIndex].value, props.measure) } : { show: false },
      markLine: summary && rows.length > 2 ? {
        silent: true, symbol: 'none' as const,
        lineStyle: { color: chart.axis, width: 1, type: 'dotted' as const },
        label: { formatter: 'median', color: chart.label, fontSize: 10, position: 'end' as const, rotate: 0, distance: 4 },
        data: [{ xAxis: summary.median }],
      } : undefined,
    }],
  }
  return <ChartFrame {...props} chartRef={ref} subtitle={props.subtitle ?? props.drillHint}>
    <ReactECharts echarts={echarts} ref={ref} style={{ height }} opts={{ renderer: 'canvas' }} option={option}
      onEvents={{ click: (event: { dataIndex: number }) => props.onSelect?.(rows[event.dataIndex]) }}/>
  </ChartFrame>
}

/** Where the cohort actually sits: a real histogram of the returned values with
 * the interquartile band and median drawn over it. No modelled spread. */
export function Distribution(props: PlotProps) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const summary = summarize(rows.map(row => row.value))
  const bins = histogram(rows.map(row => row.value), Math.min(9, Math.max(3, Math.ceil(rows.length / 2))))
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: 16, top: 14, bottom: 22, containLabel: true },
    xAxis: {
      type: 'category' as const, ...AXIS, splitLine: { show: false },
      data: bins.map(bin => formatCompact(bin.from, props.measure)),
      axisLabel: { ...AXIS.axisLabel, interval: 0, hideOverlap: true },
    },
    yAxis: { type: 'value' as const, ...AXIS, minInterval: 1, splitLine: GRID_LINE, name: 'count', nameTextStyle: { color: chart.label, fontSize: 10, align: 'left' as const } },
    tooltip: {
      ...TOOLTIP,
      formatter: (item: { dataIndex: number }) => {
        const bin = bins[item.dataIndex]
        return `${formatMeasure(bin.from, props.measure)} – ${formatMeasure(bin.to, props.measure)}<br/><strong>${bin.count}</strong> of ${rows.length}`
      },
    },
    series: [{
      type: 'bar' as const,
      data: bins.map(bin => bin.count),
      itemStyle: { color: chart.sequential[2], borderRadius: [3, 3, 0, 0] as [number, number, number, number] },
      barCategoryGap: '18%',
      markLine: summary ? {
        silent: true, symbol: 'none' as const,
        lineStyle: { color: chart.axis, width: 1, type: 'dotted' as const },
        label: { formatter: `median ${formatCompact(summary.median, props.measure)}`, color: chart.label, fontSize: 10 },
        data: [{ xAxis: bins.findIndex(bin => summary.median >= bin.from && summary.median <= bin.to) }],
      } : undefined,
    }],
  }
  const subtitle = summary ? `${summary.n} values · middle half ${formatMeasure(summary.q1, props.measure)} to ${formatMeasure(summary.q3, props.measure)}` : props.subtitle
  return <ChartFrame {...props} subtitle={subtitle} chartRef={ref}>
    <ReactECharts echarts={echarts} ref={ref} style={{ height: 250 }} opts={{ renderer: 'canvas' }} option={option}/>
  </ChartFrame>
}

/** Change over time for one governed series, endpoint-labelled. */
export function Timeseries(props: PlotProps) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: 54, top: 16, bottom: 22, containLabel: true },
    xAxis: { type: 'category' as const, boundaryGap: false, data: rows.map(row => row.label), ...AXIS, splitLine: { show: false } },
    yAxis: { type: 'value' as const, ...AXIS, scale: true, splitLine: GRID_LINE, axisLabel: { ...AXIS.axisLabel, formatter: (value: number) => formatCompact(value, props.measure) } },
    tooltip: { ...TOOLTIP, trigger: 'axis' as const, formatter: (items: Array<{ dataIndex: number }>) => rowTooltip(rows[items[0].dataIndex], props.measure, null) },
    series: [{
      type: 'line' as const, smooth: false, symbolSize: 9,
      data: rows.map(row => row.value),
      lineStyle: { width: 2, color: chart.accent },
      itemStyle: { color: chart.accent, borderColor: chart.surface, borderWidth: 2 },
      areaStyle: { color: 'rgba(0,120,92,0.08)' },
      label: { show: true, position: 'top' as const, color: chart.label, fontSize: 11, formatter: (item: { dataIndex: number }) => (item.dataIndex === rows.length - 1 || item.dataIndex === 0 ? formatCompact(rows[item.dataIndex].value, props.measure) : '') },
    }],
  }
  return <ChartFrame {...props} chartRef={ref}>
    <ReactECharts echarts={echarts} ref={ref} style={{ height: 250 }} opts={{ renderer: 'canvas' }} option={option}
      onEvents={{ click: (event: { dataIndex: number }) => props.onSelect?.(rows[event.dataIndex]) }}/>
  </ChartFrame>
}

/** Two governed measures on the same cohort, one point per entity, with median
 * crosshairs so each quadrant has a plain reading. One hue plus emphasis — an
 * all-pairs form never carries four categorical hues. */
export function ComparisonScatter(props: PlotProps & { compareRows: ExploreRow[]; compareMeasure: string }) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const lookup = new Map(props.compareRows.map(row => [row.key, row.value]))
  const points = rows.filter(row => lookup.has(row.key)).map(row => ({ key: row.key, label: row.label, x: row.value, y: lookup.get(row.key) as number }))
  const xSummary = summarize(points.map(point => point.x))
  const ySummary = summarize(points.map(point => point.y))
  const xMeta = measureMeta(props.measure)
  const yMeta = measureMeta(props.compareMeasure)
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: 22, top: 18, bottom: 34, containLabel: true },
    xAxis: { type: 'value' as const, ...AXIS, scale: true, splitLine: GRID_LINE, name: xMeta.label, nameLocation: 'middle' as const, nameGap: 28, nameTextStyle: { color: chart.label, fontSize: 11 }, axisLabel: { ...AXIS.axisLabel, formatter: (value: number) => formatCompact(value, props.measure) } },
    yAxis: { type: 'value' as const, ...AXIS, scale: true, splitLine: GRID_LINE, name: yMeta.label, nameTextStyle: { color: chart.label, fontSize: 11, align: 'left' as const }, axisLabel: { ...AXIS.axisLabel, formatter: (value: number) => formatCompact(value, props.compareMeasure) } },
    tooltip: {
      ...TOOLTIP,
      formatter: (item: { dataIndex: number }) => {
        const point = points[item.dataIndex]
        return `<strong>${point.label}</strong><br/>${xMeta.label}: ${formatMeasure(point.x, props.measure)}<br/>${yMeta.label}: ${formatMeasure(point.y, props.compareMeasure)}`
      },
    },
    series: [{
      type: 'scatter' as const,
      symbolSize: 12,
      data: points.map(point => ({
        value: [point.x, point.y],
        itemStyle: { color: props.selected === point.key ? chart.series[1] : chart.accent, opacity: 0.85, borderColor: chart.surface, borderWidth: 2 },
      })),
      label: { show: points.length <= 14, position: 'right' as const, color: chart.label, fontSize: 10, formatter: (item: { dataIndex: number }) => points[item.dataIndex].label },
      // Direct labels are selective by construction: any that would collide is dropped
      // to the tooltip and the table twin rather than overprinting a neighbour.
      labelLayout: { hideOverlap: true },
      markLine: xSummary && ySummary ? {
        silent: true, symbol: 'none' as const,
        lineStyle: { color: chart.axis, width: 1, type: 'dotted' as const },
        label: { color: chart.label, fontSize: 10 },
        data: [{ xAxis: xSummary.median, label: { formatter: 'median' } }, { yAxis: ySummary.median, label: { formatter: 'median' } }],
      } : undefined,
    }],
  }
  return <ChartFrame {...props} chartRef={ref}>
    {points.length < 2
      ? <div className="chart-state empty"><strong>Not comparable yet</strong><span>Fewer than two cohorts report both measures in this view.</span></div>
      : <ReactECharts echarts={echarts} ref={ref} style={{ height: 360 }} opts={{ renderer: 'canvas' }} option={option}
          onEvents={{ click: (event: { dataIndex: number }) => props.onSelect?.(rows.find(row => row.key === points[event.dataIndex].key) as ExploreRow) }}/>}
  </ChartFrame>
}

/** Signed distance from the cohort median — the "where does this sit" reading that
 * a ranked bar cannot give. Diverging poles carry direction; the signed label
 * carries it again, so the chart survives without colour. */
export function DeviationBar(props: PlotProps) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const summary = summarize(rows.map(row => row.value))
  const deltas = rows.map(row => ({ row, delta: row.value - (summary?.median ?? 0) }))
  const height = Math.max(200, rows.length * 24 + 50)
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: 62, top: 8, bottom: 26, containLabel: true },
    xAxis: {
      type: 'value' as const, ...AXIS, splitLine: GRID_LINE,
      axisLabel: { ...AXIS.axisLabel, formatter: (value: number) => `${value > 0 ? '+' : ''}${formatCompact(value, props.measure)}` },
    },
    yAxis: { type: 'category' as const, inverse: true, data: deltas.map(item => item.row.label), ...AXIS, splitLine: { show: false }, axisLabel: { ...AXIS.axisLabel, width: 140, overflow: 'truncate' as const } },
    tooltip: {
      ...TOOLTIP,
      formatter: (item: { dataIndex: number }) => {
        const { row, delta } = deltas[item.dataIndex]
        return `<strong>${row.label}</strong><br/>${formatMeasure(row.value, props.measure)}<br/>${delta >= 0 ? '+' : '−'}${formatMeasure(Math.abs(delta), props.measure)} vs the ${formatMeasure(summary?.median ?? 0, props.measure)} median`
      },
    },
    series: [{
      type: 'bar' as const,
      barWidth: 13,
      data: deltas.map(item => ({
        value: item.delta,
        itemStyle: { color: item.delta >= 0 ? chart.above : chart.below, opacity: item.row.thin ? 0.45 : 1, borderRadius: 3 },
      })),
      label: {
        show: rows.length <= 16, position: 'right' as const, color: chart.label, fontSize: 11,
        formatter: (item: { dataIndex: number }) => `${deltas[item.dataIndex].delta >= 0 ? '+' : '−'}${formatCompact(Math.abs(deltas[item.dataIndex].delta), props.measure)}`,
      },
    }],
  }
  return <ChartFrame {...props} subtitle={props.subtitle ?? (summary ? `Distance from the ${formatMeasure(summary.median, props.measure)} cohort median` : undefined)} chartRef={ref}>
    <ReactECharts echarts={echarts} ref={ref} style={{ height }} opts={{ renderer: 'canvas' }} option={option}
      onEvents={{ click: (event: { dataIndex: number }) => props.onSelect?.(rows[event.dataIndex]) }}/>
  </ChartFrame>
}

/** Magnitude across a grid, on the validated single-hue ramp with a scale legend. */
export function Heatmap(props: PlotProps) {
  const ref = useRef<ReactECharts>(null)
  const rows = props.rows ?? []
  const summary = summarize(rows.map(row => row.value))
  const option = {
    animationDuration: 420,
    grid: { left: 8, right: 14, top: 10, bottom: 58, containLabel: true },
    xAxis: { type: 'category' as const, data: rows.map(row => row.label), ...AXIS, splitArea: { show: true }, axisLabel: { ...AXIS.axisLabel, rotate: 32, hideOverlap: true } },
    yAxis: { type: 'category' as const, data: [measureMeta(props.measure).label], ...AXIS, splitArea: { show: true } },
    visualMap: {
      min: summary?.min ?? 0, max: summary?.max ?? 100, calculable: true, orient: 'horizontal' as const,
      left: 'center', bottom: 0, itemWidth: 12, itemHeight: 90,
      textStyle: { color: chart.label, fontSize: 10 },
      inRange: { color: [...chart.sequential] },
      formatter: (value: number) => formatCompact(value, props.measure),
    },
    tooltip: { ...TOOLTIP, formatter: (item: { dataIndex: number }) => rowTooltip(rows[item.dataIndex], props.measure, summary?.median ?? null) },
    series: [{
      type: 'heatmap' as const,
      data: rows.map((row, index) => [index, 0, row.value]),
      itemStyle: { borderColor: chart.surface, borderWidth: 2 },
      label: { show: rows.length <= 10, color: '#17231e', fontSize: 10, formatter: (item: { data: number[] }) => formatCompact(item.data[2], props.measure) },
    }],
  }
  return <ChartFrame {...props} chartRef={ref}>
    <ReactECharts echarts={echarts} ref={ref} style={{ height: 210 }} opts={{ renderer: 'canvas' }} option={option}
      onEvents={{ click: (event: { dataIndex: number }) => props.onSelect?.(rows[event.dataIndex]) }}/>
  </ChartFrame>
}

/** A headline number with its comparative context. The number is the chart. */
export function StatTile({ label, value, detail, tone = 'plain' }: { label: string; value: string; detail?: string; tone?: 'plain' | 'accent' | 'caution' }) {
  return <div className={`stat-tile tone-${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

export function ScoreBadge({ value, label }: { value: number; label: string }) {
  return <div className="score-badge"><span>{label}</span><strong>{value.toFixed(0)}</strong><small>/ 100</small></div>
}

export function PercentilePill({ value }: { value: number }) {
  return <span className="percentile-pill">Top {Math.max(1, 100 - value).toFixed(0)}%</span>
}
