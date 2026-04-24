import type { StockQuote, MoatResult } from '../../types'

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n === null || n === undefined) return '—'
  return n.toFixed(decimals)
}
function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return `${(n * 100).toFixed(1)}%`
}
function fmtCap(n: number | null | undefined): string {
  if (!n) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9)  return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6)  return `$${(n / 1e6).toFixed(1)}M`
  return `$${n.toLocaleString()}`
}

const MOAT_BADGE: Record<string, { color: string; bg: string }> = {
  Wide:   { color: '#30D158', bg: 'rgba(48,209,88,0.12)' },
  Narrow: { color: '#FF9F0A', bg: 'rgba(255,159,10,0.12)' },
  None:   { color: '#FF453A', bg: 'rgba(255,69,58,0.10)' },
}

interface Props { ticker: string; quote: StockQuote; moat?: MoatResult | null }

function Stat({ label, value, highlight, color }: {
  label: string; value: string; highlight?: boolean; color?: string
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'rgba(235,235,245,0.28)' }}>
        {label}
      </p>
      <p className="text-sm font-semibold font-mono"
        style={{ color: color ?? (highlight ? '#F5F5F7' : 'rgba(235,235,245,0.7)') }}>
        {value}
      </p>
    </div>
  )
}

// 52-week high/low price bar
function WeekRangeBar({ price, low, high }: {
  price: number | null | undefined
  low: number | null | undefined
  high: number | null | undefined
}) {
  if (!price || !low || !high || high <= low) return null
  const pct = Math.max(0, Math.min(100, ((price - low) / (high - low)) * 100))
  const nearHigh = pct >= 80
  const nearLow  = pct <= 20
  const barColor = nearHigh ? '#30D158' : nearLow ? '#FF453A' : '#FF9F0A'

  return (
    <div className="col-span-4 sm:col-span-6 lg:col-span-8 pt-1 pb-0.5">
      <div className="flex justify-between text-[10px] mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>
        <span className="uppercase tracking-wider">52-Week Range</span>
        <span className="font-mono" style={{ color: 'rgba(235,235,245,0.4)' }}>
          ${fmt(low, 2)} — ${fmt(high, 2)}
        </span>
      </div>
      <div className="relative h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div
          className="absolute h-full rounded-full"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, rgba(255,255,255,0.08), ${barColor})` }}
        />
        <div
          className="absolute w-2.5 h-2.5 rounded-full border-2 top-1/2 -translate-y-1/2 -translate-x-1/2"
          style={{ left: `${pct}%`, background: barColor, borderColor: '#242426' }}
        />
      </div>
      <div className="flex justify-between mt-1 text-[10px] font-mono" style={{ color: 'rgba(235,235,245,0.3)' }}>
        <span>Low</span>
        <span style={{ color: barColor }}>{pct.toFixed(0)}% of range</span>
        <span>High</span>
      </div>
    </div>
  )
}

// Analyst consensus badge
function AnalystBadge({ rec }: { rec: string | null | undefined }) {
  if (!rec) return <span style={{ color: 'rgba(235,235,245,0.7)' }}>—</span>
  const map: Record<string, { label: string; color: string }> = {
    'strong_buy':   { label: 'Strong Buy',    color: '#30D158' },
    'buy':          { label: 'Buy',           color: '#30D158' },
    'hold':         { label: 'Hold',          color: '#FF9F0A' },
    'underperform': { label: 'Underperform',  color: '#FF453A' },
    'sell':         { label: 'Sell',          color: '#FF453A' },
    'strong_sell':  { label: 'Strong Sell',   color: '#FF453A' },
  }
  const { label, color } = map[rec.toLowerCase()] ?? { label: rec, color: 'rgba(235,235,245,0.5)' }
  return <span className="text-sm font-semibold font-mono" style={{ color }}>{label}</span>
}

// Analyst price target range bar: Low ——[median|mean]—— High with current price pin
function TargetRangeBar({ price, low, mean, median, high, analysts }: {
  price: number | null | undefined
  low: number | null | undefined
  mean: number | null | undefined
  median: number | null | undefined
  high: number | null | undefined
  analysts: number | null | undefined
}) {
  if (!low || !high || !mean || high <= low) return null
  const rangeMin = Math.min(low, price ?? low) * 0.97
  const rangeMax = Math.max(high, price ?? high) * 1.03
  const span = rangeMax - rangeMin
  const pos = (v: number) => `${((v - rangeMin) / span) * 100}%`

  const isUpside = mean > (price ?? 0)
  const upsidePct = price ? (((mean - price) / price) * 100) : null

  return (
    <div className="col-span-4 sm:col-span-6 lg:col-span-8 mt-1">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.28)' }}>
          Analyst Price Targets{analysts ? ` · ${analysts} analysts` : ''}
        </span>
        <div className="flex items-center gap-2">
          <AnalystBadge rec={undefined} />
          {upsidePct !== null && (
            <span className="text-[11px] font-mono font-semibold"
              style={{ color: isUpside ? '#30D158' : '#FF453A' }}>
              {isUpside ? '▲' : '▼'} {Math.abs(upsidePct).toFixed(1)}% upside
            </span>
          )}
        </div>
      </div>

      {/* Range bar */}
      <div className="relative h-6">
        {/* Track */}
        <div className="absolute top-1/2 -translate-y-1/2 left-0 right-0 h-1 rounded-full"
          style={{ background: 'rgba(255,255,255,0.07)' }} />
        {/* Filled range: low → high */}
        <div className="absolute top-1/2 -translate-y-1/2 h-1 rounded-full"
          style={{
            left: pos(low), right: `${100 - parseFloat(pos(high))}%`,
            background: 'rgba(10,132,255,0.25)',
          }} />

        {/* Low marker */}
        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ left: pos(low) }}>
          <div className="w-1.5 h-3 rounded-sm" style={{ background: '#FF453A' }} />
        </div>
        {/* High marker */}
        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ left: pos(high) }}>
          <div className="w-1.5 h-3 rounded-sm" style={{ background: '#30D158' }} />
        </div>
        {/* Median marker */}
        {median && (
          <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
            style={{ left: pos(median) }}>
            <div className="w-0.5 h-4 rounded-full" style={{ background: 'rgba(255,159,10,0.8)' }} />
          </div>
        )}
        {/* Mean marker */}
        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
          style={{ left: pos(mean) }}>
          <div className="w-0.5 h-5 rounded-full" style={{ background: '#0A84FF' }} />
        </div>
        {/* Current price pin */}
        {price && (
          <div className="absolute top-0 bottom-0 -translate-x-1/2 flex items-center"
            style={{ left: pos(price) }}>
            <div className="w-2.5 h-2.5 rounded-full border-2"
              style={{ background: '#F5F5F7', borderColor: '#242426' }} />
          </div>
        )}
      </div>

      {/* Labels */}
      <div className="relative h-5 mt-0.5 text-[10px] font-mono" style={{ color: 'rgba(235,235,245,0.35)' }}>
        <span className="absolute -translate-x-1/2" style={{ left: pos(low), color: '#FF453A' }}>
          ${low.toFixed(0)}
        </span>
        {median && (
          <span className="absolute -translate-x-1/2" style={{ left: pos(median), color: '#FF9F0A' }}>
            ${median.toFixed(0)}
          </span>
        )}
        <span className="absolute -translate-x-1/2" style={{ left: pos(mean), color: '#0A84FF' }}>
          ${mean.toFixed(0)}
        </span>
        <span className="absolute -translate-x-1/2" style={{ left: pos(high), color: '#30D158' }}>
          ${high.toFixed(0)}
        </span>
        {price && (
          <span className="absolute -translate-x-1/2 font-semibold" style={{ left: pos(price), color: '#F5F5F7' }}>
            ${price.toFixed(0)}
          </span>
        )}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-1 text-[10px]" style={{ color: 'rgba(235,235,245,0.25)' }}>
        {[
          { color: '#FF453A', label: 'Low' },
          { color: '#FF9F0A', label: 'Median' },
          { color: '#0A84FF', label: 'Mean' },
          { color: '#30D158', label: 'High' },
          { color: '#F5F5F7', label: 'Current' },
        ].map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function StockOverview({ ticker, quote, moat }: Props) {
  const isUp = (quote.changesPercentage ?? 0) >= 0
  const changeColor = isUp ? '#30D158' : '#FF453A'

  return (
    <div className="rounded-xl mb-3" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.08)' }}>
      {/* Top row: name + price */}
      <div className="px-4 py-3 flex items-center gap-5 flex-wrap"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[15px] truncate" style={{ color: '#F5F5F7' }}>
            {quote.name}
          </p>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <p className="text-xs" style={{ color: 'rgba(235,235,245,0.35)' }}>
              <span className="font-mono">{ticker}</span>
              {quote.exchange ? ` · ${quote.exchange}` : ''}
              {quote.sector ? ` · ${quote.sector}` : ''}
              {quote.industry ? ` — ${quote.industry}` : ''}
            </p>
            {moat && moat.strength && (() => {
              const badge = MOAT_BADGE[moat.strength]
              return (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md"
                  style={{ background: badge.bg, color: badge.color }}>
                  {moat.strength} Moat{moat.primary_type ? ` · ${moat.primary_type}` : ''}
                </span>
              )
            })()}
          </div>
        </div>

        <div className="text-right">
          <p className="text-2xl font-bold tabular-nums" style={{ color: '#F5F5F7' }}>
            ${fmt(quote.price)}
          </p>
          <p className="text-xs font-mono mt-0.5" style={{ color: changeColor }}>
            {isUp ? '+' : ''}{fmt(quote.change)} ({isUp ? '+' : ''}{fmt(quote.changesPercentage)}%)
          </p>
        </div>
      </div>

      {/* Stats grid */}
      <div className="px-4 py-3 grid grid-cols-4 gap-x-4 gap-y-3 sm:grid-cols-6 lg:grid-cols-8">
        <Stat label="Market Cap"   value={fmtCap(quote.marketCap)} highlight />
        <Stat label="P/E (TTM)"    value={fmt(quote.pe, 1)} />
        <Stat label="Forward P/E"  value={fmt(quote.forwardPE, 1)} />
        <Stat label="PEG Ratio"    value={fmt(quote.pegRatio, 2)} />
        <Stat label="EV/EBITDA"    value={fmt(quote.evToEbitda, 1)} />
        <Stat label="FCF Yield"    value={pct(quote.fcfYield)} />
        <Stat label="ROE"          value={pct(quote.roe)} />
        <Stat label="Rev Growth"   value={pct(quote.revenueGrowth)} />

        {/* 52-week range bar — spans full row */}
        <WeekRangeBar
          price={quote.price}
          low={quote.fiftyTwoWeekLow}
          high={quote.fiftyTwoWeekHigh}
        />
      </div>

      {/* Analyst consensus row */}
      {(quote.recommendationKey || quote.targetLowPrice || quote.targetHighPrice) && (
        <div
          className="px-4 pt-2.5 pb-3"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
          {/* Rating + insider in one row */}
          <div className="flex items-center gap-6 mb-2">
            <div>
              <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'rgba(235,235,245,0.28)' }}>Consensus</p>
              <AnalystBadge rec={quote.recommendationKey} />
            </div>
            {quote.heldPercentInsiders != null && (
              <div>
                <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'rgba(235,235,245,0.28)' }}>Insider Own.</p>
                <p className="text-sm font-semibold font-mono" style={{ color: 'rgba(235,235,245,0.7)' }}>{pct(quote.heldPercentInsiders)}</p>
              </div>
            )}
          </div>

          {/* Target range bar */}
          <TargetRangeBar
            price={quote.price}
            low={quote.targetLowPrice}
            mean={quote.targetMeanPrice}
            median={quote.targetMedianPrice}
            high={quote.targetHighPrice}
            analysts={quote.numberOfAnalystOpinions}
          />
        </div>
      )}
    </div>
  )
}
