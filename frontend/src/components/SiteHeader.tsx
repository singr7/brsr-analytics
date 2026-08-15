import { useEffect, useRef, useState } from 'react'

import type { OrgSummary, UserProfile } from '../lib/auth'

const journeyItems = [
  { label: 'Explore insights', href: '/explore', routes: ['/explore', '/sectors', '/companies', '/materiality', '/assurance', '/benchmarks'] },
  { label: 'Analyse my BRSR', href: '/analyse', routes: ['/analyse'] },
  { label: 'Filing Studio', href: '/studio', routes: ['/studio'] },
  { label: 'Learn BRSR', href: '/learn', routes: ['/learn', '/library'] },
]

const utilityItems = [
  { label: 'Ask BRSR Lens', href: '/ask' },
  { label: 'Methodology', href: '/methodology' },
  { label: 'Pricing', href: '/pricing' },
]

interface AccountControlsProps {
  profile: UserProfile | null
  org: OrgSummary | null
  onOrgChange: (org: OrgSummary | null) => void
  onSignIn: () => void
  onSignOut: () => void
}

function isCurrent(path: string, routes: string[]): boolean {
  return routes.includes(path)
}

export function JourneyNav({ path }: { path: string }) {
  return <nav className="journey-nav" aria-label="Journeys">
    {journeyItems.map(item => <a key={item.href} href={item.href} aria-current={isCurrent(path, item.routes) ? 'page' : undefined}>{item.label}</a>)}
  </nav>
}

export function UtilityNav({ path }: { path: string }) {
  return <nav className="utility-nav" aria-label="Utility navigation">
    {utilityItems.map(item => <a key={item.href} href={item.href} aria-current={path === item.href ? 'page' : undefined}>{item.label}</a>)}
  </nav>
}

function AccountControls({ profile, org, onOrgChange, onSignIn, onSignOut }: AccountControlsProps) {
  return <div className="account-controls">
    {profile ? <>
      <label className="sr-only" htmlFor="organisation-switcher">Organisation</label>
      <select id="organisation-switcher" aria-label="Organisation" value={org?.id ?? ''} onChange={event => onOrgChange(profile.orgs.find(item => item.id === event.target.value) ?? null)}>
        <option value="">Personal · {profile.plan_tier}</option>
        {profile.orgs.map(item => <option value={item.id} key={item.id}>{item.name} · {item.plan_tier}</option>)}
      </select>
      <button type="button" onClick={onSignOut}>Sign out</button>
    </> : <button type="button" onClick={onSignIn}>Sign in</button>}
  </div>
}

function MobileMenu({ path, account }: { path: string; account: AccountControlsProps }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const firstLink = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    if (!open) return
    firstLink.current?.focus()
    const close = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      window.setTimeout(() => trigger.current?.focus(), 0)
    }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [open])
  return <div className="mobile-navigation">
    <button ref={trigger} type="button" className="menu-trigger" aria-expanded={open} aria-controls="mobile-menu" onClick={() => setOpen(value => !value)}>{open ? 'Close menu' : 'Open menu'}</button>
    {open && <div id="mobile-menu" className="mobile-menu">
      <nav aria-label="Mobile journeys">{journeyItems.map((item, index) => <a ref={index === 0 ? firstLink : undefined} key={item.href} href={item.href} aria-current={isCurrent(path, item.routes) ? 'page' : undefined}>{item.label}</a>)}</nav>
      <nav aria-label="Mobile utility navigation">{utilityItems.map(item => <a key={item.href} href={item.href} aria-current={path === item.href ? 'page' : undefined}>{item.label}</a>)}</nav>
      <AccountControls {...account}/>
    </div>}
  </div>
}

interface SiteHeaderProps extends AccountControlsProps {
  path: string
  tier: string
}

export function SiteHeader({ path, tier, profile, org, onOrgChange, onSignIn, onSignOut }: SiteHeaderProps) {
  const account = { profile, org, onOrgChange, onSignIn, onSignOut }
  const licence = org?.licence_state === 'grace' ? ' · grace period' : org?.licence_state === 'read_only' ? ' · read only' : ''
  return <>
    <header className="site-header">
      <a href="/" className="brand" aria-label="BRSR Lens home"><i aria-hidden="true"/>BRSR <strong>Lens</strong></a>
      <JourneyNav path={path}/>
      <div className="desktop-utility"><UtilityNav path={path}/><AccountControls {...account}/></div>
      <MobileMenu path={path} account={account}/>
    </header>
    <div className="tier-rail" aria-label="Account access">
      <span>{tier} access{licence}</span>
      {profile && <a href="/benchmarks" aria-current={path === '/benchmarks' ? 'page' : undefined}>Peer benchmarks {tier === 'explore' && '· Pro'}</a>}
      <a href="/sectors">Browse detail views</a>
    </div>
  </>
}
