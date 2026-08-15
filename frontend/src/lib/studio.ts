import { accessToken } from './auth'
import { apiUrl } from './api'

export interface StudioField { field_key: string; principle: string; section: string; label: string; dtype: string; unit?: string | null; core_kpi: boolean; required?: boolean; leadership?: boolean; repeating_group?: string }
export interface Finding { severity: string; field_key: string; message: string; fix_hint: string; tier: string }
export interface Proposal { id: string; field_key: string; value: string; unit?: string; confidence: number; review_status: string; evidence: { doc_id: string; page: number; quote: string } }
export interface FilingState { id: string; fy: number; status: string; answers: Record<string,string>; answer_meta: Record<string,Record<string,unknown>>; progress: { sections: Record<string,number>; overall_pct: number; core_pct: number }; findings: Finding[]; proposals: Proposal[] }

async function studioFetch<T>(path: string, orgId: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl}/api/studio${path}`, { ...init, headers: { Authorization: `Bearer ${accessToken() ?? ''}`, 'X-Org-ID': orgId, ...(init?.headers ?? {}) } })
  if (!response.ok) throw new Error((await response.text()) || 'Studio request failed')
  const body = (await response.json()) as { data: T }
  return body.data
}

export const getSchema = (orgId: string) => studioFetch<{ fields: StudioField[]; schema_version: string; stats: Record<string,number> }>('/schema', orgId)
export const getFilings = (orgId: string) => studioFetch<{ items: Array<{id:string;fy:number}> }>('/filings', orgId)
export const createFiling = (orgId: string, fy: number) => studioFetch<{id:string}>('/filings', orgId, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({fy}) })
export const getFiling = (orgId: string, id: string) => studioFetch<FilingState>(`/filings/${id}`, orgId)
export const saveAnswer = (orgId: string, id: string, field: StudioField, value: string) => studioFetch(`/filings/${id}/answers/${field.field_key}`, orgId, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({value,unit:field.unit ?? null}) })
export const decideProposal = (orgId:string, filingId:string, proposalId:string, decision:'accepted'|'edited'|'rejected', value?:string) => studioFetch(`/filings/${filingId}/proposals/${proposalId}`,orgId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,value})})
export const uploadDocument = (orgId:string, filingId:string, file:File) => studioFetch(`/filings/${filingId}/documents?filename=${encodeURIComponent(file.name)}`,orgId,{method:'POST',headers:{'Content-Type':file.type},body:file})
export const mapSection = (orgId:string, filingId:string, section:string) => studioFetch(`/filings/${filingId}/map/${section}`,orgId,{method:'POST'})
export const generateExports = (orgId:string, filingId:string) => studioFetch<{items:Array<{id:string;kind:string;status:string;findings:Finding[]}>}>(`/filings/${filingId}/exports`,orgId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kinds:['xbrl','docx','pdf','gap_pdf']})})
