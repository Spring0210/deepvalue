# DeepValue Agent — Architecture Reference

> Current version: **v0.4** (sector-aware Buffett analyzer + valuation engine + moat classifier + RAG chat + watchlist)
> Target version: **v0.5** (multi-agent harness + MCP server + hybrid RAG over SEC filings + eval harness + full observability)
> Last updated: 2026-05-11

---

## Table of Contents

1. [Current Architecture (v0.4)](#current-architecture-v04)
   - [Project Overview](#project-overview)
   - [Tech Stack](#tech-stack)
   - [Directory Structure](#directory-structure)
   - [API Reference](#api-reference)
   - [Data Flows](#data-flows)
   - [Buffett Ratio Reference](#buffett-ratio-reference)
   - [Environment Variables](#environment-variables)
   - [Local Development](#local-development)
   - [Key Design Decisions (v0.4)](#key-design-decisions-v04)
2. [Target Architecture (v0.5)](#target-architecture-v05)
   - [System Diagram](#system-diagram)
   - [Agent Harness](#agent-harness)
   - [Multi-Agent Orchestration](#multi-agent-orchestration)
   - [Persistence Layer](#persistence-layer)
   - [Hybrid RAG Pipeline](#hybrid-rag-pipeline)
   - [Eval Harness](#eval-harness)
   - [Observability Stack](#observability-stack)
   - [Migration Path: v0.4 → v0.5](#migration-path-v04--v05)

---

# Current Architecture (v0.4)

## Project Overview

DeepValue Agent (v0.4) is an AI-augmented equity research tool. Users search any publicly traded stock (US / HK / A-share) and receive:

- A **weighted Buffett score (0–100)** across 14 sector-adjusted, trend-aware metrics
- **Intrinsic value estimates** via four independent models (DCF, Graham, FCF Yield, EPV) plus ROIC and Price-to-FCF
- A **competitive moat classification** (Wide / Narrow / None across 5 moat types)
- A **streaming AI investment recommendation** grounded in a RAG knowledge base
- A **multi-turn RAG chat advisor** with full conversation history

v0.4 is the foundation. v0.5 (in progress) pivots the application into a multi-agent platform — see [Target Architecture](#target-architecture-v05).

---

## Tech Stack

### Backend — Python 3.11

| Layer | Technology | Notes |
|---|---|---|
| Web Framework | **FastAPI 0.111** | Async REST API, OpenAPI docs at `/docs` |
| Server | **Uvicorn (standard)** | ASGI with hot-reload in dev |
| Financial Data | **yfinance ≥ 1.3.0** | Yahoo Finance — no API key; US / HK / A-shares; calls wrapped in `asyncio.to_thread` |
| Cache | **cachetools.TTLCache** | 15-min quote / 30-min history (in-memory, single-process) |
| Rate Limiting | **slowapi 0.1.9** | Per-IP per-route limits |
| Embeddings | **sentence-transformers `all-MiniLM-L6-v2`** | 384-dim general-purpose embeddings |
| Vector Store | **FAISS (CPU) 1.8** | Local index, saved to `data/faiss_index/` on first run |
| RAG | **LangChain 0.2** | Text splitting and document loading |
| LLM (chat) | **Groq `llama-3.1-8b-instant`** | Fast multi-turn RAG chat |
| LLM (recs) | **Groq `llama-3.3-70b-versatile`** | Higher-quality investment recommendations |
| HTTP Client | **httpx** | Async-capable |
| Config | **python-dotenv** | Loads `backend/.env` |

### Frontend — React 18 + TypeScript

| Layer | Technology | Notes |
|---|---|---|
| Framework | **React 18 + TypeScript 5** | Strict mode |
| Build | **Vite 5** | Dev server on `:5173`, proxies `/api` → `:8000` |
| Styling | **Tailwind CSS 3** | Apple-HIG-inspired dark theme; inline `style` for dynamic colors |
| Charts | **Recharts 2** | Ratio bar chart + price history area chart |
| HTTP | **Axios** for REST, **fetch + ReadableStream** for SSE |
| State | **React Context** | `StockContext` (dashboard) + `WatchlistContext` (localStorage) |
| Streaming | **fetch ReadableStream** parsing `text/event-stream` |

---

## Directory Structure

```
DeepValue/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI app · CORS · slowapi handler · lifespan (FAISS init)
│   │   ├── config.py                    # Env: GROQ_API_KEY, GROQ_MODEL, GROQ_RECOMMENDATION_MODEL, ALLOWED_ORIGINS
│   │   ├── limiter.py                   # Module-level slowapi Limiter (shared across routes)
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── stock.py             # GET  /api/stock/{ticker}/quote          (30/min)
│   │   │       │                        # GET  /api/stock/{ticker}/ratios         (20/min)
│   │   │       │                        # GET  /api/stock/{ticker}/financials     (20/min)
│   │   │       │                        # GET  /api/stock/{ticker}/history        (20/min)
│   │   │       │                        # GET  /api/stock/{ticker}/valuation      (20/min)
│   │   │       │                        # GET  /api/stock/{ticker}/moat           (20/min)
│   │   │       │                        # POST /api/stock/recommendation          (5/min, SSE)
│   │   │       └── chat.py              # POST /api/chat                          (SSE, multi-turn)
│   │   ├── services/
│   │   │   ├── financial.py             # async yfinance wrapper + TTLCache
│   │   │   │                            # get_stock_quote(), get_stock_data(), get_price_history()
│   │   │   ├── buffett.py               # 14 BuffettRatio dataclasses · sector-aware thresholds
│   │   │   │                            # compute_ratios(data, sector) → list[BuffettRatio]
│   │   │   │                            # compute_weighted_score(ratios) → float
│   │   │   │                            # compute_trend_adjustment(data) → float ∈ [−10, +10]
│   │   │   ├── valuation.py             # compute_valuation(quote, data) →
│   │   │   │                            #   { dcf, graham, fcf_yield_value, epv, roic, p_fcf,
│   │   │   │                            #     margin_of_safety, circle_of_competence_flag }
│   │   │   ├── moat.py                  # compute_moat(quote) →
│   │   │   │                            #   { strength: "Wide"|"Narrow"|"None", type, dimension_scores }
│   │   │   └── rag.py                   # FAISS build/load · retrieve()
│   │   │                                # stream_chat(question, ticker, ratios, history) → AsyncIterator
│   │   │                                # stream_recommendation(...) → AsyncIterator
│   │   └── data/
│   │       ├── buffett_knowledge.txt    # ~30 RAG chunks
│   │       └── faiss_index/             # auto-generated, git-ignored
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html · vite.config.ts · tailwind.config.js · tsconfig.json
│   └── src/
│       ├── main.tsx · App.tsx          # App: Header + Sidebar + Dashboard + ChatDrawer + ErrorBoundary
│       ├── index.css                    # Tailwind + SF Pro font stack + scrollbar overrides
│       ├── types/index.ts               # BuffettRatio, StockQuote, Valuation, Moat, Message, …
│       ├── api/client.ts                # fetchQuote/Ratios/Financials/History/Valuation/Moat
│       │                                # streamChat, streamRecommendation
│       ├── utils/currency.ts            # Currency symbol per market (USD / HKD / CNY / …)
│       ├── context/
│       │   ├── StockContext.tsx         # ticker, quote, ratios, weightedScore, financials,
│       │   │                            # valuation, moat, history, recommendation, loading, error
│       │   └── WatchlistContext.tsx     # localStorage-backed add/remove/list
│       └── components/
│           ├── Header.tsx · StockSearch.tsx · Sidebar.tsx
│           ├── ErrorBoundary.tsx · ChatDrawer.tsx
│           ├── Dashboard/
│           │   ├── index.tsx            # Tabs: Ratios | Chart | Valuation | Moat | Statements | Watchlist | AI
│           │   ├── StockOverview.tsx    # Price + extended stats + 52w bar + analyst targets
│           │   ├── RatioTable.tsx       # Score ring + 14 ratio cards by statement category
│           │   ├── RatioChart.tsx       # Pass/fail bar chart
│           │   ├── PriceHistoryChart.tsx# Period selector + area chart
│           │   ├── ValuationPanel.tsx   # DCF sliders + Graham + EPV + ROIC + MoS gauge
│           │   ├── MoatCard.tsx         # Moat strength badge + dimension scores
│           │   ├── StatementTable.tsx   # Collapsible Income/Balance/CashFlow tables
│           │   ├── Watchlist.tsx        # User watchlist
│           │   └── AIRecommendation.tsx # Score gauge + streaming AI analysis
│           └── Chatbot/
│               └── ChatWindow.tsx       # Multi-turn chat (sends `history` field)
│
├── ARCHITECTURE.md                      # This file
├── ROADMAP.md                           # Phased roadmap including v0.5 target
└── README.md
```

---

## API Reference

### Stock Endpoints

```
GET  /api/stock/{ticker}/quote                                  30/min
     Response: StockQuote
       { name, price, change, changesPercentage, marketCap, pe, exchange,
         sector, industry, summary, forwardPE, pegRatio, roe, roa,
         revenueGrowth, earningsGrowth, fcfYield, dividendYield, evToEbitda,
         currency, fiftyTwoWeekHigh, fiftyTwoWeekLow, analystTargetMean, … }

GET  /api/stock/{ticker}/ratios                                 20/min
     Response:
       { ticker, weighted_score: float, trend_adjustment: float,
         ratios: BuffettRatio[] }
     BuffettRatio: { name, value, threshold, passes, description,
                     buffett_logic, category, equation, weight }

GET  /api/stock/{ticker}/financials                             20/min
     Response: StockFinancials
       { financials: {date: {field: value}},
         balanceSheet: {date: {field: value}},
         cashflow:     {date: {field: value}} }

GET  /api/stock/{ticker}/history?period=1y                      20/min
     period ∈ {1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y}
     Response: [ {date, open, high, low, close, volume}, ... ]

GET  /api/stock/{ticker}/valuation                              20/min
     Response:
       { dcf:        { fair_value, growth_rate, discount_rate, terminal_rate },
         graham:     { fair_value, eps, bvps },
         fcf_yield:  { fair_value, normalized_fcf, treasury_rate },
         epv:        { fair_value, normalized_earnings },
         roic:       { value, threshold, passes },
         p_fcf:      { value },
         margin_of_safety: { current_price, intrinsic_range, mos_pct },
         circle_of_competence_flag: bool }

GET  /api/stock/{ticker}/moat                                   20/min
     Response:
       { strength: "Wide" | "Narrow" | "None",
         type:     "Brand" | "Network Effect" | "Cost Advantage" | "Switching Costs" | "Efficient Scale",
         dimension_scores: { gross_margin, roe, fcf_yield, operating_margin, revenue_stability } }

POST /api/stock/recommendation                                  5/min, SSE
     Body: { ticker, ratios, weighted_score, quote }
     Response: text/event-stream tokens → [DONE]
```

### Chat Endpoint

```
POST /api/chat                                                  SSE
     Body: { question: string, ticker: string, ratios: BuffettRatio[],
             history: [{role: "user"|"assistant", content: string}, ...] }
     Response: text/event-stream tokens → [DONE]
```

### Health

```
GET  /api/health
     Response: { status: "ok" }
```

---

## Data Flows

### Stock Analysis (on ticker search)

```
User types ticker → StockSearch calls search()
        │
        ▼
StockContext fires parallel requests:
  ├── GET /api/stock/{ticker}/quote         → StockQuote (yfinance .info)
  ├── GET /api/stock/{ticker}/ratios        → 14 ratios + weighted_score + trend_adjustment
  ├── GET /api/stock/{ticker}/financials    → DataFrames → dicts
  ├── GET /api/stock/{ticker}/valuation     → DCF + Graham + FCF Yield + EPV + ROIC + MoS
  ├── GET /api/stock/{ticker}/moat          → strength + type + dimension_scores
  └── GET /api/stock/{ticker}/history?period=1y
        │
        ▼ (backend, all routes are async def)
financial.py: yf.Ticker(ticker).info / .financials / .balance_sheet / .cashflow / .history
              wrapped in asyncio.to_thread; TTLCache keyed by ticker
        │
        ▼
buffett.py / valuation.py / moat.py compute their outputs in parallel
        │
        ▼ (frontend)
StockContext stores all results; stale-while-revalidate (prior data stays visible during loading)
        │
        ├── StockOverview     — price + extended stats + 52w bar
        ├── RatioTable        — score ring + 14 ratio cards
        ├── RatioChart        — pass/fail bar chart
        ├── PriceHistoryChart — period selector + area chart
        ├── ValuationPanel    — DCF sliders + Graham + EPV + ROIC + MoS
        ├── MoatCard          — moat badge + dimension scores
        ├── StatementTable    — collapsible financial tables
        ├── Watchlist         — saved tickers
        └── AIRecommendation  — score gauge + (on-click) streaming AI analysis
```

### RAG Chat Flow (multi-turn)

```
User sends message → ChatWindow appends to messages, captures prior messages as `history`
        │
        ▼
POST /api/chat { question, ticker, ratios, history }
        │
        ▼
rag.py:
  • embed `question` with all-MiniLM-L6-v2
  • FAISS similarity_search(k=3) on buffett_knowledge.txt
  • assemble message list:
        [ {role: "system", content: persona + rag_context + ratio_table},
          ...history,
          {role: "user",   content: question} ]
        │
        ▼
Groq llama-3.1-8b-instant streams tokens (chat.completions, stream=True)
        │
        ▼
SSE: "data: <token>\n\n"  …  "data: [DONE]\n\n"
        │
        ▼
Frontend ReadableStream appends tokens to the last assistant message in `messages`
```

### AI Recommendation Flow

```
User clicks "Generate AI Investment Analysis"
        │
        ▼
POST /api/stock/recommendation
  { ticker, ratios (14 items w/ weight), weighted_score, quote (sector, ROE, PEG, FCF yield, …) }
        │
        ▼
rag.py:
  • retrieve sector-aware Buffett context (k=4)
  • assemble [system, user] split:
        system:
          • Analyst role + value-investing framing
          • Sector-aware few-shot example
          • Output schema: VERDICT / STRENGTHS / CONCERNS / BUFFETT ALIGNMENT / MODERN CONTEXT
        user:
          • Company snapshot (sector, industry, business summary, price, market cap,
            ROE, PEG, FCF yield, revenue growth, weighted score, trend adjustment)
          • 14-metric table: name / status / value / threshold / weight
          • RAG context chunks
        │
        ▼
Groq llama-3.3-70b-versatile (max_tokens≈800, temperature≈0.6) streams
        │
        ▼
AIRecommendation parses sections and renders the formatted output;
the partial recommendation lives in StockContext, so tab switches don't lose it
```

---

## Buffett Ratio Reference (v0.4 — 14 metrics, sector-aware)

| # | Name | Equation | Default Threshold | Category | Weight |
|---|---|---|---|---|---|
| 1 | Gross Margin | Gross Profit / Revenue | ≥ 40% (sector-adjusted) | Income Statement | 13% |
| 2 | SG&A Margin | SG&A / Gross Profit | ≤ 30% | Income Statement | 7% |
| 3 | R&D Margin | R&D / Gross Profit | ≤ 30% (relaxed for tech) | Income Statement | 4% |
| 4 | Depreciation Margin | Depreciation / Gross Profit | ≤ 10% | Income Statement | 6% |
| 5 | Interest Expense Margin | Interest Expense / Operating Income | ≤ 15% | Income Statement | 8% |
| 6 | Effective Tax Rate | Tax Provision / Pre-Tax Income | 15–30% | Income Statement | 5% |
| 7 | Net Profit Margin | Net Income / Revenue | ≥ 20% | Income Statement | 11% |
| 8 | EPS Growth (YoY) | EPS(N) / EPS(N-1) | > 1.0 | Income Statement | 10% |
| 9 | Cash vs Current Debt | Cash / Current Debt | > 1.0 | Balance Sheet | 8% |
| 10 | Adj. Debt-to-Equity | Total Debt / (Assets − Debt) | < 0.80 (relaxed for financials) | Balance Sheet | 9% |
| 11 | Preferred Stock | Balance sheet value | = $0 | Balance Sheet | 1% |
| 12 | Retained Earnings Growth | RE(N) / RE(N-1) | > 1.0 | Balance Sheet | 9% |
| 13 | Treasury Stock | Balance sheet value | Exists | Balance Sheet | 1% |
| 14 | CapEx Margin | CapEx / Net Income | < 25% | Cash Flow | 8% |

**Weighted Score formula:**
```
base_score      = Σ(weight_i for pass_i == True) / Σ(weight_i for pass_i != None) × 100
trend_bonus     = +K if metric improved 3 yrs running
trend_penalty   = −K if metric in 3-yr freefall
trend_adjustment = clamp(Σtrend, −10, +10)
weighted_score   = clamp(base_score + trend_adjustment, 0, 100)
```
N/A metrics are excluded from both numerator and denominator.

---

## Environment Variables

```bash
# backend/.env  (never commit — see .env.example)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant                 # chat
GROQ_RECOMMENDATION_MODEL=llama-3.3-70b-versatile  # AI recommendation
ALLOWED_ORIGINS=http://localhost:5173            # comma-separated for prod
```

No other API keys required in v0.4. v0.5 will add `ANTHROPIC_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `LANGFUSE_*`, `NEWSAPI_KEY`, `SEC_USER_AGENT`.

---

## Local Development

```bash
# Backend (Python 3.11)
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000        # docs: http://localhost:8000/docs

# Frontend
cd frontend
npm install
npm run dev                                       # http://localhost:5173, proxies /api → :8000
```

---

## Key Design Decisions (v0.4)

| Decision | Alternative | Rationale |
|---|---|---|
| yfinance over FMP/Polygon | Polygon, IEX Cloud, FMP | No API key; broader ticker coverage (HK, A-shares); FMP free tier limited to major US |
| FAISS local over Pinecone | Pinecone, Weaviate, Qdrant | Zero external deps; works offline; adequate for <10k chunks. Will migrate to pgvector in v0.5 |
| Groq over OpenAI/Anthropic | OpenAI GPT-4o, Anthropic Claude | Free tier; ~10× faster inference; LLaMA quality sufficient for v0.4 single-shot prompts. v0.5 adds Anthropic for agent layer |
| LLaMA 70B for recs, 8B for chat | Single model | Recommendation prompt is dense and benefits from larger model; chat is high-frequency so favors speed/cost |
| SSE over WebSocket | WebSocket | Simpler for one-directional token streaming; no ws library needed |
| React Context over Zustand/Redux | Zustand, Redux Toolkit | Single-ticker state; adding a store would be premature. Will revisit when v0.5 introduces user/portfolio state |
| `cachetools.TTLCache` over Redis | Redis, memcached | Single-process is fine in dev; v0.5 migrates to Redis for multi-worker correctness |
| slowapi per-IP rate limit | API gateway / nginx limit | Library-level keeps limits portable across deploy targets; v0.5 switches to per-user (Redis-backed) |
| Tailwind + inline style | MUI, Ant Design | Full control over Apple HIG dark design without fighting component defaults |

---

# Target Architecture (v0.5)

> **This section is the design plan for the v0.5 pivot described in [ROADMAP.md](./ROADMAP.md). It is not yet implemented; the file paths below are proposed.**

The pivot turns DeepValue from a single-page analyzer into a multi-agent research platform. The v0.4 services (`buffett.py`, `valuation.py`, `moat.py`, `financial.py`) survive as **tools** that subagents invoke; the new layers are the harness, orchestration, persistence, advanced RAG, and observability.

## System Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                            Browser (React 18)                                  │
│  ┌──────────────────────────┐   ┌────────────────────────────────────────┐    │
│  │ Dashboard (v0.4 panels)  │   │ Agent Console                          │    │
│  │  Ratios · Valuation ·    │   │   • NL query input                     │    │
│  │  Moat · Charts · …       │   │   • Live trace panel (tool calls,      │    │
│  └──────────────────────────┘   │     args, results, latency, cost)      │    │
│                                  │   • Final report w/ source citations   │    │
│                                  └────────────────────────────────────────┘    │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │ HTTPS + SSE
                               ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI (async, OTel-instrumented)                     │
│  Auth (OAuth + JWT) · per-user rate limit (slowapi + Redis) · CORS · CSRF      │
│                                                                                │
│  Routes:                                                                       │
│   /api/auth/*         · /api/stock/* (v0.4)         · /api/chat                │
│   /api/agent/run      · /api/agent/{run_id}         · /api/agent/{run_id}/stream│
│   /api/evals/*        · /api/admin/*                · MCP transport (HTTP)     │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼─────────────────────────────────────────┐
        ▼                      ▼                                         ▼
┌──────────────────┐  ┌────────────────────────────────────┐  ┌──────────────────┐
│  Agent Harness   │  │  Domain Services (v0.4 carry-over) │  │   MCP Server      │
│  (self-authored) │  │   buffett · valuation · moat ·     │  │   stdio + HTTP    │
│                  │  │   financial · rag                  │  │   transports      │
│  ┌─────────────┐ │  └────────────────────────────────────┘  │   Tools exposed:  │
│  │ Orchestrator│ │                                          │   get_quote,      │
│  └──────┬──────┘ │  Tools (Pydantic-typed):                 │   get_buffett_… , │
│         ▼        │   • get_stock_quote                      │   search_filings, │
│  ┌────────────┐  │   • get_buffett_score                    │   …               │
│  │ Subagents  │  │   • get_valuation                        └──────────────────┘
│  │ • Fundamentals│ │   • get_moat                                    ▲
│  │ • News       │ │   • get_news                                    │ Claude Desktop / Cursor /
│  │ • Technical  │ │   • get_technicals                              │ any MCP client
│  │ • Valuation  │ │   • get_peer_comparison
│  │ • Risk       │ │   • search_filings (hybrid RAG)
│  └──────────────┘ │   • get_prior_analysis
│                   │   • web_search
│  Per step:        │
│   • plan          │
│   • dispatch tool │
│   • observe       │
│   • reflect       │
│   • persist       │
│   • emit SSE event│
└──────────┬────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16 (+ pgvector)                                  │
│   users · watchlists · portfolios                                              │
│   agent_runs(id, user_id, query, status, total_cost_usd, total_latency_ms,…)   │
│   agent_steps(run_id, step_idx, type, payload, latency_ms, tokens_in/out,cost) │
│   analyses · evals_runs · evals_scores                                         │
│   filings · filings_chunks (vector + bm25)                                     │
│   knowledge_chunks (vector)                                                    │
└────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐   ┌──────────────────────┐   ┌─────────────────────────────────┐
│   Redis 7    │   │   Celery / Arq        │   │  External LLM APIs              │
│   • cache    │   │   • nightly watchlist │   │   • Anthropic Haiku/Sonnet/Opus │
│   • broker   │   │     agent scan        │   │     (with prompt caching)       │
│   • pub/sub  │   │   • SEC EDGAR ingest  │   │   • Groq LLaMA (chat, cheap)    │
│   • rate-lim │   │   • eval regression   │   │   • Embedding APIs              │
└──────────────┘   └──────────────────────┘   └─────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│  Observability:  Langfuse (LLM traces)  ·  OpenTelemetry (request → run → LLM) │
│                  Prometheus + Grafana (RED metrics, cost, cache hit-rate)      │
│                  Sentry (errors)                                               │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Agent Harness

> Self-authored; no LangGraph. Interviewers will ask you to explain every layer — own it.

```
backend/app/agent/
├── runner.py           # AgentRunner: plan → act → observe → reflect state machine
├── tools/
│   ├── registry.py     # Tool registration + JSON schema generation from Pydantic
│   ├── dispatcher.py   # Async dispatcher: parallel calls, timeout, retry/backoff, sandbox
│   ├── financial.py    # Wraps services/financial.py
│   ├── buffett.py      # Wraps services/buffett.py
│   ├── valuation.py    # Wraps services/valuation.py
│   ├── moat.py         # Wraps services/moat.py
│   ├── news.py         # NewsAPI / Tavily
│   ├── technicals.py   # RSI / MACD / MAs
│   ├── peers.py        # Auto-fetch sector peers + ratio comparison
│   ├── filings.py      # search_filings — hybrid RAG over SEC corpus
│   ├── memory.py       # get_prior_analysis from agent_runs table
│   └── web.py          # Tavily / Brave fallback search
├── prompts/            # System prompts per role; few-shot examples; output schemas
├── models.py           # Pydantic: ResearchPlan, ToolCall, Observation, Finding, Report
├── router.py           # Model routing policy: role → Haiku|Sonnet|Opus
├── cache.py            # Anthropic prompt-cache helpers
├── state.py            # Persist agent_runs + agent_steps; resume(run_id)
└── stream.py           # SSE step emitter → Redis pub/sub → /api/agent/{id}/stream
```

**Loop invariant:**
1. **Plan** — orchestrator produces a `ResearchPlan` (typed) decomposing the user query into subagent tasks
2. **Dispatch** — subagents run (in parallel where independent); each subagent runs its own inner tool-use loop
3. **Observe** — each tool result and subagent `Finding` is persisted
4. **Reflect** — final orchestrator pass reviews findings, dedupes contradictions, can dispatch follow-up runs
5. **Synthesize** — structured `Report` (Pydantic) → rendered to UI + persisted

Every step writes a row to `agent_steps` with `tokens_in`, `tokens_out`, `cached_tokens`, `cost_usd`, `latency_ms`. `resume(run_id)` reconstructs the loop from the persisted trail and continues.

## Multi-Agent Orchestration

| Agent | Role | Tools it owns |
|---|---|---|
| **Orchestrator** | Decompose query → plan; dispatch subagents; reflect; synthesize | (calls subagents, not raw tools) |
| **Fundamentals** | Buffett ratios, DCF/EPV/ROIC/Graham, statement quality | `get_buffett_score`, `get_valuation`, `get_stock_quote` |
| **News & Sentiment** | Last N days news, event classification, sentiment scoring | `get_news`, `web_search` |
| **Technical** | Price action, RSI/MACD, support/resistance, volatility | `get_technicals`, `get_stock_quote` |
| **Valuation** | Peer comparison, sector medians, reverse-DCF implied growth | `get_peer_comparison`, `get_valuation` |
| **Risk** | 10-K risk factors, debt maturity wall, concentration | `search_filings(item="1A")`, `get_buffett_score` |

Subagents return typed `Finding` objects (claim + evidence + source ref + confidence). Orchestrator dedupes by topic, surfaces contradictions, and produces the final structured `Report`.

## Persistence Layer

```sql
-- PostgreSQL 16 + pgvector
CREATE TABLE users           (id, email, oauth_provider, created_at, …);
CREATE TABLE watchlists      (id, user_id, ticker, added_at);
CREATE TABLE portfolios      (id, user_id, ticker, qty, cost_basis, …);
CREATE TABLE agent_runs      (id, user_id, query, status, started_at, finished_at,
                              total_cost_usd, total_latency_ms, report_jsonb);
CREATE TABLE agent_steps     (id, run_id, step_idx, type, payload_jsonb,
                              tokens_in, tokens_out, cached_tokens, cost_usd, latency_ms);
CREATE TABLE filings         (cik, ticker, filing_type, fiscal_year, filing_date, url);
CREATE TABLE filings_chunks  (id, filing_id, item, chunk_idx, content, embedding vector(1024),
                              tsv tsvector);  -- pgvector + BM25/FTS
CREATE TABLE evals_runs      (id, suite, model_version, started_at, finished_at, score_avg);
CREATE TABLE evals_scores    (run_id, question_id, score, judgment_jsonb);
```

`cachetools` is replaced by Redis (multi-worker correctness). FAISS is replaced by `pgvector` (joinable with metadata, indexable, concurrent-safe).

## Hybrid RAG Pipeline

```
SEC EDGAR (daily cron)
   ↓ download 10-K / 10-Q / 8-K
filings_chunks ingest:
   • parse by Item (1A Risk Factors, 7 MD&A, 7A Market Risk, 8 Financial)
   • hierarchical chunking (parent doc → ~500-tok children, with overlap)
   • contextual retrieval: prepend doc-level context to each chunk (Anthropic technique)
   • embed (voyage-3 or text-embedding-3-small, 1024-dim)
   • write vector + tsvector (BM25/FTS) to filings_chunks

Query path (search_filings tool):
   query → embed
        → pgvector ANN top-50  +  Postgres tsvector BM25 top-50
        → merge + dedup
        → bge-reranker-v2-m3 cross-encoder → top-5
        → return chunks with parent-doc context + source URL + filing date
```

GraphRAG (optional): extract company-supplier-competitor entities into a graph table; orchestrator can traverse for "Who competes with NVDA?" types of queries.

## Eval Harness

```
backend/app/evals/
├── golden/                  # 100 manually-curated questions w/ reference answers
│   └── 2026-Q2.jsonl
├── judges/
│   ├── factual.py           # Sonnet judges factual accuracy
│   ├── grounding.py         # Sonnet judges citation grounding
│   └── completeness.py      # Sonnet judges report completeness
├── runner.py                # python -m deepvalue.evals run --suite golden --model sonnet
├── reporters/markdown.py
└── ci.py                    # PR-blocking sampled subset; nightly full run
```

Outputs land in `evals_runs` / `evals_scores`. `/evals` page surfaces score deltas per release.

## Observability Stack

| Concern | Tool | What it shows |
|---|---|---|
| LLM-level tracing | **Langfuse** (self-hosted) | Every LLM call w/ prompt, response, tokens, cost; agent-run tree view |
| Request-level tracing | **OpenTelemetry** | HTTP request → agent run → tool calls → LLM calls, all correlated |
| Metrics | **Prometheus + Grafana** | RED metrics per route, P50/P95/P99 latency, token spend/min, cache hit-rate |
| Errors | **Sentry** | Backend + frontend, source-mapped, release-tagged |
| Health | `/api/status` endpoint | DB, Redis, yfinance, Anthropic, Groq health checks |

## Migration Path: v0.4 → v0.5

Phased, non-breaking:

1. **Phase 7 (weeks 1–6)** — add `backend/app/agent/` alongside v0.4 routes; v0.4 keeps working. New `/api/agent/*` endpoints. UI gains an Agent Console tab but Dashboard is untouched.
2. **Phase 8 (weeks 7–10)** — introduce Postgres + Redis behind feature flags. Migrate `cachetools` → Redis first (low-risk). Migrate FAISS → pgvector. Add Auth gradually: agent endpoints require login first, v0.4 endpoints later. Wire Langfuse + OTel + Sentry.
3. **Phase 9 (weeks 11–14)** — start SEC EDGAR ingestion as a Celery job. `search_filings` tool comes online for subagents. Eval harness runs in CI from day one (initially red — that's fine, baseline first).
4. **Phase 10 (weeks 15–16)** — public deploy, collect metrics, open-source `deepvalue-harness` (the agent runner + tool registry, no domain code).

The v0.4 `services/*.py` modules are not refactored — they become library code that the new `agent/tools/*.py` shims wrap. This preserves the existing test surface and means Phase 7 can ship without touching financial logic.

---

*See [ROADMAP.md](./ROADMAP.md) for the phased build plan with success metrics, and the README for v0.4 user-facing capabilities.*
