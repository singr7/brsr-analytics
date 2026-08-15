import ReactECharts from 'echarts-for-react/lib/core'
import { useRef } from 'react'

import { tokens } from '../theme/tokens'
import { echarts } from './echarts'

export interface ChartDatum { name: string; value: number; lineageKey?: string }
interface ChartProps {
  title: string
  data?: ChartDatum[]
  loading?: boolean
  suppressed?: string
  onDatumClick?: (datum: ChartDatum) => void
  onLineage?: (pin: string) => void
}

function Frame({ title, loading, suppressed, children, chartRef }: ChartProps & { children: React.ReactNode; chartRef?: React.RefObject<ReactECharts> }) {
  const download = () => {
    const url = chartRef?.current?.getEchartsInstance().getDataURL({ pixelRatio: 2, backgroundColor: tokens.color.white })
    if (!url) return
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${title.toLowerCase().replaceAll(' ', '-')}.png`; anchor.click()
  }
  return <section className="chart-frame" aria-label={title}>
    <div className="chart-heading"><h3>{title}</h3><button className="text-button" onClick={download} disabled={!chartRef}>PNG ↗</button></div>
    {loading ? <div className="chart-state shimmer">Loading governed metrics…</div> : suppressed ? <div className="chart-state suppressed"><strong>Cohort protected</strong><span>{suppressed}</span></div> : children}
  </section>
}

export function RankedBar(props: ChartProps & { marker?: string }) {
  const ref = useRef<ReactECharts>(null)
  const data = props.data ?? []
  return <Frame {...props} chartRef={ref}><ReactECharts echarts={echarts} ref={ref} style={{ height: 330 }} option={{
    animationDuration: 550, grid: { left: 12, right: 28, top: 14, bottom: 12, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#e8e2d7' } } },
    yAxis: { type: 'category', data: data.map(d => d.name), axisLine: { show: false }, axisTick: { show: false } },
    tooltip: { trigger: 'item' }, series: [{ type: 'bar', data: data.map(d => ({ value: d.value, itemStyle: { color: d.name === props.marker ? tokens.color.saffron : tokens.color.pine, borderRadius: [0, 5, 5, 0] } })), barWidth: 18 }],
  }} onEvents={{ click: (event: { dataIndex: number }) => props.onDatumClick?.(data[event.dataIndex]) }} />
  <LineageLinks data={data} onLineage={props.onLineage} /></Frame>
}

export function Distribution(props: ChartProps) {
  const ref = useRef<ReactECharts>(null); const data = props.data ?? []
  return <Frame {...props} chartRef={ref}><ReactECharts echarts={echarts} ref={ref} style={{ height: 300 }} option={{
    grid: { left: 35, right: 18, top: 20, bottom: 34 }, xAxis: { type: 'category', data: data.map(d => d.name) }, yAxis: { type: 'value' },
    tooltip: { trigger: 'axis' }, series: [{ type: 'boxplot', data: data.map(d => [Math.max(0, d.value - 12), d.value - 6, d.value, d.value + 7, Math.min(100, d.value + 14)]), itemStyle: { color: '#bfd7c8', borderColor: tokens.color.pine } }],
  }} /></Frame>
}

export function Timeseries(props: ChartProps) {
  const ref = useRef<ReactECharts>(null); const data = props.data ?? []
  return <Frame {...props} chartRef={ref}><ReactECharts echarts={echarts} ref={ref} style={{ height: 300 }} option={{
    grid: { left: 38, right: 20, top: 20, bottom: 35 }, xAxis: { type: 'category', boundaryGap: false, data: data.map(d => d.name) }, yAxis: { type: 'value' },
    tooltip: { trigger: 'axis' }, series: [{ type: 'line', smooth: true, symbolSize: 9, data: data.map(d => d.value), areaStyle: { color: '#bfd7c855' }, lineStyle: { width: 3, color: tokens.color.pine }, itemStyle: { color: tokens.color.saffron } }],
  }} /><LineageLinks data={data} onLineage={props.onLineage} /></Frame>
}

export function Heatmap(props: ChartProps) {
  const ref = useRef<ReactECharts>(null); const data = props.data ?? []
  return <Frame {...props} chartRef={ref}><div className="heat-grid">{data.map(item => <button key={item.name} onClick={() => props.onDatumClick?.(item)} style={{ background: tokens.sequential[Math.min(4, Math.floor(item.value / 21))], color: item.value > 60 ? 'white' : 'inherit' }}><span>{item.name}</span><strong>{item.value.toFixed(0)}</strong></button>)}</div></Frame>
}

function LineageLinks({ data, onLineage }: { data: ChartDatum[]; onLineage?: (pin: string) => void }) {
  const count = data.filter(item => item.lineageKey).length
  if (!count) return null
  return <button className="lineage-link" onClick={() => { const pin = data.find(item => item.lineageKey)?.lineageKey; if (pin) onLineage?.(pin) }}>◎ View source lineage ({count})</button>
}

export function ScoreBadge({ value, label }: { value: number; label: string }) { return <div className="score-badge"><span>{label}</span><strong>{value.toFixed(0)}</strong><small>/ 100</small></div> }
export function PercentilePill({ value }: { value: number }) { return <span className="percentile-pill">Top {Math.max(1, 100 - value).toFixed(0)}%</span> }
