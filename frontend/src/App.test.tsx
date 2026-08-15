import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'

import App from './App'

vi.mock('echarts-for-react', () => ({ default: () => <div>chart</div> }))
vi.mock('echarts-for-react/lib/core', () => ({ default: () => <div>chart</div> }))

const semantic = { data: [{ sector: 'Energy', value: 78 }, { sector: 'Metals', value: 71 }], lineage_refs: {}, applied_policy: [], catalog_version: '1', cache_hit: false }

function responseFor(input: RequestInfo | URL) {
  const url = String(input)
  const body = url.includes('/api/query') ? semantic
    : url.includes('/healthz') ? { status: 'ok', database: { status: 'ok' }, redis: { status: 'ok' }, llm_config: { status: 'ok' } }
      : url.includes('/api/library') ? { access: 'teaser', items: [] }
        : url.includes('/api/auth/me') ? { id: 'user-1', email: 'reader@example.test', display_name: 'Reader', plan_tier: 'pro', is_admin: false, orgs: [{ id: 'org-1', name: 'Example Org', slug: 'example', role: 'owner', plan_tier: 'pro', licence_state: 'active', seat_limit: 5 }] }
          : { accepted: 1 }
  return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response)
}

function renderApp() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  window.history.replaceState(null, '', '/')
  localStorage.clear()
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn(responseFor))
})

test('renders the intent-led anonymous shell, home, and governed insight', async () => {
  renderApp()
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Understand the filing')
  expect(screen.getByRole('navigation', { name: 'Journeys' })).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: 'Analyse my BRSR' })[0]).toHaveAttribute('href', '/analyse')
  expect(screen.getAllByRole('link', { name: 'Filing Studio' })[0]).toHaveAttribute('href', '/studio')
  expect(screen.getByText('Private by default')).toBeInTheDocument()
  expect(await screen.findByText('Energy currently has the highest sector completeness in this view.')).toBeInTheDocument()
  expect(await screen.findByText('ok')).toBeInTheDocument()
})

test('restores the authenticated organisation and plan shell', async () => {
  localStorage.setItem('brsrlens_access_token', 'token')
  renderApp()
  expect(await screen.findByRole('combobox', { name: 'Organisation' })).toHaveValue('org-1')
  expect(screen.getByText('pro access')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Peer benchmarks' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
})

test.each([
  ['/explore', 'Start with a useful question.'],
  ['/sectors', 'Sector scorecards'],
  ['/assurance', 'Assurance trends'],
  ['/studio', 'Your reporting workspace starts here.'],
  ['/ask', 'A question in. An evidence-backed answer.'],
  ['/library', 'Patterns worth learning from.'],
])('keeps legacy route %s working', async (route, heading) => {
  cleanup()
  window.history.replaceState(null, '', route)
  renderApp()
  expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
})

test('preserves saved semantic query state on the sector route', async () => {
  const query = { measures: ['completeness'], dimensions: ['sector'], filters: [{ dimension: 'fy', operator: 'eq', value: 2024 }], shape: 'ranking' }
  window.history.replaceState(null, '', `/sectors?${new URLSearchParams({ q: JSON.stringify(query) })}`)
  renderApp()
  expect(await screen.findByDisplayValue('2024')).toBeInTheDocument()
  await waitFor(() => expect(window.location.search).toContain('%22value%22%3A2024'))
})
