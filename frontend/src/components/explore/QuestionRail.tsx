import { useMemo, useState } from 'react'

import { guidedQuestions, type GuidedQuestion, type PlanTier } from '../../content/guided-questions'

const categoryLabels: Record<GuidedQuestion['category'], string> = {
  sector: 'Sector shape', core: 'BRSR Core', substance: 'Disclosure substance',
  materiality: 'Materiality', assurance: 'Assurance', environment: 'Environment',
}

/** The question list, grouped by theme and filterable, so thirteen questions read
 * as six decisions rather than one flat wall of buttons. */
export function QuestionRail({ activeId, planTier, onSelect }: { activeId: string; planTier: string; onSelect: (id: string) => void }) {
  const [category, setCategory] = useState<'all' | GuidedQuestion['category']>('all')
  const categories = useMemo(() => [...new Set(guidedQuestions.map(item => item.category))], [])
  const visible = category === 'all' ? guidedQuestions : guidedQuestions.filter(item => item.category === category)
  return <section className="question-rail" aria-label="Guided questions">
    <div className="rail-filter" role="group" aria-label="Filter questions by theme">
      <button className={category === 'all' ? 'active' : ''} aria-pressed={category === 'all'} onClick={() => setCategory('all')}>All {guidedQuestions.length}</button>
      {categories.map(item => <button key={item} className={category === item ? 'active' : ''} aria-pressed={category === item} onClick={() => setCategory(item)}>{categoryLabels[item]}</button>)}
    </div>
    <div className="question-grid">{visible.map(item => {
      const locked = !item.eligibleTiers.includes(planTier as PlanTier)
      return <button key={item.id} className={item.id === activeId ? 'active' : ''} onClick={() => onSelect(item.id)} aria-pressed={item.id === activeId}>
        <span>{categoryLabels[item.category]}</span>
        <strong>{item.question}</strong>
        {locked && <small>Pro question</small>}
      </button>
    })}</div>
  </section>
}
