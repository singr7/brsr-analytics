import { useEffect, useState } from 'react'

import { accessToken } from '../lib/auth'
import { apiUrl } from '../lib/api'

interface Lineage { field: { label: string; value: string; unit?: string; method: string; confidence?: number; qa_status: string; version: number }; source: { page?: number; text?: string; image_url?: string; span?: { start?: number; end?: number } }; annotations: Array<{ id: string; body: string }> }

export function LineageViewer({ pin, onClose }: { pin: string | null; onClose: () => void }) {
  const [data, setData] = useState<Lineage | null>(null); const [issue, setIssue] = useState('')
  useEffect(() => { if (pin) void fetch(`${apiUrl}/api/lineage/${pin}`).then(r => r.json() as Promise<Lineage>).then(setData) }, [pin])
  if (!pin) return null
  const highlighted = () => {
    const text = data?.source.text ?? ''; const start = data?.source.span?.start ?? 0; const end = data?.source.span?.end ?? 0
    return <>{text.slice(0, start)}<mark>{text.slice(start, end) || data?.field.value}</mark>{text.slice(end)}</>
  }
  const report = async () => {
    if (issue.length < 10) return
    await fetch(`${apiUrl}/api/corrections`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken() ? { Authorization: `Bearer ${accessToken()}` } : {}) }, body: JSON.stringify({ pin_id: pin, description: issue }) }); setIssue('Report received — thank you.')
  }
  return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Source lineage"><div className="lineage-modal">
    <button className="modal-close" onClick={onClose}>Close ×</button>
    {!data ? <p>Loading filing source…</p> : <><p className="eyebrow">Auditable source · page {data.source.page ?? '—'}</p><h2>{data.field.label}</h2>
      <div className="source-value"><strong>{data.field.value}</strong> {data.field.unit}</div>
      <div className="source-page">{data.source.image_url && <img src={data.source.image_url} alt={`Filing page ${data.source.page}`} />}<blockquote>{highlighted()}</blockquote></div>
      <dl className="metadata"><div><dt>Method</dt><dd>{data.field.method}</dd></div><div><dt>Confidence</dt><dd>{data.field.confidence ? `${(data.field.confidence * 100).toFixed(0)}%` : '—'}</dd></div><div><dt>QA</dt><dd>{data.field.qa_status}</dd></div><div><dt>Version</dt><dd>v{data.field.version}</dd></div></dl>
      {data.annotations.map(item => <aside className="annotation" key={item.id}><strong>Company response</strong><p>{item.body}</p></aside>)}
      <label className="issue-box">Something looks wrong?<textarea value={issue} onChange={e => setIssue(e.target.value)} placeholder="Describe the issue (10+ characters)" /><button onClick={() => void report()}>Report an issue</button></label></>}
  </div></div>
}
