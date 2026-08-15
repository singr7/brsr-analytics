import type { StudioField } from '../lib/studio'
import { fieldsForSection, progressFor } from '../lib/studio-ui'

const fields: StudioField[] = [
  { field_key: 'a.basics.name', principle: 'A', section: 'basics', label: 'Name', dtype: 'text', core_kpi: false },
  { field_key: 'b.policy.p1.policy_exists', principle: 'P1', section: 'policy_matrix', label: 'Policy', dtype: 'boolean', core_kpi: false },
  { field_key: 'p1.essential.processes', principle: 'P1', section: 'essential', label: 'Processes', dtype: 'text', core_kpi: false },
]

test('Studio separates the policy matrix from principle indicators', () => {
  expect(fieldsForSection(fields, 'B', 'p1').map(field => field.field_key)).toEqual(['b.policy.p1.policy_exists'])
  expect(fieldsForSection(fields, 'P1', 'p1').map(field => field.field_key)).toEqual(['p1.essential.processes'])
})

test('Studio progress is based on required answers without painting blanks as errors', () => {
  expect(progressFor(fields, {})).toBe(0)
  expect(progressFor(fields, Object.fromEntries(fields.map(field => [field.field_key, 'done'])))).toBe(100)
})
