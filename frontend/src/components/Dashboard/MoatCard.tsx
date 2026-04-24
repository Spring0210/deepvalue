import { useStock } from '../../context/StockContext'

const STRENGTH_CONFIG = {
  Wide:   { color: '#30D158', bg: 'rgba(48,209,88,0.12)',   border: 'rgba(48,209,88,0.25)' },
  Narrow: { color: '#FF9F0A', bg: 'rgba(255,159,10,0.12)',  border: 'rgba(255,159,10,0.25)' },
  None:   { color: '#FF453A', bg: 'rgba(255,69,58,0.10)',   border: 'rgba(255,69,58,0.20)' },
}

const MOAT_DESCRIPTIONS: Record<string, string> = {
  'Network Effect':    'Value grows as more users join the platform, creating a self-reinforcing advantage.',
  'Switching Costs':   'Customers find it expensive or disruptive to switch to a competitor.',
  'Cost Advantage':    'Produces goods or services cheaper than competitors due to scale or process efficiency.',
  'Intangible Assets': 'Brand, patents, or regulatory licenses that competitors cannot easily replicate.',
  'Efficient Scale':   'Dominates a niche market where a second entrant would be unprofitable.',
}

function ScoreBar({ label, score, isPrimary }: { label: string; score: number; isPrimary: boolean }) {
  const pct = Math.round(score * 100)
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[11px]" style={{ color: isPrimary ? '#F5F5F7' : 'rgba(235,235,245,0.4)' }}>
          {label}
        </span>
        <span className="text-[11px] font-mono" style={{ color: isPrimary ? '#0A84FF' : 'rgba(235,235,245,0.28)' }}>
          {pct}
        </span>
      </div>
      <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: isPrimary ? '#0A84FF' : 'rgba(255,255,255,0.15)',
          }}
        />
      </div>
    </div>
  )
}

export default function MoatCard() {
  const { moat } = useStock()
  if (!moat) return null

  const cfg = STRENGTH_CONFIG[moat.strength]
  const sortedScores = Object.entries(moat.scores).sort(([, a], [, b]) => b - a)

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-2 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.35)' }}>
          Competitive Moat
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-md"
          style={{ background: 'rgba(191,90,242,0.15)', color: '#BF5AF2' }}>
          Buffett Phase 4
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Strength badge + primary type */}
        <div className="flex items-start gap-4">
          <div className="rounded-xl px-4 py-3 text-center flex-shrink-0"
            style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, minWidth: 80 }}>
            <div className="text-lg font-bold leading-tight" style={{ color: cfg.color }}>
              {moat.strength}
            </div>
            <div className="text-[10px] uppercase tracking-wider mt-0.5"
              style={{ color: cfg.color, opacity: 0.7 }}>
              Moat
            </div>
          </div>

          <div className="flex-1 min-w-0">
            {moat.primary_type ? (
              <>
                <div className="text-sm font-semibold" style={{ color: '#F5F5F7' }}>
                  {moat.primary_type}
                </div>
                <div className="text-[11px] mt-0.5 leading-relaxed" style={{ color: 'rgba(235,235,245,0.4)' }}>
                  {MOAT_DESCRIPTIONS[moat.primary_type] ?? ''}
                </div>
                {moat.indicators.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {moat.indicators.map(ind => (
                      <span key={ind} className="text-[10px] px-2 py-0.5 rounded-md"
                        style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(235,235,245,0.5)' }}>
                        {ind}
                      </span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm leading-relaxed" style={{ color: 'rgba(235,235,245,0.4)' }}>
                No clear competitive advantage identified from available metrics.
                This may indicate a commoditized business or insufficient data.
              </div>
            )}
          </div>
        </div>

        {/* Score bars */}
        <div className="rounded-lg p-3 space-y-2.5"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <p className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'rgba(235,235,245,0.25)' }}>
            Moat Type Scores
          </p>
          {sortedScores.map(([name, score]) => (
            <ScoreBar key={name} label={name} score={score} isPrimary={name === moat.primary_type} />
          ))}
        </div>

        <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.2)' }}>
          <span style={{ color: '#30D158' }}>Wide</span> = durable multi-year advantage. {' '}
          <span style={{ color: '#FF9F0A' }}>Narrow</span> = some advantage but under competitive pressure. {' '}
          <span style={{ color: '#FF453A' }}>None</span> = commoditized business.
          Derived from sector, margins, ROE, growth, and valuation signals.
        </p>
      </div>
    </div>
  )
}
