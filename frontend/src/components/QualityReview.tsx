import { useEffect, useState } from 'react'

import { apiUrl } from '../lib/api'
import { accessToken } from '../lib/auth'

interface ReviewItem {
  review_id: string
  field_key: string
  value_raw: string
  confidence: string | null
  source_page: number | null
  source_quote: string | null
  page_image: string | null
}

export function QualityReview() {
  const [queue, setQueue] = useState<ReviewItem[]>([])
  const [correction, setCorrection] = useState('')
  const current = queue[0]

  async function load() {
    const response = await fetch(`${apiUrl}/api/admin/reviews`, {
      headers: { Authorization: `Bearer ${accessToken() ?? ''}` },
    })
    if (response.ok) setQueue((await response.json()) as ReviewItem[])
  }

  async function decide(correctedValue?: string) {
    if (!current) return
    const response = await fetch(`${apiUrl}/api/admin/reviews/${current.review_id}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${accessToken() ?? ''}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ corrected_value: correctedValue || null }),
    })
    if (response.ok) {
      setCorrection('')
      setQueue((items) => items.slice(1))
    }
  }

  useEffect(() => { void load() }, [])
  if (!current) return <aside className="rounded-2xl bg-white/70 p-5 text-sm">QA queue is clear.</aside>
  return (
    <aside className="rounded-2xl border border-amber-700/20 bg-amber-50 p-5">
      <p className="m-0 text-xs font-semibold uppercase tracking-wider text-amber-800">Extraction QA</p>
      <h2 className="mt-2 text-lg">{current.field_key}</h2>
      <p className="text-sm">Page {current.source_page ?? '—'} · confidence {current.confidence ?? '—'}</p>
      {current.page_image && <p className="break-all text-xs text-slate-500">Image: {current.page_image}</p>}
      <blockquote className="border-l-2 border-amber-600 pl-3 text-sm">{current.source_quote ?? 'No quote supplied'}</blockquote>
      <p className="font-medium">Extracted: {current.value_raw}</p>
      <input className="w-full rounded-lg border bg-white px-3 py-2" value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="Corrected value" />
      <div className="mt-3 flex gap-2">
        <button className="rounded-lg bg-emerald-800 px-3 py-2 text-white" onClick={() => void decide()}>Accept</button>
        <button className="rounded-lg border px-3 py-2" disabled={!correction} onClick={() => void decide(correction)}>Save correction</button>
      </div>
    </aside>
  )
}
