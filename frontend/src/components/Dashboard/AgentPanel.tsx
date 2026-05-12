import { useEffect, useRef, useState } from 'react'
import { streamAgent } from '../../api/client'
import type { AgentRunSummary, AgentStep, AgentToolCall, AgentToolResult } from '../../types'

export default function AgentPanel() {
  const [query,   setQuery]   = useState('')
  const [steps,   setSteps]   = useState<AgentStep[]>([])
  const [summary, setSummary] = useState<AgentRunSummary | null>(null)
  const [running, setRunning] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const traceEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [steps.length, summary, error])

  async function handleRun() {
    if (!query.trim() || running) return
    setSteps([]); setSummary(null); setError(null); setRunning(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await streamAgent(
        query.trim(),
        s   => setSteps(prev => [...prev, s]),
        sum => setSummary(sum),
        msg => setError(msg),
        ctrl.signal,
      )
    } catch (e) {
      const err = e as Error
      if (err?.name !== 'AbortError') setError(err.message || String(e))
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }

  function handleStop() { abortRef.current?.abort() }

  return (
    <div className="space-y-4">
      {/* Query */}
      <div className="rounded-xl p-3"
        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleRun() }
          }}
          placeholder="Ask anything — e.g. &quot;Should I buy NVDA?&quot; or &quot;Compare AAPL vs MSFT in services revenue.&quot;"
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
            >Run agent</button>
          )}
        </div>
      </div>

      {/* Empty state */}
      {steps.length === 0 && !running && !error && (
        <div className="text-center py-10" style={{ color: 'rgba(235,235,245,0.35)' }}>
          <p className="text-sm">The orchestrator picks its own tools and streams every step live.</p>
          <p className="text-xs mt-1" style={{ color: 'rgba(235,235,245,0.22)' }}>
            Available tools: get_stock_quote · get_buffett_score · get_valuation · get_moat · get_price_history · get_technicals
          </p>
        </div>
      )}

      {/* Live trace */}
      {steps.length > 0 && (
        <div className="space-y-2">
          {steps.map((step, i) => <StepCard key={i} step={step} />)}
          {running && (
            <div className="flex items-center gap-2 px-3 py-2 text-xs"
              style={{ color: 'rgba(235,235,245,0.4)' }}>
              <div className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'rgba(10,132,255,0.2)', borderTopColor: '#0A84FF' }} />
              <span>Working…</span>
            </div>
          )}
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
      {summary && <SummaryBar summary={summary} stepCount={steps.length} />}

      <div ref={traceEndRef} />
    </div>
  )
}

// ── Step cards ───────────────────────────────────────────────────────────────

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
  kind: string; accent: string; children: React.ReactNode
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
      <p className="text-[13px] leading-relaxed whitespace-pre-wrap"
        style={{ color: '#F5F5F7' }}>
        {step.text || '(empty)'}
      </p>
    </div>
  )
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
