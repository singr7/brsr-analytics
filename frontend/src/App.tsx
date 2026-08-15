import { useEffect, useState } from 'react'

import { AuthPanel } from './components/AuthPanel'
import { CookieDisclosure } from './components/CookieDisclosure'
import { HealthFooter } from './components/HealthFooter'
import {
  AskPage, AssurancePage, BenchmarksPage, CompanyPage, HomePage, LibraryPage,
  MaterialityPage, MethodologyPage, PricingPage, SectorPage, StyleguidePage,
} from './components/Phase2Pages'
import { QualityReview } from './components/QualityReview'
import { accessToken, fetchMe, logout, type OrgSummary, type UserProfile } from './lib/auth'
import { trackPageview } from './lib/track'

const publicNav = [['Sectors', '/sectors'], ['Companies', '/companies'], ['Materiality', '/materiality'], ['Assurance', '/assurance'], ['Methodology', '/methodology']]
const pageMap: Record<string, () => JSX.Element> = { '/': HomePage, '/sectors': SectorPage, '/companies': CompanyPage, '/benchmarks': BenchmarksPage, '/materiality': MaterialityPage, '/assurance': AssurancePage, '/ask': AskPage, '/library': LibraryPage, '/methodology': MethodologyPage, '/pricing': PricingPage, '/styleguide': StyleguidePage }

export default function App() {
  const [profile, setProfile] = useState<UserProfile | null>(null); const [org, setOrg] = useState<OrgSummary | null>(null); const [authOpen, setAuthOpen] = useState(false)
  useEffect(() => { trackPageview(); if (accessToken()) void fetchMe().then(user => { setProfile(user); setOrg(user.orgs[0] ?? null) }).catch(logout) }, [])
  useEffect(() => {
    const path = window.location.pathname; const title = path === '/' ? 'BRSR Lens — disclosure intelligence with lineage' : `${path.slice(1).replaceAll('-', ' ')} — BRSR Lens`; document.title = title
    let citation = document.querySelector<HTMLMetaElement>('meta[name="citation_title"]'); if (!citation) { citation = document.createElement('meta'); citation.name = 'citation_title'; document.head.append(citation) } citation.content = title
  }, [])
  const Page = pageMap[window.location.pathname] ?? HomePage; const tier = org?.plan_tier ?? profile?.plan_tier ?? 'explore'
  return <div className="app-shell"><header className="site-header"><a href="/" className="brand"><i/>BRSR <strong>Lens</strong></a><nav aria-label="Public navigation">{publicNav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav><div className="header-actions"><a href="/ask">Ask the corpus</a>{profile ? <><select aria-label="Organisation" value={org?.id ?? ''} onChange={event => setOrg(profile.orgs.find(item => item.id === event.target.value) ?? null)}><option value="">Personal · {profile.plan_tier}</option>{profile.orgs.map(item => <option value={item.id} key={item.id}>{item.name} · {item.plan_tier}</option>)}</select><button onClick={() => { logout(); setProfile(null); setOrg(null) }}>Sign out</button></> : <button onClick={() => setAuthOpen(true)}>Sign in</button>}</div></header>
    <div className="tier-rail"><span>{tier} access</span><a href="/benchmarks">My benchmarks {tier === 'explore' && '· Pro'}</a><a href="/library">Learning Library</a><a href="/pricing">Pricing</a></div>
    <main className="page"><Page/>{profile?.is_admin && window.location.pathname === '/account' && <QualityReview/>}</main>
    <footer className="site-footer"><div className="brand"><i/>BRSR <strong>Lens</strong></div><p>Disclosure intelligence that keeps the evidence attached.</p><div><a href="/methodology">Methodology</a><a href="/styleguide">Styleguide</a><a href="/pricing">Access</a></div><HealthFooter/></footer>
    {authOpen && <div className="modal-backdrop" role="dialog" aria-label="Sign in"><div className="auth-modal"><button className="modal-close" onClick={() => setAuthOpen(false)}>Close ×</button><AuthPanel onAuthenticated={user => { setProfile(user); setOrg(user.orgs[0] ?? null); setAuthOpen(false) }}/></div></div>}<CookieDisclosure/></div>
}
