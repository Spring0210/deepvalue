import { useState, useMemo } from 'react'
import { useStock } from '../../context/StockContext'
import MoatCard from './MoatCard'
import { getCurrencySymbol } from '../../utils/currency'

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
function Card({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
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
      </div>
      <div className="p-4">{children}</div>
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

// ── Main ─────────────────────────────────────────────────────────────────────
export default function ValuationPanel() {
  const { valuation, quote } = useStock()
  const sym = getCurrencySymbol(quote?.currency)

  const defaultGrowth = valuation?.inputs.default_growth ?? 0.10
  const [growth,   setGrowth]   = useState(defaultGrowth)
  const [discount, setDiscount] = useState(0.10)
  const [terminal, setTerminal] = useState(0.03)

  const price  = valuation?.current_price ?? quote?.price ?? null
  const graham = valuation?.graham ?? null

  const dcfLive = useMemo(() =>
    calcDCF(valuation?.inputs.fcf ?? null, valuation?.inputs.shares ?? null, growth, discount, terminal),
    [valuation, growth, discount, terminal]
  )

  const mosDCF    = mos(price, dcfLive)
  const mosGraham = mos(price, graham)

  if (!valuation) {
    return (
      <div className="flex items-center justify-center h-40">
        <p className="text-sm" style={{ color: 'rgba(235,235,245,0.3)' }}>Search a stock to see valuation.</p>
      </div>
    )
  }

  const pctFmt = (v: number) => `${(v * 100).toFixed(1)}%`

  return (
    <div className="space-y-4">

      {/* Competitive Moat */}
      <MoatCard />

      {/* Margin of Safety summary */}
      <Card title="Margin of Safety">
        <div className="flex gap-8 justify-center py-2">
          <MoSGauge value={mosGraham} label="Graham Number" />
          <div className="w-px" style={{ background: 'rgba(255,255,255,0.07)' }} />
          <MoSGauge value={mosDCF} label="DCF (10-yr)" />
        </div>
        <p className="text-[11px] mt-3 text-center" style={{ color: 'rgba(235,235,245,0.2)' }}>
          Positive = price below intrinsic value. Buffett targets ≥ 25–30% margin of safety.
        </p>
      </Card>

      {/* Graham Number */}
      <Card title="Graham Number" badge="√(22.5 × EPS × BVPS)">
        {graham ? (
          <div className="space-y-3">
            <PriceBar price={price} iv={graham} label="Graham Number vs Market Price" color="#BF5AF2" sym={sym} />
            <div className="grid grid-cols-3 gap-3 mt-2">
              {[
                { label: 'Trailing EPS', value: valuation.inputs.eps != null ? `${sym}${valuation.inputs.eps.toFixed(2)}` : '—' },
                { label: 'Book Value/Share', value: valuation.inputs.bvps != null ? `${sym}${valuation.inputs.bvps.toFixed(2)}` : '—' },
                { label: 'Graham Number', value: `${sym}${graham.toFixed(2)}` },
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
            !valuation.inputs.eps ? ' EPS not available.' : ''
          }${!valuation.inputs.bvps ? ' Book value not available.' : ''}`} />
        )}
      </Card>

      {/* DCF Calculator */}
      <Card title="DCF Calculator" badge="10-Year Discounted Cash Flow">
        {valuation.inputs.fcf && valuation.inputs.shares ? (
          <div className="space-y-4">
            <PriceBar price={price} iv={dcfLive} label="DCF Intrinsic Value vs Market Price" color="#5AC8F5" sym={sym} />

            {/* Assumption sliders */}
            <div className="rounded-lg p-3 space-y-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.25)' }}>Assumptions</p>
              <SliderRow
                label="FCF Growth Rate (yrs 1–10)"
                value={growth} min={0} max={0.40} step={0.005}
                format={pctFmt} onChange={setGrowth}
              />
              <SliderRow
                label="Discount Rate (WACC)"
                value={discount} min={0.05} max={0.20} step={0.005}
                format={pctFmt} onChange={setDiscount}
              />
              <SliderRow
                label="Terminal Growth Rate"
                value={terminal} min={0.01} max={0.05} step={0.005}
                format={pctFmt} onChange={setTerminal}
              />
            </div>

            {/* DCF inputs summary */}
            <div className="grid grid-cols-3 gap-3">
              {[
                {
                  label: 'Free Cash Flow',
                  value: valuation.inputs.fcf != null
                    ? (Math.abs(valuation.inputs.fcf) >= 1e9
                        ? `${sym}${(valuation.inputs.fcf / 1e9).toFixed(1)}B`
                        : `${sym}${(valuation.inputs.fcf / 1e6).toFixed(0)}M`)
                    : '—'
                },
                { label: 'Shares Outstanding',
                  value: valuation.inputs.shares != null
                    ? (valuation.inputs.shares >= 1e9
                        ? `${(valuation.inputs.shares / 1e9).toFixed(2)}B`
                        : `${(valuation.inputs.shares / 1e6).toFixed(0)}M`)
                    : '—'
                },
                { label: 'DCF Value/Share', value: dcfLive != null ? `${sym}${dcfLive.toFixed(2)}` : '—' },
              ].map(s => (
                <div key={s.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(235,235,245,0.28)' }}>{s.label}</p>
                  <p className="text-sm font-semibold font-mono" style={{ color: 'rgba(235,235,245,0.75)' }}>{s.value}</p>
                </div>
              ))}
            </div>

            <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(235,235,245,0.25)' }}>
              10-year FCF projection discounted at WACC, plus Gordon Growth terminal value.
              Default growth rate derived from revenue growth (capped 3–25%). Adjust sliders for bull/bear scenarios.
            </p>
          </div>
        ) : (
          <NoData reason="DCF requires Free Cash Flow and Shares Outstanding data from yfinance." />
        )}
      </Card>

    </div>
  )
}
