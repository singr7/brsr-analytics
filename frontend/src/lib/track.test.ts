import { track } from './track'

test('first-party beacon sends a registered event with credentials', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true })
  vi.stubGlobal('fetch', fetchMock)
  await track('viewed_company', { company_id: 'fixture-company' })
  expect(fetchMock).toHaveBeenCalledOnce()
  const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(request.credentials).toBe('include')
  expect(JSON.parse(request.body as string)).toMatchObject({
    events: [{ name: 'viewed_company', properties: { company_id: 'fixture-company' } }],
  })
})

test('analytics opt-out suppresses the beacon absolutely', async () => {
  document.cookie = 'analytics_opt_out=1; Path=/'
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  await track('pricing_viewed')
  expect(fetchMock).not.toHaveBeenCalled()
  document.cookie = 'analytics_opt_out=0; Path=/'
})
