import { BarChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts'
import { DatasetComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart, LineChart, ScatterChart, HeatmapChart,
  GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent,
  VisualMapComponent, DatasetComponent, CanvasRenderer,
])

export { echarts }
