export interface BuffettRatio {
  name: string
  value: number | null
  threshold: string
  passes: boolean | null
  description: string
  buffett_logic: string
  category: string
  equation: string
  weight: number
}

export interface StockFinancials {
  financials: Record<string, Record<string, number | null>>
  balanceSheet: Record<string, Record<string, number | null>>
  cashflow: Record<string, Record<string, number | null>>
}

export interface StockQuote {
  name: string
  price: number | null
  change: number | null
  changesPercentage: number | null
  marketCap: number | null
  pe: number | null
  exchange: string
  sector?: string
  industry?: string
  summary?: string
  forwardPE?: number | null
  pegRatio?: number | null
  roe?: number | null
  roa?: number | null
  revenueGrowth?: number | null
  earningsGrowth?: number | null
  fcfYield?: number | null
  freeCashflow?: number | null
  dividendYield?: number | null
  evToEbitda?: number | null
  // 52-week range
  fiftyTwoWeekHigh?: number | null
  fiftyTwoWeekLow?: number | null
  // Analyst consensus
  targetLowPrice?: number | null
  targetMeanPrice?: number | null
  targetMedianPrice?: number | null
  targetHighPrice?: number | null
  recommendationKey?: string | null
  numberOfAnalystOpinions?: number | null
  // Insider ownership
  heldPercentInsiders?: number | null
  // Valuation inputs
  trailingEps?: number | null
  bookValue?: number | null
  sharesOutstanding?: number | null
  // Currency
  currency?: string | null
}

export interface StockValuation {
  graham: number | null
  dcf_base: number | null
  current_price: number | null
  mos_graham: number | null
  mos_dcf: number | null
  inputs: {
    eps: number | null
    bvps: number | null
    fcf: number | null
    shares: number | null
    default_growth: number | null
  }
}

export interface PriceHistory {
  dates: string[]
  prices: number[]
  volumes: number[]
}

export interface MoatResult {
  strength: 'Wide' | 'Narrow' | 'None'
  primary_type: string | null
  scores: Record<string, number>
  indicators: string[]
}

export type Section = 'ratios' | 'chart' | 'valuation' | 'statements' | 'ai'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}
