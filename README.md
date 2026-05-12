# DeepValue Agent

> An AI-native, multi-agent investment research platform. Ask a natural-language question — *"Should I buy NVDA?"*, *"Compare AAPL vs MSFT in services margin trajectory"* — and a coordinated set of specialized agents autonomously plan the research, dispatch tools (financials, news, technicals, valuation, SEC filings), reflect on findings, and produce a structured, source-grounded report with end-to-end observability over every tool call, token, and dollar spent.

![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude-D97757?style=flat)
![Groq](https://img.shields.io/badge/Groq-LLaMA-F55036?style=flat)
![yfinance](https://img.shields.io/badge/yfinance-1.3-blueviolet?style=flat)

> **Status:** v0.4 ships a full single-agent value-investing analyzer (14-metric Buffett score, DCF/EPV/ROIC valuation, moat classification, RAG chat). v0.5 — *in progress* — is an AI-native pivot to a multi-agent harness with MCP server, hybrid RAG over SEC filings, LLM-as-judge eval harness, and full observability stack. See [ROADMAP.md](./ROADMAP.md) for the 16-week build plan.

---

## What makes this AI-native (v0.5 target)

| Layer | What it is | Why it matters |
|---|---|---|
| **Self-authored agent harness** | Plan-act-reflect loop with tool registry, sandboxing, retry, persistent state, resumable runs | Demonstrates agentic-system design end-to-end (not just `langgraph.invoke`) |
| **Multi-agent orchestration** | Orchestrator + 5 specialized subagents (Fundamentals, News, Technical, Valuation, Risk) | Real task decomposition, inter-agent messaging, reflexion |
| **MCP server** | All financial tools exposed via Model Context Protocol | Pluggable into Claude Desktop, Cursor, or any MCP client |
| **Hybrid RAG over SEC EDGAR** | BM25 + dense + cross-encoder rerank + contextual retrieval + GraphRAG over 10-K/10-Q | State-of-the-art retrieval grounded in primary sources |
| **Model routing + prompt caching** | Haiku → Sonnet → Opus by role; ephemeral cache on system prompt | Quantified cost reduction (target ≥ 60% vs Opus-only baseline) |
| **LLM-as-judge eval harness** | 100-question golden set, regression in CI, hallucination-rate tracking | Quality engineering practice mirroring how LLM products are actually shipped |
| **Full observability** | Langfuse + OpenTelemetry + Prometheus + Sentry, every step traced with cost & latency | Production-grade visibility (resume keyword: SRE-friendly LLM ops) |

---

## v0.4 — What works today

### Buffett Score (0–100) — sector-adjusted, trend-aware
14 financial metrics derived from Buffett's principles, each weighted by importance. Thresholds adapt per sector (tech R&D allowance, financials leverage tolerance). Three-year improving trends earn a bonus; deteriorating metrics incur a penalty. Score is normalized over non-N/A metrics so missing data never artificially deflates it.

| Category | Metrics |
|---|---|
| Income Statement | Gross Margin, SG&A Margin, R&D Margin, Depreciation Margin, Interest Expense Margin, Effective Tax Rate, Net Profit Margin, EPS Growth |
| Balance Sheet | Cash vs Current Debt, Adj. Debt-to-Equity, Preferred Stock, Retained Earnings Growth, Treasury Stock |
| Cash Flow | CapEx Margin |

### Valuation Engine
Four independent intrinsic-value models with live-adjustable assumptions:
- **DCF Calculator** — 10-year free-cash-flow projection discounted at WACC + Gordon Growth terminal. Sliders for growth, discount, terminal rates.
- **Graham Number** — `√(22.5 × EPS × BVPS)`.
- **FCF Yield Valuation** — fair value from normalized FCF yield vs 10Y Treasury.
- **Earnings Power Value (EPV)** — Bruce Greenwald's no-growth DCF variant.

Plus **ROIC**, **Price-to-FCF**, a **Margin-of-Safety gauge**, and a **Circle of Competence** complexity flag.

### Competitive Moat Classification
Auto-classified Wide / Narrow / None rating across five moat types (Brand, Network Effect, Cost Advantage, Switching Costs, Efficient Scale), derived from gross margin, ROE, FCF yield, operating margins, and revenue growth.

### Extended Quote Data
Sector / Industry, Forward P/E, PEG, EV/EBITDA, FCF Yield, ROE, ROA, Revenue Growth, Earnings Growth, Dividend Yield, 52-Week Range, Analyst Price Targets — all from Yahoo Finance, no API key.

### Streaming AI Recommendation (current)
Sector-aware, few-shot, structured output (Verdict / Strengths / Concerns / Buffett Alignment / Modern Context). Streams token-by-token over SSE from Groq LLaMA 3.3-70B. Prompt injects business summary, all 14 weighted metrics, modern valuation data, multi-year trends.

### RAG Chat Advisor
Multi-turn chat grounded in a Buffett knowledge base via FAISS + sentence-transformers. Streams from Groq LLaMA 3.1-8B with full conversation history.

### Watchlist & Multi-Market
LocalStorage watchlist with add/remove and persistence. Currency symbols adapt per market (`$` US, `HK$` Hong Kong, `¥` A-shares).

### Production-grade Backend Hygiene
Async yfinance via `asyncio.to_thread`, `cachetools.TTLCache` (15-min quote / 30-min history), `slowapi` rate limiting per route, ticker input sanitization, configurable `ALLOWED_ORIGINS`, React Error Boundary.

---

## Tech Stack

| Layer | v0.4 (now) | v0.5 (target — see ROADMAP) |
|---|---|---|
| Frontend | React 18 · TypeScript · Vite · Tailwind · Recharts | + live agent trace panel, OAuth login |
| Backend | FastAPI · async Python 3.11 · Uvicorn | + Celery/Arq workers, OTel middleware |
| Persistence | `cachetools.TTLCache` (in-memory) · localStorage | PostgreSQL + pgvector · Redis |
| Financial Data | yfinance — no API key | + SEC EDGAR pipeline · NewsAPI/Tavily |
| LLM | Groq LLaMA 3.1-8B (chat) · LLaMA 3.3-70B (recs) | + Anthropic Claude (Haiku/Sonnet/Opus) with model routing + prompt caching |
| Vector / RAG | FAISS + `all-MiniLM-L6-v2` (384-dim) | pgvector + voyage-3/text-embedding-3-small + cross-encoder reranker + GraphRAG |
| Agent | Single-shot prompt | Self-authored harness + 5 subagents + MCP server |
| Streaming | Server-Sent Events | SSE for tokens + agent step events |
| Observability | — | Langfuse · OpenTelemetry · Prometheus · Grafana · Sentry |
| Rate Limit | `slowapi` per-IP | `slowapi` per-user (Redis-backed) |
| Eval | — | LLM-as-judge harness, golden set, CI regression |
| Deployment | Local dev | Docker Compose · GitHub Actions CI · Fly.io / Railway |

---

## Getting Started

### Prerequisites
- Python 3.11
- Node.js 18+
- [Groq API key](https://console.groq.com) — free tier, no credit card

### 1. Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
GROQ_RECOMMENDATION_MODEL=llama-3.3-70b-versatile
ALLOWED_ORIGINS=http://localhost:5173
```

```bash
uvicorn app.main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

> Vite dev server proxies `/api` → `localhost:8000`.

---

## API Endpoints (v0.4)

| Method | Endpoint | Rate Limit | Description |
|---|---|---|---|
| GET | `/api/health` | — | Health check |
| GET | `/api/stock/{ticker}/quote` | 30/min | Price, market cap, ROE, PEG, FCF yield, sector, currency… |
| GET | `/api/stock/{ticker}/ratios` | 20/min | 14 Buffett ratios + weighted score + trend adjustment |
| GET | `/api/stock/{ticker}/financials` | 20/min | Income / Balance / Cash Flow (4 yrs) |
| GET | `/api/stock/{ticker}/history` | 20/min | OHLCV history (period: `1d`/`5d`/`1mo`/`3mo`/`6mo`/`1y`/`2y`/`5y`) |
| GET | `/api/stock/{ticker}/valuation` | 20/min | DCF + Graham + FCF Yield Value + EPV + ROIC |
| GET | `/api/stock/{ticker}/moat` | 20/min | Moat strength + dominant type |
| POST | `/api/stock/recommendation` | 5/min | SSE — streaming AI investment recommendation |
| POST | `/api/chat` | — | SSE — streaming RAG chat with stock context + history |

v0.5 will add: `/api/agent/run` (start a research run), `/api/agent/{run_id}` (stream steps + final report), `/api/auth/*` (OAuth), and MCP `stdio` / `streamable-http` transports.

---

## Weighted Scoring

Each metric carries a weight reflecting its importance. The score is normalized to exclude N/A metrics:

```
Score = Σ(weight_i  where passes == True)
        ─────────────────────────────────── × 100   +   trend_adjustment ∈ [−10, +10]
        Σ(weight_i  where passes != None)
```

| Weight | Metrics |
|---|---|
| 13% | Gross Margin |
| 11% | Net Profit Margin |
| 10% | EPS Growth |
| 9% | Adj. Debt-to-Equity, Retained Earnings Growth |
| 8% | Interest Expense Margin, Cash vs Current Debt, CapEx Margin |
| 7% | SG&A Margin |
| 6% | Depreciation Margin |
| 5% | Effective Tax Rate |
| 4% | R&D Margin |
| 1% | Preferred Stock, Treasury Stock |

---

## Project Structure (v0.4)

```
DeepValue/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI entry · CORS · slowapi · lifespan (FAISS init)
│   │   ├── config.py                    # Env vars, ALLOWED_ORIGINS
│   │   ├── limiter.py                   # slowapi Limiter instance
│   │   ├── api/routes/
│   │   │   ├── stock.py                 # quote · ratios · financials · history · valuation · moat · recommendation
│   │   │   └── chat.py                  # SSE streaming chat with history
│   │   ├── services/
│   │   │   ├── financial.py             # async yfinance + cachetools.TTLCache
│   │   │   ├── buffett.py               # 14 ratios + sector-aware thresholds + trend adjustment
│   │   │   ├── valuation.py             # DCF / Graham / FCF Yield Value / EPV / ROIC / P-FCF
│   │   │   ├── moat.py                  # Competitive moat classification
│   │   │   └── rag.py                   # FAISS, retrieval, Groq streaming (chat + recommendation)
│   │   └── data/
│   │       ├── buffett_knowledge.txt
│   │       └── faiss_index/             # auto-generated
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── App.tsx                      # Root: Header + Sidebar + Dashboard + ChatDrawer
        ├── api/client.ts                # fetchQuote/Ratios/Financials/Valuation/Moat/History · streamChat/Recommendation
        ├── context/
        │   ├── StockContext.tsx         # ticker, quote, ratios, valuation, moat, recommendation
        │   └── WatchlistContext.tsx     # localStorage-backed watchlist
        ├── types/index.ts
        ├── utils/currency.ts            # Multi-market currency symbol helper
        └── components/
            ├── Header.tsx · StockSearch.tsx · Sidebar.tsx · ErrorBoundary.tsx · ChatDrawer.tsx
            ├── Dashboard/
            │   ├── index.tsx            # Tabs: Ratios | Chart | Valuation | Moat | Statements | Watchlist | AI
            │   ├── StockOverview.tsx · RatioTable.tsx · RatioChart.tsx
            │   ├── PriceHistoryChart.tsx · ValuationPanel.tsx · MoatCard.tsx
            │   ├── StatementTable.tsx · Watchlist.tsx · AIRecommendation.tsx
            └── Chatbot/
                └── ChatWindow.tsx
```

For the v0.5 target structure (agent harness + multi-agent + MCP server + workers + observability), see [ARCHITECTURE.md](./ARCHITECTURE.md#target-architecture-v05).

---

## Supported Tickers

Any ticker supported by Yahoo Finance:

- **US**: `AAPL`, `MSFT`, `KO`, `BRK-B`, `NVDA`
- **Hong Kong**: `0700.HK` (Tencent), `9988.HK` (Alibaba)
- **A-shares**: `600519.SS` (Kweichow Moutai), `000858.SZ` (Wuliangye)

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the full 16-week build plan. Headline items:

- **Phase 7 (weeks 1–6) — Agent System & Harness:** self-authored harness, 5 subagents, MCP server, model routing, streaming agent traces
- **Phase 8 (weeks 7–10) — Enterprise Infrastructure:** PostgreSQL + pgvector + Redis + Celery, OAuth + multi-tenancy, Langfuse + OTel + Prometheus + Sentry, Docker + GitHub Actions CI
- **Phase 9 (weeks 11–14) — Advanced RAG + Eval Harness:** SEC EDGAR pipeline, hybrid + contextual + GraphRAG, LLM-as-judge in CI, golden dataset
- **Phase 10 (weeks 15–16) — Launch:** public deploy, blog post, open-source `deepvalue-harness`, collected resume metrics

---

## License

MIT
