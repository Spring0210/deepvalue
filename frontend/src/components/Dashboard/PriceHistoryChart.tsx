import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts'
import { useStock } from '../../context/StockContext'
import { fetchHistory } from '../../api/client'
import type { PriceHistory } from '../../types'

const PERIODS = [
  { label: '1D', value: '1d'  },
  { label: '1W', value: '5d'  },
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y'  },
  { label: '2Y', value: '2y'  },
  { label: '5Y', value: '5y'  },
]

function fmt(dateStr: string, period: string): string {
  // Intraday: "2024-01-15 14:30"
  if (period === '1d' || period === '5d') {
    if (dateStr.includes(' ')) {
      const [datePart, timePart] = dateStr.split(' ')
      if (period === '1d') return timePart.slice(0, 5)  // HH:MM
      const d = new Date(datePart)
      const day = d.toLocaleDateString('en-US', { weekday: 'short' })
      return `${day} ${timePart.slice(0, 5)}`
    }
    return dateStr
  }
  const d = new Date(dateStr)
  if (period === '1mo' || period === '3mo' || period === '6mo')
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return d.toLocaleDateString('en-US', { year: '2-digit', month: 'short' })
}

// Show roughly 6 ticks regardless of data density
function tickInterval(len: number): number {
  return Math.max(1, Math.floor(len / 6))
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl px-3 py-2 shadow-xl text-xs"
      style={{ background: '#3A3A3C', border: '1px solid rgba(255,255,255,0.12)' }}>
      <p className="font-mono text-[11px] mb-0.5" style={{ color: 'rgba(235,235,245,0.4)' }}>{label}</p>
      <p className="font-semibold font-mono" style={{ color: '#F5F5F7' }}>
        ${payload[0].value.toFixed(2)}
      </p>
    </div>
  )
}

export default function PriceHistoryChart() {
  const { ticker } = useStock()
  const [period, setPeriod]     = useState<string>('1y')
  const [data, setData]         = useState<PriceHistory | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  useEffect(() => {
    if (!ticker) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchHistory(ticker, period)
      .then(d => { if (!cancelled) setData(d) })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticker, period])

  if (!ticker) return (
    <div className="flex items-center justify-center h-48">
      <p className="text-sm" style={{ color: 'rgba(235,235,245,0.3)' }}>Search a stock to see price history.</p>
    </div>
  )

  const chartData = data
    ? data.dates.map((date, i) => ({ date, price: data.prices[i], volume: data.volumes[i] }))
    : []

  const startPrice  = chartData[0]?.price ?? null
  const latestPrice = chartData[chartData.length - 1]?.price ?? null
  const isUp        = latestPrice !== null && startPrice !== null && latestPrice >= startPrice
  const changePct   = startPrice && latestPrice ? ((latestPrice - startPrice) / startPrice) * 100 : null
  const lineColor   = isUp ? '#30D158' : '#FF453A'
  const gradientId  = `grad-${isUp ? 'up' : 'down'}`

  const minPrice = chartData.length ? Math.min(...chartData.map(d => d.price)) * 0.995 : 0
  const maxPrice = chartData.length ? Math.max(...chartData.map(d => d.price)) * 1.005 : 0

  return (
    <div className="space-y-3">
      {/* Header: period selector + change */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1.5">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all"
              style={{
                background: period === p.value ? '#0A84FF' : 'rgba(255,255,255,0.06)',
                color:      period === p.value ? '#ffffff'  : 'rgba(235,235,245,0.4)',
                border: `1px solid ${period === p.value ? 'transparent' : 'rgba(255,255,255,0.06)'}`,
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        {changePct !== null && (
          <span className="text-sm font-semibold font-mono" style={{ color: lineColor }}>
            {isUp ? '▲' : '▼'} {Math.abs(changePct).toFixed(2)}%
            <span className="text-[11px] ml-1 font-normal" style={{ color: 'rgba(235,235,245,0.3)' }}>
              over period
            </span>
          </span>
        )}
      </div>

      {/* Chart */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: 'rgba(10,132,255,0.2)', borderTopColor: '#0A84FF' }} />
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-48">
          <p className="text-xs" style={{ color: '#FF453A' }}>{error}</p>
        </div>
      ) : chartData.length === 0 ? (
        <div className="flex items-center justify-center h-48">
          <p className="text-xs" style={{ color: 'rgba(235,235,245,0.3)' }}>No data available.</p>
        </div>
      ) : (
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={lineColor} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={lineColor} stopOpacity={0.01} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />

              {startPrice && (
                <ReferenceLine
                  y={startPrice}
                  stroke="rgba(255,255,255,0.12)"
                  strokeDasharray="4 4"
                />
              )}

              <XAxis
                dataKey="date"
                tickFormatter={d => fmt(d, period)}
                interval={tickInterval(chartData.length)}
                tick={{ fill: 'rgba(235,235,245,0.25)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[minPrice, maxPrice]}
                tickFormatter={v => `$${v.toFixed(0)}`}
                tick={{ fill: 'rgba(235,235,245,0.25)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={52}
              />
              <Tooltip content={<CustomTooltip />} />

              <Area
                type="monotone"
                dataKey="price"
                stroke={lineColor}
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, fill: lineColor, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Start/end labels */}
      {!loading && !error && chartData.length > 0 && (
        <div className="flex justify-between text-[10px] font-mono" style={{ color: 'rgba(235,235,245,0.2)' }}>
          <span>{chartData[0].date}</span>
          <span>{chartData[chartData.length - 1].date}</span>
        </div>
      )}
    </div>
  )
}
