export type ServiceState = 'ok' | 'error'

export interface HealthResponse {
  status: 'ok' | 'degraded'
  database: { status: ServiceState; detail: string | null }
  redis: { status: ServiceState; detail: string | null }
  llm_config: { status: ServiceState; detail: string | null }
}

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiUrl}/healthz`)
  const body = (await response.json()) as HealthResponse
  if (!response.ok && response.status !== 503) throw new Error('Health check failed')
  return body
}

