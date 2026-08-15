import { useEffect, useMemo, useState } from 'react'

import {
  createFiling,
  decideProposal,
  generateExports,
  getFiling,
  getFilings,
  getSchema,
  mapSection,
  saveAnswer,
  uploadDocument,
  type FilingState,
  type Finding,
  type StudioField,
} from '../lib/studio'
import { fieldsForSection, progressFor, type StudioSection } from '../lib/studio-ui'

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

const sectionOrder: StudioSection[] = ['A', 'B', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9']
const sectionNames: Record<StudioSection, string> = {
  A: 'Company profile',
  B: 'Policies & governance',
  P1: 'Ethics & transparency',
  P2: 'Sustainable products',
  P3: 'Workforce well-being',
  P4: 'Stakeholders',
  P5: 'Human rights',
  P6: 'Environment',
  P7: 'Public policy',
  P8: 'Inclusive growth',
  P9: 'Customer value',
}
const groupNames: Record<string, string> = {
  basics: 'Entity and reporting details',
  operations: 'Products, operations and material issues',
  policy_matrix: 'Policy matrix',
  essential: 'Essential indicators',
  leadership: 'Leadership indicators · optional',
  workforce: 'Workforce and well-being',
  human_rights: 'Human rights',
  environment: 'Environmental performance',
  e1: 'Energy', e2: 'Water', e3: 'Emissions', e4: 'Air emissions', e5: 'Waste',
}

export function StudioPage({ orgId }: { orgId?: string }) {
  const [schema, setSchema] = useState<StudioField[]>([])
  const [filing, setFiling] = useState<FilingState>()
  const [section, setSection] = useState<StudioSection>('A')
  const [policyPrinciple, setPolicyPrinciple] = useState('p1')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [reviewMode, setReviewMode] = useState(false)
  const [touched, setTouched] = useState<Set<string>>(new Set())
  const [saveState, setSaveState] = useState<SaveState>('idle')

  const refresh = async (id: string) => {
    if (orgId) setFiling(await getFiling(orgId, id))
  }

  useEffect(() => {
    if (!orgId) return
    void Promise.all([getSchema(orgId), getFilings(orgId)]).then(async ([form, list]) => {
      setSchema(form.fields)
      let id = list.items[0]?.id
      if (!id) id = (await createFiling(orgId, new Date().getFullYear())).id
      setFiling(await getFiling(orgId, id))
    }).catch(error => setNotice(error instanceof Error ? error.message : String(error)))
  }, [orgId])

  const navigation = useMemo(() => sectionOrder.map(key => {
    const all = key === 'B'
      ? schema.filter(field => field.field_key.startsWith('b.'))
      : fieldsForSection(schema, key, policyPrinciple)
    return { key, label: sectionNames[key], progress: filing ? progressFor(all, filing.answers) : 0 }
  }), [schema, filing, policyPrinciple])
  const visibleFields = useMemo(
    () => fieldsForSection(schema, section, policyPrinciple),
    [schema, section, policyPrinciple],
  )
  const groupedFields = useMemo(() => {
    const groups: Array<{ key: string; fields: StudioField[] }> = []
    for (const field of visibleFields) {
      const existing = groups.find(group => group.key === field.section)
      if (existing) existing.fields.push(field)
      else groups.push({ key: field.section, fields: [field] })
    }
    return groups
  }, [visibleFields])

  if (!orgId) return <section className="studio-signin"><p className="eyebrow">Filing Studio</p><h1>Your reporting workspace starts here.</h1><p>Sign in with a Studio organisation to prepare a filing, upload evidence, and review AI-assisted drafts.</p><p className="demo-hint">Local demo · demo+studio@brsrlens.local · DemoPassword123!</p></section>
  if (!filing) return <div className="chart-state shimmer">Opening your filing workspace… {notice}</div>

  const currentProgress = progressFor(visibleFields, filing.answers)
  const sectionFindings = filing.findings.filter(item => visibleFields.some(field => field.field_key === item.field_key))
  const visibleFindings = reviewMode
    ? sectionFindings
    : sectionFindings.filter(item => touched.has(item.field_key) && item.tier !== 'L3')
  const missingCount = sectionFindings.filter(item => item.message === 'Required answer is missing').length
  const proposalCount = filing.proposals.filter(item => item.review_status === 'unreviewed').length
  const blockingCount = filing.findings.filter(item => item.severity === 'error').length
  const reload = () => refresh(filing.id)

  const upload = async (file: File) => {
    setBusy(true); setNotice('')
    try {
      const result = await uploadDocument(orgId, filing.id, file) as { kind?: string }
      setNotice(`${file.name} is ready · classified as ${String(result.kind ?? 'evidence').replaceAll('_', ' ')}`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Upload failed')
    } finally { setBusy(false) }
  }

  const draft = async () => {
    const target = visibleFields[0]?.section
    if (!target) return
    setBusy(true); setNotice('')
    try {
      await mapSection(orgId, filing.id, target)
      await reload()
      setNotice('Evidence scan complete. Review each proposal before it counts toward completion.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Document mapping failed')
    } finally { setBusy(false) }
  }

  const exportPackage = async () => {
    setBusy(true); setNotice('')
    try {
      const output = await generateExports(orgId, filing.id)
      setNotice(output.items.map(item => `${item.kind.replace('_', ' ')} · ${item.status}`).join('   |   '))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Export failed')
    } finally { setBusy(false) }
  }

  const goToFinding = (finding: Finding) => {
    const target = schema.find(field => field.field_key === finding.field_key)
    if (!target) return
    if (target.field_key.startsWith('a.')) setSection('A')
    else if (target.field_key.startsWith('b.')) {
      setSection('B'); setPolicyPrinciple(target.field_key.split('.')[2])
    } else setSection(target.principle as StudioSection)
    window.setTimeout(() => document.getElementById(finding.field_key)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
  }

  return <div className="studio">
    <header className="studio-head">
      <div><p className="eyebrow">Filing Studio · FY {filing.fy}</p><h1>Build the filing in three clear passes.</h1><p>Complete the questionnaire, attach evidence, then review every AI-assisted answer before export.</p></div>
      <div className="studio-score"><span>Filing</span><strong>{filing.progress.overall_pct}%</strong><span>Core KPIs</span><strong>{filing.progress.core_pct}%</strong></div>
    </header>

    <ol className="studio-steps" aria-label="Filing workflow">
      <li className={filing.progress.overall_pct < 100 ? 'active' : 'done'}><span>1</span><div><strong>Complete</strong><small>Questionnaire and policy matrix</small></div></li>
      <li className={proposalCount ? 'active' : ''}><span>2</span><div><strong>Evidence</strong><small>Upload documents and review AI drafts</small></div></li>
      <li className={reviewMode ? 'active' : ''}><span>3</span><div><strong>Validate & export</strong><small>Resolve blockers and create files</small></div></li>
    </ol>

    <div className="studio-toolbar">
      <div><strong>{filing.status === 'draft' ? 'Draft filing' : filing.status}</strong><small>Schema {filing.schema_version} · {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'All changes saved' : saveState === 'error' ? 'Save failed' : 'Autosave on'}</small></div>
      <label className="upload">Upload evidence<input type="file" accept=".pdf,.docx,.xlsx" onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file) }}/></label>
      <button className="secondary" onClick={() => setReviewMode(true)}>Check readiness</button>
      <button disabled={busy || blockingCount > 0} title={blockingCount ? `Resolve ${blockingCount} blocking findings before export` : 'Generate filing package'} onClick={() => void exportPackage()}>Export package</button>
    </div>
    {notice && <div className="studio-notice" role="status">{notice}</div>}

    <div className="studio-layout">
      <aside className="section-nav"><h2>Filing sections</h2>{navigation.map(item => <button key={item.key} className={section === item.key ? 'active' : ''} onClick={() => { setSection(item.key); setReviewMode(false) }}><i style={{ background: `conic-gradient(#174f3d ${item.progress}%,#ddd ${item.progress}%)` }}/><span><strong>{item.key}</strong><small>{item.label}</small></span><b>{item.progress}%</b></button>)}</aside>

      <section className="questionnaire">
        <header><div><p className="eyebrow">{section} · {currentProgress}% complete</p><h2>{sectionNames[section]}</h2><p>{missingCount ? `${missingCount} required answers remain in this section.` : 'This section is complete.'}</p></div><button disabled={busy} onClick={() => void draft()}>Draft from evidence</button></header>
        {section === 'B' && <div className="policy-principles" aria-label="Policy principle"><span>Policy matrix for</span>{Array.from({ length: 9 }, (_, index) => `p${index + 1}`).map(key => <button key={key} className={policyPrinciple === key ? 'active' : ''} onClick={() => setPolicyPrinciple(key)}>{key.toUpperCase()}</button>)}</div>}
        {groupedFields.map(group => <section className="question-group" key={group.key}><header><h3>{groupNames[group.key] ?? group.key.replaceAll('_', ' ')}</h3><span>{group.fields.filter(field => filing.answers[field.field_key]).length}/{group.fields.length} answered</span></header>{group.fields.map(field => <FieldInput key={field.field_key} field={field} initial={filing.answers[field.field_key] ?? ''} finding={visibleFindings.find(item => item.field_key === field.field_key)?.message} onTouch={() => setTouched(previous => new Set(previous).add(field.field_key))} onSave={async value => { setSaveState('saving'); try { await saveAnswer(orgId, filing.id, field, value); setTouched(previous => new Set(previous).add(field.field_key)); await reload(); setSaveState('saved'); window.setTimeout(() => setSaveState('idle'), 1800) } catch { setSaveState('error') } }}/>)}</section>)}
      </section>

      <aside className="review-lane">
        <section><div className="review-heading"><h2>AI review</h2>{proposalCount > 0 && <span>{proposalCount}</span>}</div>{filing.proposals.filter(item => item.review_status === 'unreviewed').map(item => <article key={item.id}><span>{Math.round(item.confidence * 100)}% confidence</span><h3>{schema.find(field => field.field_key === item.field_key)?.label ?? item.field_key}</h3><p>{item.value}</p><blockquote>{item.evidence.quote}</blockquote><small>Evidence · page {item.evidence.page}</small><div><button onClick={async () => { await decideProposal(orgId, filing.id, item.id, 'accepted'); await reload() }}>Accept</button><button className="secondary" onClick={async () => { await decideProposal(orgId, filing.id, item.id, 'rejected'); await reload() }}>Reject</button></div></article>)}{!proposalCount && <div className="empty-state"><strong>No proposals waiting</strong><p>Upload evidence, then choose “Draft from evidence” for the section you are working on.</p></div>}</section>
        <section><div className="review-heading"><h2>Readiness</h2>{reviewMode && <span>{blockingCount}</span>}</div>{!reviewMode ? <div className="readiness-summary"><strong>{blockingCount} checks pending</strong><p>Missing answers stay quiet while you work. Run readiness when you want a section-by-section fix list.</p><button onClick={() => setReviewMode(true)}>Review blockers</button></div> : <>{sectionFindings.length ? <div className="finding-list">{sectionFindings.slice(0, 8).map(item => <button key={`${item.field_key}:${item.message}`} onClick={() => goToFinding(item)}><span>{item.tier}</span><div><strong>{schema.find(field => field.field_key === item.field_key)?.label ?? item.field_key}</strong><small>{item.message}</small></div></button>)}</div> : <div className="ready-state"><strong>Section ready</strong><p>No blocking findings here.</p></div>}<small className="finding-total">{blockingCount} blockers across the full filing</small><a className="expert-cta studio-expert" href="/deep-dive">Work through assurance gaps with Panacea Bioedge →</a></>}</section>
      </aside>
    </div>
    <p className="submission-reminder">BRSR Lens prepares validated files; the reporting company and its advisors remain responsible for review, approval, and exchange submission.</p>
  </div>
}

function FieldInput({ field, initial, onSave, onTouch, finding }: { field: StudioField; initial: string; onSave: (value: string) => Promise<void>; onTouch: () => void; finding?: string }) {
  const [value, setValue] = useState(initial)
  useEffect(() => setValue(initial), [initial])
  const save = () => { onTouch(); if (value && value !== initial) void onSave(value) }
  const common = { id: field.field_key, value, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setValue(event.target.value), onBlur: save }
  const longAnswer = field.section === 'essential' || field.section === 'leadership' || /(address|scope|issues|products|services|targets|performance|standards|reason)/i.test(field.label)
  return <div id={field.field_key} className={`studio-field ${finding ? 'has-finding' : ''}`}>
    <label htmlFor={`${field.field_key}-control`}>{field.label}{field.required !== false && !field.leadership && <em>Required</em>}{field.core_kpi && <b>Core KPI</b>}</label>
    {field.dtype === 'boolean'
      ? <select {...common} id={`${field.field_key}-control`}><option value="">Choose yes or no</option><option value="true">Yes</option><option value="false">No</option></select>
      : field.dtype === 'text' && longAnswer
        ? <textarea {...common} id={`${field.field_key}-control`} rows={3} placeholder="Enter the disclosed response…"/>
        : <input {...common} id={`${field.field_key}-control`} type={field.dtype === 'date' ? 'date' : field.dtype === 'number' || field.dtype === 'integer' ? 'number' : 'text'} placeholder={field.dtype === 'text' ? 'Enter response…' : undefined}/>}
    <div className="field-meta"><span>{field.unit ?? 'No unit'}</span><details><summary>Schema reference</summary>{field.field_key}</details></div>
    {finding && <p>{finding}</p>}
  </div>
}
