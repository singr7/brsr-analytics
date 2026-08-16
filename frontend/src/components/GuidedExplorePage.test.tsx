import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { guidedQuestions } from '../content/guided-questions'
import { GuidedExplorePage } from './GuidedExplorePage'

vi.mock('echarts-for-react', () => ({ default: () => <div>chart</div> }))
vi.mock('echarts-for-react/lib/core', () => ({ default: () => <div>chart</div> }))

const sectorRows = [
  { sector: 'Energy', value: 78, cohort_n: 9, measure: 'completeness' },
  { sector: 'Metals', value: 71, cohort_n: 6, measure: 'completeness' },
  { sector: 'Automotive', value: 67, cohort_n: 5, measure: 'completeness' },
  { sector: 'Consumer', value: 52, cohort_n: 2, thin_cohort: true, measure: 'completeness' },
]
const companyRows = [
  { company: 'Alpha Ltd', value: 81, lineage_key: 'pin-1', measure: 'completeness' },
  { company: 'Beta Ltd', value: 74, lineage_key: 'pin-2', measure: 'completeness' },
]

interface SentQuery { measures: string[]; dimensions: string[]; filters: Array<Record<string, unknown>> }
let queries: SentQuery[] = []

function mockFetch(companyResult = companyRows) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    let body: unknown = { accepted: 1 }
    if (url.includes('/api/query')) {
      const sent = JSON.parse(String(init?.body)) as SentQuery
      queries.push(sent)
      const base = sent.dimensions.includes('company') ? companyResult : sectorRows
      const data = base.map(row => ({ ...row, measure: sent.measures[0] }))
      body = { data, lineage_refs: {}, applied_policy: [], catalog_version: '1', cache_hit: false }
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response)
  })
}

function renderExplore(planTier = 'explore') {
  return render(<QueryClientProvider client={new QueryClient()}><GuidedExplorePage planTier={planTier} authState="anonymous"/></QueryClientProvider>)
}

beforeEach(() => {
  window.history.replaceState(null, '', '/explore')
  sessionStorage.clear()
  queries = []
  vi.stubGlobal('fetch', mockFetch())
})

test('a question leads with a governed result, its cohort metrics, and URL state', async () => {
  renderExplore()
  const rail = document.querySelector('.question-grid') as HTMLElement
  expect(within(rail).getByRole('button', { pressed: true })).toHaveTextContent(guidedQuestions[0].question)
  expect(await screen.findByText('Energy has the highest average completeness in the eligible FY25 cohort.')).toBeInTheDocument()
  // The metric strip reports the cohort it is describing, not just the leader.
  const strip = document.querySelector('.metric-strip') as HTMLElement
  expect(within(strip).getByText('4 sector cohorts')).toBeInTheDocument()
  expect(within(strip).getByText('69.0 / 100')).toBeInTheDocument()
  expect(within(strip).getByText('1 of 4')).toBeInTheDocument()
  expect(window.location.search).toContain('question=sector-completeness-fy25')
  expect(window.location.search).toContain('%22measures%22')
})

test('derived insights are stated only where the rows support them', async () => {
  renderExplore()
  const list = await screen.findByRole('list')
  expect(within(list).getByText(/middle half of 4 sector cohorts falls between/)).toBeInTheDocument()
  expect(within(list).getByText(/rest on fewer companies than the published minimum/)).toBeInTheDocument()
  // Completeness is an average, so no summed total is ever offered.
  expect(within(list).queryByText(/of the .* total on screen/)).not.toBeInTheDocument()
})

test('every chart exposes a table twin carrying the same numbers', async () => {
  renderExplore()
  await screen.findByText(/Energy has the highest/)
  fireEvent.click(screen.getAllByRole('button', { name: 'Table' })[0])
  const table = await screen.findByRole('table')
  expect(within(table).getByRole('columnheader', { name: /vs median/ })).toBeInTheDocument()
  expect(within(table).getByRole('rowheader', { name: /Energy/ })).toBeInTheDocument()
  expect(within(table).getByText('+9.0 / 100')).toBeInTheDocument()
})

test('changing the measure rewrites the governed query rather than the rendering', async () => {
  renderExplore()
  await screen.findByText(/Energy has the highest/)
  fireEvent.change(screen.getByLabelText('Measure'), { target: { value: 'substance' } })
  await waitFor(() => expect(queries.some(item => item.measures[0] === 'substance')).toBe(true))
})

test('selecting a sector drills into the companies inside it and can be cleared', async () => {
  renderExplore('pro')
  await screen.findByText(/Energy has the highest/)
  fireEvent.click(screen.getAllByRole('button', { name: 'Table' })[0])
  fireEvent.click(within(await screen.findByRole('table')).getByRole('button', { name: 'Energy' }))

  await waitFor(() => expect(queries.some(item => item.dimensions[0] === 'company')).toBe(true))
  const drilled = queries.find(item => item.dimensions[0] === 'company') as SentQuery
  expect(drilled.filters).toContainEqual({ dimension: 'sector', operator: 'eq', value: 'Energy' })
  await waitFor(() => expect(window.location.search).toContain('drill='))
  expect(await screen.findByRole('button', { name: 'Clear drill-down ×' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Clear drill-down ×' }))
  await waitFor(() => expect(window.location.search).not.toContain('drill='))
})

test('drill-down analytics record the path without carrying any question text', async () => {
  const fetchMock = vi.mocked(fetch)
  renderExplore('pro')
  await screen.findByText(/Energy has the highest/)
  fireEvent.click(screen.getAllByRole('button', { name: 'Table' })[0])
  fireEvent.click(within(await screen.findByRole('table')).getByRole('button', { name: 'Energy' }))
  await waitFor(() => {
    const drillEvent = fetchMock.mock.calls.find(call => String(call[0]).includes('/api/events') && String((call[1] as RequestInit).body).includes('explore_drilldown_opened'))
    expect(drillEvent).toBeDefined()
    const payload = String((drillEvent?.[1] as RequestInit).body)
    expect(payload).toContain('"from_dimension":"sector"')
    expect(payload).toContain('"to_dimension":"company"')
    expect(payload).not.toContain('Energy')
  })
})

test('a paid question explains access instead of rendering an empty chart', async () => {
  renderExplore()
  fireEvent.click(screen.getByRole('button', { name: /What do leading companies disclose/ }))
  expect(await screen.findByText('This question needs Pro access.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Table' })).not.toBeInTheDocument()
  await waitFor(() => expect(window.location.search).toContain('question=company-scope3'))
})

test('follow-up payload keeps context separate and analytics excludes question text', async () => {
  const fetchMock = vi.mocked(fetch)
  renderExplore()
  fireEvent.click(await screen.findByRole('button', { name: 'Compare this with FY 2024.' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/nlq'), expect.objectContaining({ method: 'POST' })))
  const nlqCall = fetchMock.mock.calls.find(call => String(call[0]).includes('/api/nlq'))
  const payload = JSON.parse(String((nlqCall?.[1] as RequestInit).body)) as Record<string, unknown>
  expect(payload).toHaveProperty('question', 'Compare this with FY 2024.')
  expect(payload).toHaveProperty('base_dsl')
  const eventCalls = fetchMock.mock.calls.filter(call => String(call[0]).includes('/api/events'))
  expect(eventCalls.some(call => String((call[1] as RequestInit).body).includes('Compare this with FY 2024.'))).toBe(false)
})

test('re-measuring drops the curated summary rather than mislabelling the new measure', async () => {
  renderExplore()
  expect(await screen.findByText(/highest average completeness/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Measure'), { target: { value: 'p6.e1.energy_total_gj' } })
  // The question's wording described completeness; it must not survive the switch.
  await waitFor(() => expect(screen.queryByText(/highest average completeness/)).not.toBeInTheDocument())
  expect(screen.getByText(/adjusted/)).toBeInTheDocument()
  expect(await screen.findByText(/reports the largest value in this view/)).toBeInTheDocument()
})
