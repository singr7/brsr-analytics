import { useEffect, useState } from 'react'

import { AuthPanel } from './components/AuthPanel'
import { CookieDisclosure } from './components/CookieDisclosure'
import { DemoChart } from './components/DemoChart'
import { HealthFooter } from './components/HealthFooter'
import { accessToken, fetchMe, logout, type OrgSummary, type UserProfile } from './lib/auth'
import { trackPageview } from './lib/track'

const navItems = [
  { label: 'Explore', tiers: ['explore', 'pro', 'studio', 'research'] },
  { label: 'Peer analytics', tiers: ['pro', 'research'] },
  { label: 'Filing Studio', tiers: ['studio'] },
  { label: 'Research API', tiers: ['research'] },
]

export default function App() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [org, setOrg] = useState<OrgSummary | null>(null)

  useEffect(() => {
    trackPageview()
    if (accessToken()) void fetchMe()
      .then((user) => { setProfile(user); setOrg(user.orgs[0] ?? null) })
      .catch(logout)
  }, [])

  const tier = org?.plan_tier ?? profile?.plan_tier ?? 'explore'
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_#dceee3,_transparent_42%)]">
      <header className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-7">
        <div className="text-xl font-semibold tracking-tight">BRSR Lens</div>
        <nav className="flex flex-wrap items-center gap-3" aria-label="Product navigation">
          {navItems.map((item) => {
            const unlocked = item.tiers.includes(tier)
            return <span key={item.label} className={`rounded-full px-3 py-1 text-xs ${unlocked ? 'bg-white/70' : 'border border-amber-600/30 bg-amber-50 text-amber-900'}`}>{item.label}{!unlocked && ' · Upgrade'}</span>
          })}
        </nav>
        {profile ? (
          <div className="flex items-center gap-3 text-sm">
            <select aria-label="Organisation" className="rounded-lg border bg-white px-2 py-1" value={org?.id ?? ''} onChange={(event) => setOrg(profile.orgs.find((item) => item.id === event.target.value) ?? null)}>
              <option value="">Personal · {profile.plan_tier}</option>
              {profile.orgs.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.plan_tier}</option>)}
            </select>
            <button onClick={() => { logout(); setProfile(null); setOrg(null) }}>Sign out</button>
          </div>
        ) : <span className="rounded-full border border-emerald-900/20 px-3 py-1 text-xs uppercase tracking-widest">Public</span>}
      </header>
      <main className="mx-auto grid max-w-6xl gap-8 px-6 pb-16 pt-14 lg:grid-cols-[1fr_1.15fr]">
        <section className="self-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.24em] text-emerald-700">Disclosure intelligence</p>
          <h1 className="m-0 text-5xl font-semibold leading-tight tracking-tight">See the substance behind sustainability reporting.</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-emerald-950/70">Traceable BRSR analytics, filing preparation, and assurance readiness in one disciplined platform.</p>
          {!profile && <div className="mt-8"><AuthPanel onAuthenticated={(user) => { setProfile(user); setOrg(user.orgs[0] ?? null) }} /></div>}
        </section>
        <section className="rounded-3xl border border-white/70 bg-white/80 p-6 shadow-xl shadow-emerald-950/10 backdrop-blur">
          <div className="mb-5 flex items-baseline justify-between">
            <div><p className="m-0 text-sm text-emerald-950/60">Illustrative portfolio</p><h2 className="m-0 mt-1 text-2xl">BRSR readiness</h2></div>
            <span className="text-sm text-emerald-700">FY 2025–26</span>
          </div>
          <DemoChart />
        </section>
      </main>
      <CookieDisclosure />
      <HealthFooter />
    </div>
  )
}
