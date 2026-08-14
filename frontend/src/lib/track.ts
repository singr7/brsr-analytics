import { accessToken } from './auth'
import { apiUrl } from './api'

const sessionKey = 'brsrlens_session_id'
export type EventName =
  | 'page_viewed'
  | 'viewed_company'
  | 'viewed_gap_panel'
  | 'nlq_asked'
  | 'export_generated'
  | 'studio_gap_report'
  | 'pricing_viewed'
  | 'deepdive_requested'

function sessionId(): string {
  const current = sessionStorage.getItem(sessionKey)
  if (current) return current
  const created = crypto.randomUUID()
  sessionStorage.setItem(sessionKey, created)
  return created
}

export async function track(name: EventName, properties: Record<string, unknown> = {}): Promise<void> {
  const token = accessToken()
  await fetch(`${apiUrl}/api/events`, {
    method: 'POST', credentials: 'include', keepalive: true,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ events: [{ name, properties, session_id: sessionId(), occurred_at: new Date().toISOString() }] }),
  })
}

export function trackPageview(): void {
  void track('page_viewed', { path: window.location.pathname, title: document.title })
}
