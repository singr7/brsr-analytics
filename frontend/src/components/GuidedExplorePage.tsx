import { useEffect, useMemo, useState } from 'react'

import { ComparisonScatter, DeviationBar, Distribution, RankedBar, Timeseries } from '../charts/ChartKit'
import { guidedQuestionById, type PlanTier } from '../content/guided-questions'
import {
  applyDrill, drillTarget, primaryDimension, readDrill, toRows,
  type DrillStep, type ExploreRow,
} from '../lib/explore'
import { buildInsights } from '../lib/insights'
import { defaultCompare, formatMeasure, measureMeta } from '../lib/measures'
import { decodeQueryState, type SemanticDSL, useSemanticQuery } from '../lib/semantic'
import { summarize } from '../lib/stats'
import { track } from '../lib/track'
import { AskFollowUp } from './AskFollowUp'
import { LineageViewer } from './LineageViewer'
import { ExploreSummaryPanel } from './explore/ExploreStory'
import { ExploreToolbar } from './explore/ExploreToolbar'
import { MetricStrip } from './explore/ExploreSummary'
import { PolicyNotes } from './explore/PolicyNotes'
import { QuestionRail } from './explore/QuestionRail'

const SECTOR_LIMIT = 60

export function GuidedExplorePage({ planTier, authState }: { planTier: string; authState: 'anonymous' | 'authenticated' }) {
  const search = window.location.search
  const params = new URLSearchParams(search)
  const initial = guidedQuestionById(params.get('question'))
  const [active, setActive] = useState(initial)
  const [dsl, setDsl] = useState<SemanticDSL>(() => decodeQueryState(search, initial.dsl))
  const [drill, setDrill] = useState<DrillStep[]>(() => readDrill(search))
  const [compare, setCompare] = useState<string | null>(() => params.get('compare') ?? defaultCompare(decodeQueryState(search, initial.dsl).measures[0]))
  const [selected, setSelected] = useState<string | null>(null)
  const [pin, setPin] = useState<string | null>(null)

  const locked = !active.eligibleTiers.includes(planTier as PlanTier)
  const measure = dsl.measures[0]
  const effective = useMemo(() => applyDrill(dsl, drill), [dsl, drill])
  const query = useSemanticQuery(effective, !locked)
  const compareDsl = useMemo(() => ({ ...effective, measures: [compare ?? measure] }), [effective, compare, measure])
  const compareQuery = useSemanticQuery(compareDsl, !locked && Boolean(compare))
  const fy = dsl.filters.find(item => item.dimension === 'fy')?.value ?? 2025
  const sectorDsl = useMemo<SemanticDSL>(() => ({ measures: ['completeness'], dimensions: ['sector'], filters: [{ dimension: 'fy', operator: 'eq', value: fy }], shape: 'distribution', sort: { by: 'value', direction: 'desc' }, limit: SECTOR_LIMIT }), [fy])
  const sectorQuery = useSemanticQuery(sectorDsl)

  const dimension = primaryDimension(effective, query.data?.data)
  const rows = useMemo(() => toRows(query.data, dimension, measure), [query.data, dimension, measure])
  const compareRows = useMemo(() => (compare ? toRows(compareQuery.data, dimension, compare) : []), [compareQuery.data, dimension, compare])
  const summary = useMemo(() => summarize(rows.map(row => row.value)), [rows])
  const ascending = (effective.sort?.direction ?? 'desc') === 'asc'
  const insights = useMemo(() => buildInsights({ rows, measure, dimension, ascending, shape: effective.shape }), [rows, measure, dimension, ascending, effective.shape])
  const sectors = useMemo(() => [...new Set((sectorQuery.data?.data ?? []).map(row => String(row.sector ?? '')).filter(Boolean))].sort(), [sectorQuery.data])
  const gatedNotice = query.data?.applied_policy.find(item => item.code === 'company_detail_gated' || item.code === 'tier_gated')

  useEffect(() => {
    const next = new URLSearchParams({ question: active.id, q: JSON.stringify(dsl) })
    if (drill.length) next.set('drill', JSON.stringify(drill))
    if (compare) next.set('compare', compare)
    window.history.replaceState(null, '', `${window.location.pathname}?${next}`)
  }, [active.id, dsl, drill, compare])

  const selectQuestion = (id: string) => {
    const next = guidedQuestionById(id)
    setActive(next); setDsl(next.dsl); setDrill([]); setSelected(null)
    setCompare(defaultCompare(next.dsl.measures[0]))
    void track('guided_question_selected', { guided_question_id: next.id, auth_state: authState, plan_tier: planTier, source_surface: 'guided_explore' })
  }

  const changeQuery = (next: SemanticDSL) => {
    if (next.measures[0] !== measure) void track('explore_measure_changed', { measure: next.measures[0], previous: measure, source_surface: 'guided_explore' })
    setDsl(next); setSelected(null)
  }

  const onSelect = (row: ExploreRow | undefined) => {
    if (!row) return
    const target = drillTarget(dimension)
    if (!target) {
      // Already an atomic row: emphasise it and open its evidence rather than drilling.
      setSelected(current => (current === row.key ? null : row.key))
      if (row.lineageKey) { setPin(row.lineageKey); void track('explore_lineage_opened', { measure, dimension, source_surface: 'guided_explore' }) }
      return
    }
    setSelected(null)
    setDrill(current => [...current, { dimension, value: row.label }])
    void track('explore_drilldown_opened', { from_dimension: dimension, to_dimension: target, measure, depth: drill.length + 1, plan_tier: planTier, source_surface: 'guided_explore' })
  }

  const onExport = (kind: 'png' | 'csv' | 'table') => void track('explore_view_exported', { kind, measure, dimension, source_surface: 'guided_explore' })

  // The curated summary only describes the question's own measure and cohort.
  const adjusted = measure !== active.dsl.measures[0] || drill.length > 0
  const leader = rows.length ? rows.reduce((best, row) => (ascending ? row.value < best.value : row.value > best.value) ? row : best) : null
  const takeaway = active.summaryTemplate
    .replace('{leader}', leader?.label ?? 'The leading eligible cohort')
    .replace('{value}', leader ? formatMeasure(leader.value, measure) : 'not yet available')
  const drillHint = drillTarget(dimension) ? `Select any ${dimension.replaceAll('_', ' ')} to open the companies inside it.` : rows.some(row => row.lineageKey) ? 'Select any bar to open its source disclosure.' : undefined
  const frame = { measure, dimension, rows, loading: query.isLoading, stale: query.isPlaceholderData, onExport, onLineage: setPin, onSelect, selected: selected ?? undefined }
  const meta = measureMeta(measure)

  const primary = effective.shape === 'timeseries'
    ? <Timeseries {...frame} title={`${meta.label} over time`}/>
    : <RankedBar {...frame} title={`${meta.label} by ${dimension.replaceAll('_', ' ')}`} drillHint={drillHint}/>

  return <>
    <header className="page-head guided-head">
      <p className="eyebrow">Explore insights · guided questions v1.0</p>
      <h1>Start with a useful question. Then take it apart.</h1>
      <p>Every view is a governed materialisation you can re-measure, filter, drill into, read as a table, and export — with the evidence still attached.</p>
    </header>

    <QuestionRail activeId={active.id} planTier={planTier} onSelect={selectQuestion}/>

    {locked
      ? <section className="locked-message" role="status">
          <strong>This question needs Pro access.</strong>
          <p>The governed company-level result stays protected. Public questions remain available above.</p>
          <a href="/pricing">Compare plans →</a>
        </section>
      : <>
        <ExploreToolbar dsl={dsl} onChange={changeQuery} sectors={sectors} compare={compare} onCompare={setCompare}
          drill={drill} onDrillTo={depth => { setDrill(current => current.slice(0, depth)); setSelected(null) }}/>

        {query.isError && <p className="preview-notice" role="alert"><strong>The governed result could not be loaded.</strong> No preview values are substituted here. Retry, or open the detailed view.</p>}
        {gatedNotice && <section className="locked-message" role="status">
          <strong>Company-level detail is protected at this plan.</strong>
          <p>{gatedNotice.message}</p>
          <a href="/pricing">Compare plans →</a>
        </section>}

        <MetricStrip rows={rows} summary={summary} measure={measure} dimension={dimension} ascending={ascending}/>

        <section className="explore-main">
          {primary}
          <ExploreSummaryPanel question={active} takeaway={takeaway} insights={insights} measure={measure} loading={query.isLoading} hasRows={rows.length > 0} adjusted={adjusted}/>
        </section>

        <PolicyNotes notices={query.data?.applied_policy}/>

        <div className="explore-secondary">
          {rows.length >= 4 && effective.shape !== 'timeseries' && <Distribution {...frame} title="How the cohort is spread"/>}
          {rows.length >= 3 && <DeviationBar {...frame} title="Distance from the cohort median"/>}
        </div>

        {compare && <div className="explore-compare">
          <ComparisonScatter {...frame} title={`${meta.label} against ${measureMeta(compare).label}`}
            subtitle={compareQuery.isError ? 'The second measure could not be loaded.' : 'Median crosshairs split the cohort into four quadrants; overlapping labels move to the tooltip and the table.'}
            compareRows={compareRows} compareMeasure={compare}/>
        </div>}

        <details className="refine-drawer">
          <summary>View query details</summary>
          <p>This is the exact governed query behind every panel above, including the drill-down path. The page URL carries the same state.</p>
          <pre>{JSON.stringify(effective, null, 2)}</pre>
        </details>

        <AskFollowUp baseDsl={effective} suggestions={active.followUps} questionId={active.id}/>
      </>}

    <p className="expert-bypass">
      <a href={active.destination}>Open the detailed view →</a>
      <a href="/methodology" onClick={() => void track('learn_explanation_opened', { guided_question_id: active.id, source_surface: 'guided_explore' })}>Methodology and sources →</a>
      <a href={`/ask?${new URLSearchParams({ q: JSON.stringify(effective) })}`}>Open the full Ask BRSR Lens workspace →</a>
    </p>
    <LineageViewer pin={pin} onClose={() => setPin(null)}/>
  </>
}
