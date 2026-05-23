# DeepValue Agent

> An AI-native, multi-agent investment research platform. Ask a natural-language question — *"Should I buy NVDA?"*, *"Compare AAPL vs MSFT in services margin trajectory"* — and a coordinated set of specialized agents autonomously plan the research, dispatch tools (financials, news, technicals, valuation, SEC filings), reflect on findings, and produce a structured, source-grounded report with end-to-end observability over every tool call, token, and dollar spent.

![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude-D97757?style=flat)
![Groq](https://img.shields.io/badge/Groq-LLaMA-F55036?style=flat)
![yfinance](https://img.shields.io/badge/yfinance-1.3-blueviolet?style=flat)

> **Status:** v0.6.1-beta. The self-authored **agent harness**, **multi-agent orchestrator** (Planner → Fundamentals + Technical subagents → Synthesizer), and **improved RAG** (Claude provider, multi-file knowledge base, markdown rendering + source citations) are all shipped. Next up: News / Valuation / Risk subagents, MCP server, Postgres persistence, SEC EDGAR pipeline + LLM-as-judge eval. See [ROADMAP.md](./ROADMAP.md) for the full 16-week plan.

---

## What makes this AI-native

| Layer | What it is | Status |
|---|---|---|
| **Self-authored agent harness** | Plan-act loop with Pydantic-typed tool registry, async dispatcher with timeout + retry, structured-output enforcement + repair, token/cost accounting (incl. cache reads/writes), SSE streaming traces | ✅ Shipped (Phase 7.1) |
| **Multi-agent orchestration** | Orchestrator decomposes the query into a `ResearchPlan`, dispatches subagents in parallel, returns structured `Finding` objects, then a Synthesizer produces the final report. Failed subagents degrade gracefully | ✅ Shipped (Phase 7.2 — Fundamentals + Technical; News / Valuation / Risk planned) |
| **Improved RAG** | Multi-file knowledge base (Buffett shareholder letters 2015-2024 + curated knowledge), per-chunk `source` metadata, auto-rebuild on source-file change, Claude provider (Haiku 4.5 chat / Sonnet 4.5 reco) with Groq fallback, markdown rendering + inline source citations in the UI | ✅ Shipped |
| **Prompt caching** | Anthropic ephemeral `cache_control` on system block + tools array tail; cache reads priced at 10%, writes at 125% — savings surface directly in `total_cost_usd` | ✅ Shipped |
| **Live agent UI** | Single-agent / multi-agent toggle, live trace panel streams every LLM / TOOL_BATCH / REPAIR / FINAL step as cards with tokens, cost, latency, attempt count, expandable JSON. Per-subagent Finding cards with citation chips → final Synthesis card | ✅ Shipped (Phase 7.6) |
| **MCP server** | All financial tools exposed via Model Context Protocol — pluggable into Claude Desktop, Cursor, any MCP client | 🔜 Phase 7.4 |
| **Hybrid RAG over SEC EDGAR** | BM25 + dense + cross-encoder rerank + contextual retrieval + GraphRAG over 10-K/10-Q | 🔜 Phase 9 |
| **LLM-as-judge eval harness** | 100-question golden set, regression in CI, hallucination-rate tracking per release | 🔜 Phase 9 |
| **Full observability** | Langfuse + OpenTelemetry + Prometheus + Sentry, every step traced with cost & latency | 🔜 Phase 8 |

---

## What's new in v0.6 (this release)

### Self-authored agent harness (`app/agent/`)
A from-scratch plan-act loop — no LangGraph, no langchain — built around three primitives:
- **Tool registry** (`tools/registry.py`) — Pydantic-typed tool definitions; JSON schemas auto-generated for the Anthropic API; runtime arg validation. Tools never raise — failures land in `ToolResult.error`.
- **Dispatcher** (`tools/dispatcher.py`) — async execution, **parallel** tool calls per turn, per-tool `wait_for` timeout, retry with exponential backoff.
- **Runner** (`runner.py`) — drives the loop, enforces structured output against an optional `output_schema`, emits a `REPAIR` step + retries up to `max_repairs` on parse failure, accounts tokens / cost / cache reads / cache writes / latency per LLM call. `runner.stream()` async generator powers the SSE endpoint.

**6 tools wired** — `get_stock_quote`, `get_buffett_score`, `get_valuation`, `get_moat`, `get_price_history`, `get_technicals`. All reuse the existing `services/` modules.

### Multi-agent orchestration (`app/agent/orchestrator.py`, `app/agent/subagents/`)
Three-stage pipeline:
1. **Planner** (no tools, structured output) decomposes the query into a `ResearchPlan` — list of `(role, ticker)` tasks.
2. **Subagents** run in parallel, each with its own restricted tool subset and `output_schema=Finding`:
   - **Fundamentals** — `get_stock_quote` · `get_buffett_score` · `get_valuation` · `get_moat`
   - **Technical** — `get_stock_quote` · `get_price_history` · `get_technicals`
3. **Synthesizer** (no tools) receives the JSON-serialized findings as a user message and writes the final Buffett-format verdict.

Partial-failure semantics: any subagent that errors lands as a `SUBAGENT` step with `finding=None`; the run continues if at least one finding made it.

### Improved RAG (`app/services/rag.py`)
- **Multi-file knowledge base** — scans `data/buffett_knowledge.txt` + every `.txt` under `data/buffett_letters/`; attaches `source` metadata per chunk; rebuilds FAISS automatically when source files change (signature file).
- **Letter fetcher** — `scripts/fetch_buffett_letters.py` downloads 2015-2024 Berkshire shareholder letters (PDF → text). Letters dir is gitignored.
- **Claude provider** — chat uses Haiku 4.5, recommendation uses Sonnet 4.5, when `ANTHROPIC_API_KEY` is set; automatic Groq fallback. Force the old path with `CHAT_PROVIDER=groq`.
- **Markdown + citations in the UI** — chat answers render markdown and each answer lists the source chunks it pulled from. Prompts generalized from Buffett-only to broader value investing.

### Live multi-agent UI (`frontend/src/components/Agent/`)
- Single-agent / multi-agent toggle in the Agent panel.
- Multi-agent trace streams `plan` → per-subagent `Finding` cards (summary + bullets + tool-name citation chips) → final `Synthesis` card.
- Footer rolls up wall-clock, total cost, token totals, and `n_findings / n_subagents`. Run is abortable mid-flight.

---

## v0.4 — What still works (foundation)

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

| Layer | v0.6 (now) | Next (see ROADMAP) |
|---|---|---|
| Frontend | React 18 · TypeScript · Vite · Tailwind · Recharts · **live agent trace panel** · markdown chat rendering | OAuth login, PDF export |
| Backend | FastAPI · async Python 3.11 · Uvicorn · **self-authored agent harness** | Celery/Arq workers, OTel middleware |
| Persistence | `cachetools.TTLCache` (in-memory) · localStorage · FAISS file index | PostgreSQL + pgvector · Redis · resumable agent runs |
| Financial Data | yfinance — no API key | + SEC EDGAR pipeline · NewsAPI/Tavily |
| LLM | **Anthropic Claude** (Haiku 4.5 chat / Sonnet 4.5 reco + agent harness) with **Groq fallback** (LLaMA 3.1-8B / 3.3-70B) · **prompt caching** on system + tools | Full Haiku→Sonnet→Opus routing per subagent role |
| Vector / RAG | FAISS + `all-MiniLM-L6-v2` (384-dim) · **multi-file knowledge base** · per-chunk source metadata · auto-rebuild on change | pgvector + voyage-3/text-embedding-3-small + cross-encoder reranker + GraphRAG |
| Agent | **Self-authored harness** (tool registry, dispatcher, runner, structured-output + repair) · **Orchestrator + Fundamentals + Technical subagents** · 6 tools | News / Valuation / Risk subagents · Reflexion · MCP server · resumable runs |
| Streaming | **SSE** for chat tokens · agent step events · multi-agent plan/subagent/synth events | Per-claim source deep-links |
| Observability | Per-step token/cost/cache/latency in API response | Langfuse · OpenTelemetry · Prometheus · Grafana · Sentry |
| Rate Limit | `slowapi` per-IP | Per-user (Redis-backed) |
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
# Anthropic (agent harness + multi-agent orchestrator + preferred chat/reco)
ANTHROPIC_API_KEY=your_anthropic_key_here
ANTHROPIC_MODEL=claude-sonnet-4-5
AGENT_MAX_ITERS=8

# Groq (fallback for chat + recommendation if Anthropic key is missing)
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
GROQ_RECOMMENDATION_MODEL=llama-3.3-70b-versatile

# CORS (CSV); CHAT_PROVIDER=groq forces the old non-Anthropic path
ALLOWED_ORIGINS=http://localhost:5173
```

> Without `ANTHROPIC_API_KEY`, all `/api/agent/*` endpoints return 503. Chat and recommendation will automatically use Groq.

(Optional) Fetch the Buffett shareholder letters for a richer RAG corpus:

```bash
cd backend && .venv/bin/python -m scripts.fetch_buffett_letters
# Downloads 2015-2024 letters into data/buffett_letters/ (gitignored)
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

## API Endpoints

### Stock data
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
| POST | `/api/chat` | — | SSE — streaming RAG chat (markdown + source citations, stock context + history) |

### Agent (Phase 7)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/agent/tools` | List registered tools + their JSON schemas |
| POST | `/api/agent/run` | Run the single-agent harness to completion; returns full `AgentRun` (steps + usage + cost) |
| POST | `/api/agent/stream` | SSE — single-agent run; events: `llm`, `tool_batch`, `repair`, `final`, `error`, `done` |
| POST | `/api/agent/orchestrate` | Run the multi-agent orchestrator to completion; returns `OrchestratorRun` (plan + per-subagent findings + synthesis) |
| POST | `/api/agent/orchestrate/stream` | SSE — multi-agent run; events: `plan`, `subagent`, `synth`, `error`, `done` |

All `/api/agent/*` endpoints require `ANTHROPIC_API_KEY` (return 503 otherwise).

Coming next: `/api/auth/*` (OAuth, Phase 8), `/api/agent/{run_id}/resume` (Phase 8 — needs Postgres), and an MCP server with `stdio` + `streamable-http` transports (Phase 7.4).

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

## Project Structure (v0.6)

```
DeepValue/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI entry · CORS · slowapi · lifespan (FAISS init)
│   │   ├── config.py                    # Env vars, ALLOWED_ORIGINS, ANTHROPIC_MODEL, AGENT_MAX_ITERS
│   │   ├── limiter.py                   # slowapi Limiter instance
│   │   ├── api/routes/
│   │   │   ├── stock.py                 # quote · ratios · financials · history · valuation · moat · recommendation
│   │   │   ├── chat.py                  # SSE streaming chat (markdown + source citations)
│   │   │   └── agent.py                 # /run · /stream · /orchestrate · /orchestrate/stream · /tools
│   │   ├── agent/                       # ── NEW · self-authored harness ────────────────
│   │   │   ├── llm.py                   # Anthropic client; cost + cache-token accounting
│   │   │   ├── models.py                # AgentRun, AgentStep, ToolCall, ToolResult, LLMUsage, Finding…
│   │   │   ├── prompts.py               # System prompts for orchestrator + subagents
│   │   │   ├── runner.py                # Plan-act loop, structured-output enforcement + REPAIR
│   │   │   ├── structured.py            # JSON-schema hint injection + output parser/validator
│   │   │   ├── orchestrator.py          # Planner → parallel subagents → Synthesizer + SSE
│   │   │   ├── tools/
│   │   │   │   ├── registry.py          # Pydantic-typed tool defs, auto JSON-schema
│   │   │   │   ├── dispatcher.py        # Async dispatch · timeout · retry · parallel batches
│   │   │   │   └── financial_tools.py   # 6 tools: quote · buffett · valuation · moat · history · technicals
│   │   │   └── subagents/
│   │   │       ├── fundamentals.py      # Buffett + valuation + moat → Finding
│   │   │       └── technical.py         # RSI / MACD / SMA / drawdown → Finding
│   │   ├── services/
│   │   │   ├── financial.py             # async yfinance + cachetools.TTLCache
│   │   │   ├── buffett.py               # 14 ratios + sector-aware thresholds + trend adjustment
│   │   │   ├── valuation.py             # DCF / Graham / FCF Yield Value / EPV / ROIC / P-FCF
│   │   │   ├── moat.py                  # Competitive moat classification
│   │   │   ├── technicals.py            # RSI / MACD / SMA / volatility
│   │   │   └── rag.py                   # FAISS multi-file index, Claude→Groq fallback, citations
│   │   └── data/
│   │       ├── buffett_knowledge.txt
│   │       ├── buffett_letters/         # ── NEW · gitignored, populated by fetch script
│   │       └── faiss_index/             # auto-rebuilt on source change
│   ├── scripts/
│   │   └── fetch_buffett_letters.py     # ── NEW · downloads 2015-2024 shareholder letters
│   ├── tests/
│   │   ├── agent/                       # ── NEW · harness, orchestrator, subagents (offline)
│   │   └── services/                    # buffett, valuation, moat, rag, financial
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── App.tsx                      # Root: Header + Sidebar + Dashboard + ChatDrawer
        ├── api/client.ts                # stock fetches · streamChat/Recommendation · agent SSE clients
        ├── context/
        │   ├── StockContext.tsx         # ticker, quote, ratios, valuation, moat, recommendation
        │   └── WatchlistContext.tsx     # localStorage-backed watchlist
        ├── types/index.ts
        ├── utils/currency.ts            # Multi-market currency symbol helper
        └── components/
            ├── Header.tsx · StockSearch.tsx · Sidebar.tsx · ErrorBoundary.tsx · ChatDrawer.tsx
            ├── Agent/                   # ── NEW
            │   ├── AgentPanel.tsx       # Single-agent / multi-agent toggle, query textarea, abort
            │   ├── TraceCard.tsx        # LLM / TOOL_BATCH / REPAIR / FINAL / ERROR cards
            │   ├── FindingCard.tsx      # Per-subagent Finding + citation chips
            │   └── SummaryBar.tsx       # Wall-clock · cost · tokens · n_findings/n_subagents
            ├── Dashboard/
            │   ├── index.tsx            # Tabs: Ratios | Chart | Valuation | Moat | Statements | Watchlist | AI
            │   ├── StockOverview.tsx · RatioTable.tsx · RatioChart.tsx
            │   ├── PriceHistoryChart.tsx · ValuationPanel.tsx · MoatCard.tsx
            │   ├── StatementTable.tsx · Watchlist.tsx · AIRecommendation.tsx
            └── Chatbot/
                └── ChatWindow.tsx       # Markdown rendering + per-message source chips
```

For the long-term target (MCP server + workers + Postgres + Langfuse + SEC EDGAR), see [ARCHITECTURE.md](./ARCHITECTURE.md#target-architecture-v05).

---

## Supported Tickers

Any ticker supported by Yahoo Finance:

- **US**: `AAPL`, `MSFT`, `KO`, `BRK-B`, `NVDA`
- **Hong Kong**: `0700.HK` (Tencent), `9988.HK` (Alibaba)
- **A-shares**: `600519.SS` (Kweichow Moutai), `000858.SZ` (Wuliangye)

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the full 16-week build plan. Headline items:

- **Phase 7 (weeks 1–6) — Agent System & Harness:** ✅ harness shipped (7.1) · ✅ Orchestrator + Fundamentals + Technical (7.2) · ✅ live multi-agent UI (7.6) · ✅ prompt caching (7.5) · 🔜 News / Valuation / Risk subagents · 🔜 MCP server (7.4) · 🔜 Reflexion pass · 🔜 model routing
- **Phase 8 (weeks 7–10) — Enterprise Infrastructure:** PostgreSQL + pgvector + Redis + Celery, OAuth + multi-tenancy, Langfuse + OTel + Prometheus + Sentry, Docker + GitHub Actions CI
- **Phase 9 (weeks 11–14) — Advanced RAG + Eval Harness:** SEC EDGAR pipeline, hybrid + contextual + GraphRAG, LLM-as-judge in CI, golden dataset
- **Phase 10 (weeks 15–16) — Launch:** public deploy, blog post, open-source `deepvalue-harness`, collected resume metrics

---

## License

MIT
