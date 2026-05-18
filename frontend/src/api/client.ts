import axios from 'axios'
import type {
  BuffettRatio, StockFinancials, StockQuote, StockValuation, MoatResult, PriceHistory,
  AgentStep, AgentRunSummary,
  OrchestratorStep, OrchestratorRunSummary,
  ChatSource,
} from '../types'

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
  question:    string,
  ticker:      string,
  ratios:      BuffettRatio[],
  history:     Array<{ role: string; content: string }>,
  onToken:     (token: string) => void,
  onDone:      () => void,
  onSources?:  (sources: ChatSource[]) => void,
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ticker, ratios, history }),
  })
  if (!response.ok) throw new Error(`Server error: ${response.status}`)

  await _readEventSSE(response, (event, data) => {
    if (event === 'token') {
      const t = (data as { text?: string })?.text
      if (t) onToken(t)
    } else if (event === 'sources') {
      const items = (data as { items?: ChatSource[] })?.items
      if (items && onSources) onSources(items)
    } else if (event === 'done') {
      onDone()
    } else if (event === 'error') {
      const err = (data as { error?: string })?.error || 'streaming error'
      throw new Error(err)
    }
  })
}

export async function streamRecommendation(
  ticker:        string,
  ratios:        BuffettRatio[],
  weightedScore: number,
  quote:         StockQuote,
  onToken:       (token: string) => void,
  onDone:        () => void,
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

  await _readEventSSE(response, (event, data) => {
    if (event === 'token') {
      const t = (data as { text?: string })?.text
      if (t) onToken(t)
    } else if (event === 'done') {
      onDone()
    } else if (event === 'error') {
      const err = (data as { error?: string })?.error || 'streaming error'
      throw new Error(err)
    }
  })
}

// ── Agent SSE (event-typed: event: <name>\ndata: <json>\n\n) ─────────────────

export async function streamAgent(
  query: string,
  onStep:  (step: AgentStep) => void,
  onDone:  (summary: AgentRunSummary) => void,
  onError: (message: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('/api/agent/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ query }),
      signal,
    })
  } catch (err) {
    if ((err as { name?: string })?.name === 'AbortError') return
    onError((err as Error).message || 'Network error')
    return
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = _stringifyDetail(body.detail)
    } catch { /* ignore */ }
    onError(detail)
    return
  }
  await _readEventSSE(response, (event, data) => {
    if (event === 'done')        onDone(data as AgentRunSummary)
    else if (event === 'error')  onError(
      ((data as { error?: string })?.error) || 'Unknown agent error',
    )
    else                         onStep(data as AgentStep)
  })
}

// ── Multi-agent (Orchestrator) SSE ───────────────────────────────────────────

export async function streamOrchestrate(
  query: string,
  onStep:  (step: OrchestratorStep) => void,
  onDone:  (summary: OrchestratorRunSummary) => void,
  onError: (message: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('/api/agent/orchestrate/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ query }),
      signal,
    })
  } catch (err) {
    if ((err as { name?: string })?.name === 'AbortError') return
    onError((err as Error).message || 'Network error')
    return
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = _stringifyDetail(body.detail)
    } catch { /* ignore */ }
    onError(detail)
    return
  }
  await _readEventSSE(response, (event, data) => {
    if (event === 'done')       onDone(data as OrchestratorRunSummary)
    else if (event === 'error') onError(
      ((data as { error?: string })?.error) || 'Unknown orchestrator error',
    )
    else                        onStep(data as OrchestratorStep)
  })
}

/** FastAPI/Pydantic v2 422 detail is an array of `{type,loc,msg,input}`; 503/429
 *  detail is a plain string. Reduce anything to a single readable string. */
function _stringifyDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(d => {
        if (typeof d === 'string') return d
        const obj = d as { msg?: string; loc?: unknown[] }
        const loc = Array.isArray(obj?.loc) ? obj.loc.join('.') : ''
        return obj?.msg ? (loc ? `${loc}: ${obj.msg}` : obj.msg) : JSON.stringify(d)
      })
      .join('; ')
  }
  try { return JSON.stringify(detail) } catch { return String(detail) }
}

async function _readEventSSE(
  response: Response,
  onEvent:  (event: string, data: unknown) => void,
): Promise<void> {
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  if (!reader) return

  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      sep = buffer.indexOf('\n\n')

      let eventName  = 'message'
      const dataLines: string[] = []
      for (const line of block.split('\n')) {
        if      (line.startsWith('event: ')) eventName = line.slice(7).trim()
        else if (line.startsWith('data: '))  dataLines.push(line.slice(6))
      }
      if (dataLines.length === 0) continue
      try {
        onEvent(eventName, JSON.parse(dataLines.join('\n')))
      } catch { /* drop malformed event */ }
    }
  }
}
