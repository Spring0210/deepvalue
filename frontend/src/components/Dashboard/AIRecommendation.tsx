import type { ReactNode } from 'react'
import { useState, useRef } from 'react'
import { useStock } from '../../context/StockContext'
import { streamRecommendation } from '../../api/client'

// ── Weighted Score Gauge ──────────────────────────────────────────────────────
function ScoreGauge({ score }: { score: number }) {
  const R = 52
  const C = 2 * Math.PI * R
  // Half-circle gauge (180 deg): use full circle but only show top half via transform
  const full = C * 0.75   // 270° arc
  const filled = (score / 100) * full
  const color = score >= 70 ? '#30D158' : score >= 40 ? '#FF9F0A' : '#FF453A'
  const label = score >= 70 ? 'Strong Buy Zone' : score >= 55 ? 'Hold Zone' : 'Avoid Zone'

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className="w-full h-full" style={{ transform: 'rotate(135deg)' }}>
          <circle cx="60" cy="60" r={R} fill="none"
            stroke="rgba(255,255,255,0.07)" strokeWidth="8"
            strokeDasharray={`${full} ${C}`} strokeLinecap="round" />
          <circle cx="60" cy="60" r={R} fill="none"
            stroke={color} strokeWidth="8"
            strokeDasharray={`${filled} ${C}`} strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 1s ease', filter: `drop-shadow(0 0 6px ${color}66)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold tabular-nums" style={{ color }}>{score.toFixed(0)}</span>
          <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.35)' }}>/ 100</span>
        </div>
      </div>
      <span className="text-xs font-medium mt-1" style={{ color }}>{label}</span>
      <span className="text-[11px] mt-0.5" style={{ color: 'rgba(235,235,245,0.3)' }}>
        Weighted Value-Investing Score
      </span>
    </div>
  )
}

// ── Weight Bar ─────────────────────────────────────────────────────────────
function WeightBreakdown({ ratios }: { ratios: ReturnType<typeof useStock>['ratios'] }) {
  const categories = ['Income Statement', 'Returns on Capital', 'Balance Sheet', 'Cash Flow'] as const
  const catColors: Record<string, string> = {
    'Income Statement':   '#5AC8F5',
    'Returns on Capital': '#30D158',
    'Balance Sheet':      '#BF5AF2',
    'Cash Flow':          '#FF9F0A',
  }

  return (
    <div className="space-y-2">
      {categories.map(cat => {
        const catRatios = ratios.filter(r => r.category === cat)
        const totalW    = catRatios.reduce((s, r) => s + r.weight, 0)
        const passW     = catRatios.filter(r => r.passes === true).reduce((s, r) => s + r.weight, 0)
        const scoredW   = catRatios.filter(r => r.passes !== null).reduce((s, r) => s + r.weight, 0)
        const pct       = scoredW > 0 ? passW / scoredW : 0
        const color     = catColors[cat]

        return (
          <div key={cat}>
            <div className="flex justify-between mb-1">
              <span className="text-[11px] font-medium" style={{ color }}>{cat}</span>
              <span className="text-[11px] font-mono" style={{ color: 'rgba(235,235,245,0.4)' }}>
                {(pct * 100).toFixed(0)}% · {(totalW * 100).toFixed(0)}% weight
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.07)' }}>
              <div className="h-full rounded-full transition-all duration-700"
                style={{ width: `${pct * 100}%`, background: color }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Recommendation text renderer (parses sections) ───────────────────────────

// Strip Markdown leakage from the LLM output. The system prompt asks for plain
// text, but real models still sometimes emit **bold**, `code`, or a stray '#'.
// We render through a custom layout (not a Markdown engine), so any leftover
// syntax would otherwise show literally — strip it defensively.
function sanitize(line: string): string {
  return line
    .replace(/\*\*([^*]+)\*\*/g, '$1')     // **bold** → bold
    .replace(/(^|\s)\*([^*\s][^*]*)\*/g, '$1$2')  // *italic* → italic (avoid '* ' bullets)
    .replace(/`([^`]+)`/g, '$1')           // `code` → code
    .replace(/^#{1,6}\s+/, '')             // leading '#' headings
    .replace(/^\*\s+/, '- ')               // '* bullet' → '- bullet'
}

// Section-aware accent colors. Order of keys matters — first match wins.
const SECTION_STYLES: Array<{ match: RegExp; color: string; label: string }> = [
  { match: /^STRENGTHS\b/i,                 color: '#30D158', label: 'Strengths' },
  { match: /^CONCERNS\b/i,                  color: '#FF9F0A', label: 'Concerns' },
  { match: /^(VALUE\s+INVESTING\s+ALIGNMENT|BUFFETT\s+ALIGNMENT|ALIGNMENT)\b/i,
                                            color: '#0A84FF', label: 'Value Investing Alignment' },
  { match: /^MODERN\s+CONTEXT\b/i,          color: '#BF5AF2', label: 'Modern Context' },
]

function classifySection(raw: string): { color: string; label: string } | null {
  const trimmed = raw.replace(/:$/, '').trim()
  for (const s of SECTION_STYLES) if (s.match.test(trimmed)) return { color: s.color, label: s.label }
  return null
}

// Bold the first number-with-unit in a bullet so the eye lands on the metric.
function emphasizeNumber(text: string): ReactNode {
  // Match things like "47.3%", "3.1%", "22x", "$1.2B", "82/100", "0.85"
  const m = text.match(/(-?\d[\d,]*\.?\d*\s*(?:%|x|×|B|M|T|K|\/100)?)/)
  if (!m || m.index === undefined) return text
  const before = text.slice(0, m.index)
  const num    = m[0]
  const after  = text.slice(m.index + num.length)
  return (
    <>
      {before}
      <span className="font-semibold tabular-nums" style={{ color: '#F5F5F7' }}>{num}</span>
      {after}
    </>
  )
}

type Block =
  | { kind: 'verdict'; content: string }
  | { kind: 'section'; color: string; label: string }
  | { kind: 'bullet';  text: string; color: string }
  | { kind: 'para';    text: string }
  | { kind: 'gap' }

function parseRecommendation(text: string): Block[] {
  const blocks: Block[] = []
  let currentColor = 'rgba(235,235,245,0.55)'   // default before any section

  for (const raw of text.split('\n')) {
    const line = sanitize(raw).trimEnd()
    const trimmed = line.trim()

    if (!trimmed) { blocks.push({ kind: 'gap' }); continue }

    if (/^VERDICT\s*:/i.test(trimmed)) {
      blocks.push({ kind: 'verdict', content: trimmed.replace(/^VERDICT\s*:\s*/i, '') })
      continue
    }

    if (/^[A-Z][A-Z\s&-]+:\s*$/.test(trimmed)) {
      const cls = classifySection(trimmed)
      if (cls) {
        currentColor = cls.color
        blocks.push({ kind: 'section', color: cls.color, label: cls.label })
      } else {
        // Unknown uppercase header — render as muted section label.
        currentColor = 'rgba(235,235,245,0.55)'
        blocks.push({ kind: 'section', color: currentColor, label: trimmed.replace(/:$/, '') })
      }
      continue
    }

    if (/^[-•]\s+/.test(trimmed)) {
      blocks.push({ kind: 'bullet', text: trimmed.replace(/^[-•]\s+/, ''), color: currentColor })
      continue
    }

    blocks.push({ kind: 'para', text: trimmed })
  }
  return blocks
}

function RecommendationText({ text, streaming }: { text: string; streaming: boolean }) {
  if (!text) return null

  const blocks = parseRecommendation(text)

  return (
    <div className="space-y-1">
      {blocks.map((b, i) => {
        if (b.kind === 'gap') return <div key={i} className="h-1.5" />

        if (b.kind === 'verdict') {
          const content = b.content
          const isBuy   = /^BUY\b/i.test(content)
          const isAvoid = /^AVOID\b/i.test(content)
          const color   = isBuy ? '#30D158' : isAvoid ? '#FF453A' : '#FF9F0A'
          const verdict = isBuy ? 'BUY' : isAvoid ? 'AVOID' : 'HOLD'
          const tail    = content.replace(/^(BUY|HOLD|AVOID)\s*[—–-]?\s*/i, '')
          return (
            <div key={i} className="flex items-start gap-3 mb-3 pb-3"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
              <span className="text-[11px] font-bold tracking-wider px-2.5 py-1 rounded-md flex-shrink-0 mt-0.5"
                style={{ background: `${color}1F`, color, border: `1px solid ${color}55`,
                  boxShadow: `0 0 12px ${color}22` }}>
                {verdict}
              </span>
              <p className="text-[13.5px] leading-relaxed" style={{ color: '#F5F5F7' }}>
                {emphasizeNumber(tail)}
              </p>
            </div>
          )
        }

        if (b.kind === 'section') {
          return (
            <div key={i} className="flex items-center gap-2 pt-3 pb-1">
              <span className="w-1 h-3 rounded-full" style={{ background: b.color }} />
              <span className="text-[10.5px] font-bold uppercase tracking-[0.12em]"
                style={{ color: b.color }}>
                {b.label}
              </span>
            </div>
          )
        }

        if (b.kind === 'bullet') {
          return (
            <div key={i} className="flex gap-2.5 pl-0.5">
              <span className="text-[14px] leading-[1.4] flex-shrink-0 select-none"
                style={{ color: b.color, opacity: 0.7 }}>•</span>
              <p className="text-[13px] leading-relaxed flex-1"
                style={{ color: 'rgba(235,235,245,0.82)' }}>
                {emphasizeNumber(b.text)}
              </p>
            </div>
          )
        }

        return (
          <p key={i} className="text-[13px] leading-relaxed"
            style={{ color: 'rgba(235,235,245,0.82)' }}>
            {emphasizeNumber(b.text)}
          </p>
        )
      })}
      {streaming && (
        <span className="inline-block w-0.5 h-3.5 animate-pulse align-text-bottom ml-0.5"
          style={{ background: 'rgba(235,235,245,0.6)' }} />
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AIRecommendation() {
  const { ticker, ratios, weightedScore, quote, recommendation, setRecommendation } = useStock()
  const [error, setError] = useState<string | null>(null)
  const accumulatedText = useRef('')

  const { text, streaming } = recommendation
  const generated = recommendation.ticker === ticker && (text !== '' || streaming)

  const generate = async () => {
    if (!ticker || !quote || streaming) return
    setError(null)
    accumulatedText.current = ''
    setRecommendation({ text: '', ticker, streaming: true })

    try {
      await streamRecommendation(
        ticker, ratios, weightedScore, quote,
        token => {
          accumulatedText.current += token
          setRecommendation({ text: accumulatedText.current, ticker, streaming: true })
        },
        () => {
          setRecommendation({ text: accumulatedText.current, ticker, streaming: false })
        },
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate recommendation.')
      setRecommendation({ text: accumulatedText.current, ticker, streaming: false })
    }
  }

  return (
    <div className="space-y-4">
      {/* Score + breakdown */}
      <div className="rounded-xl p-4" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="flex gap-6 items-start flex-wrap">
          <ScoreGauge score={weightedScore} />
          <div className="flex-1 min-w-[200px]">
            <p className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: 'rgba(235,235,245,0.3)' }}>
              Score Breakdown by Category
            </p>
            <WeightBreakdown ratios={ratios} />
            <p className="text-[11px] mt-3 leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              Weights reflect each metric's importance in modern value investing.
              Higher-weight metrics (Gross Margin 13%, Net Margin 11%, EPS Growth 10%)
              have more impact on the final score than binary checks like Preferred Stock (1%).
            </p>
          </div>
        </div>
      </div>

      {/* Weight table */}
      <div className="rounded-xl overflow-hidden" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="px-4 py-2.5 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.35)' }}>
            Metric Weights
          </span>
        </div>
        <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          {ratios.map(r => {
            const passColor = r.passes === true ? '#30D158' : r.passes === false ? '#FF453A' : 'rgba(235,235,245,0.2)'
            return (
              <div key={r.name} className="flex items-center px-4 py-2 gap-3">
                <div className="w-1 h-4 rounded-full flex-shrink-0" style={{ background: passColor }} />
                <span className="flex-1 text-[12px]" style={{ color: 'rgba(235,235,245,0.6)' }}>{r.name}</span>
                <div className="w-20 h-1 rounded-full flex-shrink-0" style={{ background: 'rgba(255,255,255,0.07)' }}>
                  <div className="h-full rounded-full" style={{ width: `${r.weight * 100 / 0.13 * 100}%`, background: passColor, opacity: 0.7 }} />
                </div>
                <span className="text-[11px] font-mono w-8 text-right flex-shrink-0"
                  style={{ color: 'rgba(235,235,245,0.3)' }}>
                  {(r.weight * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Generate button */}
      {!generated && (
        <button
          onClick={generate}
          className="w-full rounded-xl py-3 text-sm font-semibold transition-all"
          style={{ background: '#0A84FF', color: '#ffffff' }}
        >
          Generate AI Investment Analysis
        </button>
      )}

      {/* AI output */}
      {generated && (
        <div className="rounded-xl p-4" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-md flex items-center justify-center text-white font-bold text-[9px]"
                style={{ background: '#0A84FF' }}>
                AI
              </div>
              <span className="text-xs font-semibold" style={{ color: 'rgba(235,235,245,0.5)' }}>
                AI Investment Analysis — {ticker}
              </span>
            </div>
            {!streaming && (
              <button
                onClick={generate}
                className="text-[11px] px-2.5 py-1 rounded-md transition-opacity hover:opacity-70"
                style={{ color: '#0A84FF', background: 'rgba(10,132,255,0.1)' }}>
                Regenerate
              </button>
            )}
          </div>

          {error ? (
            <p className="text-sm" style={{ color: '#FF453A' }}>{error}</p>
          ) : (
            <RecommendationText text={text} streaming={streaming} />
          )}
        </div>
      )}
    </div>
  )
}
