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

// ── Main ─────────────────────────────────────────────────────────────────────
export default function ValuationPanel() {
  const { valuation, quote } = useStock()
  const sym = getCurrencySymbol(quote?.currency)

  const defaultGrowth = valuation?.inputs.default_growth ?? 0.10
  const [growth,        setGrowth]        = useState(defaultGrowth)
  const [discount,      setDiscount]      = useState(0.10)
  const [terminal,      setTerminal]      = useState(0.03)
  const [requiredYield, setRequiredYield] = useState(0.07)

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
      <Card title="Graham Number" badge="√(22.5 × EPS × BVPS)">
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
      <Card title="DCF Calculator" badge="10-Year Discounted Cash Flow">
        {valuation.inputs.fcf && valuation.inputs.shares ? (
          <div className="space-y-4">
            <PriceBar price={price} iv={dcfLive} label="DCF Intrinsic Value vs Market Price" color="#5AC8F5" sym={sym} />
            <div className="rounded-lg p-3 space-y-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'rgba(235,235,245,0.25)' }}>Assumptions</p>
              <SliderRow label="FCF Growth Rate (yrs 1–10)" value={growth}   min={0}    max={0.40} step={0.005} format={pctFmt} onChange={setGrowth} />
              <SliderRow label="Discount Rate (WACC)"       value={discount} min={0.05} max={0.20} step={0.005} format={pctFmt} onChange={setDiscount} />
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
              10-year FCF projection discounted at WACC, plus Gordon Growth terminal value.
              Default growth rate derived from revenue growth (capped 3–25%). Adjust sliders for bull/bear scenarios.
            </p>
          </div>
        ) : (
          <NoData reason="DCF requires Free Cash Flow and Shares Outstanding data from yfinance." />
        )}
      </Card>

      {/* FCF Yield Valuation */}
      <Card title="FCF Yield Valuation" badge="FCF/Share ÷ Required Yield">
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
      <Card title="Earnings Power Value" badge="Greenwald No-Growth DCF">
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
