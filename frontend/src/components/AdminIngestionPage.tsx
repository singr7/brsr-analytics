import { useEffect, useMemo, useState } from 'react'

import { apiUrl } from '../lib/api'
import { accessToken } from '../lib/auth'

interface InventoryItem {
  company_id: string; company_name: string; ticker: string; sector: string; industry: string
  fy: number | null; status: string; source: string | null; submission_date: string | null
  revision_date: string | null; acquired_at: string | null; raw_fact_count: number
  mapped_field_count: number; source_url: string | null
}
interface IngestionRun {
  id: string; mode: string; status: string; target_fy: number; requested_count: number
  fetched_count: number; parsed_count: number; missing_count: number; error_count: number
  started_at: string; completed_at: string | null
}
interface ConceptMapping {
  id: string; source_concept: string; field_key: string; target_unit: string | null
  selection_strategy: string; unit_rules: Record<string, unknown>; confidence: number
  rationale: string; assumption: string; evidence_url: string; review_status: string
  reviewer_notes: string | null; reviewed_at: string | null
}
interface Inventory {
  config: { source_enabled: boolean; schedule_enabled: boolean; refresh_hours: number; default_fy: number; default_batch_size: number; next_offset: number }
  companies: number; filings: number; parsed_filings: number; raw_facts: number
  items: InventoryItem[]; recent_runs: IngestionRun[]; concept_mappings: ConceptMapping[]
}

function MappingReviewRow({ mapping, onSave }: { mapping: ConceptMapping; onSave: (id: string, status: string, notes: string) => Promise<void> }) {
  const [status, setStatus] = useState(mapping.review_status)
  const [notes, setNotes] = useState(mapping.reviewer_notes ?? '')
  const [saving, setSaving] = useState(false)
  return <tr><td><strong>{mapping.field_key}</strong><small>{mapping.source_concept}</small></td><td>{mapping.target_unit ?? 'Boolean/text'}</td><td>{Math.round(mapping.confidence * 100)}%</td><td><p>{mapping.rationale}</p><details><summary>Assumption and conversion</summary><p>{mapping.assumption}</p><code>{JSON.stringify(mapping.unit_rules)}</code></details></td><td><select value={status} onChange={event => setStatus(event.target.value)}><option value="provisional">Provisional</option><option value="needs_review">Needs review</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select><textarea value={notes} onChange={event => setNotes(event.target.value)} placeholder="Reviewer notes"/><button disabled={saving} onClick={() => { setSaving(true); void onSave(mapping.id, status, notes).finally(() => setSaving(false)) }}>{saving ? 'Saving…' : 'Save review'}</button></td></tr>
}

export function AdminIngestionPage() {
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    void fetch(`${apiUrl}/api/admin/ingestion`, { headers: { Authorization: `Bearer ${accessToken() ?? ''}` } })
      .then(response => { if (!response.ok) throw new Error('Administrator access is required.'); return response.json() as Promise<Inventory> })
      .then(setInventory).catch((reason: Error) => setError(reason.message))
  }, [])
  const items = useMemo(() => {
    const term = query.trim().toLowerCase()
    return inventory?.items.filter(item => !term || [item.company_name, item.ticker, item.sector, String(item.fy ?? '')].some(value => value.toLowerCase().includes(term))) ?? []
  }, [inventory, query])
  const saveReview = async (id: string, review_status: string, reviewer_notes: string) => {
    const response = await fetch(`${apiUrl}/api/admin/ingestion/mappings/${id}`, { method: 'PATCH', headers: { Authorization: `Bearer ${accessToken() ?? ''}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ review_status, reviewer_notes: reviewer_notes || null }) })
    if (!response.ok) throw new Error('The mapping review could not be saved.')
    const updated = await response.json() as ConceptMapping
    setInventory(current => current ? { ...current, concept_mappings: current.concept_mappings.map(item => item.id === id ? updated : item) } : current)
  }
  if (error) return <p role="alert" className="preview-notice">{error}</p>
  if (!inventory) return <div className="chart-state shimmer">Loading ingestion inventory…</div>
  return <>
    <header className="page-head"><p className="eyebrow">Platform administration</p><h1>NSE BRSR ingestion</h1><p>See exactly which official filings and extracted XBRL facts are persisted, plus the configured refresh behavior.</p></header>
    <section className="ingestion-stats" aria-label="Ingestion summary">
      <article><span>Companies</span><strong>{inventory.companies}</strong></article><article><span>Filings</span><strong>{inventory.filings}</strong></article><article><span>Parsed</span><strong>{inventory.parsed_filings}</strong></article><article><span>Raw XBRL facts</span><strong>{inventory.raw_facts.toLocaleString()}</strong></article>
    </section>
    <section className="ingestion-config"><h2>Refresh configuration</h2><dl><div><dt>Source</dt><dd>{inventory.config.source_enabled ? 'Enabled' : 'Disabled'}</dd></div><div><dt>Scheduler</dt><dd>{inventory.config.schedule_enabled ? `Every ${inventory.config.refresh_hours} hours` : 'Disabled'}</dd></div><div><dt>Default FY</dt><dd>{inventory.config.default_fy}</dd></div><div><dt>Next cohort offset</dt><dd>{inventory.config.next_offset}</dd></div></dl></section>
    <section className="ingestion-inventory"><div className="inventory-heading"><div><p className="eyebrow">Database inventory</p><h2>Companies and filings</h2></div><label>Filter inventory<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Company, symbol, sector, FY"/></label></div><div className="table-scroll"><table><thead><tr><th>Company</th><th>FY</th><th>Sector</th><th>Status</th><th>Submitted</th><th>Raw facts</th><th>Mapped</th><th>Evidence</th></tr></thead><tbody>{items.map(item => <tr key={`${item.company_id}:${item.fy ?? 'none'}`}><td><strong>{item.company_name}</strong><small>{item.ticker}</small></td><td>{item.fy ?? '—'}</td><td>{item.sector}</td><td><span className={`status status-${item.status}`}>{item.status}</span></td><td>{item.submission_date ?? '—'}</td><td>{item.raw_fact_count.toLocaleString()}</td><td>{item.mapped_field_count.toLocaleString()}</td><td>{item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer">NSE XBRL ↗</a> : '—'}</td></tr>)}</tbody></table></div></section>
    <section className="mapping-review"><div><p className="eyebrow">Domain review workspace</p><h2>Provisional NSE concept mappings</h2><p>These assumptions currently seed Explorer. Accept, reject, or flag each mapping; notes are retained with the reviewer and timestamp.</p></div><div className="table-scroll"><table><thead><tr><th>Governed field / NSE concept</th><th>Common unit</th><th>Confidence</th><th>Reasoning</th><th>Review</th></tr></thead><tbody>{inventory.concept_mappings.map(mapping => <MappingReviewRow key={mapping.id} mapping={mapping} onSave={saveReview}/>)}</tbody></table></div></section>
    <section className="ingestion-runs"><h2>Recent runs</h2>{inventory.recent_runs.length ? inventory.recent_runs.map(run => <article key={run.id}><div><strong>{run.mode} · FY {run.target_fy}</strong><span>{run.status}</span></div><p>{run.parsed_count} parsed · {run.missing_count} missing · {run.error_count} errors · requested {run.requested_count}</p><small>{new Date(run.started_at).toLocaleString()}</small></article>) : <p>No ingestion runs recorded yet.</p>}</section>
  </>
}
