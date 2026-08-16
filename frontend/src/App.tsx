import { useEffect, useState } from 'react'

import { AuthPanel } from './components/AuthPanel'
import { AdminIngestionPage } from './components/AdminIngestionPage'
import { CookieDisclosure } from './components/CookieDisclosure'
import { AdminAnalyticsPage, AdminLeadsPage, BillingPage, DeepDivePage, PrivacyPage } from './components/EngagementPages'
import { HealthFooter } from './components/HealthFooter'
import { GuidedExplorePage } from './components/GuidedExplorePage'
import { AnalysePage } from './components/JourneyPages'
import {
  AskPage, AssurancePage, BenchmarksPage, CompanyPage, HomePage, LibraryPage,
  MaterialityPage, MethodologyPage, PricingPage, SectorPage, StyleguidePage,
} from './components/Phase2Pages'
import { QualityReview } from './components/QualityReview'
import { SiteHeader } from './components/SiteHeader'
import { StudioPage } from './components/StudioPage'
import { accessToken, fetchMe, logout, type OrgSummary, type UserProfile } from './lib/auth'
import { trackPageview } from './lib/track'

const pageMap: Record<string, () => JSX.Element> = { '/sectors': SectorPage, '/companies': CompanyPage, '/benchmarks': BenchmarksPage, '/materiality': MaterialityPage, '/assurance': AssurancePage, '/ask': AskPage, '/library': LibraryPage, '/learn': LibraryPage, '/analyse': AnalysePage, '/methodology': MethodologyPage, '/pricing': PricingPage, '/styleguide': StyleguidePage }
const titles: Record<string, string> = { '/': 'BRSR Lens — understand, compare, and improve BRSR filings', '/explore': 'Explore BRSR insights — BRSR Lens', '/analyse': 'Analyse my BRSR — BRSR Lens', '/studio': 'Filing Studio — BRSR Lens', '/learn': 'Learn BRSR — BRSR Lens', '/assurance': 'Assurance trends — BRSR Lens', '/ask': 'Ask BRSR Lens' }

function updateMetadata(path: string): void {
  const title = titles[path] ?? `${path.slice(1).replaceAll('-', ' ')} — BRSR Lens`
  document.title = title
  ;[['citation_title', title], ['citation_public_url', `${window.location.origin}${path}`]].forEach(([name, content]) => {
    let element = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
    if (!element) { element = document.createElement('meta'); element.name = name; document.head.append(element) }
    element.content = content
  })
  const canonicalPath = path === '/learn' ? '/library' : path
  let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!canonical) { canonical = document.createElement('link'); canonical.rel = 'canonical'; document.head.append(canonical) }
  canonical.href = `${window.location.origin}${canonicalPath}`
}

export default function App() {
  const [profile, setProfile] = useState<UserProfile | null>(null); const [org, setOrg] = useState<OrgSummary | null>(null); const [authOpen, setAuthOpen] = useState(false)
  const [authReady, setAuthReady] = useState(() => !accessToken())
  const path = window.location.pathname; const tier = org?.plan_tier ?? profile?.plan_tier ?? 'explore'
  useEffect(() => { updateMetadata(path); trackPageview(); if (accessToken()) void fetchMe().then(user => { setProfile(user); setOrg(user.orgs[0] ?? null) }).catch(logout).finally(() => setAuthReady(true)) }, [path])
  const Page = pageMap[path]
  const content = path === '/' ? <HomePage authState={profile ? 'authenticated' : 'anonymous'} planTier={tier} trackView={authReady}/> : path === '/explore' ? <GuidedExplorePage planTier={tier} authState={profile ? 'authenticated' : 'anonymous'}/> : path === '/studio' ? <StudioPage orgId={org?.id}/> : path === '/deep-dive' ? <DeepDivePage profile={profile} org={org}/> : path === '/privacy' ? <PrivacyPage profile={profile}/> : path === '/billing' ? <BillingPage profile={profile} org={org}/> : path === '/admin/ingestion' ? <AdminIngestionPage/> : path === '/admin/analytics' ? <AdminAnalyticsPage/> : path === '/admin/leads' ? <AdminLeadsPage/> : Page ? <Page/> : <HomePage authState={profile ? 'authenticated' : 'anonymous'} planTier={tier} trackView={authReady}/>
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to main content</a>
    <SiteHeader path={path} tier={tier} profile={profile} org={org} onOrgChange={setOrg} onSignIn={() => setAuthOpen(true)} onSignOut={() => { logout(); setProfile(null); setOrg(null) }}/>
    <main id="main-content" className="page" tabIndex={-1}>{path === '/explore' && <aside className="provisional-corpus-notice"><strong>Provisional FY25 figures</strong><span>Environmental metrics are converted to common units from official NSE BRSR filings and are still under review. Each figure links to its source disclosure. Read the <a href="/methodology">methodology</a> before citing these numbers.{profile?.is_admin && <> Reviewers: open <a href="/admin/ingestion">Admin → Ingestion</a>.</>}</span></aside>}{content}{profile?.is_admin && path === '/account' && <QualityReview/>}</main>
    <footer className="site-footer"><div className="brand"><i/>BRSR <strong>Lens</strong></div><p>Disclosure intelligence that keeps the evidence attached.</p><div><a href="/methodology">Methodology</a><a href="/privacy">Privacy</a><a href="/pricing">Access</a></div><HealthFooter/></footer>
    {authOpen && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Sign in"><div className="auth-modal"><button className="modal-close" onClick={() => setAuthOpen(false)} aria-label="Close sign-in dialog">Close ×</button><AuthPanel onAuthenticated={user => { setProfile(user); setOrg(user.orgs[0] ?? null); setAuthOpen(false) }}/></div></div>}<CookieDisclosure/></div>
}
