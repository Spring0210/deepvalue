import { useStock } from '../../context/StockContext'
import type { BuffettRatio } from '../../types'
import { getCurrencySymbol } from '../../utils/currency'

// ── Score Ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score, pass, total }: { score: number; pass: number; total: number }) {
  const R = 36
  const C = 2 * Math.PI * R
  const filled = (score / 100) * C
  const color = score >= 70 ? '#30D158' : score >= 40 ? '#FF9F0A' : '#FF453A'

  return (
    <div className="relative w-20 h-20 flex-shrink-0">
      <svg viewBox="0 0 84 84" className="w-full h-full -rotate-90">
        <circle cx="42" cy="42" r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="6" />
        <circle cx="42" cy="42" r={R} fill="none" stroke={color} strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${C}`}
          style={{ transition: 'stroke-dasharray 0.7s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold leading-none" style={{ color }}>{score.toFixed(0)}</span>
        <span className="text-[10px]" style={{ color: 'rgba(235,235,245,0.3)' }}>{pass}/{total}</span>
      </div>
    </div>
  )
}

// ── Status Badge ──────────────────────────────────────────────────────────────
function Badge({ passes }: { passes: boolean | null }) {
  if (passes === null)
    return (
      <span className="text-[11px] px-2 py-0.5 rounded font-medium"
        style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(235,235,245,0.3)' }}>
        N/A
      </span>
    )
  return passes ? (
    <span className="text-[11px] px-2 py-0.5 rounded font-semibold"
      style={{ background: 'rgba(48,209,88,0.12)', color: '#30D158' }}>
      PASS
    </span>
  ) : (
    <span className="text-[11px] px-2 py-0.5 rounded font-semibold"
      style={{ background: 'rgba(255,69,58,0.12)', color: '#FF453A' }}>
      FAIL
    </span>
  )
}

// ── Value formatter ───────────────────────────────────────────────────────────
function fmt(value: number | null, name: string, sym: string): string {
  if (value === null) return '—'
  if (name === 'Treasury Stock' || name === 'Preferred Stock') {
    const abs = Math.abs(value)
    if (abs >= 1e9) return `${sym}${(value / 1e9).toFixed(1)}B`
    if (abs >= 1e6) return `${sym}${(value / 1e6).toFixed(0)}M`
    return `${sym}${value.toFixed(0)}`
  }
  if (Math.abs(value) >= 5) return `${value.toFixed(2)}x`
  return `${(value * 100).toFixed(1)}%`
}

// ── Category config ───────────────────────────────────────────────────────────
const CATEGORY_META: Record<string, { color: string; label: string }> = {
  'Income Statement': { color: '#5AC8F5', label: 'Income Statement' },
  'Balance Sheet':    { color: '#BF5AF2', label: 'Balance Sheet' },
  'Cash Flow':        { color: '#FF9F0A', label: 'Cash Flow' },
}

// ── Ratio Card ────────────────────────────────────────────────────────────────
function RatioCard({ ratio }: { ratio: BuffettRatio }) {
  const { quote } = useStock()
  const sym = getCurrencySymbol(quote?.currency)
  const passColor  = ratio.passes === true ? '#30D158' : ratio.passes === false ? '#FF453A' : 'rgba(235,235,245,0.2)'

  return (
    <div
      className="rounded-xl mb-2.5 overflow-hidden"
      style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}
    >
      {/* Top row */}
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-0.5 h-5 rounded-full flex-shrink-0" style={{ background: passColor }} />
          <span className="text-[14px] font-medium" style={{ color: '#F5F5F7' }}>{ratio.name}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[13px] font-semibold" style={{ color: passColor }}>
            {fmt(ratio.value, ratio.name, sym)}
          </span>
          <Badge passes={ratio.passes} />
        </div>
      </div>

      {/* Detail rows */}
      <div className="px-4 py-3 grid gap-1.5">
        <DetailRow label="Equation" value={ratio.equation} mono />
        <DetailRow label="Rule" value={ratio.threshold} color={passColor} mono />
        <DetailRow label="About" value={ratio.description} />
        <div className="flex items-start gap-3 pt-2 mt-1" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <span className="text-[11px] flex-shrink-0 pt-0.5 font-medium"
            style={{ color: 'rgba(235,235,245,0.25)', minWidth: '56px' }}>
            Buffett
          </span>
          <span className="text-[12px] italic" style={{ color: 'rgba(235,235,245,0.45)', lineHeight: '1.5' }}>
            "{ratio.buffett_logic}"
          </span>
        </div>
      </div>
    </div>
  )
}

function DetailRow({
  label, value, mono, color,
}: { label: string; value: string; mono?: boolean; color?: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-[11px] flex-shrink-0 pt-0.5 font-medium"
        style={{ color: 'rgba(235,235,245,0.25)', minWidth: '56px' }}>
        {label}
      </span>
      <span
        className={`text-[12px] ${mono ? 'font-mono' : ''}`}
        style={{ color: color ?? 'rgba(235,235,245,0.55)', lineHeight: '1.5' }}
      >
        {value}
      </span>
    </div>
  )
}

// ── Category Section ──────────────────────────────────────────────────────────
function CategorySection({ category, ratios }: { category: string; ratios: BuffettRatio[] }) {
  const meta  = CATEGORY_META[category] ?? { color: 'rgba(235,235,245,0.3)', label: category }
  const pass  = ratios.filter(r => r.passes === true).length
  const total = ratios.length

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-sm" style={{ background: meta.color }} />
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: meta.color }}>
            {meta.label}
          </span>
        </div>
        <span className="text-[11px] font-mono" style={{ color: 'rgba(235,235,245,0.3)' }}>
          {pass}/{total} passed
        </span>
      </div>
      {ratios.map(r => <RatioCard key={r.name} ratio={r} />)}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
const CATEGORY_ORDER = ['Income Statement', 'Balance Sheet', 'Cash Flow']

export default function RatioTable({ ratios }: { ratios: BuffettRatio[] }) {
  const { weightedScore } = useStock()
  const pass  = ratios.filter(r => r.passes === true).length
  const fail  = ratios.filter(r => r.passes === false).length
  const na    = ratios.length - pass - fail
  const total = ratios.length
  const pct   = weightedScore

  const byCategory = CATEGORY_ORDER.reduce<Record<string, BuffettRatio[]>>((acc, cat) => {
    acc[cat] = ratios.filter(r => r.category === cat)
    return acc
  }, {})

  return (
    <div>
      {/* Score summary */}
      <div className="flex items-center gap-5 mb-5 p-4 rounded-xl"
        style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
        <ScoreRing score={weightedScore} pass={pass} total={total} />
        <div className="flex-1">
          <p className="text-sm font-semibold mb-0.5" style={{ color: '#F5F5F7' }}>
            Buffett Score
          </p>
          <p className="text-xs mb-3" style={{ color: 'rgba(235,235,245,0.35)' }}>
            {pct >= 70 ? 'Strong competitive moat' : pct >= 55 ? 'Mixed signals — review carefully' : 'Does not meet Buffett criteria'}
          </p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Passed', value: pass, color: '#30D158', bg: 'rgba(48,209,88,0.08)' },
              { label: 'Failed', value: fail, color: '#FF453A', bg: 'rgba(255,69,58,0.08)' },
              { label: 'N/A',    value: na,   color: 'rgba(235,235,245,0.3)', bg: 'rgba(255,255,255,0.04)' },
            ].map(s => (
              <div key={s.label} className="rounded-lg p-2.5 text-center" style={{ background: s.bg }}>
                <p className="text-lg font-bold" style={{ color: s.color }}>{s.value}</p>
                <p className="text-[10px] mt-0.5 uppercase tracking-wide"
                  style={{ color: 'rgba(235,235,245,0.3)' }}>{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Grouped sections */}
      {CATEGORY_ORDER.map(cat => (
        byCategory[cat]?.length > 0 && (
          <CategorySection key={cat} category={cat} ratios={byCategory[cat]} />
        )
      ))}
    </div>
  )
}
