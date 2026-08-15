import { decodeQueryState, encodeQueryState, type SemanticDSL } from './semantic'

test('semantic query state survives a shareable URL round trip', () => {
  const query: SemanticDSL = { measures: ['completeness'], dimensions: ['sector'], filters: [{ dimension: 'fy', operator: 'eq', value: 2025 }], shape: 'comparison' }
  expect(decodeQueryState(`?${encodeQueryState(query)}`, { ...query, measures: ['substance'] })).toEqual(query)
})
