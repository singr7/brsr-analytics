import { useEffect, useMemo, useState } from 'react'

import { RankedBar, type ChartDatum } from '../charts/ChartKit'
import { apiUrl } from '../lib/api'
import { accessToken, type OrgSummary, type UserProfile } from '../lib/auth'
import { track } from '../lib/track'

const authHeaders = () => ({ Authorization: `Bearer ${accessToken() ?? ''}` })

function Head({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return <header className="page-head"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{copy}</p></header>
}

interface CompanyOption { id: string; name: string; sector: string }
export function DeepDivePage({ profile, org }: { profile: UserProfile | null; org: OrgSummary | null }) {
  const [companies, setCompanies] = useState<CompanyOption[]>([]); const [selected, setSelected] = useState<string[]>([])
  const [question, setQuestion] = useState(''); const [timeframe, setTimeframe] = useState('FY 2024–25 and FY 2023–24')
  const [budget, setBudget] = useState('unsure'); const [email, setEmail] = useState(profile?.email ?? ''); const [message, setMessage] = useState('')
  useEffect(() => { void fetch(`${apiUrl}/api/companies/options`).then(response => response.json() as Promise<CompanyOption[]>).then(setCompanies); void track('expert_cta_viewed', { surface: 'deepdive_form' }) }, [])
  useEffect(() => { if (profile?.email) setEmail(profile.email) }, [profile?.email])
  const submit = async () => {
    setMessage('Sending your brief…')
    const response = await fetch(`${apiUrl}/api/deepdives`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(org ? { 'X-Org-ID': org.id } : {}) }, body: JSON.stringify({ question, company_ids: selected, timeframe, budget_band: budget, contact_email: email }) })
    if (response.ok) setMessage('Request received. We’ll scope it before anything is quoted.')
    else setMessage(response.status === 401 ? 'Sign in before sending your brief.' : 'Please check every field and try again.')
  }
  return <><Head eyebrow="Expert research" title="Request an expert deep-dive" copy="Set the question and boundaries first. Panacea Bioedge will scope the work with you before quoting it."/><section className="deepdive-form"><label>What decision or disclosure question should this answer?<textarea value={question} onChange={event => setQuestion(event.target.value)} minLength={20}/></label><fieldset><legend>Companies · choose up to 20</legend><div className="company-picker">{companies.map(company => <label key={company.id}><input type="checkbox" checked={selected.includes(company.id)} disabled={!selected.includes(company.id) && selected.length >= 20} onChange={event => setSelected(current => event.target.checked ? [...current, company.id] : current.filter(id => id !== company.id))}/><span><strong>{company.name}</strong><small>{company.sector}</small></span></label>)}</div></fieldset><div className="form-row"><label>Timeframe<input value={timeframe} onChange={event => setTimeframe(event.target.value)}/></label><label>Budget band<select value={budget} onChange={event => setBudget(event.target.value)}><option value="unsure">Not sure yet</option><option value="under_1l">Under ₹1 lakh</option><option value="1l_3l">₹1–3 lakh</option><option value="3l_5l">₹3–5 lakh</option><option value="5l_plus">₹5 lakh+</option></select></label></div><label>Contact email<input type="email" value={email} onChange={event => setEmail(event.target.value)}/></label><button disabled={question.length < 20 || !selected.length || !email} onClick={() => void submit()}>Send scoped request →</button>{message && <p role="status">{message}</p>}<small>No automatic sales sequence. Your brief goes to the team responsible for scoping the work.</small></section></>
}

interface FunnelStep { name: string; users: number; conversion_from_previous: number | null }
interface Count { name: string; count: number }
interface Analytics { visit_to_pro: FunnelStep[]; studio_to_export: FunnelStep[]; feature_usage: Count[]; nlq_themes: Count[]; sector_interest: Count[] }
const chart = (items: Count[] | FunnelStep[]): ChartDatum[] => items.map(item => ({ name: item.name, value: 'count' in item ? item.count : item.users }))

export function AdminAnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null)
  useEffect(() => { void fetch(`${apiUrl}/api/admin/analytics`, { headers: authHeaders() }).then(response => response.ok ? response.json() as Promise<Analytics> : Promise.reject()).then(setData).catch(() => setData(null)) }, [])
  return <><Head eyebrow="Internal · first-party" title="Engagement analytics" copy="Funnels, product use, market questions, and sector interest—built directly on the disclosed event stream."/>{data ? <div className="dashboard-grid"><RankedBar title="Visit → signup → Pro" data={chart(data.visit_to_pro)}/><RankedBar title="Studio start → export" data={chart(data.studio_to_export)}/><RankedBar title="Feature usage" data={chart(data.feature_usage)}/><RankedBar title="NLQ themes · embedding clusters" data={chart(data.nlq_themes)}/><RankedBar title="Sector interest" data={chart(data.sector_interest)}/></div> : <div className="chart-state">Administrator access is required.</div>}</>
}

interface Signal { key: string; label: string; occurred_at: string; points: number }
interface Lead { id: string; score: number; status: string; outcome: string | null; signals: Signal[] }
interface DeepDive { id: string; question: string; timeframe: string; budget_band: string; status: string }
interface Quality { by_signal: Array<{ signal: string; leads: number; positive_outcomes: number; conversion_rate: number }> }
export function AdminLeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]); const [requests, setRequests] = useState<DeepDive[]>([]); const [quality, setQuality] = useState<Quality>({ by_signal: [] })
  const load = () => { void fetch(`${apiUrl}/api/admin/leads`, { headers: authHeaders() }).then(r => r.json() as Promise<Lead[]>).then(setLeads); void fetch(`${apiUrl}/api/admin/deepdives`, { headers: authHeaders() }).then(r => r.json() as Promise<DeepDive[]>).then(setRequests); void fetch(`${apiUrl}/api/admin/leads/quality`, { headers: authHeaders() }).then(r => r.json() as Promise<Quality>).then(setQuality) }
  useEffect(load, [])
  const qualityChart = useMemo(() => quality.by_signal.map(item => ({ name: item.signal.replaceAll('_', ' '), value: Math.round(item.conversion_rate * 100) })), [quality])
  const outcome = async (id: string, value: string) => { await fetch(`${apiUrl}/api/admin/leads/${id}/outcome`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify({ outcome: value }) }); load() }
  const advance = async (item: DeepDive) => { const next: Record<string, string> = { new: 'scoped', scoped: 'quoted', quoted: 'delivered' }; if (!next[item.status]) return; await fetch(`${apiUrl}/api/admin/deepdives/${item.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify({ status: next[item.status] }) }); load() }
  return <><Head eyebrow="Bioedge workflow" title="Leads and expert briefs" copy="Context for a useful conversation, with a visible outcome loop for tuning signal weights."/><div className="admin-columns"><section><h2>Lead context</h2>{leads.map(lead => <article className="workflow-card" key={lead.id}><div><strong>{lead.score} points</strong><span>{lead.status}</span></div><ol>{lead.signals.map(signal => <li key={`${signal.key}:${signal.occurred_at}`}>{signal.label} <small>+{signal.points}</small></li>)}</ol><label>BD outcome<select value={lead.outcome ?? ''} onChange={event => void outcome(lead.id, event.target.value)}><option value="">Record outcome…</option><option value="qualified">Qualified</option><option value="meeting">Meeting</option><option value="proposal">Proposal</option><option value="won">Won</option><option value="lost">Lost</option><option value="not_a_fit">Not a fit</option></select></label></article>)}</section><section><h2>Deep-dive tickets</h2>{requests.map(item => <article className="workflow-card" key={item.id}><span>{item.status}</span><h3>{item.question}</h3><p>{item.timeframe} · {item.budget_band.replaceAll('_', ' ')}</p>{item.status !== 'delivered' && <button onClick={() => void advance(item)}>Advance workflow →</button>}</article>)}</section></div><RankedBar title="Positive outcome by signal · %" data={qualityChart}/></>
}

export function PrivacyPage({ profile }: { profile: UserProfile | null }) {
  const [enabled, setEnabled] = useState(!document.cookie.includes('analytics_opt_out=1')); const [message, setMessage] = useState('')
  const save = async () => { if (!profile) { document.cookie = `analytics_opt_out=${enabled ? '0' : '1'}; Max-Age=31536000; Path=/; SameSite=Lax`; setMessage('Preference saved on this browser.'); return } const response = await fetch(`${apiUrl}/api/privacy/preference`, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify({ analytics_enabled: enabled }) }); setMessage(response.ok ? 'Preference saved. Opting out also removed your identified raw events.' : 'Could not save preference.') }
  return <><Head eyebrow="Privacy" title="First-party analytics, under your control" copy="BRSR Lens uses its own event stream to understand product reliability, useful workflows, and aggregate market questions. It does not load third-party advertising pixels."/><section className="privacy-card"><h2>Your analytics preference</h2><label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)}/> Allow first-party product analytics</label><p>Raw events are retained for 13 months, then reduced to daily aggregate counts. Lead routing is suppressed when you opt out. You can also export or delete identified events from your account.</p><button onClick={() => void save()}>Save preference</button>{message && <p role="status">{message}</p>}</section></>
}

export function BillingPage({ profile, org }: { profile: UserProfile | null; org: OrgSummary | null }) {
  const [tier, setTier] = useState('pro'); const [seats, setSeats] = useState(5); const [message, setMessage] = useState('')
  const submit = async () => {
    if (!profile || !org) { setMessage('Sign in and select an organisation first.'); return }
    setMessage('Sending invoice request…')
    const response = await fetch(`${apiUrl}/api/billing/invoice-requests`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders(), 'X-Org-ID': org.id }, body: JSON.stringify({ tier, seats, term_months: 12, billing_email: profile.email }) })
    setMessage(response.ok ? 'Request received. The team will confirm licence dates and invoice terms by email.' : 'Only an organisation owner can request an invoice. Please check your selected organisation.')
  }
  return <><Head eyebrow="Billing-lite" title="Request annual access" copy="No card checkout. Choose the working plan and seats; the team confirms the licence term before activating it."/><section className="privacy-card"><h2>Invoice plan sheet</h2><div className="form-row"><label>Plan<select value={tier} onChange={event => setTier(event.target.value)}><option value="pro">Pro</option><option value="studio">Studio</option><option value="research">Research</option></select></label><label>Seats<input type="number" min="1" max="500" value={seats} onChange={event => setSeats(Number(event.target.value))}/></label></div><p>Billing contact: {profile?.email ?? 'Sign in required'}<br/>Organisation: {org?.name ?? 'Select an organisation'}</p><button onClick={() => void submit()}>Request invoice →</button>{message && <p role="status">{message}</p>}</section></>
}
