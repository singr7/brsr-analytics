import { useState } from 'react'
import { accessToken } from '../lib/auth'
import { apiUrl } from '../lib/api'
import type { SemanticDSL } from '../lib/semantic'
import { track } from '../lib/track'

interface Answer { dsl?: SemanticDSL; interpretation: string; confidence: number; refusal?: string; context?: { applied: boolean; inherited_filters: string[]; overridden_filters: string[] } }

export function AskFollowUp({ baseDsl, suggestions, questionId }: { baseDsl: SemanticDSL; suggestions: Array<{ id: string; question: string }>; questionId: string }) {
  const [question, setQuestion] = useState(''); const [answer, setAnswer] = useState<Answer | null>(null); const [running, setRunning] = useState(false)
  const ask = async (text = question, followUpId?: string) => {
    if (text.trim().length < 3) return
    setQuestion(text); setRunning(true)
    void track('guided_followup_selected', { guided_question_id: questionId, followup_id: followUpId ?? 'custom', question_length: text.length, source_surface: 'guided_explore' })
    try { const response = await fetch(`${apiUrl}/api/nlq`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken() ? { Authorization: `Bearer ${accessToken()}` } : {}) }, body: JSON.stringify({ question: text, base_dsl: baseDsl }) }); setAnswer(await response.json() as Answer) } finally { setRunning(false) }
  }
  return <section className="followup" aria-labelledby="followup-title"><p className="eyebrow">Ask a follow-up</p><h2 id="followup-title">Keep this cohort in the conversation.</h2><p className="context-line"><strong>Data included:</strong> {baseDsl.dimensions.join(', ') || 'all eligible records'} · {baseDsl.filters.map(item => `${item.dimension} ${String(item.value)}`).join(' · ') || 'no additional filters'}</p><div className="suggested-followups">{suggestions.map(item => <button key={item.id} onClick={() => void ask(item.question, item.id)}>{item.question}</button>)}</div><div className="ask-box"><textarea value={question} onChange={event => setQuestion(event.target.value)} aria-label="Ask a follow-up question" placeholder="Ask about the result in front of you…"/><button onClick={() => void ask()} disabled={running || question.trim().length < 3}>{running ? 'Interpreting…' : 'Ask BRSR Lens →'}</button></div>{answer && <div className="transparency" aria-live="polite"><p className="eyebrow">I understood your question as… · confidence {(answer.confidence * 100).toFixed(0)}%</p><h3>{answer.interpretation}</h3>{answer.refusal && <p className="refusal">{answer.refusal}</p>}<p><strong>Data included:</strong> {answer.context?.applied ? 'The visible guided context was applied.' : 'No guided context was applied.'}</p>{answer.context?.overridden_filters.length ? <p>Updated filters: {answer.context.overridden_filters.join(', ')}</p> : null}<details><summary>View query details</summary><pre>{JSON.stringify(answer.dsl, null, 2)}</pre></details></div>}</section>
}
