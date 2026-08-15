import { fireEvent, render, screen } from '@testing-library/react'

import { SiteHeader } from './SiteHeader'

const noop = () => undefined

test('marks the active journey and exposes the anonymous utility actions', () => {
  render(<SiteHeader path="/assurance" tier="explore" profile={null} org={null} onOrgChange={noop} onSignIn={noop} onSignOut={noop}/>)
  expect(screen.getByRole('link', { name: 'Explore insights' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Ask BRSR Lens' })).toHaveAttribute('href', '/ask')
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
})

test('mobile menu moves focus in, closes on Escape, and restores trigger focus', async () => {
  render(<SiteHeader path="/" tier="explore" profile={null} org={null} onOrgChange={noop} onSignIn={noop} onSignOut={noop}/>)
  const trigger = screen.getByRole('button', { name: 'Open menu' })
  fireEvent.click(trigger)
  expect(screen.getByRole('navigation', { name: 'Mobile journeys' })).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: 'Explore insights' })[1]).toHaveFocus()
  fireEvent.keyDown(document, { key: 'Escape' })
  await new Promise(resolve => window.setTimeout(resolve, 0))
  expect(screen.queryByRole('navigation', { name: 'Mobile journeys' })).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
