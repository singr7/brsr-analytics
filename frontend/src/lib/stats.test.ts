import { change, concentration, histogram, percentileRank, quantile, ratio, summarize } from './stats'

test('quartiles interpolate the way a reader would read them off a sorted list', () => {
  const sorted = [10, 20, 30, 40, 50]
  expect(quantile(sorted, 0.5)).toBe(30)
  expect(quantile(sorted, 0.25)).toBe(20)
  expect(quantile(sorted, 0.75)).toBe(40)
  expect(quantile([10, 20, 30, 40], 0.5)).toBe(25)
  expect(quantile([7], 0.9)).toBe(7)
})

test('summarize reports the cohort without inventing any spread', () => {
  const summary = summarize([52, 61, 78, 67, 71])
  expect(summary).not.toBeNull()
  expect(summary).toMatchObject({ n: 5, min: 52, max: 78, median: 67, total: 329 })
  expect(summary?.iqr).toBe(10)
  expect(summary?.mean).toBeCloseTo(65.8, 5)
})

test('non-finite values are dropped rather than coerced to zero', () => {
  expect(summarize([Number.NaN, Number.POSITIVE_INFINITY])).toBeNull()
  expect(summarize([10, Number.NaN, 30])).toMatchObject({ n: 2, median: 20 })
})

test('percentile rank is the share at or below the value', () => {
  expect(percentileRank([10, 20, 30, 40], 30)).toBe(75)
  expect(percentileRank([10, 20, 30, 40], 5)).toBe(0)
  expect(percentileRank([], 5)).toBeNull()
})

test('ratio refuses to divide by zero instead of returning Infinity', () => {
  expect(ratio(10, 4)).toBe(2.5)
  expect(ratio(10, 0)).toBeNull()
})

test('concentration needs more rows than it summarises', () => {
  expect(concentration([50, 30, 15, 5], 3)).toBe(95)
  expect(concentration([50, 30, 20], 3)).toBeNull()
  expect(concentration([0, 0, 0, 0], 3)).toBeNull()
})

test('histogram bins cover the range and keep the maximum in the last bin', () => {
  const bins = histogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
  expect(bins).toHaveLength(5)
  expect(bins.reduce((total, bin) => total + bin.count, 0)).toBe(11)
  expect(bins[4].to).toBe(10)
  expect(bins[4].count).toBe(3)
  expect(histogram([5, 5, 5])).toEqual([{ from: 5, to: 5, count: 3 }])
  expect(histogram([])).toEqual([])
})

test('change reports first-to-last movement, and nothing from one point', () => {
  expect(change([50, 60, 75])).toEqual({ absolute: 25, percent: 50 })
  expect(change([80])).toBeNull()
  expect(change([0, 10])).toEqual({ absolute: 10, percent: null })
})
