export const tokens = {
  color: {
    ink: '#17231e', paper: '#f4f1e9', pine: '#174f3d', moss: '#52715d',
    saffron: '#e39a36', coral: '#d36150', blue: '#3b6f8f', violet: '#75669a',
    teal: '#2d7f78', stone: '#8b877d', white: '#fffdf8', line: '#d8d3c7',
  },
  categorical: ['#174f3d', '#e39a36', '#3b6f8f', '#d36150', '#75669a', '#2d7f78', '#8b684d', '#6f7d38'],
  sequential: ['#edf4ef', '#bfd7c8', '#7fac91', '#42745b', '#174f3d'],
  diverging: ['#b34f44', '#df9b70', '#eee7d9', '#84aaa0', '#1c6258'],
} as const

/** Chart-surface palette. Every ramp below was checked with the dataviz validator
 * against the `#fffdf8` chart surface; the brand `categorical` ramp above is an
 * identity/print palette and fails CVD separation at slots 7–8, so plotted marks
 * use these instead.
 *
 *   series      · 4 slots, adjacent-pair safe (worst ΔE 14.3 protan). Adjacent
 *                 forms only — grouped bars and lines. All-pairs forms (scatter)
 *                 use `accent` + `context` emphasis rather than four hues.
 *   sequential  · single hue, monotone lightness, light end clears the surface at
 *                 2.12:1. Magnitude only.
 *   below/above · diverging poles, warm ↔ cool (ΔE 15.6 protan) with a neutral
 *                 midpoint. Signed values only, always with a signed label.
 *
 * `series[1]` (#d98518) sits at 2.82:1 against the surface, so any chart using it
 * carries visible labels and a table view rather than relying on the hue alone.
 */
export const chart = {
  surface: '#fffdf8',
  series: ['#00785c', '#d98518', '#2178a8', '#cf4230'],
  sequential: ['#93b9a5', '#71a087', '#4f866c', '#316d53', '#124b38'],
  accent: '#00785c',
  context: '#9a958a',
  below: '#c0563f',
  neutral: '#d3cec3',
  above: '#2178a8',
  grid: '#e8e2d7',
  axis: '#8b877d',
  label: '#4a5550',
} as const

/** Step index into `chart.sequential` for a value's position in [0, 1]. */
export function sequentialStep(fraction: number): string {
  const index = Math.min(chart.sequential.length - 1, Math.max(0, Math.floor(fraction * chart.sequential.length)))
  return chart.sequential[index]
}
