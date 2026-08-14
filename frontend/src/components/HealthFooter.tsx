import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from '../lib/api'

export function HealthFooter() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })
  const state = health.data?.status ?? (health.isError ? 'degraded' : 'checking')

  return (
    <footer className="border-t border-emerald-950/10 px-6 py-4 text-sm text-emerald-950/70">
      <span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-600" />
      Platform status: <strong>{state}</strong>
    </footer>
  )
}

