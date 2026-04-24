import axios from 'axios'
import type { BuffettRatio, StockFinancials, StockQuote, StockValuation, MoatResult, PriceHistory } from '../types'

const api = axios.create({ baseURL: '/api' })

export async function fetchQuote(ticker: string): Promise<StockQuote> {
  const { data } = await api.get(`/stock/${ticker}/quote`)
  return data
}

export async function fetchRatios(
  ticker: string,
): Promise<{ ticker: string; ratios: BuffettRatio[]; weighted_score: number }> {
  const { data } = await api.get(`/stock/${ticker}/ratios`)
  return data
}

export async function fetchFinancials(ticker: string): Promise<StockFinancials> {
  const { data } = await api.get(`/stock/${ticker}/financials`)
  return data
}

export async function fetchValuation(ticker: string): Promise<StockValuation> {
  const { data } = await api.get(`/stock/${ticker}/valuation`)
  return data
}

export async function fetchMoat(ticker: string): Promise<MoatResult> {
  const { data } = await api.get(`/stock/${ticker}/moat`)
  return data
}

export async function fetchHistory(ticker: string, period: string): Promise<PriceHistory> {
  const { data } = await api.get(`/stock/${ticker}/history`, { params: { period } })
  return data
}

export async function streamChat(
  question: string,
  ticker: string,
  ratios: BuffettRatio[],
  history: Array<{ role: string; content: string }>,
  onToken: (token: string) => void,
  onDone: () => void,
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ticker, ratios, history }),
  })
  if (!response.ok) throw new Error(`Server error: ${response.status}`)
  await _readSSE(response, onToken, onDone)
}

export async function streamRecommendation(
  ticker: string,
  ratios: BuffettRatio[],
  weightedScore: number,
  quote: StockQuote,
  onToken: (token: string) => void,
  onDone: () => void,
): Promise<void> {
  const response = await fetch('/api/stock/recommendation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker,
      ratios,
      weighted_score: weightedScore,
      quote,
    }),
  })
  if (!response.ok) throw new Error(`Server error: ${response.status}`)
  await _readSSE(response, onToken, onDone)
}

async function _readSSE(
  response: Response,
  onToken: (token: string) => void,
  onDone: () => void,
): Promise<void> {
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  if (!reader) return

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6)
        if (token === '[DONE]') { onDone(); return }
        if (token.startsWith('[ERROR]')) throw new Error(token.slice(8))
        onToken(token)
      }
    }
  }
  onDone()
}
