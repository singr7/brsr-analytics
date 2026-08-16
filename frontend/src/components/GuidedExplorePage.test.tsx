import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { guidedQuestions } from '../content/guided-questions'
import { GuidedExplorePage } from './GuidedExplorePage'

vi.mock('echarts-for-react', () => ({ default: () => <div>chart</div> }))
vi.mock('echarts-for-react/lib/core', () => ({ default: () => <div>chart</div> }))

const semantic = { data: [{ sector: 'Energy', value: 78 }, { sector: 'Metals', value: 71 }], lineage_refs: {}, applied_policy: [], catalog_version: '1', cache_hit: false }

beforeEach(() => {
  window.history.replaceState(null, '', '/explore')
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const body = String(input).includes('/api/query') ? semantic : { accepted: 1 }
    return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response)
  }))
})

test('curated questions lead with a result and preserve URL state', async () => {
  render(<QueryClientProvider client={new QueryClient()}><GuidedExplorePage planTier="explore" authState="anonymous"/></QueryClientProvider>)
  expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(12)
  expect(screen.getByRole('button', { pressed: true })).toHaveTextContent(guidedQuestions[0].question)
  expect(await screen.findByText('Energy has the highest average completeness in the eligible FY25 cohort.')).toBeInTheDocument()
  expect(window.location.search).toContain('question=sector-completeness-fy25')
  expect(window.location.search).toContain('%22measures%22')
})

test('advanced controls are one action away and paid questions explain access', async () => {
  render(<QueryClientProvider client={new QueryClient()}><GuidedExplorePage planTier="explore" authState="anonymous"/></QueryClientProvider>)
  fireEvent.click(screen.getAllByText('Refine this view')[0])
  expect(screen.getByLabelText('Financial year')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /What do leading companies disclose/ }))
  expect(await screen.findByText('This question needs Pro access.')).toBeInTheDocument()
  await waitFor(() => expect(window.location.search).toContain('question=company-scope3'))
})

test('follow-up payload keeps context separate and analytics excludes question text', async () => {
  const fetchMock = vi.mocked(fetch)
  render(<QueryClientProvider client={new QueryClient()}><GuidedExplorePage planTier="explore" authState="anonymous"/></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Compare this with FY 2024.' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/nlq'), expect.objectContaining({ method: 'POST' })))
  const nlqCall = fetchMock.mock.calls.find(call => String(call[0]).includes('/api/nlq'))
  const payload = JSON.parse(String((nlqCall?.[1] as RequestInit).body)) as Record<string, unknown>
  expect(payload).toHaveProperty('question', 'Compare this with FY 2024.')
  expect(payload).toHaveProperty('base_dsl')
  const eventCalls = fetchMock.mock.calls.filter(call => String(call[0]).includes('/api/events'))
  expect(eventCalls.some(call => String((call[1] as RequestInit).body).includes('Compare this with FY 2024.'))).toBe(false)
})
