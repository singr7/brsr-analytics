import { useState } from 'react'

const disclosureKey = 'brsrlens_cookie_disclosure'

export function CookieDisclosure() {
  const [visible, setVisible] = useState(() => localStorage.getItem(disclosureKey) !== 'seen')
  if (!visible) return null
  return (
    <aside aria-label="Cookie disclosure" className="fixed bottom-4 left-4 right-4 z-20 mx-auto flex max-w-3xl items-center justify-between gap-5 rounded-2xl bg-emerald-950 px-5 py-4 text-sm text-white shadow-2xl">
      <span>We use a first-party anonymous ID to understand product usage. No advertising pixels or third-party analytics. <a className="underline" href="/privacy">Review or opt out</a>.</span>
      <button className="rounded-lg bg-white px-4 py-2 font-semibold text-emerald-950" onClick={() => { localStorage.setItem(disclosureKey, 'seen'); setVisible(false) }}>Understood</button>
    </aside>
  )
}
