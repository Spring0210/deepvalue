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
        Weighted Buffett Score
      </span>
    </div>
  )
}

// ── Weight Bar ─────────────────────────────────────────────────────────────
function WeightBreakdown({ ratios }: { ratios: ReturnType<typeof useStock>['ratios'] }) {
  const categories = ['Income Statement', 'Balance Sheet', 'Cash Flow'] as const
  const catColors: Record<string, string> = {
    'Income Statement': '#5AC8F5',
    'Balance Sheet':    '#BF5AF2',
    'Cash Flow':        '#FF9F0A',
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
function RecommendationText({ text, streaming }: { text: string; streaming: boolean }) {
  if (!text) return null

  const lines = text.split('\n')

  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        const isSectionHeader = /^[A-Z][A-Z\s&]+:/.test(line.trim())
        const isVerdict = line.trim().startsWith('VERDICT:')

        if (isVerdict) {
          const content = line.replace('VERDICT:', '').trim()
          const isBuy   = /BUY/i.test(content)
          const isAvoid = /AVOID/i.test(content)
          const color   = isBuy ? '#30D158' : isAvoid ? '#FF453A' : '#FF9F0A'
          const verdict = isBuy ? 'BUY' : isAvoid ? 'AVOID' : 'HOLD'
          return (
            <div key={i} className="flex items-center gap-3 mb-3 pb-3"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              <span className="text-xs font-bold px-3 py-1 rounded-lg"
                style={{ background: `${color}18`, color, border: `1px solid ${color}44` }}>
                {verdict}
              </span>
              <span className="text-[13px]" style={{ color: 'rgba(235,235,245,0.7)' }}>
                {content.replace(/^(BUY|HOLD|AVOID)\s*[—–-]?\s*/i, '')}
              </span>
            </div>
          )
        }

        if (isSectionHeader) {
          return (
            <p key={i} className="text-[11px] font-semibold uppercase tracking-wider pt-2 pb-0.5"
              style={{ color: 'rgba(235,235,245,0.35)' }}>
              {line.replace(':', '')}
            </p>
          )
        }

        if (line.trim().startsWith('-')) {
          return (
            <div key={i} className="flex gap-2">
              <span className="text-[11px] mt-0.5 flex-shrink-0" style={{ color: 'rgba(235,235,245,0.2)' }}>–</span>
              <p className="text-[13px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.65)' }}>
                {line.replace(/^[-•]\s*/, '')}
              </p>
            </div>
          )
        }

        if (!line.trim()) return <div key={i} className="h-1" />

        return (
          <p key={i} className="text-[13px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.65)' }}>
            {line}
          </p>
        )
      })}
      {streaming && (
        <span className="inline-block w-0.5 h-3.5 animate-pulse align-text-bottom ml-0.5"
          style={{ background: 'rgba(235,235,245,0.5)' }} />
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
