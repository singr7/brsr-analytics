import ReactECharts from 'echarts-for-react'

const option = {
  color: ['#16845b'],
  tooltip: { trigger: 'axis' },
  grid: { left: 38, right: 12, top: 20, bottom: 28 },
  xAxis: { type: 'category', data: ['Energy', 'Water', 'Waste', 'Workforce', 'Assurance'] },
  yAxis: { type: 'value', max: 100 },
  series: [{ type: 'bar', data: [84, 72, 68, 91, 55], borderRadius: [5, 5, 0, 0] }],
}

export function DemoChart() {
  return <ReactECharts option={option} style={{ height: 320 }} aria-label="Readiness score demo chart" />
}

