import { FormEvent, useEffect, useState } from 'react'

import { login, signup, verifyEmail, type UserProfile } from '../lib/auth'

interface Props { onAuthenticated: (profile: UserProfile) => void }

export function AuthPanel({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('verify')
    if (token) void verifyEmail(token)
      .then(() => setMessage('Email verified. You can now sign in.'))
      .catch(() => setMessage('That verification link is invalid or expired.'))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setMessage('')
    try {
      if (mode === 'login') onAuthenticated(await login(email, password))
      else {
        const token = await signup(email, password, name)
        setMessage(token ? `Account created. Development verification token: ${token}` : 'Account created. Check your email to verify it.')
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Request failed') }
  }

  return (
    <section className="rounded-3xl border border-emerald-900/10 bg-white/90 p-6 shadow-xl shadow-emerald-950/10">
      <div className="mb-5 flex gap-2">{(['login', 'signup'] as const).map((item) => <button key={item} className={`rounded-full px-4 py-2 text-sm ${mode === item ? 'bg-emerald-900 text-white' : 'bg-emerald-50'}`} onClick={() => setMode(item)}>{item === 'login' ? 'Sign in' : 'Create account'}</button>)}</div>
      <form className="grid gap-3" onSubmit={(event) => void submit(event)}>
        {mode === 'signup' && <input aria-label="Display name" className="rounded-xl border p-3" placeholder="Display name" value={name} onChange={(event) => setName(event.target.value)} required />}
        <input aria-label="Email" className="rounded-xl border p-3" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <input aria-label="Password" className="rounded-xl border p-3" type="password" placeholder="Password (10+ characters)" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={10} />
        <button className="rounded-xl bg-emerald-700 p-3 font-semibold text-white" type="submit">{mode === 'login' ? 'Sign in' : 'Sign up'}</button>
      </form>
      {message && <p className="mt-4 break-all text-sm text-emerald-800" role="status">{message}</p>}
    </section>
  )
}
