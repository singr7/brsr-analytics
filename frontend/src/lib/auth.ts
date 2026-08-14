import { apiUrl } from './api'

export interface OrgSummary {
  id: string
  name: string
  slug: string
  role: 'owner' | 'member'
  plan_tier: 'explore' | 'pro' | 'studio' | 'research'
}

export interface UserProfile {
  id: string
  email: string
  display_name: string
  plan_tier: string
  orgs: OrgSummary[]
}

interface TokenPair { access_token: string; refresh_token: string }

const accessKey = 'brsrlens_access_token'
const refreshKey = 'brsrlens_refresh_token'

export function accessToken(): string | null { return localStorage.getItem(accessKey) }

function saveTokens(tokens: TokenPair): void {
  localStorage.setItem(accessKey, tokens.access_token)
  localStorage.setItem(refreshKey, tokens.refresh_token)
}

export async function login(email: string, password: string): Promise<UserProfile> {
  const response = await fetch(`${apiUrl}/api/auth/login`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) throw new Error(await response.text())
  saveTokens((await response.json()) as TokenPair)
  return fetchMe()
}

export async function signup(email: string, password: string, displayName: string): Promise<string | null> {
  const response = await fetch(`${apiUrl}/api/auth/signup`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, display_name: displayName }),
  })
  if (!response.ok) throw new Error(await response.text())
  const body = (await response.json()) as { verification_token?: string }
  return body.verification_token ?? null
}

export async function verifyEmail(token: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/auth/verify`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }),
  })
  if (!response.ok) throw new Error(await response.text())
}

export async function fetchMe(): Promise<UserProfile> {
  const token = accessToken()
  if (!token) throw new Error('Not signed in')
  const response = await fetch(`${apiUrl}/api/auth/me`, {
    credentials: 'include', headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error('Session expired')
  return response.json() as Promise<UserProfile>
}

export function logout(): void {
  localStorage.removeItem(accessKey)
  localStorage.removeItem(refreshKey)
}
