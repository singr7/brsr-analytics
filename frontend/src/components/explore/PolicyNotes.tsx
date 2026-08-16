import { consolidatePolicyNotices, type PolicyNotice } from '../../lib/semantic'

const labels: Record<string, string> = {
  minimum_cohort: 'Cohort size',
  tier_gated: 'Plan access',
  company_detail_gated: 'Company detail',
  bottom_ranking_anonymised: 'Responsible ranking',
}

/** Why the result on screen is not the whole picture. Suppression is explained
 * where it happens, never left as a silently short chart. */
export function PolicyNotes({ notices }: { notices?: PolicyNotice[] }) {
  const unique = consolidatePolicyNotices(notices)
  if (!unique.length) return null
  return <aside className="policy-note" aria-label="Applied policy">
    <strong>Why some results are shaped this way</strong>
    {unique.map(item => <p key={item.code}><span>{labels[item.code] ?? item.code.replaceAll('_', ' ')}</span>{item.message}</p>)}
  </aside>
}
