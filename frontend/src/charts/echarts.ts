import { BarChart, BoxplotChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, BoxplotChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer])

export { echarts }
