import { render, screen } from '@testing-library/react'

import { PricingPage } from './Phase2Pages'

test('renders pricing from the shared plans response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      tiers: {
        research: { name: 'Research', price_label: 'Configured price', description: 'Configured description', features: ['Scoped API keys'], cta: 'Contact research licensing' },
      },
      faq: [{ question: 'Configured question?', answer: 'Configured answer.' }],
    }),
  }))
  render(<PricingPage />)
  expect(await screen.findByText('Configured price')).toBeInTheDocument()
  expect(screen.getByText('Scoped API keys')).toBeInTheDocument()
  expect(screen.getByText('Configured question?')).toBeInTheDocument()
})
