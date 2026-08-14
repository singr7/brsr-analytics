import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'

import App from './App'

vi.mock('echarts-for-react', () => ({ default: () => <div>chart</div> }))

test('renders the product shell and health status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ status: 'ok', database: { status: 'ok' }, redis: { status: 'ok' }, llm_config: { status: 'ok' } }),
  }))
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  )
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('See the substance')
  expect(await screen.findByText('ok')).toBeInTheDocument()
})
