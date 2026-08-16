import type { GuidedQuestion } from '../../content/guided-questions'
import type { Insight } from '../../lib/insights'
import { measureMeta, polarityLabel } from '../../lib/measures'
import { InsightList } from './ExploreSummary'

/** The reading beside the chart: the headline the question asked for, the derived
 * statements the rows support, and the caveat that keeps the number honest.
 *
 * Once the reader re-measures or drills, the question's own wording no longer
 * describes what is plotted, so the panel drops the curated summary and explanation
 * and falls back to statements derived from the rows actually on screen. */
export function ExploreSummaryPanel({ question, takeaway, insights, measure, loading, hasRows, adjusted }: {
  question: GuidedQuestion
  takeaway: string
  insights: Insight[]
  measure: string
  loading: boolean
  hasRows: boolean
  /** The view has moved away from the question's own measure or cohort. */
  adjusted: boolean
}) {
  const meta = measureMeta(measure)
  const derived = insights.find(item => item.id === 'leader')?.text
  const headline = loading
    ? 'Reading the governed materialisation…'
    : !hasRows
      ? 'No eligible result is available for this cohort.'
      : adjusted
        ? derived ?? `This view plots ${meta.label} for the cohort on screen.`
        : takeaway
  return <aside className="explore-story" aria-labelledby="active-question">
    <p className="eyebrow">Current question{adjusted && <em> · adjusted</em>}</p>
    <h2 id="active-question">{question.question}</h2>
    {adjusted && <p className="adjusted-note">You have changed the measure or cohort, so the reading below is derived from the rows on screen rather than from this question&rsquo;s curated summary.</p>}
    <div className="takeaway"><span>Key takeaway</span><strong>{headline}</strong></div>
    <InsightList insights={adjusted ? insights.filter(item => item.id !== 'leader') : insights}/>
    <h3>Why this matters</h3>
    <p>{adjusted ? meta.note : question.explanation}</p>
    <p className="polarity-note">{polarityLabel(measure)}</p>
  </aside>
}
