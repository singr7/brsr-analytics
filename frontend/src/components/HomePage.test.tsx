import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { HomePage } from './Phase2Pages'

vi.mock('echarts-for-react', () => ({ default: () => <div>chart</div> }))
vi.mock('echarts-for-react/lib/core', () => ({ default: () => <div>chart</div> }))

test('entry events contain only the approved privacy-safe context', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    void init
    const body = String(input).includes('/api/query')
      ? { data: [{ sector: 'Energy', value: 78 }], lineage_refs: {}, applied_policy: [], catalog_version: '1', cache_hit: false }
      : { accepted: 1 }
    return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient()}><HomePage authState="authenticated" planTier="studio"/></QueryClientProvider>)
  const analysisLink = screen.getByRole('link', { name: /I have a BRSR report/ })
  analysisLink.addEventListener('click', event => event.preventDefault())
  fireEvent.click(analysisLink)
  await waitFor(() => expect(fetchMock.mock.calls.filter(call => String(call[0]).includes('/api/events')).length).toBeGreaterThanOrEqual(3))
  const payloads = fetchMock.mock.calls.filter(call => String(call[0]).includes('/api/events')).map(call => JSON.parse(String((call[1] as RequestInit).body)) as { events: Array<{ name: string; properties: Record<string, unknown> }> })
  const s18Events = payloads.flatMap(payload => payload.events).filter(event => ['guided_insight_viewed', 'home_intent_selected', 'analyse_cta_selected'].includes(event.name))
  expect(s18Events.map(event => event.name)).toEqual(expect.arrayContaining(['guided_insight_viewed', 'home_intent_selected', 'analyse_cta_selected']))
  for (const event of s18Events) {
    expect(Object.keys(event.properties).sort()).toEqual(['auth_state', 'intent', 'plan_tier', 'source_surface'])
    expect(JSON.stringify(event.properties)).not.toMatch(/report_text|query_text|question|email|company|organisation/i)
  }
})
