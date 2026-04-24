import { useStock } from '../../context/StockContext'
import RatioTable from './RatioTable'
import RatioChart from './RatioChart'
import PriceHistoryChart from './PriceHistoryChart'
import StatementTable from './StatementTable'
import StockOverview from './StockOverview'
import AIRecommendation from './AIRecommendation'
import ValuationPanel from './ValuationPanel'
import type { Section } from '../../types'

const SECTION_LABELS: Record<Section, string> = {
  ratios:     'Buffett Ratios',
  chart:      'Price & Ratio Charts',
  valuation:  'Valuation Models',
  statements: 'Financial Statements',
  ai:         'AI Investment Analysis',
}

function SectionHeader({ section }: { section: Section }) {
  return (
    <div className="mb-4">
      <h2 className="text-[15px] font-semibold" style={{ color: '#F5F5F7' }}>
        {SECTION_LABELS[section]}
      </h2>
    </div>
  )
}

interface Props { section: Section }

export default function Dashboard({ section }: Props) {
  const { ticker, quote, ratios, weightedScore, financials, moat, loading, error } = useStock()

  // Full-screen loader only on first search (no data yet)
  if (loading && !ticker) {
    return (
      <div className="h-full flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <div className="text-center">
          <div
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto mb-3"
            style={{ borderColor: 'rgba(10,132,255,0.2)', borderTopColor: '#0A84FF' }}
          />
          <p className="text-sm" style={{ color: 'rgba(235,235,245,0.5)' }}>Fetching financial data…</p>
          <p className="text-xs mt-1" style={{ color: 'rgba(235,235,245,0.25)' }}>Pulling statements from Yahoo Finance</p>
        </div>
      </div>
    )
  }

  if (error && !ticker) {
    return (
      <div className="flex items-center justify-center p-8" style={{ minHeight: '60vh' }}>
        <div className="rounded-2xl p-6 text-center max-w-sm w-full"
          style={{ background: 'rgba(255,69,58,0.08)', border: '1px solid rgba(255,69,58,0.2)' }}>
          <p className="font-semibold mb-1" style={{ color: '#FF453A' }}>Failed to load data</p>
          <p className="text-sm" style={{ color: 'rgba(235,235,245,0.5)' }}>{error}</p>
          <p className="text-xs mt-2" style={{ color: 'rgba(235,235,245,0.25)' }}>Check the ticker symbol and try again.</p>
        </div>
      </div>
    )
  }

  if (!ticker) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '70vh' }}>
        <div className="text-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: '#0A84FF', boxShadow: '0 8px 32px rgba(10,132,255,0.35)' }}
          >
            <span className="text-3xl font-bold text-white">B</span>
          </div>
          <p className="font-semibold text-[17px]" style={{ color: '#F5F5F7' }}>
            Warren Buffett Stock Analyzer
          </p>
          <p className="text-sm mt-1.5 max-w-xs mx-auto" style={{ color: 'rgba(235,235,245,0.45)' }}>
            Enter any stock ticker to analyze against Buffett's investment criteria
          </p>
          <div className="flex gap-2 justify-center mt-4 flex-wrap">
            {['AAPL', 'MSFT', 'KO', 'BRK-B', 'JNJ'].map(t => (
              <span key={t} className="text-xs font-mono rounded-md px-2.5 py-1"
                style={{ color: 'rgba(235,235,245,0.4)', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const pass  = ratios.filter(r => r.passes === true).length
  const total = ratios.length

  return (
    <div className="p-4 space-y-4">
      {/* Stock overview — always visible across all sections */}
      {quote && (
        <div style={{ position: 'relative' }}>
          <StockOverview ticker={ticker} quote={quote} moat={moat} />
          {/* Subtle re-fetching indicator */}
          {loading && (
            <div className="absolute top-3 right-3">
              <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'rgba(10,132,255,0.2)', borderTopColor: '#0A84FF' }} />
            </div>
          )}
        </div>
      )}

      {/* Weighted score bar */}
      {ticker && (
        <div
          className="rounded-xl px-4 py-2.5 flex items-center justify-between"
          style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}
        >
          <div>
            <span className="text-xs" style={{ color: 'rgba(235,235,245,0.35)' }}>Buffett Weighted Score</span>
            <span className="text-[11px] ml-2" style={{ color: 'rgba(235,235,245,0.2)' }}>
              ({pass}/{total} criteria passed)
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-36 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${weightedScore}%`,
                  background: weightedScore >= 70 ? '#30D158' : weightedScore >= 40 ? '#FF9F0A' : '#FF453A',
                }}
              />
            </div>
            <span
              className="text-base font-bold font-mono tabular-nums w-12 text-right"
              style={{ color: weightedScore >= 70 ? '#30D158' : weightedScore >= 40 ? '#FF9F0A' : '#FF453A' }}
            >
              {weightedScore.toFixed(0)}
              <span className="text-xs font-normal" style={{ color: 'rgba(235,235,245,0.3)' }}>/100</span>
            </span>
          </div>
        </div>
      )}

      {/* Error banner (non-blocking) */}
      {error && ticker && (
        <div className="rounded-xl px-4 py-2.5" style={{ background: 'rgba(255,69,58,0.1)', border: '1px solid rgba(255,69,58,0.2)' }}>
          <p className="text-sm" style={{ color: '#FF453A' }}>{error}</p>
        </div>
      )}

      {/* Section content */}
      <div className="rounded-xl overflow-hidden"
        style={{ background: '#2C2C2E', border: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="px-4 py-3 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
          <SectionHeader section={section} />
        </div>
        <div className="p-4">
          {section === 'ratios'     && <RatioTable ratios={ratios} />}
          {section === 'chart'      && (
            <div className="space-y-6">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider mb-3"
                  style={{ color: 'rgba(235,235,245,0.3)' }}>Price History</p>
                <PriceHistoryChart />
              </div>
              <div className="border-t pt-5" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
                <p className="text-[11px] font-semibold uppercase tracking-wider mb-3"
                  style={{ color: 'rgba(235,235,245,0.3)' }}>Buffett Ratio Analysis</p>
                <RatioChart ratios={ratios} />
              </div>
            </div>
          )}
          {section === 'valuation'  && <ValuationPanel />}
          {section === 'statements' && financials && <StatementTable financials={financials} />}
          {section === 'statements' && !financials && (
            <p className="text-sm text-center py-8" style={{ color: 'rgba(235,235,245,0.3)' }}>
              No financial statement data available.
            </p>
          )}
          {section === 'ai'         && <AIRecommendation />}
        </div>
      </div>
    </div>
  )
}
