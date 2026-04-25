import { useState } from 'react'
import type { StockFinancials } from '../../types'
import { useStock } from '../../context/StockContext'
import { getCurrencySymbol } from '../../utils/currency'

function fmtMoney(val: number | null | undefined, sym: string): string {
  if (val === null || val === undefined) return '—'
  const abs = Math.abs(val)
  const sign = val < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${sym}${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9)  return `${sign}${sym}${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6)  return `${sign}${sym}${(abs / 1e6).toFixed(1)}M`
  return `${sign}${sym}${abs.toLocaleString()}`
}

const SECTION_META: Record<string, { color: string }> = {
  'Income Statement':    { color: '#5AC8F5' },
  'Balance Sheet':       { color: '#BF5AF2' },
  'Cash Flow Statement': { color: '#FF9F0A' },
}

function Statement({ title, data, sym }: {
  title: string
  data: Record<string, Record<string, number | null>>
  sym: string
}) {
  const [open, setOpen] = useState(true)
  const columns = Object.keys(data)
  if (columns.length === 0) return null
  const rows = Object.keys(data[columns[0]] ?? {})
  const meta = SECTION_META[title] ?? { color: 'rgba(235,235,245,0.4)' }

  return (
    <div className="mb-4 last:mb-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-sm font-semibold mb-2.5 transition-opacity hover:opacity-70 w-full text-left"
        style={{ color: meta.color }}
      >
        <svg
          className="w-3 h-3 transition-transform flex-shrink-0"
          style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}
          viewBox="0 0 6 10" fill="currentColor"
        >
          <path d="M0.5 1L5 5L0.5 9" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
        {title}
        <span className="text-[11px] font-normal" style={{ color: 'rgba(235,235,245,0.25)' }}>
          {rows.length} items · {columns.length} yrs
        </span>
      </button>

      {open && (
        <div className="overflow-x-auto rounded-xl"
          style={{ border: '1px solid rgba(255,255,255,0.07)', background: '#1C1C1E' }}>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                <th className="text-left px-4 py-2.5 font-medium min-w-[220px]"
                  style={{ color: 'rgba(235,235,245,0.3)' }}>
                  Line Item
                </th>
                {columns.map(col => (
                  <th key={col} className="text-right px-3 py-2.5 font-medium whitespace-nowrap"
                    style={{ color: 'rgba(235,235,245,0.3)' }}>
                    FY{col.slice(0, 4)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr
                  key={row}
                  style={{
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    background: ri % 2 === 1 ? 'rgba(255,255,255,0.015)' : 'transparent',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  onMouseLeave={e => (e.currentTarget.style.background = ri % 2 === 1 ? 'rgba(255,255,255,0.015)' : 'transparent')}
                >
                  <td className="px-4 py-2 truncate max-w-[220px]"
                    style={{ color: 'rgba(235,235,245,0.5)' }}>
                    {row}
                  </td>
                  {columns.map(col => {
                    const v = data[col]?.[row] ?? null
                    return (
                      <td key={col} className="px-3 py-2 text-right font-mono tabular-nums"
                        style={{ color: v !== null && v < 0 ? '#FF453A' : 'rgba(235,235,245,0.6)' }}>
                        {fmtMoney(v, sym)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function StatementTable({ financials }: { financials: StockFinancials }) {
  const { quote } = useStock()
  const sym = getCurrencySymbol(quote?.currency)
  return (
    <div>
      <Statement title="Income Statement"    data={financials.financials}  sym={sym} />
      <Statement title="Balance Sheet"       data={financials.balanceSheet} sym={sym} />
      <Statement title="Cash Flow Statement" data={financials.cashflow}     sym={sym} />
    </div>
  )
}
