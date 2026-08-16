/** Presentation metadata for governed measures.
 *
 * `label`, `unit` and `format` mirror `taxonomy/semantic.yaml`, which stays the
 * source of truth — `/api/catalog` serves the same three fields and
 * `mergeCatalogMeasures` overlays them at runtime so a catalog bump reaches the UI
 * without a redeploy.
 *
 * `polarity` and `additive` are presentation-only and have no server equivalent.
 * They decide what the interface is allowed to say about a number:
 *   polarity 'up'      — a higher value is a better disclosure outcome
 *   polarity 'down'    — a lower value is better (intensity per INR crore)
 *   polarity 'neutral' — a scale measure. Absolute energy, water and emissions
 *                        totals track company size, so the UI reports "largest
 *                        reported", never "leader" or "best".
 *   additive           — values may be summed across rows. True only for absolute
 *                        physical quantities; false for scores (already averages)
 *                        and intensities (ratios), where a total is meaningless.
 */
export type Polarity = 'up' | 'down' | 'neutral'

export interface MeasureMeta {
  key: string
  label: string
  unit: string
  format: string
  polarity: Polarity
  additive: boolean
  /** Short plain-English gloss shown beside the measure in the toolbar. */
  note: string
}

const SCORE_NOTE = 'A 0–100 governed score. Compare within a cohort, not across method versions.'

export const measures: Record<string, MeasureMeta> = {
  completeness: { key: 'completeness', label: 'Disclosure completeness', unit: 'score', format: '.1f', polarity: 'up', additive: false, note: SCORE_NOTE },
  substance: { key: 'substance', label: 'Disclosure substance', unit: 'score', format: '.1f', polarity: 'up', additive: false, note: SCORE_NOTE },
  assurance_readiness: { key: 'assurance_readiness', label: 'Assurance readiness', unit: 'score', format: '.1f', polarity: 'up', additive: false, note: 'Evidence coverage and validation checks — not independent assurance.' },
  'p6.e1.energy_total_gj': { key: 'p6.e1.energy_total_gj', label: 'Total energy consumed', unit: 'GJ', format: ',.0f', polarity: 'neutral', additive: true, note: 'A scale measure converted to GJ. Larger totals usually mean a larger company.' },
  'p6.e2.water_total_kl': { key: 'p6.e2.water_total_kl', label: 'Total water withdrawal', unit: 'kL', format: ',.0f', polarity: 'neutral', additive: true, note: 'Entity-wide withdrawal in kL. Reflects scale and sector, not water management.' },
  'p6.e3.scope1_tco2e': { key: 'p6.e3.scope1_tco2e', label: 'Scope 1 emissions', unit: 'tCO2e', format: ',.0f', polarity: 'neutral', additive: true, note: 'Direct emissions. Boundaries and estimation methods differ between filers.' },
  'p6.e3.scope2_tco2e': { key: 'p6.e3.scope2_tco2e', label: 'Scope 2 emissions', unit: 'tCO2e', format: ',.0f', polarity: 'neutral', additive: true, note: 'Purchased-energy emissions. Location and market methods are not separated here.' },
  'p6.e3.scope12_total_tco2e': { key: 'p6.e3.scope12_total_tco2e', label: 'Scope 1+2 emissions', unit: 'tCO2e', format: ',.0f', polarity: 'neutral', additive: true, note: 'Direct plus purchased-energy emissions, as converted from the filing.' },
  'normalized.energy_gj_per_inr_crore': { key: 'normalized.energy_gj_per_inr_crore', label: 'Energy intensity', unit: 'GJ / INR crore', format: '.2f', polarity: 'down', additive: false, note: 'Converted GJ over registry-resolved turnover. Compare within a sector.' },
  'normalized.water_kl_per_inr_crore': { key: 'normalized.water_kl_per_inr_crore', label: 'Water intensity', unit: 'kL / INR crore', format: '.2f', polarity: 'down', additive: false, note: 'Withdrawal in kL over registry-resolved turnover. Compare within a sector.' },
  'normalized.scope12_tco2e_per_inr_crore': { key: 'normalized.scope12_tco2e_per_inr_crore', label: 'Scope 1+2 emissions intensity', unit: 'tCO2e / INR crore', format: '.2f', polarity: 'down', additive: false, note: 'Converted tCO2e over registry-resolved turnover. Compare within a sector.' },
}

const FALLBACK: MeasureMeta = { key: '', label: 'Measure', unit: '', format: '.2f', polarity: 'neutral', additive: false, note: '' }

/** Presentation-only quantities plotted on internal and illustrative surfaces.
 * They are not governed catalog measures and never appear in the measure picker. */
const auxiliary: Record<string, MeasureMeta> = {
  count: { key: 'count', label: 'Count', unit: '', format: ',.0f', polarity: 'neutral', additive: true, note: 'A record count from the first-party event stream.' },
  percent: { key: 'percent', label: 'Share', unit: '%', format: '.0f', polarity: 'up', additive: false, note: 'A percentage of the stated denominator.' },
  score: { key: 'score', label: 'Score', unit: 'score', format: '.1f', polarity: 'up', additive: false, note: 'An illustrative 0–100 score.' },
}

export function measureMeta(key: string): MeasureMeta {
  return measures[key] ?? auxiliary[key] ?? { ...FALLBACK, key, label: key.replaceAll('_', ' ') }
}

/** Overlay the live catalog's label/unit/format without touching local polarity. */
export function mergeCatalogMeasures(catalog: Record<string, { label?: string; unit?: string; format?: string }>): void {
  for (const [key, spec] of Object.entries(catalog)) {
    const current = measures[key] ?? { ...FALLBACK, key, label: key }
    measures[key] = { ...current, label: spec.label ?? current.label, unit: spec.unit ?? current.unit, format: spec.format ?? current.format }
  }
}

/** The subset of `format` used by the catalog: `.1f`, `.2f`, `,.0f`. */
export function formatNumber(value: number, format: string): string {
  if (!Number.isFinite(value)) return '—'
  const digits = Number(/\.(\d+)f$/.exec(format)?.[1] ?? 2)
  const grouped = format.includes(',')
  return value.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: grouped })
}

/** A value with its unit, as it should read in prose, tooltips, and table cells. */
export function formatMeasure(value: number, key: string): string {
  const meta = measureMeta(key)
  const number = formatNumber(value, meta.format)
  if (meta.unit === 'score') return `${number} / 100`
  return meta.unit ? `${number} ${meta.unit}` : number
}

/** A low–high range carrying its unit once, so "52.0 – 65.5 / 100" never breaks
 * with the unit orphaned on its own line. */
export function formatRange(low: number, high: number, key: string): string {
  const meta = measureMeta(key)
  const pair = `${formatNumber(low, meta.format)} – ${formatNumber(high, meta.format)}`
  if (meta.unit === 'score') return `${pair} / 100`
  return meta.unit ? `${pair} ${meta.unit}` : pair
}

/** Axis ticks stay short: 1.2M rather than 12,00,000. */
export function formatCompact(value: number, key: string): string {
  const meta = measureMeta(key)
  if (meta.unit === 'score' || Math.abs(value) < 1000) return formatNumber(value, meta.format)
  const [divisor, suffix] = Math.abs(value) >= 1e9 ? [1e9, 'B'] : Math.abs(value) >= 1e6 ? [1e6, 'M'] : [1e3, 'k']
  return `${(value / divisor).toFixed(1).replace(/\.0$/, '')}${suffix}`
}

/** The measure most worth plotting against this one, kept inside the same access
 * tier where a same-tier partner exists so the comparison is not born locked. */
const comparePartners: Record<string, string> = {
  completeness: 'substance',
  substance: 'completeness',
  assurance_readiness: 'completeness',
  'p6.e1.energy_total_gj': 'p6.e3.scope12_total_tco2e',
  'p6.e2.water_total_kl': 'p6.e1.energy_total_gj',
  'p6.e3.scope1_tco2e': 'p6.e3.scope2_tco2e',
  'p6.e3.scope2_tco2e': 'p6.e3.scope1_tco2e',
  'p6.e3.scope12_total_tco2e': 'p6.e1.energy_total_gj',
  'normalized.energy_gj_per_inr_crore': 'p6.e1.energy_total_gj',
  'normalized.water_kl_per_inr_crore': 'p6.e2.water_total_kl',
  'normalized.scope12_tco2e_per_inr_crore': 'p6.e3.scope12_total_tco2e',
}

export function defaultCompare(key: string): string | null {
  return comparePartners[key] ?? null
}

/** "higher is better" / "lower is better" / "" — drives insight wording. */
export function polarityLabel(key: string): string {
  const { polarity } = measureMeta(key)
  return polarity === 'up' ? 'Higher is a stronger disclosure outcome.' : polarity === 'down' ? 'Lower is a stronger outcome.' : 'This is a scale measure, not a ranking of performance.'
}

/** What to call the row at the favourable end of the current sort. */
export function extremeNoun(key: string): string {
  return measureMeta(key).polarity === 'neutral' ? 'largest reported' : 'leading'
}
