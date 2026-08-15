import type { StudioField } from './studio'

export type StudioSection = 'A' | 'B' | `P${number}`

export function fieldsForSection(fields: StudioField[], section: StudioSection, policyPrinciple: string) {
  if (section === 'A') return fields.filter(field => field.field_key.startsWith('a.'))
  if (section === 'B') return fields.filter(field => field.field_key.startsWith(`b.policy.${policyPrinciple}.`))
  return fields.filter(field => field.principle === section && !field.field_key.startsWith('b.'))
}

export function progressFor(fields: StudioField[], answers: Record<string, string>) {
  const required = fields.filter(field => field.required !== false && !field.leadership)
  return required.length ? Math.round(100 * required.filter(field => answers[field.field_key]).length / required.length) : 100
}
