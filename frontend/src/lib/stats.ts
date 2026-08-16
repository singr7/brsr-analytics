/** Descriptive statistics over a governed result set.
 *
 * Every figure here is computed from values the API actually returned. Nothing is
 * modelled, smoothed, or extrapolated: if a statistic cannot be computed from the
 * rows in hand, the function returns `null` and the caller shows nothing.
 */

export interface Summary {
  n: number
  min: number
  q1: number
  median: number
  q3: number
  max: number
  mean: number
  iqr: number
  /** Only meaningful for additive measures; the caller decides whether to show it. */
  total: number
}

const ascending = (a: number, b: number) => a - b

/** Linear-interpolated quantile (the R-7 / Excel PERCENTILE.INC definition). */
export function quantile(sorted: number[], fraction: number): number {
  if (!sorted.length) return NaN
  if (sorted.length === 1) return sorted[0]
  const position = (sorted.length - 1) * Math.min(1, Math.max(0, fraction))
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) return sorted[lower]
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}

export function summarize(values: number[]): Summary | null {
  const clean = values.filter(value => Number.isFinite(value))
  if (!clean.length) return null
  const sorted = [...clean].sort(ascending)
  const total = sorted.reduce((sum, value) => sum + value, 0)
  const q1 = quantile(sorted, 0.25)
  const q3 = quantile(sorted, 0.75)
  return {
    n: sorted.length,
    min: sorted[0],
    q1,
    median: quantile(sorted, 0.5),
    q3,
    max: sorted[sorted.length - 1],
    mean: total / sorted.length,
    iqr: q3 - q1,
    total,
  }
}

/** Share of rows at or below `value`, as a percentage. */
export function percentileRank(values: number[], value: number): number | null {
  const clean = values.filter(item => Number.isFinite(item))
  if (!clean.length || !Number.isFinite(value)) return null
  const atOrBelow = clean.filter(item => item <= value).length
  return (atOrBelow / clean.length) * 100
}

/** `value` as a multiple of `reference`, or null when the ratio would not be real. */
export function ratio(value: number, reference: number): number | null {
  if (!Number.isFinite(value) || !Number.isFinite(reference) || reference === 0) return null
  const result = value / reference
  return Number.isFinite(result) ? result : null
}

/** Combined share of the `count` largest values, as a percentage of the total. */
export function concentration(values: number[], count: number): number | null {
  const clean = values.filter(value => Number.isFinite(value) && value >= 0)
  if (clean.length <= count || count < 1) return null
  const total = clean.reduce((sum, value) => sum + value, 0)
  if (total <= 0) return null
  const top = [...clean].sort((a, b) => b - a).slice(0, count).reduce((sum, value) => sum + value, 0)
  return (top / total) * 100
}

/** Equal-width histogram bins over the observed range. */
export interface Bin { from: number; to: number; count: number }

export function histogram(values: number[], binCount = 8): Bin[] {
  const clean = values.filter(value => Number.isFinite(value)).sort(ascending)
  if (!clean.length) return []
  const min = clean[0]
  const max = clean[clean.length - 1]
  if (min === max) return [{ from: min, to: max, count: clean.length }]
  const bins = Math.max(1, Math.min(20, binCount))
  const width = (max - min) / bins
  const result: Bin[] = Array.from({ length: bins }, (_, index) => ({ from: min + index * width, to: min + (index + 1) * width, count: 0 }))
  for (const value of clean) {
    // The top edge is inclusive so the maximum lands in the last bin, not past it.
    const index = Math.min(bins - 1, Math.floor((value - min) / width))
    result[index].count += 1
  }
  return result
}

/** Signed change between the first and last point of an ordered series. */
export function change(series: number[]): { absolute: number; percent: number | null } | null {
  const clean = series.filter(value => Number.isFinite(value))
  if (clean.length < 2) return null
  const first = clean[0]
  const last = clean[clean.length - 1]
  return { absolute: last - first, percent: first === 0 ? null : ((last - first) / Math.abs(first)) * 100 }
}
