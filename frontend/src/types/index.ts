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
  dcf_bear: number | null
  dcf_bull: number | null
  fcf_yield_value: number | null
  epv: number | null
  current_price: number | null
  discount_rate: number | null
  mos_graham: number | null
  mos_dcf: number | null
  mos_dcf_bear: number | null
  mos_fcf_yield: number | null
  mos_epv: number | null
  roic: number | null
  price_to_fcf: number | null
  circle_of_competence: {
    within: boolean
    flags: string[]
    complexity: 'Low' | 'Medium' | 'High'
  } | null
  inputs: {
    eps: number | null
    bvps: number | null
    fcf: number | null
    shares: number | null
    default_growth: number | null
    beta: number | null
    discount_rate: number | null
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

export type Section = 'ratios' | 'chart' | 'valuation' | 'statements' | 'ai' | 'watchlist' | 'agent'

export interface ChatSource {
  id: number
  source: string
  snippet: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  sources?: ChatSource[]
}

// ── Agent harness wire types (mirror app/agent/models.py) ────────────────────

export type AgentStepKind = 'llm' | 'tool_batch' | 'final' | 'error' | 'repair'

export interface AgentToolCall {
  id:   string
  name: string
  args: Record<string, unknown>
}

export interface AgentToolResult {
  call_id:    string
  name:       string
  ok:         boolean
  output?:    unknown
  error?:     string | null
  latency_ms: number
  attempts:   number
}

export interface AgentLLMUsage {
  model:              string
  input_tokens:       number
  output_tokens:      number
  cache_read_tokens:  number
  cache_write_tokens: number
  cost_usd:           number
  latency_ms:         number
}

export interface AgentStep {
  idx:          number
  kind:         AgentStepKind
  started_at:   number
  text?:        string | null
  tool_calls:   AgentToolCall[]
  usage?:       AgentLLMUsage | null
  tool_results: AgentToolResult[]
  error?:       string | null
}

export interface AgentRunSummary {
  id:                  string
  status:              'running' | 'completed' | 'failed' | 'capped'
  final_text:          string | null
  total_cost_usd:      number
  total_latency_ms:    number
  total_input_tokens:  number
  total_output_tokens: number
  error:               string | null
}

// ── Multi-agent (Orchestrator) wire types — mirror app/agent/models.py ───────

export type SubagentRole = 'fundamentals' | 'news' | 'technical' | 'valuation' | 'risk'

export interface Subtask {
  role:   SubagentRole
  ticker: string
  focus?: string | null
}

export interface ResearchPlan {
  rationale: string
  subtasks:  Subtask[]
}

export interface Finding {
  role:      SubagentRole
  ticker:    string
  summary:   string
  bullets:   string[]
  citations: string[]
}

export type OrchestratorStepKind = 'plan' | 'subagent' | 'synth' | 'final' | 'error'

export interface OrchestratorStep {
  idx:        number
  kind:       OrchestratorStepKind
  started_at: number
  plan?:      ResearchPlan | null
  role?:      SubagentRole | null
  ticker?:    string | null
  finding?:   Finding | null
  text?:      string | null
  error?:     string | null
}

export interface OrchestratorRunSummary {
  id:                  string
  status:              'running' | 'completed' | 'failed' | 'capped'
  final_text:          string | null
  n_subagents:         number
  n_findings:          number
  total_cost_usd:      number
  total_latency_ms:    number
  total_input_tokens:  number
  total_output_tokens: number
  error:               string | null
}
