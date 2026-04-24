import { createContext, useContext, useState, type ReactNode } from 'react'
import type { BuffettRatio, StockFinancials, StockQuote, StockValuation, MoatResult } from '../types'
import { fetchRatios, fetchFinancials, fetchQuote, fetchValuation, fetchMoat } from '../api/client'

interface Recommendation {
  text: string
  ticker: string
  streaming: boolean
}

interface StockContextType {
  ticker: string
  quote: StockQuote | null
  ratios: BuffettRatio[]
  weightedScore: number
  financials: StockFinancials | null
  valuation: StockValuation | null
  moat: MoatResult | null
  loading: boolean
  error: string | null
  recommendation: Recommendation
  setRecommendation: (r: Recommendation) => void
  search: (ticker: string) => Promise<void>
}

const StockContext = createContext<StockContextType | null>(null)

const EMPTY_RECOMMENDATION: Recommendation = { text: '', ticker: '', streaming: false }

export function StockProvider({ children }: { children: ReactNode }) {
  const [ticker, setTicker]               = useState('')
  const [quote, setQuote]                 = useState<StockQuote | null>(null)
  const [ratios, setRatios]               = useState<BuffettRatio[]>([])
  const [weightedScore, setWeightedScore] = useState(0)
  const [financials, setFinancials]       = useState<StockFinancials | null>(null)
  const [valuation, setValuation]         = useState<StockValuation | null>(null)
  const [moat, setMoat]                   = useState<MoatResult | null>(null)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState<string | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation>(EMPTY_RECOMMENDATION)

  const search = async (newTicker: string) => {
    setLoading(true)
    setError(null)
    try {
      const [ratioData, finData, quoteData, valuationData, moatData] = await Promise.all([
        fetchRatios(newTicker),
        fetchFinancials(newTicker),
        fetchQuote(newTicker),
        fetchValuation(newTicker),
        fetchMoat(newTicker),
      ])
      setTicker(ratioData.ticker)
      setRatios(ratioData.ratios)
      setWeightedScore(ratioData.weighted_score)
      setFinancials(finData)
      setQuote(quoteData)
      setValuation(valuationData)
      setMoat(moatData)
      setRecommendation(EMPTY_RECOMMENDATION)
    } catch (e) {
      const msg = (e instanceof Error && e.message) ? e.message : 'Failed to fetch stock data.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <StockContext.Provider value={{
      ticker, quote, ratios, weightedScore, financials, valuation, moat,
      loading, error, recommendation, setRecommendation, search,
    }}>
      {children}
    </StockContext.Provider>
  )
}

export function useStock() {
  const ctx = useContext(StockContext)
  if (!ctx) throw new Error('useStock must be used within StockProvider')
  return ctx
}
