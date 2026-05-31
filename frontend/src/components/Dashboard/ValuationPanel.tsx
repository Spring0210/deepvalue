import { useState, useMemo } from 'react'
import { useStock } from '../../context/StockContext'
import MoatCard from './MoatCard'
import { getCurrencySymbol } from '../../utils/currency'

// Lynch's six categories, each with a distinct accent colour.
const LYNCH_COLORS: Record<string, string> = {
  'Fast Grower':  '#30D158',
  'Stalwart':     '#5AC8F5',
  'Slow Grower':  '#8E8E93',
  'Cyclical':     '#FF9F0A',
  'Turnaround':   '#FF453A',
  'Asset Play':   '#BF5AF2',
}

// Muted tints + saturated text (Apple/Stripe), never solid fills.
const VERDICT_TONE: Record<string, { fg: string; bg: string }> = {
  pass:    { fg: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  watch:   { fg: '#FBBF24', bg: 'rgba(251,191,36,0.12)' },
  fail:    { fg: '#F87171', bg: 'rgba(248,113,113,0.12)' },
  neutral: { fg: '#9CA3AF', bg: 'rgba(156,163,175,0.10)' },
}


// ── DCF math (mirrors backend, runs on frontend for live slider updates) ────
function calcDCF(
  fcf: number | null,
  shares: number | null,
  growth: number,
  discount: number,
  terminal: number,
): number | null {
  if (!fcf || !shares || fcf <= 0 || shares <= 0 || discount <= terminal) return null
  let pv = 0
  let fcfT = fcf
  for (let t = 1; t <= 10; t++) {
    fcfT *= (1 + growth)
    pv += fcfT / (1 + discount) ** t
  }
  const tv = (fcfT * (1 + terminal)) / (discount - terminal)
  pv += tv / (1 + discount) ** 10
  return pv / shares
}

function mos(price: number | null, iv: number | null): number | null {
  if (!price || !iv || iv <= 0) return null
  return ((iv - price) / iv) * 100
}

// ── Margin of Safety gauge ───────────────────────────────────────────────────
function MoSGauge({ value, label }: { value: number | null; label: string }) {
  if (value === null) return (
    <div className="flex flex-col items-center gap-1">
      <div className="text-lg font-bold font-mono" style={{ color: 'rgba(235,235,245,0.3)' }}>N/A</div>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.25)' }}>{label}</div>
    </div>
  )
  const color = value >= 30 ? '#30D158' : value >= 0 ? '#FF9F0A' : '#FF453A'
  const label2 = value >= 30 ? 'Undervalued' : value >= 0 ? 'Fairly Valued' : 'Overvalued'
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>
        {value >= 0 ? '+' : ''}{value.toFixed(1)}%
      </div>
      <div className="text-[11px] font-medium" style={{ color }}>{label2}</div>
      <div className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: 'rgba(235,235,245,0.25)' }}>{label}</div>
    </div>
  )
}

// ── Price vs Value bar ───────────────────────────────────────────────────────
function PriceBar({ price, iv, label, color, sym }: {
  price: number | null; iv: number | null; label: string; color: string; sym: string
}) {
  if (!price || !iv) return null
  const max = Math.max(price, iv) * 1.15
  const pricePct = (price / max) * 100
  const ivPct    = (iv / max) * 100
  const isUnder  = iv > price

  return (
    <div>
      <div className="flex justify-between text-[10px] mb-1.5" style={{ color: 'rgba(235,235,245,0.35)' }}>
        <span className="uppercase tracking-wider">{label}</span>
        <span className="font-mono" style={{ color }}>
          {sym}{iv.toFixed(2)} intrinsic · {sym}{price.toFixed(2)} price
        </span>
      </div>
      <div className="relative h-5 rounded-lg overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
        {/* IV bar */}
        <div className="absolute h-full rounded-lg opacity-25 transition-all duration-500"
          style={{ width: `${ivPct}%`, background: color }} />
        {/* Price marker */}
        <div className="absolute top-0 bottom-0 w-0.5 transition-all duration-500"
          style={{ left: `${pricePct}%`, background: 'rgba(235,235,245,0.5)' }} />
        <div className="absolute inset-0 flex items-center px-2 gap-3">
          <span className="text-[10px] font-mono z-10" style={{ color }}>
            IV {sym}{iv.toFixed(0)}
          </span>
          <span className="text-[10px] font-mono z-10" style={{ color: 'rgba(235,235,245,0.5)' }}>
            Price {sym}{price.toFixed(0)}
          </span>
          <span className="text-[10px] font-semibold ml-auto z-10"
            style={{ color: isUnder ? '#30D158' : '#FF453A' }}>
            {isUnder ? '▼ Underpriced' : '▲ Overpriced'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Slider row ───────────────────────────────────────────────────────────────
function SliderRow({ label, value, min, max, step, format, onChange }: {
  label: string; value: number; min: number; max: number; step: number
  format: (v: number) => string; onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.5)' }}>{label}</span>
        <span className="text-[11px] font-mono font-semibold" style={{ color: '#0A84FF' }}>{format(value)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full h-1 rounded-full appearance-none cursor-pointer"
        style={{ accentColor: '#0A84FF', background: `linear-gradient(90deg, #0A84FF ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.1) 0%)` }}
      />
    </div>
  )
}

// ── Valuation card wrapper ───────────────────────────────────────────────────
const LENS_META: Record<string, { label: string; fg: string; bg: string }> = {
  primary:        { label: 'Primary lens', fg: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  secondary:      { label: 'Context',      fg: '#9CA3AF', bg: 'rgba(156,163,175,0.10)' },
  not_applicable: { label: 'Not suited',   fg: '#FBBF24', bg: 'rgba(251,191,36,0.12)' },
}

function Card({ title, badge, lens, children }: {
  title: string
  badge?: string
  lens?: { tier: string; reason: string }
  children: React.ReactNode
}) {
  const lm    = lens ? LENS_META[lens.tier] : null
  const muted = lens?.tier === 'not_applicable'
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="px-4 py-2.5 flex items-center gap-2 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.35)' }}>
          {title}
        </span>
        {badge && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-md" style={{ background: 'rgba(10,132,255,0.15)', color: '#0A84FF' }}>
            {badge}
          </span>
        )}
        {lm && (
          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-md" style={{ background: lm.bg, color: lm.fg }}>
            {lm.label}
          </span>
        )}
      </div>
      <div className="p-4">
        {muted && lens && (
          <p className="text-[11px] mb-3 leading-relaxed" style={{ color: '#FBBF24' }}>⚠ Not suited here — {lens.reason}</p>
        )}
        <div style={muted ? { opacity: 0.4 } : undefined}>{children}</div>
      </div>
    </div>
  )
}

// ── No-data placeholder ──────────────────────────────────────────────────────
function NoData({ reason }: { reason: string }) {
  return (
    <div className="text-center py-4">
      <p className="text-xs" style={{ color: 'rgba(235,235,245,0.25)' }}>{reason}</p>
    </div>
  )
}

// ── FCF Yield math (mirrors backend) ────────────────────────────────────────
function calcFCFYield(
  fcf: number | null,
  shares: number | null,
  requiredYield: number,
): number | null {
  if (!fcf || !shares || fcf <= 0 || shares <= 0 || requiredYield <= 0) return null
  return (fcf / shares) / requiredYield
}

// ── Stat cell ────────────────────────────────────────────────────────────────
function StatCell({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
      <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>{label}</p>
      <p className="text-sm font-semibold font-mono" style={{ color: 'rgba(235,235,245,0.75)' }}>{value}</p>
      {sub && <p className="text-[10px] mt-0.5" style={{ color: 'rgba(235,235,245,0.3)' }}>{sub}</p>}
    </div>
  )
}

// ── Verdict hero — price positioned in a growth-aware fair-value range ────────
function VerdictHero({ v, decomp, sym, required, onRequired }: {
  v: NonNullable<ReturnType<typeof useStock>['valuation']>['verdict']
  decomp: NonNullable<ReturnType<typeof useStock>['valuation']>['price_decomposition']
  sym: string
  required: number
  onRequired: (n: number) => void
}) {
  if (!v || v.fair_base === null || v.price === null || v.fair_low === null || v.fair_high === null) return null
  const t = VERDICT_TONE[v.tone]
  const { fair_low: lo, fair_base: base, fair_high: hi, price } = v
  const buyAt = base * (1 - required)            // price for the required discount to base

  // Scale: pad the [low..high, price, buy] span so every marker is visible.
  const loEnd = Math.min(lo, price, buyAt)
  const hiEnd = Math.max(hi, price)
  const span  = (hiEnd - loEnd) || 1
  const pad   = span * 0.08
  const min   = loEnd - pad, max = hiEnd + pad
  const pct   = (x: number) => `${((x - min) / (max - min)) * 100}%`

  return (
    <div className="rounded-2xl p-5" style={{ background: '#1C1C1E', border: '1px solid rgba(255,255,255,0.07)' }}>
      <p className="text-[10px] uppercase tracking-wider mb-3" style={{ color: 'rgba(235,235,245,0.35)' }}>
        Valuation · fair-value range
      </p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-4">
        <span className="text-base font-semibold px-2.5 py-1 rounded-lg" style={{ background: t.bg, color: t.fg }}>
          {v.signal}
        </span>
        <span className="text-[12px] flex-1 min-w-[12rem]" style={{ color: 'rgba(235,235,245,0.5)' }}>{v.rationale}</span>
        <span className="text-[11px] px-2 py-0.5 rounded-md" style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(235,235,245,0.55)' }}>
          Confidence: {v.confidence}
        </span>
      </div>

      {/* Range bar: fair-value band, current price, and the buy threshold */}
      <div className="relative mt-7 mb-6 h-2 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
        {/* fair-value band low→high */}
        <div className="absolute h-full rounded-full" style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})`, background: 'rgba(90,200,245,0.22)' }} />
        {/* buy threshold (dashed marker) */}
        <div className="absolute -top-1.5 -bottom-1.5 w-px" style={{ left: pct(buyAt), background: 'rgba(52,211,153,0.5)' }} />
        {/* current price marker */}
        <div className="absolute -top-2 -bottom-2 w-0.5 rounded" style={{ left: pct(price), background: t.fg }} />
        {/* labels */}
        <span className="absolute -top-6 -translate-x-1/2 text-[10px] font-mono tabular-nums" style={{ left: pct(price), color: t.fg }}>
          {sym}{price.toFixed(0)}
        </span>
        <span className="absolute top-4 -translate-x-1/2 text-[10px] font-mono tabular-nums" style={{ left: pct(lo), color: 'rgba(235,235,245,0.4)' }}>
          {sym}{lo.toFixed(0)}
        </span>
        <span className="absolute top-4 -translate-x-1/2 text-[10px] font-mono tabular-nums" style={{ left: pct(hi), color: 'rgba(235,235,245,0.4)' }}>
          {sym}{hi.toFixed(0)}
        </span>
      </div>
      <div className="flex justify-between text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.28)' }}>
        <span>Conservative</span><span>Fair value {sym}{base.toFixed(0)}</span><span>Optimistic</span>
      </div>

      {/* Implied-growth honesty line */}
      {v.implied_growth !== null && (
        <p className="mt-4 text-[12px]" style={{ color: 'rgba(235,235,245,0.55)' }}>
          Price implies ~<span className="font-mono">{(v.implied_growth * 100).toFixed(0)}%</span>/yr cash-flow growth
          {v.reference_growth !== null && <> vs ~<span className="font-mono">{(v.reference_growth * 100).toFixed(0)}%</span> recently delivered</>}.
        </p>
      )}
      {v.floor !== null && (
        <p className="mt-1 text-[12px]" style={{ color: 'rgba(235,235,245,0.4)' }}>
          No-growth floor (EPV): <span className="font-mono">{sym}{v.floor.toFixed(0)}</span>.
        </p>
      )}

      {/* What you're paying for — the value↔growth bridge */}
      {decomp && (
        <div className="mt-4">
          <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'rgba(235,235,245,0.3)' }}>
            What you're paying for
          </p>
          <div className="flex h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <div style={{ width: `${decomp.epv_share * 100}%`, background: 'rgba(90,200,245,0.55)' }} />
            <div style={{ width: `${decomp.growth_share * 100}%`, background: 'rgba(251,191,36,0.6)' }} />
          </div>
          <p className="mt-1.5 text-[12px]" style={{ color: 'rgba(235,235,245,0.55)' }}>
            {decomp.below_no_growth_value
              ? <>Price is below the no-growth value (EPV <span className="font-mono">{sym}{decomp.epv.toFixed(0)}</span>) — cheap even with zero growth.</>
              : <><span style={{ color: '#5AC8F5' }}>{(decomp.epv_share * 100).toFixed(0)}%</span> business as-is (EPV) · <span style={{ color: '#FBBF24' }}>{(decomp.growth_share * 100).toFixed(0)}%</span> growth premium</>}
          </p>
        </div>
      )}

      {/* Required margin-of-safety control → live buy threshold */}
      <div className="mt-4">
        <div className="flex justify-between mb-1">
          <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.5)' }}>
            Required margin of safety — buy below <span className="font-mono" style={{ color: '#34D399' }}>{sym}{buyAt.toFixed(0)}</span>
          </span>
          <span className="text-[11px] font-mono font-semibold" style={{ color: '#0A84FF' }}>{(required * 100).toFixed(0)}%</span>
        </div>
        <input
          type="range" min={0} max={0.6} step={0.05} value={required}
          onChange={e => onRequired(parseFloat(e.target.value))}
          className="w-full h-1 rounded-full appearance-none cursor-pointer"
          style={{ accentColor: '#0A84FF', background: `linear-gradient(90deg, #0A84FF ${(required / 0.6) * 100}%, rgba(255,255,255,0.1) 0%)` }}
        />
      </div>

      {v.caveats.length > 0 && (
        <ul className="mt-3 space-y-1">
          {v.caveats.map((c, i) => (
            <li key={i} className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.5)' }}>⚠ {c}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function ValuationPanel() {
  const { valuation, quote } = useStock()
  const sym = getCurrencySymbol(quote?.currency)

  const defaultGrowth   = valuation?.inputs.default_growth ?? 0.10
  const capmDiscount    = valuation?.inputs.discount_rate ?? 0.10
  const [growth,        setGrowth]        = useState(defaultGrowth)
  const [discount,      setDiscount]      = useState(capmDiscount)
  const [terminal,      setTerminal]      = useState(0.03)
  const [requiredYield, setRequiredYield] = useState(0.07)
  const [requiredMos,   setRequiredMos]   = useState(valuation?.verdict?.required_mos ?? 0.30)

  const price  = valuation?.current_price ?? quote?.price ?? null
  const graham = valuation?.graham ?? null

  const dcfLive = useMemo(() =>
    calcDCF(valuation?.inputs.fcf ?? null, valuation?.inputs.shares ?? null, growth, discount, terminal),
    [valuation, growth, discount, terminal]
  )

  const fcfYieldLive = useMemo(() =>
    calcFCFYield(valuation?.inputs.fcf ?? null, valuation?.inputs.shares ?? null, requiredYield),
    [valuation, requiredYield]
  )

  const mosDCF      = mos(price, dcfLive)
  const mosGraham   = mos(price, graham)
  const mosFCFYield = mos(price, fcfYieldLive)
  const mosEPV      = mos(price, valuation?.epv ?? null)

  if (!valuation) {
    return (
      <div className="flex items-center justify-center h-40">
        <p className="text-sm" style={{ color: 'rgba(235,235,245,0.3)' }}>Search a stock to see valuation.</p>
      </div>
    )
  }

  const pctFmt = (v: number) => `${(v * 100).toFixed(1)}%`
  const coc = valuation.circle_of_competence

  return (
    <div className="space-y-4">

      {/* Verdict — the single actionable answer */}
      <VerdictHero v={valuation.verdict} decomp={valuation.price_decomposition} sym={sym} required={requiredMos} onRequired={setRequiredMos} />

      {/* Circle of Competence warning */}
      {coc && !coc.within && (
        <div className="rounded-xl px-4 py-3 flex gap-3" style={{ background: 'rgba(255,159,10,0.1)', border: '1px solid rgba(255,159,10,0.25)' }}>
          <div className="mt-0.5 text-[13px]" style={{ color: '#FF9F0A' }}>⚠</div>
          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: '#FF9F0A' }}>
              Circle of Competence — {coc.complexity} Complexity
            </p>
            <ul className="space-y-0.5">
              {coc.flags.map((f, i) => (
                <li key={i} className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.5)' }}>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Competitive Moat */}
      <MoatCard />

      {/* Lynch category */}
      {valuation.lynch && (
        <Card title="Lynch Category">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-semibold px-2 py-0.5 rounded-md"
              style={{ background: `${LYNCH_COLORS[valuation.lynch.category] ?? '#5AC8F5'}22`, color: LYNCH_COLORS[valuation.lynch.category] ?? '#5AC8F5' }}>
              {valuation.lynch.category}
            </span>
            <span className="text-[11px]" style={{ color: 'rgba(235,235,245,0.5)' }}>{valuation.lynch.rationale}</span>
          </div>
          <p className="text-[11px] leading-relaxed mb-1" style={{ color: 'rgba(235,235,245,0.5)' }}>
            <span style={{ color: 'rgba(235,235,245,0.35)' }}>Yardstick: </span>{valuation.lynch.yardstick}
          </p>
          <p className="text-[11px] leading-relaxed font-medium" style={{ color: 'rgba(235,235,245,0.7)' }}>
            {valuation.lynch.verdict}
          </p>
        </Card>
      )}

      {/* Through-cycle earnings — only for cyclicals (P/E-trap defense) */}
      {valuation.through_cycle && (
        <Card title="Through-cycle earnings" badge="Mid-cycle" lens={valuation.lenses?.epv}>
          <div className="grid grid-cols-2 gap-3">
            <StatCell label="EPS — trailing"    value={valuation.through_cycle.ttm_eps != null ? `${sym}${valuation.through_cycle.ttm_eps.toFixed(2)}` : '—'} />
            <StatCell label="EPS — mid-cycle"    value={`${sym}${valuation.through_cycle.normalized_eps.toFixed(2)}`} sub="8-yr average" />
            <StatCell label="P/E on trailing"    value={valuation.through_cycle.ttm_pe != null ? `${valuation.through_cycle.ttm_pe.toFixed(1)}x` : '—'} />
            <StatCell label="P/E on mid-cycle"   value={valuation.through_cycle.normalized_pe != null ? `${valuation.through_cycle.normalized_pe.toFixed(1)}x` : '—'} />
          </div>
          {valuation.through_cycle.peak_earnings_trap && (
            <p className="text-[11px] leading-relaxed mt-3" style={{ color: '#FBBF24' }}>
              ⚠ Peak-earnings trap: cheap on trailing earnings but expensive on mid-cycle — typical near a cyclical top. A low P/E here is a danger, not a bargain.
            </p>
          )}
          <p className="text-[11px] leading-relaxed mt-2" style={{ color: 'rgba(235,235,245,0.25)' }}>
            Cyclicals should be judged on normalized mid-cycle earnings, not the latest year.
          </p>
        </Card>
      )}

      {/* PEG / PEGY — growth multiple (Lynch) */}
      {valuation.peg && (
        <Card title="PEG / growth" badge="Lynch">
          <div className="grid grid-cols-2 gap-3">
            <StatCell label="PEG" value={valuation.peg.peg.toFixed(2)} sub={valuation.peg.label} />
            <StatCell label="PEGY (incl. yield)" value={valuation.peg.pegy != null ? valuation.peg.pegy.toFixed(2) : '—'} />
          </div>
          <p className="text-[11px] leading-relaxed mt-3" style={{ color: 'rgba(235,235,245,0.25)' }}>
            Lynch's growth yardstick: pay no more than the growth rate (PEG ≈ 1). PEGY adds the dividend yield to growth.
          </p>
        </Card>
      )}

      {/* ROIC + P/FCF row */}
      {(valuation.roic != null || valuation.price_to_fcf != null) && (
        <Card title="Capital Efficiency">
          <div className="grid grid-cols-2 gap-3">
            <StatCell
              label="ROIC"
              value={valuation.roic != null ? `${(valuation.roic * 100).toFixed(1)}%` : '—'}
              sub={valuation.roic != null
                ? (valuation.roic >= 0.15 ? 'Excellent (≥ 15%)' : valuation.roic >= 0.10 ? 'Good (≥ 10%)' : 'Below average')
                : undefined}
            />
            <StatCell
              label="Price / FCF"
              value={valuation.price_to_fcf != null ? `${valuation.price_to_fcf.toFixed(1)}x` : '—'}
              sub={valuation.price_to_fcf != null
                ? (valuation.price_to_fcf < 15 ? 'Cheap (< 15×)' : valuation.price_to_fcf < 25 ? 'Fair (15–25×)' : 'Expensive (> 25×)')
                : undefined}
            />
          </div>
          <p className="text-[11px] mt-3" style={{ color: 'rgba(235,235,245,0.2)' }}>
            ROIC = NOPAT / Invested Capital. Buffett's preferred measure of capital allocation quality.
            P/FCF compares market price to free cash flow yield.
          </p>
        </Card>
      )}

      {/* Margin of Safety summary — 2×2 grid */}
      <Card title="Margin of Safety">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 py-2">
          <MoSGauge value={mosGraham}   label="Graham Number" />
          <MoSGauge value={mosDCF}      label="DCF (10-yr)" />
          <MoSGauge value={mosFCFYield} label="FCF Yield Value" />
          <MoSGauge value={mosEPV}      label="EPV (no growth)" />
        </div>
        <p className="text-[11px] mt-3 text-center" style={{ color: 'rgba(235,235,245,0.2)' }}>
          Positive = price below intrinsic value. Buffett targets ≥ 25–30% margin of safety.
        </p>
      </Card>

      {/* Graham Number */}
      <Card title="Graham Number" badge="√(22.5 × EPS × BVPS)" lens={valuation.lenses?.graham}>
        {graham ? (
          <div className="space-y-3">
            <PriceBar price={price} iv={graham} label="Graham Number vs Market Price" color="#BF5AF2" sym={sym} />
            <div className="grid grid-cols-3 gap-3 mt-2">
              {[
                { label: 'Trailing EPS',   value: valuation.inputs.eps  != null ? `${sym}${valuation.inputs.eps.toFixed(2)}`  : '—' },
                { label: 'Book Value/Share', value: valuation.inputs.bvps != null ? `${sym}${valuation.inputs.bvps.toFixed(2)}` : '—' },
                { label: 'Graham Number',  value: `${sym}${graham.toFixed(2)}` },
              ].map(s => (
                <div key={s.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>{s.label}</p>
                  <p className="text-sm font-semibold font-mono" style={{ color: 'rgba(235,235,245,0.75)' }}>{s.value}</p>
                </div>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              Ben Graham's formula for the maximum price to pay for a quality stock.
              Requires positive EPS and book value — does not apply to high-growth or negative-EPS companies.
            </p>
          </div>
        ) : (
          <NoData reason={`Graham Number requires positive EPS and Book Value per Share.${
            !valuation.inputs.eps  ? ' EPS not available.'        : ''
          }${!valuation.inputs.bvps ? ' Book value not available.' : ''}`} />
        )}
      </Card>

      {/* DCF Calculator */}
      <Card title="DCF Calculator" badge="10-Year Discounted Cash Flow" lens={valuation.lenses?.dcf_fcf}>
        {valuation.inputs.fcf && valuation.inputs.shares ? (
          <div className="space-y-4">
            <PriceBar price={price} iv={dcfLive} label="DCF Intrinsic Value vs Market Price" color="#5AC8F5" sym={sym} />

            {/* Bear / Base / Bull range from the backend (CAPM discount) */}
            {valuation.dcf_base != null && (
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Bear', value: valuation.dcf_bear, color: '#FF453A' },
                  { label: 'Base', value: valuation.dcf_base, color: '#5AC8F5' },
                  { label: 'Bull', value: valuation.dcf_bull, color: '#30D158' },
                ].map(s => (
                  <div key={s.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
                    <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>{s.label}</p>
                    <p className="text-sm font-semibold font-mono" style={{ color: s.color }}>
                      {s.value != null ? `${sym}${s.value.toFixed(2)}` : '—'}
                    </p>
                  </div>
                ))}
              </div>
            )}

            <div className="rounded-lg p-3 space-y-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.25)' }}>Assumptions</p>
              <SliderRow label="FCF Growth Rate (yrs 1–10)" value={growth}   min={0}    max={0.40} step={0.005} format={pctFmt} onChange={setGrowth} />
              <SliderRow
                label={`Discount Rate (CAPM${valuation.inputs.beta != null ? `, β ${valuation.inputs.beta.toFixed(2)}` : ''})`}
                value={discount} min={0.05} max={0.20} step={0.005} format={pctFmt} onChange={setDiscount}
              />
              <SliderRow label="Terminal Growth Rate"        value={terminal} min={0.01} max={0.05} step={0.005} format={pctFmt} onChange={setTerminal} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Free Cash Flow', value: valuation.inputs.fcf != null
                    ? (Math.abs(valuation.inputs.fcf) >= 1e9 ? `${sym}${(valuation.inputs.fcf / 1e9).toFixed(1)}B` : `${sym}${(valuation.inputs.fcf / 1e6).toFixed(0)}M`)
                    : '—' },
                { label: 'Shares Outstanding', value: valuation.inputs.shares != null
                    ? (valuation.inputs.shares >= 1e9 ? `${(valuation.inputs.shares / 1e9).toFixed(2)}B` : `${(valuation.inputs.shares / 1e6).toFixed(0)}M`)
                    : '—' },
                { label: 'DCF Value/Share', value: dcfLive != null ? `${sym}${dcfLive.toFixed(2)}` : '—' },
              ].map(s => (
                <div key={s.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>{s.label}</p>
                  <p className="text-sm font-semibold font-mono" style={{ color: 'rgba(235,235,245,0.75)' }}>{s.value}</p>
                </div>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              10-year FCF projection discounted at the cost of equity, plus Gordon Growth terminal value.
              Discount rate defaults to CAPM (risk-free + β × equity premium); growth derived from revenue
              growth (capped 3–25%). Bear/Base/Bull above flex growth ±4% and discount ±2%.
            </p>
          </div>
        ) : (
          <NoData reason="DCF requires Free Cash Flow and Shares Outstanding data from yfinance." />
        )}
      </Card>

      {/* FCF Yield Valuation */}
      <Card title="FCF Yield Valuation" badge="FCF/Share ÷ Required Yield" lens={valuation.lenses?.fcf_yield}>
        {valuation.inputs.fcf && valuation.inputs.shares ? (
          <div className="space-y-4">
            <PriceBar price={price} iv={fcfYieldLive} label="FCF Yield Fair Value vs Market Price" color="#30D158" sym={sym} />
            <div className="rounded-lg p-3 space-y-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.25)' }}>Required FCF Yield</p>
              <SliderRow
                label="Required Yield (risk-free + equity premium)"
                value={requiredYield} min={0.04} max={0.15} step={0.005}
                format={pctFmt} onChange={setRequiredYield}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatCell label="FCF / Share"    value={valuation.inputs.fcf && valuation.inputs.shares
                ? `${sym}${(valuation.inputs.fcf / valuation.inputs.shares).toFixed(2)}` : '—'} />
              <StatCell label="Fair Value"      value={fcfYieldLive != null ? `${sym}${fcfYieldLive.toFixed(2)}` : '—'} />
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              Treats the stock like a bond: Fair Value = FCF per share ÷ required yield.
              Default 7% = ~4.5% risk-free rate + 2.5% equity premium.
              Lower yield assumption → higher implied fair value.
            </p>
          </div>
        ) : (
          <NoData reason="FCF Yield Valuation requires Free Cash Flow and Shares Outstanding." />
        )}
      </Card>

      {/* EPV */}
      <Card title="Earnings Power Value" badge="Greenwald No-Growth DCF" lens={valuation.lenses?.epv}>
        {valuation.epv != null ? (
          <div className="space-y-3">
            <PriceBar price={price} iv={valuation.epv} label="EPV vs Market Price" color="#FF9F0A" sym={sym} />
            <div className="grid grid-cols-2 gap-3">
              <StatCell label="EPV / Share"     value={`${sym}${valuation.epv.toFixed(2)}`} />
              <StatCell label="Margin of Safety" value={mosEPV != null ? `${mosEPV >= 0 ? '+' : ''}${mosEPV.toFixed(1)}%` : '—'} />
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              Bruce Greenwald's no-growth valuation: EPV = NOPAT ÷ WACC.
              Assumes zero future growth — represents the floor value of the business's current earnings power.
              Any price above EPV requires you to pay for growth expectations.
            </p>
          </div>
        ) : (
          <NoData reason="EPV requires Operating Income data from financial statements." />
        )}
      </Card>

    </div>
  )
}
