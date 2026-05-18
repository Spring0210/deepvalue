import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { streamAgent, streamOrchestrate } from '../../api/client'
import type {
  AgentRunSummary, AgentStep, AgentToolCall, AgentToolResult,
  Finding, OrchestratorRunSummary, OrchestratorStep, ResearchPlan, SubagentRole,
} from '../../types'

type Mode = 'single' | 'multi'

export default function AgentPanel() {
  const [query,    setQuery]    = useState('')
  const [mode,     setMode]     = useState<Mode>('single')
  const [steps,    setSteps]    = useState<AgentStep[]>([])
  const [summary,  setSummary]  = useState<AgentRunSummary | null>(null)
  const [orchSteps,   setOrchSteps]   = useState<OrchestratorStep[]>([])
  const [orchSummary, setOrchSummary] = useState<OrchestratorRunSummary | null>(null)
  const [running, setRunning] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const traceEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [steps.length, orchSteps.length, summary, orchSummary, error])

  function reset() {
    setSteps([]); setSummary(null)
    setOrchSteps([]); setOrchSummary(null)
    setError(null)
  }

  async function handleRun() {
    if (!query.trim() || running) return
    reset(); setRunning(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      if (mode === 'single') {
        await streamAgent(
          query.trim(),
          s   => setSteps(prev => [...prev, s]),
          sum => setSummary(sum),
          msg => setError(msg),
          ctrl.signal,
        )
      } else {
        await streamOrchestrate(
          query.trim(),
          s   => setOrchSteps(prev => [...prev, s]),
          sum => setOrchSummary(sum),
          msg => setError(msg),
          ctrl.signal,
        )
      }
    } catch (e) {
      const err = e as Error
      if (err?.name !== 'AbortError') setError(err.message || String(e))
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }

  function handleStop() { abortRef.current?.abort() }

  const hasOutput = mode === 'single' ? steps.length > 0 : orchSteps.length > 0
  const activeSummary = mode === 'single' ? summary : orchSummary

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <ModeToggle
        mode={mode}
        disabled={running}
        onChange={m => { if (m !== mode) { setMode(m); reset() } }}
      />

      {/* Query */}
      <div className="rounded-xl p-3"
        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleRun() }
          }}
          placeholder={
            mode === 'single'
              ? 'Ask anything — e.g. "Should I buy NVDA?" or "Compare AAPL vs MSFT in services revenue."'
              : 'Ask a research question — the planner picks specialists per ticker. e.g. "Analyze AAPL through a Buffett lens."'
          }
          rows={2}
          disabled={running}
          className="w-full bg-transparent outline-none resize-none text-sm"
          style={{ color: '#F5F5F7' }}
        />
        <div className="flex justify-between items-center mt-2">
          <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.3)' }}>
            ⌘/Ctrl + Enter to run
          </span>
          {running ? (
            <button
              onClick={handleStop}
              className="rounded-lg px-3 py-1.5 text-sm font-medium"
              style={{ background: 'rgba(255,69,58,0.15)', color: '#FF453A', border: '1px solid rgba(255,69,58,0.3)' }}
            >Stop</button>
          ) : (
            <button
              onClick={handleRun}
              disabled={!query.trim()}
              className="rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: '#0A84FF', color: 'white' }}
            >{mode === 'single' ? 'Run agent' : 'Run pipeline'}</button>
          )}
        </div>
      </div>

      {/* Empty state */}
      {!hasOutput && !running && !error && (
        <div className="text-center py-10" style={{ color: 'rgba(235,235,245,0.35)' }}>
          {mode === 'single' ? (
            <>
              <p className="text-sm">The orchestrator picks its own tools and streams every step live.</p>
              <p className="text-xs mt-1" style={{ color: 'rgba(235,235,245,0.22)' }}>
                Available tools: get_stock_quote · get_buffett_score · get_valuation · get_moat · get_price_history · get_technicals
              </p>
            </>
          ) : (
            <>
              <p className="text-sm">Planner → specialist subagents (parallel) → Synthesizer.</p>
              <p className="text-xs mt-1" style={{ color: 'rgba(235,235,245,0.22)' }}>
                Specialists: <span style={{ color: 'rgba(235,235,245,0.45)' }}>fundamentals</span>{' '}
                <span style={{ color: 'rgba(235,235,245,0.22)' }}>· news · technical · valuation · risk</span>{' '}
                <span style={{ color: 'rgba(235,235,245,0.22)' }}>(reserved)</span>
              </p>
            </>
          )}
        </div>
      )}

      {/* Live trace */}
      {mode === 'single' && steps.length > 0 && (
        <div className="space-y-2">
          {steps.map((step, i) => <StepCard key={i} step={step} />)}
          {running && <WorkingIndicator />}
        </div>
      )}
      {mode === 'multi' && orchSteps.length > 0 && (
        <div className="space-y-2">
          {orchSteps.map((step, i) => <OrchStepCard key={i} step={step} />)}
          {running && <WorkingIndicator />}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="rounded-xl px-4 py-3"
          style={{ background: 'rgba(255,69,58,0.1)', border: '1px solid rgba(255,69,58,0.2)' }}>
          <p className="text-sm font-medium mb-0.5" style={{ color: '#FF453A' }}>Agent error</p>
          <p className="text-xs" style={{ color: 'rgba(255,69,58,0.8)' }}>{error}</p>
        </div>
      )}

      {/* Run summary */}
      {activeSummary && (
        mode === 'single'
          ? <SummaryBar summary={summary!} stepCount={steps.length} />
          : <OrchSummaryBar summary={orchSummary!} stepCount={orchSteps.length} />
      )}

      <div ref={traceEndRef} />
    </div>
  )
}

// ── Mode toggle ──────────────────────────────────────────────────────────────

function ModeToggle({ mode, disabled, onChange }: {
  mode: Mode; disabled: boolean; onChange: (m: Mode) => void
}) {
  return (
    <div className="inline-flex rounded-lg p-0.5"
      style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
      {(['single', 'multi'] as Mode[]).map(m => {
        const active = m === mode
        return (
          <button
            key={m}
            onClick={() => onChange(m)}
            disabled={disabled}
            className="px-3 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-40"
            style={{
              background: active ? '#0A84FF' : 'transparent',
              color:      active ? 'white'   : 'rgba(235,235,245,0.6)',
            }}
          >
            {m === 'single' ? 'Single agent' : 'Multi-agent'}
          </button>
        )
      })}
    </div>
  )
}

function WorkingIndicator() {
  return (
    <div className="flex items-center gap-2 px-3 py-2 text-xs"
      style={{ color: 'rgba(235,235,245,0.4)' }}>
      <div className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin"
        style={{ borderColor: 'rgba(10,132,255,0.2)', borderTopColor: '#0A84FF' }} />
      <span>Working…</span>
    </div>
  )
}

// ── Single-agent step cards ──────────────────────────────────────────────────

function StepCard({ step }: { step: AgentStep }) {
  switch (step.kind) {
    case 'llm':        return <LLMStepCard        step={step} />
    case 'tool_batch': return <ToolBatchStepCard  step={step} />
    case 'repair':     return <RepairStepCard     step={step} />
    case 'final':      return <FinalStepCard      step={step} />
    case 'error':      return <ErrorStepCard      step={step} />
  }
}

function StepFrame({ kind, accent, children }: {
  kind: string; accent: string; children: ReactNode
}) {
  return (
    <div className="rounded-xl p-3 text-sm"
      style={{ background: '#1F1F22', border: `1px solid ${accent}33` }}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
          style={{ background: `${accent}22`, color: accent }}>
          {kind}
        </span>
      </div>
      <div style={{ color: 'rgba(235,235,245,0.85)' }}>{children}</div>
    </div>
  )
}

function LLMStepCard({ step }: { step: AgentStep }) {
  return (
    <StepFrame kind="LLM" accent="#0A84FF">
      {step.text && (
        <p className="whitespace-pre-wrap text-[13px] leading-relaxed mb-2">{step.text}</p>
      )}
      {step.tool_calls.length > 0 && (
        <div className="space-y-1">
          {step.tool_calls.map(tc => <ToolCallLine key={tc.id} call={tc} />)}
        </div>
      )}
      {step.usage && (
        <div className="mt-2 text-[10px] font-mono"
          style={{ color: 'rgba(235,235,245,0.3)' }}>
          {step.usage.input_tokens} in · {step.usage.output_tokens} out ·{' '}
          ${step.usage.cost_usd.toFixed(4)} · {step.usage.latency_ms}ms
        </div>
      )}
    </StepFrame>
  )
}

function ToolCallLine({ call }: { call: AgentToolCall }) {
  return (
    <div className="font-mono text-[12px]"
      style={{ color: 'rgba(235,235,245,0.55)' }}>
      → <span style={{ color: '#5E5CE6' }}>{call.name}</span>
      <span style={{ color: 'rgba(235,235,245,0.35)' }}>
        ({formatArgs(call.args)})
      </span>
    </div>
  )
}

function ToolBatchStepCard({ step }: { step: AgentStep }) {
  return (
    <StepFrame kind="TOOLS" accent="#5E5CE6">
      <div className="space-y-1.5">
        {step.tool_results.map(r => <ToolResultRow key={r.call_id} result={r} />)}
      </div>
    </StepFrame>
  )
}

function ToolResultRow({ result }: { result: AgentToolResult }) {
  const [open, setOpen] = useState(false)
  const color = result.ok ? '#30D158' : '#FF453A'
  const preview = result.ok ? previewOutput(result.output) : (result.error || 'failed')
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full text-left flex items-start gap-2 group"
      >
        <span style={{ color }}>{result.ok ? '✓' : '✗'}</span>
        <span className="font-mono text-[12px]" style={{ color: '#5E5CE6' }}>{result.name}</span>
        <span className="text-[11px] flex-1 truncate"
          style={{ color: 'rgba(235,235,245,0.4)' }}>
          {preview}
        </span>
        <span className="text-[10px] font-mono"
          style={{ color: 'rgba(235,235,245,0.3)' }}>
          {result.latency_ms}ms{result.attempts > 1 ? ` · ${result.attempts}×` : ''}
        </span>
      </button>
      {open && (
        <pre className="mt-1.5 ml-5 p-2 rounded text-[11px] font-mono overflow-x-auto whitespace-pre-wrap"
          style={{ background: '#111113', color: 'rgba(235,235,245,0.65)', maxHeight: 240 }}>
          {result.ok ? JSON.stringify(result.output, null, 2) : (result.error || '')}
        </pre>
      )}
    </div>
  )
}

function RepairStepCard({ step }: { step: AgentStep }) {
  return (
    <StepFrame kind="REPAIR" accent="#FF9F0A">
      <p className="text-[12px]" style={{ color: 'rgba(235,235,245,0.7)' }}>
        Output didn't match schema — asking the model to retry.
      </p>
      {step.error && (
        <p className="text-[11px] mt-1 font-mono" style={{ color: 'rgba(255,159,10,0.7)' }}>
          {step.error}
        </p>
      )}
    </StepFrame>
  )
}

function FinalStepCard({ step }: { step: AgentStep }) {
  return (
    <div className="rounded-xl p-4"
      style={{ background: 'rgba(48,209,88,0.06)', border: '1px solid rgba(48,209,88,0.25)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(48,209,88,0.15)', color: '#30D158' }}>
          Final
        </span>
      </div>
      {step.text
        ? <MarkdownLite text={step.text} />
        : <p className="text-[13px]" style={{ color: 'rgba(235,235,245,0.5)' }}>(empty)</p>}
    </div>
  )
}

// ── Multi-agent step cards ───────────────────────────────────────────────────

function OrchStepCard({ step }: { step: OrchestratorStep }) {
  switch (step.kind) {
    case 'plan':     return <PlanStepCard     step={step} />
    case 'subagent': return <SubagentStepCard step={step} />
    case 'synth':    return null  // Synth and Final carry the same text; show only Final.
    case 'final':    return <SynthFinalStepCard text={step.text || ''} />
    case 'error':    return <OrchErrorStepCard  step={step} />
  }
}

function PlanStepCard({ step }: { step: OrchestratorStep }) {
  const plan: ResearchPlan | null | undefined = step.plan
  if (!plan) return null
  return (
    <StepFrame kind="Plan" accent="#0A84FF">
      <p className="text-[13px] leading-relaxed mb-2" style={{ color: '#F5F5F7' }}>
        {plan.rationale}
      </p>
      <div className="space-y-1">
        {plan.subtasks.map((t, i) => (
          <div key={i} className="flex items-center gap-2 text-[12px]"
            style={{ color: 'rgba(235,235,245,0.7)' }}>
            <RoleChip role={t.role} />
            <span className="font-mono" style={{ color: '#F5F5F7' }}>{t.ticker}</span>
            {t.focus && (
              <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.4)' }}>
                — {t.focus}
              </span>
            )}
          </div>
        ))}
      </div>
    </StepFrame>
  )
}

function SubagentStepCard({ step }: { step: OrchestratorStep }) {
  const ok = !!step.finding && !step.error
  const accent = ok ? '#30D158' : '#FF453A'
  return (
    <div className="rounded-xl p-3"
      style={{ background: '#1F1F22', border: `1px solid ${accent}33` }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
          style={{ background: `${accent}22`, color: accent }}>
          {ok ? 'Finding' : 'Subagent failed'}
        </span>
        {step.role && <RoleChip role={step.role} />}
        {step.ticker && (
          <span className="font-mono text-[12px]" style={{ color: '#F5F5F7' }}>{step.ticker}</span>
        )}
      </div>
      {ok && step.finding ? (
        <FindingBody finding={step.finding} />
      ) : (
        <p className="text-[12px] font-mono" style={{ color: '#FF453A' }}>
          {step.error || 'Unknown error'}
        </p>
      )}
    </div>
  )
}

function FindingBody({ finding }: { finding: Finding }) {
  return (
    <div style={{ color: 'rgba(235,235,245,0.85)' }}>
      <p className="text-[13px] leading-relaxed mb-2">{finding.summary}</p>
      {finding.bullets.length > 0 && (
        <ul className="list-disc ml-5 space-y-0.5 text-[12.5px] leading-relaxed mb-2"
          style={{ color: 'rgba(235,235,245,0.8)' }}>
          {finding.bullets.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      )}
      {finding.citations.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {finding.citations.map(c => (
            <span key={c} className="font-mono text-[10px] px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(94,92,230,0.15)', color: '#5E5CE6' }}>
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function SynthFinalStepCard({ text }: { text: string }) {
  return (
    <div className="rounded-xl p-4"
      style={{ background: 'rgba(48,209,88,0.06)', border: '1px solid rgba(48,209,88,0.25)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(48,209,88,0.15)', color: '#30D158' }}>
          Synthesis
        </span>
      </div>
      {text
        ? <MarkdownLite text={text} />
        : <p className="text-[13px]" style={{ color: 'rgba(235,235,245,0.5)' }}>(empty)</p>}
    </div>
  )
}

function OrchErrorStepCard({ step }: { step: OrchestratorStep }) {
  return (
    <StepFrame kind="Error" accent="#FF453A">
      <p className="text-[12px] font-mono" style={{ color: '#FF453A' }}>
        {step.error || 'Unknown error'}
      </p>
    </StepFrame>
  )
}

function RoleChip({ role }: { role: SubagentRole }) {
  const colors: Record<SubagentRole, string> = {
    fundamentals: '#5E5CE6',
    news:         '#FF9F0A',
    technical:    '#64D2FF',
    valuation:    '#BF5AF2',
    risk:         '#FF453A',
  }
  const c = colors[role]
  return (
    <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
      style={{ background: `${c}22`, color: c }}>
      {role}
    </span>
  )
}

// Tiny markdown renderer for the orchestrator's final answer.
// The agent's output shape is fixed by the system prompt — `##`/`###`
// headings, `**bold**` for key numbers, `- ` bullets, blank-line paragraphs.
// A 30-line hand-rolled parser beats pulling in react-markdown + remark + rehype.
function MarkdownLite({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const nodes: ReactNode[] = []
  let bullets: string[] = []
  let paragraph: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    nodes.push(
      <ul key={`ul-${nodes.length}`} className="list-disc ml-5 space-y-1 mb-2 text-[13px] leading-relaxed"
        style={{ color: '#F5F5F7' }}>
        {bullets.map((b, i) => <li key={i}>{renderInline(b)}</li>)}
      </ul>
    )
    bullets = []
  }
  const flushParagraph = () => {
    if (!paragraph.length) return
    nodes.push(
      <p key={`p-${nodes.length}`} className="text-[13px] leading-relaxed mb-2"
        style={{ color: '#F5F5F7' }}>
        {renderInline(paragraph.join(' '))}
      </p>
    )
    paragraph = []
  }
  const flushAll = () => { flushBullets(); flushParagraph() }

  for (const raw of lines) {
    const line = raw.trim()

    if (!line || /^-{3,}$/.test(line)) { flushAll(); continue }

    const h2 = line.match(/^##\s+(.+?)\s*$/)
    const h3 = line.match(/^###\s+(.+?)\s*$/)
    if (h2 || h3) {
      flushAll()
      const heading = (h2?.[1] ?? h3?.[1] ?? '').replace(/\*\*/g, '')
      const isTop = !!h2
      nodes.push(
        <h3 key={`h-${nodes.length}`}
          className={isTop ? 'text-[12px] font-bold uppercase tracking-wider mt-3 mb-1.5'
                           : 'text-[12px] font-semibold mt-2 mb-1'}
          style={{ color: isTop ? '#30D158' : 'rgba(235,235,245,0.85)' }}>
          {heading}
        </h3>
      )
      continue
    }

    const bullet = line.match(/^[-*]\s+(.+)$/)
    if (bullet) { flushParagraph(); bullets.push(bullet[1]); continue }

    flushBullets()
    paragraph.push(line)
  }
  flushAll()

  return <div>{nodes}</div>
}

// Inline: **bold** segments. Everything else is plain text.
function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const regex = /\*\*([^*]+)\*\*/g
  let lastIdx = 0
  let m: RegExpExecArray | null
  let key = 0
  while ((m = regex.exec(text)) !== null) {
    if (m.index > lastIdx) parts.push(text.slice(lastIdx, m.index))
    parts.push(<strong key={key++} style={{ color: '#FFFFFF' }}>{m[1]}</strong>)
    lastIdx = m.index + m[0].length
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx))
  return parts
}

function ErrorStepCard({ step }: { step: AgentStep }) {
  return (
    <StepFrame kind="ERROR" accent="#FF453A">
      <p className="text-[12px] font-mono" style={{ color: '#FF453A' }}>
        {step.error || 'Unknown error'}
      </p>
    </StepFrame>
  )
}

// ── Summary ──────────────────────────────────────────────────────────────────

function SummaryBar({ summary, stepCount }: { summary: AgentRunSummary; stepCount: number }) {
  const ok = summary.status === 'completed'
  const color = ok ? '#30D158' : summary.status === 'capped' ? '#FF9F0A' : '#FF453A'
  return (
    <div className="rounded-xl px-4 py-2.5 flex items-center justify-between text-xs"
      style={{ background: '#1F1F22', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(235,235,245,0.6)' }}>
      <div className="flex items-center gap-2">
        <span style={{ color, fontWeight: 600, textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
          {summary.status}
        </span>
        <span>·</span>
        <span>{stepCount} steps</span>
        <span>·</span>
        <span>{(summary.total_latency_ms / 1000).toFixed(2)}s</span>
      </div>
      <div className="font-mono">
        ${summary.total_cost_usd.toFixed(4)} · {summary.total_input_tokens} in /{' '}
        {summary.total_output_tokens} out
      </div>
    </div>
  )
}

function OrchSummaryBar({ summary, stepCount }: { summary: OrchestratorRunSummary; stepCount: number }) {
  const color =
    summary.status === 'completed' ? '#30D158'
    : summary.status === 'capped'  ? '#FF9F0A'
    :                                '#FF453A'
  return (
    <div className="rounded-xl px-4 py-2.5 flex items-center justify-between text-xs"
      style={{ background: '#1F1F22', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(235,235,245,0.6)' }}>
      <div className="flex items-center gap-2">
        <span style={{ color, fontWeight: 600, textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
          {summary.status}
        </span>
        <span>·</span>
        <span>{stepCount} steps</span>
        <span>·</span>
        <span>{summary.n_findings}/{summary.n_subagents} findings</span>
        <span>·</span>
        <span>{(summary.total_latency_ms / 1000).toFixed(2)}s</span>
      </div>
      <div className="font-mono">
        ${summary.total_cost_usd.toFixed(4)} · {summary.total_input_tokens} in /{' '}
        {summary.total_output_tokens} out
      </div>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────────────────────

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args)
  if (entries.length === 0) return ''
  return entries
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(', ')
    .slice(0, 120)
}

function previewOutput(output: unknown): string {
  if (output === null || output === undefined) return 'null'
  if (typeof output === 'string') return output.slice(0, 100)
  try {
    const s = JSON.stringify(output)
    return s.length > 100 ? s.slice(0, 100) + '…' : s
  } catch {
    return String(output)
  }
}
