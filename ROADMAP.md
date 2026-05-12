# DeepValue Agent — Product Roadmap

> **Goal:** An AI-native, multi-agent investment research platform. Users ask natural-language questions ("Should I buy NVDA?", "Compare AAPL vs MSFT in cloud margin trajectory"), and the system autonomously plans research, dispatches specialized subagents (Fundamentals / News / Technical / Valuation / Risk), retrieves SEC filings, reflects on findings, and produces a structured, source-grounded report — with full observability over every tool call, token cost, and latency P95.
>
> **Resume narrative:** *"Designed and built a production multi-agent investment research platform. Self-authored agent harness with plan-act-reflect loop, tool sandboxing, and resumable execution. Orchestrator coordinates 5 specialized subagents. Hybrid RAG (BM25 + dense + cross-encoder rerank + GraphRAG) over SEC EDGAR. Multi-model routing across Haiku/Sonnet/Opus + Anthropic prompt caching cut average inference cost by X%. LLM-as-judge eval harness tracks hallucination rate per release. Postgres+pgvector / Redis / Celery / Docker / GitHub Actions / Langfuse. Exposed all financial tools as an MCP server for client interoperability."*

---

## Current State (v0.4)

- 14 Buffett metrics with weighted scoring (0–100), sector-adjusted thresholds, trend bonus/penalty
- yfinance data backend — no API key required (US/HK/A-shares)
- Extended quote data: ROE, PEG, FCF Yield, Forward P/E, EV/EBITDA, Revenue Growth, Sector/Industry
- RAG-powered chat advisor (Groq LLaMA 3.1-8B + FAISS) with multi-turn history
- Streaming AI investment recommendation (Groq LLaMA 70B) with sector-aware few-shot prompts
- Valuation engine: DCF, Graham Number, FCF Yield Value, EPV, ROIC, Margin of Safety, Circle of Competence
- Competitive moat classifier: 5 moat types × Wide/Narrow/None strength rating
- Financial statement viewer (Income / Balance / Cash Flow)
- Watchlist (localStorage) with add/remove and persistent state
- Price history chart
- Apple HIG dark UI — bar chart, ratio cards, score gauge, valuation panel, moat card
- API rate limiting (slowapi) + async yfinance calls + ticker input sanitization

---

## Phase 0 — Technical Debt & Bug Fixes (Fix Before Next Feature)

> These are architecture problems identified in code review. Must be resolved before the project scales.

### P0 — Critical (breaks correctness or security)

- [x] **`lru_cache` has no TTL** (`financial.py`)
  — Replaced with `cachetools.TTLCache(maxsize=64, ttl=900)` (15-min expiry). Stale data now auto-evicts.

- [x] **Chat is single-turn — no conversation history** (`rag.py` / `ChatWindow.tsx`)
  — `ChatWindow` now captures completed messages as `history` before each send. `POST /api/chat` accepts `history: list[dict]`. `rag.py` builds a proper `[system, ...history, user]` message list for Groq.

- [x] **CORS origin hardcoded to `localhost:5173`** (`main.py`)
  — Reads `ALLOWED_ORIGINS` env var (comma-separated). Falls back to `http://localhost:5173` if unset.

### P1 — High (degrades quality or creates risk)

- [x] **LLM model too small for financial reasoning** (`rag.py`)
  — `stream_recommendation()` now uses `GROQ_RECOMMENDATION_MODEL` (default `llama-3.3-70b-versatile`). Chat keeps 8B for speed.

- [x] **AI Pick recommendation lost on tab switch** (`AIRecommendation.tsx`)
  — `recommendation: {text, ticker, streaming}` lifted into `StockContext`. Tab switches no longer destroy it.

- [x] **Prompt uses single `user` message — no system/user separation** (`rag.py`)
  — All prompts now split into `[{role: "system", content: persona}, {role: "user", content: data+question}]`.

- [x] **Ticker input not sanitized — prompt injection risk** (`stock.py`)
  — All route handlers call `_validate_ticker()` which enforces `^[A-Z0-9.\-]{1,10}$` before processing.

- [x] **`assert` used for weight validation in production code** (`buffett.py`)
  — Replaced with explicit `if not ...: raise ValueError(...)`.

### P2 — Medium (performance / UX)

- [x] **yfinance calls are synchronous — blocks FastAPI event loop** (`financial.py`)
  — `get_stock_quote` / `get_stock_data` are now `async` and wrap sync fetchers with `asyncio.to_thread`. All stock route handlers are `async def`.

- [x] **Search clears stale data immediately** (`StockContext.tsx`)
  — Removed pre-search `setRatios([])` / `setFinancials(null)`. Previous data stays visible until new data arrives (stale-while-revalidate). Error no longer clears data either.

- [x] **No React Error Boundary**
  — `ErrorBoundary.tsx` added. `<Dashboard>` and `<ChatWindow>` both wrapped in `App.tsx`.

### P3 — Low (quality improvements)

- [ ] **RAG uses small 384-dim embeddings with no re-ranking** (`rag.py`)
  — `all-MiniLM-L6-v2` is a general-purpose model. Retrieval quality for financial terminology is limited.
  — Fix (later): add a cross-encoder re-ranking step, or switch to a finance-tuned embedding model.

- [ ] **Knowledge base is a single static file** (`buffett_knowledge.txt`)
  — All queries retrieve from the same undifferentiated corpus regardless of sector or question type.
  — Fix (later): split into domain-specific documents (Buffett principles, tech sector, consumer staples, etc.) and tag with metadata for filtered retrieval.

- [x] **No rate limiting on API routes**
  — A single client can flood yfinance with requests, triggering Yahoo Finance IP bans.
  — Fix: add `slowapi` rate limiter (e.g. 10 req/min per IP on stock endpoints).

---

## Phase 1 — Data & Intelligence Upgrade (Current Sprint)

**Goal:** Make the analysis richer and the AI recommendation meaningfully better.

### 1.1 Expanded Quote Data
- [x] Sector / Industry classification
- [x] ROE, ROA from yfinance `.info`
- [x] Revenue Growth, Earnings Growth (YoY)
- [x] PEG Ratio, Forward P/E
- [x] FCF Yield (Free Cash Flow / Market Cap)
- [x] Dividend Yield & Payout Ratio
- [x] EV/EBITDA (enterprise value multiple)
- [x] Insider ownership percentage

### 1.2 AI Recommendation Quality
- [x] Company business summary in prompt context
- [x] Sector/industry framing
- [x] Multi-year trend data for key metrics
- [x] Modern metrics (ROE, FCF Yield, PEG) in context
- [x] Few-shot example in system prompt
- [ ] Prompt caching for repeated tickers

### 1.3 Scoring Refinements
- [x] Industry-adjusted thresholds (e.g., R&D threshold higher for tech)
- [x] Trend bonus: metrics that improved 3 years in a row get +weight
- [x] Penalty system: metrics in freefall get negative weight

### 1.4 StockOverview Panel
- [x] Sector & Industry display
- [x] ROE, Forward P/E, FCF Yield display
- [x] 52-week high/low bar
- [x] Analyst consensus (from yfinance `.info`)

---

## Phase 2 — Valuation Engine (Month 2)

**Goal:** Give users a concrete estimate of intrinsic value and margin of safety.

### 2.1 Intrinsic Value Models
- [x] **DCF Calculator** — 10-year discounted cash flow with user-adjustable growth rate and discount rate
- [x] **Graham Number** — √(22.5 × EPS × BVPS) — classic Ben Graham formula
- [x] **FCF Yield Valuation** — fair value based on normalized FCF yield vs 10Y Treasury
- [x] **Earnings Power Value (EPV)** — Bruce Greenwald's no-growth DCF variant

### 2.2 Margin of Safety
- [x] Display current price vs estimated intrinsic value range
- [x] Visual margin-of-safety gauge (price vs value)
- [x] "Buffett Circle of Competence" check — flag highly complex businesses

### 2.3 Modern Valuation Metrics
- [x] **ROIC** (Return on Invested Capital) — Buffett's preferred efficiency metric
- [ ] **EV/EBITDA** comparison vs sector median
- [x] **Price-to-FCF** ratio
- [ ] **PEG Ratio** interpretation (growth-adjusted value)

---

## Phase 3 — Stock Screener (Month 2–3)

**Goal:** Let users discover stocks that meet Buffett criteria, not just analyze one at a time.

### 3.1 Buffett Screen
- [ ] Pre-built screen: Weighted Score ≥ 70 + Gross Margin ≥ 40% + Net Margin ≥ 20%
- [ ] Configurable filters: sector, market cap, exchange
- [ ] S&P 500 batch analysis (top 100 by score)
- [ ] Results ranked by weighted Buffett score

### 3.2 Custom Screener
- [ ] Drag-and-drop metric filter builder
- [ ] Save/load custom screen presets
- [ ] Export results to CSV

### 3.3 Watchlist
- [x] Save stocks to personal watchlist (localStorage)
- [ ] Daily score change notifications (if backend cron job)
- [ ] Side-by-side comparison of up to 4 stocks

---

## Phase 4 — Modern Investment Concepts (Month 3–4)

**Goal:** Evolve beyond pure Buffett criteria to incorporate frameworks Buffett himself has adapted to.

### 4.1 Quality Investing Overlay
- [ ] **ROIC vs WACC spread** — economic profit indicator
- [ ] **Capital Allocation Score** — buyback history, dividend growth, acquisition discipline
- [ ] **Management Compensation Alignment** — CEO pay vs EPS growth ratio
- [ ] **Insider Ownership** threshold check (Buffett prefers owner-operators)

### 4.2 Competitive Moat Classification
- [x] Auto-classify moat type based on metrics:
  - Network Effect (platform companies, high gross margin)
  - Switching Costs (high retention, recurring revenue)
  - Cost Advantage (low CapEx, economies of scale)
  - Intangible Assets (brand, patents — high gross margin + low R&D need)
  - Efficient Scale (regulated monopolies, utilities)
- [x] Moat strength rating: Wide / Narrow / None

### 4.3 Industry-Aware Scoring
- [x] Sector-specific metric weights (tech vs consumer vs financials vs utilities) — `_sector_threshold()` in `buffett.py`
- [ ] Peer comparison: how does the stock rank within its sector?
- [ ] Sector median benchmarks for each metric

### 4.4 Macro Context
- [ ] Interest rate sensitivity flag (high-debt companies warned in rising rate environments)
- [ ] Fed Funds Rate overlay on valuation multiples
- [ ] Recession resilience score (based on revenue stability, cash position, debt maturity)

---

## Phase 5 — Portfolio & Tracking (Month 4–5)

**Goal:** Allow users to manage a virtual portfolio through a Buffett lens.

### 5.1 Portfolio Builder
- [ ] Add stocks with position size
- [ ] Portfolio-level weighted Buffett score
- [ ] Concentration analysis (sector/industry diversification)
- [ ] Portfolio P&L tracking (price from yfinance)

### 5.2 Monitoring & Alerts
- [ ] Weekly score re-calculation (cron job)
- [ ] Alert when a held stock's score drops below threshold
- [ ] Earnings calendar integration

### 5.3 Performance Attribution
- [ ] Backtest: how would a Buffett-screened portfolio have performed vs S&P 500?
- [ ] Score vs return correlation analysis

---

## Phase 6 — UX & Polish (Ongoing)

- [ ] Mobile-responsive layout
- [ ] PDF report export (one-page stock tearsheet)
- [ ] Keyboard shortcuts (type ticker + Enter from anywhere)
- [ ] Light / dark mode toggle
- [ ] Onboarding tour for new users
- [ ] Accessibility (ARIA labels, keyboard nav)
- [ ] Internationalization: Chinese / English toggle for UI labels

---

## Phase 7 — Agent System & Harness (Weeks 1–6) — **THE CORE**

**Goal:** Build a production-grade, observable, multi-agent harness from scratch. This is the centerpiece of the project and the strongest resume signal: system design + agentic AI + observability.

**Success metrics (quantify on resume):**
- ≥ 95% tool-call success rate (with retry/fallback)
- Median end-to-end agent run < 30s for "single ticker buy/sell" query
- P95 < 90s for "compare 3 stocks" multi-subagent query
- 100% of agent runs traceable end-to-end (every step recorded)
- Resumable: any agent run can be interrupted and resumed from checkpoint

**Status (2026-05-12):** Phase 7.1 MVP shipped in commit `09e1952` — single-agent plan-act-observe loop running against Anthropic Claude, 2 tools wired. **Update:** SSE streaming live (`POST /api/agent/stream`) and tool library expanded to 6 tools (`get_stock_quote`, `get_buffett_score`, `get_valuation`, `get_moat`, `get_price_history`, `get_technicals`). Orchestrator prompt updated so the agent reaches for valuation / moat / momentum at the right moments. Next: agent UI (live trace panel), Postgres persistence, multi-agent orchestration.

### 7.1 Agent Harness (self-authored, no LangGraph)

> Build it yourself. LangGraph hides the parts that interviewers want you to explain.

- [x] **`AgentRunner` core loop** — plan → act → observe; reflect pass deferred to 7.2
- [x] **Tool registry** — Pydantic-typed tool definitions, JSON schema auto-generated for the LLM, runtime arg validation
- [x] **Tool dispatcher** — async tool execution, parallel tool calls in one turn, per-tool timeout, retry with exponential backoff
- [x] **Tool sandbox** — each tool runs in a bounded `asyncio.Task` with `wait_for` timeout; failures encoded in `ToolResult.error` and never crash the loop
- [ ] **Structured output enforcement** — auto-repair loop on Pydantic parse failure (args validation done; output-shape repair pending)
- [ ] **Persistent agent state** — every step written to Postgres `agent_runs` + `agent_steps` tables (Phase 8 dependency)
- [ ] **Resumable execution** — `resume(run_id)` picks up from last persisted step
- [x] **Token / cost accounting** — every LLM call records `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `model`, `latency_ms` (per-model price table in `llm.py`)
- [x] **Streaming traces** — SSE channel emits each step as it happens (`{"type":"tool_call","name":"get_news",...}`) for the UI. `runner.stream()` async generator + `POST /api/agent/stream` endpoint shipped; events: `llm`, `tool_batch`, `final`, `error`, `done`.

### 7.2 Multi-Agent Orchestration

- [ ] **Orchestrator Agent** — decomposes user query into a `ResearchPlan` (Pydantic), routes subtasks to specialists
- [ ] **Fundamentals Subagent** — owns Buffett ratios, DCF, EPV, ROIC, Graham Number; uses existing `buffett.py` / `valuation.py` as tools
- [ ] **News & Sentiment Subagent** — fetches news (NewsAPI / Tavily / Perplexity), classifies sentiment, dedupes by event
- [ ] **Technical Subagent** — RSI, MACD, MA50/MA200, volume profile, support/resistance
- [ ] **Valuation Subagent** — peer comparison, EV/EBITDA vs sector median, reverse-DCF implied growth
- [ ] **Risk Subagent** — debt maturity wall, customer concentration, regulatory exposure (pulled from 10-K Item 1A)
- [ ] **Inter-agent messaging** — subagents return structured `Finding` objects; orchestrator dedupes contradictions and synthesizes
- [ ] **Reflexion pass** — final agent reviews its own report against the original query, flags gaps, can dispatch follow-up subagent runs

### 7.3 Tool Library (called by all subagents)

- [x] `get_stock_quote` — live price, sector/industry, key ratios, 52w range
- [x] `get_buffett_score` — full 14-ratio breakdown + sector-adjusted thresholds + trend adjustment
- [x] `get_valuation` — DCF / Graham / EPV / FCF-yield / Margin-of-Safety / ROIC / Price-to-FCF / Circle-of-Competence
- [x] `get_moat` — moat type + Wide/Narrow/None strength + per-dimension scores + supporting indicators
- [x] `get_price_history` — period summary (start/latest/high/low, total return %, drawdown from high) for 1mo–max
- [ ] `get_news` — last N days + sentiment
- [x] `get_technicals` — RSI(14), MACD(12/26/9), SMA-50/200, price-vs-MA %, 30d annualized volatility
- [ ] `get_peer_comparison` — auto-pick 3-5 sector peers, compare key ratios
- [ ] `search_filings` — hybrid RAG over SEC 10-K/10-Q (delivered in Phase 9)
- [ ] `get_prior_analysis` — recall past agent runs for the same ticker
- [ ] `web_search` — fallback for ad-hoc queries (Tavily / Brave)

### 7.4 MCP Server (Model Context Protocol)

> 2026 keyword. Any MCP client (Claude Desktop, Cursor, custom) can plug into your tools.

- [ ] Wrap the entire tool library as an MCP server (`mcp-server-deepvalue`)
- [ ] Publish `stdio` + `streamable-http` transports
- [ ] Document tool schemas; ship example `claude_desktop_config.json` snippet
- [ ] Demo video: Claude Desktop using DeepValue tools end-to-end

### 7.5 Model Routing

- [ ] **Router policy** — Haiku for intent classification + simple RAG, Sonnet for analytical subagents, Opus for final synthesis (configurable per role)
- [ ] **Prompt caching** — Anthropic ephemeral cache on system prompt + few-shots (target ≥ 80% cache hit rate on repeat tickers)
- [ ] **Cost telemetry** — dashboard shows token spend per agent role, per query
- [ ] **A/B harness** — pin two model configs side-by-side, route X% of traffic to each

### 7.6 Agent UI

- [ ] Natural-language entry: *"Should I buy Google?"*, *"Compare AAPL vs MSFT in services revenue growth"*
- [ ] **Live trace panel** — streams each tool call, args, result preview, latency, cost (Anthropic Console-style)
- [ ] **Final report** — structured sections: Summary · Fundamentals · Valuation · News · Technicals · Risks · Verdict
- [ ] **Sources** — every claim links back to its tool call or filing chunk
- [ ] PDF export of the agent report

---

## Phase 8 — Enterprise Infrastructure (Weeks 7–10)

**Goal:** Move from "side project running on a laptop" to "production-deployable platform with auth, persistence, async work, CI/CD, and observability." This is what FAANG infra / 国内大厂 platform interviews drill on.

**Success metrics:**
- Cold-start `docker compose up` → working app in < 60s
- All API routes < 500ms P95 (excluding LLM streaming)
- 100% of releases pass CI before merge
- Zero secrets in repo (validated by gitleaks pre-commit)

### 8.1 Persistence Layer

- [ ] **PostgreSQL** — replace localStorage / in-memory state. Tables: `users`, `watchlists`, `portfolios`, `agent_runs`, `agent_steps`, `analyses`, `filings_chunks`
- [ ] **pgvector** — vector column on `filings_chunks` and `knowledge_chunks`; replaces FAISS (single-file, no concurrent writes)
- [ ] **Redis** — cache layer for yfinance quotes (currently `cachetools`), pub/sub channel for agent step streaming, Celery broker
- [ ] **Alembic migrations** — schema versioned in git, `migrate` runs in CI
- [ ] **DB connection pooling** — `asyncpg` + `SQLAlchemy 2.x async`

### 8.2 Auth & Multi-Tenancy

- [ ] **OAuth login** — Google + GitHub via `Authlib`
- [ ] **JWT sessions** — short-lived access + refresh tokens, httpOnly cookies
- [ ] **Row-level access control** — every query scoped by `user_id`; agent runs / watchlists private per user
- [ ] **API keys for programmatic access** — per-user tokens with scoped permissions
- [ ] **Audit log** — every agent run, every tool invocation logged with `user_id`, `ip`, `ts`

### 8.3 Async Workers

- [ ] **Celery (or Arq)** + Redis broker
- [ ] **Background job: nightly watchlist scan** — agent runs on every user's watchlist; deltas emailed/notified
- [ ] **Background job: SEC EDGAR ingestion** — daily poll for new filings, chunk + embed
- [ ] **Background job: regression eval** — Phase 9 eval suite runs on every model/prompt change
- [ ] **Worker autoscale** — separate `worker-heavy` (LLM) and `worker-light` (data) queues

### 8.4 Observability

- [ ] **Langfuse self-hosted** (or LangSmith) — every LLM call, every agent step, every tool call traced; UI shows full conversation tree per run
- [ ] **OpenTelemetry** — FastAPI middleware exports traces; correlate HTTP request → agent run → LLM calls
- [ ] **Prometheus + Grafana** — RED metrics on every route, P50/P95/P99 latency, token spend per minute, cache hit rate
- [ ] **Sentry** — error tracking for backend + frontend, source-mapped
- [ ] **Status page** — `/status` endpoint shows DB, Redis, yfinance, Anthropic, Groq health

### 8.5 DevOps & CI/CD

- [ ] **Docker Compose** for local dev — backend + worker + postgres + redis + frontend + langfuse, one command
- [ ] **Multi-stage Dockerfile** for backend (slim runtime image)
- [ ] **GitHub Actions CI** — lint (ruff), type check (mypy + tsc), unit tests (pytest), integration tests, security scan (bandit + gitleaks), Docker build
- [ ] **Pre-commit hooks** — ruff, mypy, gitleaks, conventional-commits
- [ ] **Deploy target** — Fly.io / Railway (one-click) + Terraform module for AWS ECS (showcase)
- [ ] **Environment config validation** — Pydantic `Settings` checks all required env vars at startup, fails fast

### 8.6 Security & Reliability Hardening

- [ ] **Input/output guardrails** — Pydantic validation on all routes, output filtering for PII / prompt-injection signatures
- [ ] **LLM prompt-injection defenses** — system-prompt isolation, tool-result sanitization, never echo raw user input back to a tool that executes code
- [ ] **Rate limiting per user** (currently per-IP) — `slowapi` + Redis backend
- [ ] **Circuit breakers** on yfinance / NewsAPI / Anthropic — `pybreaker` or hand-rolled
- [ ] **Graceful shutdown** — drain in-flight agent runs on SIGTERM

---

## Phase 9 — Advanced RAG + Eval Harness (Weeks 11–14)

**Goal:** Turn the project's knowledge layer from a static text file into a queryable, evaluated corpus over real SEC filings. The eval harness is what makes the project look like it was built by someone who has shipped LLM products.

**Success metrics:**
- ≥ 10,000 chunks indexed from ≥ 500 latest 10-K/10-Q filings
- Hybrid retrieval beats dense-only on golden set by ≥ 15% recall@5
- LLM-as-judge eval suite runs in CI; PR blocks if hallucination rate regresses by > 2pp
- All claims in agent reports have source citations to a filing chunk or tool output

### 9.1 SEC EDGAR Pipeline

- [ ] **Crawler** — daily poll of EDGAR full-text search, fetch new 10-K / 10-Q / 8-K for tracked tickers
- [ ] **Parser** — split filings by Item (1A Risk Factors, 7 MD&A, 7A Market Risk, 8 Financial Statements)
- [ ] **Hierarchical chunking** — parent doc (Item-level) → child chunks (~500 tokens) with overlap; store both, retrieve children, return parents
- [ ] **Metadata** — every chunk tagged with `ticker`, `cik`, `filing_date`, `item`, `fiscal_year`

### 9.2 Hybrid Retrieval

- [ ] **BM25** index (Postgres FTS or `rank_bm25`) for lexical matches
- [ ] **Dense embeddings** — `text-embedding-3-small` or `voyage-3` (better than MiniLM for finance)
- [ ] **Cross-encoder reranker** — `bge-reranker-v2-m3` on top-50 candidates → top-5
- [ ] **Contextual retrieval** (Anthropic technique) — prepend a 50-token doc-level context to each chunk before embedding; cuts retrieval failure ~35% on Anthropic's reference benchmark
- [ ] **Metadata filters** — agent can constrain by ticker, year, item: `search_filings(query, ticker="NVDA", item="1A", year=2025)`

### 9.3 GraphRAG (optional but resume-shiny)

- [ ] Extract entity graph from filings: company → competitors / suppliers / customers / regulators
- [ ] Store in Postgres (or Neo4j) — supports "Who competes with NVDA?" and "What companies cite TSMC as supplier?"
- [ ] Hybrid: vector retrieval finds candidate chunks, graph traversal expands to related entities

### 9.4 LLM Eval Harness

- [ ] **Golden dataset** — 100 manually-curated investment questions with reference answers (ticker, ground-truth verdict, key facts)
- [ ] **LLM-as-judge** — Sonnet evaluates agent output on: factual accuracy, citation grounding, completeness, hallucination
- [ ] **Eval runner CLI** — `python -m deepvalue.eval run --suite golden --model sonnet` → markdown report with per-question scoring
- [ ] **Regression in CI** — every PR runs a sampled subset; full suite nightly
- [ ] **Per-subagent evals** — separate eval sets for Fundamentals / News / Risk subagents
- [ ] **Failure-mode tagging** — hallucination, missing-source, format-error, off-topic — track distribution over time
- [ ] **Public eval dashboard** — `/evals` page shows latest scores per release

### 9.5 Quality Signals on Live Traffic

- [ ] **Thumb-up/down** on agent reports → labeled dataset for future SFT
- [ ] **Output structured-error rate** — % of runs that failed Pydantic parse on first try
- [ ] **Citation coverage** — % of factual claims with a source link

---

## Phase 10 — Polish, Metrics & Launch (Weeks 15–16)

**Goal:** Ship to public, collect real usage, generate the numbers you put on your resume.

- [ ] **Public deploy** — `deepvalue.app` (or similar), HTTPS, status page
- [ ] **Onboarding** — sign in, search a ticker, see live agent trace
- [ ] **Showcase reports** — pre-generated agent reports on 20 popular tickers, indexable for SEO
- [ ] **Mobile responsive**
- [ ] **Open source** the agent harness + MCP server as a separate repo (`deepvalue-harness`) with its own README — this is what recruiters click on
- [ ] **Write a launch blog post** — "How I built a multi-agent investment research platform" (HN / r/MachineLearning / 知乎)
- [ ] **Collect numbers for resume:**
  - Total agent runs served
  - Cost reduction from prompt caching + model routing (vs Opus-only baseline)
  - Hallucination-rate delta vs single-shot LLM baseline (eval harness output)
  - P50 / P95 / P99 latency
  - GitHub stars

---

## Phase 11+ — Stretch (Months 5+)

- [ ] **Fine-tune** a small open model (Qwen / Llama 3.1 8B) on collected agent traces — show end-to-end ML loop (data → SFT → deploy → eval)
- [ ] **Backtest** agent verdicts vs forward returns (12-month rolling). Causal claims need care — frame as "verdict-return correlation," not "alpha"
- [ ] **Voice agent** — Realtime API / Whisper + TTS; "Hey DeepValue, what's the take on NVDA today?"
- [ ] **Multi-modal** — chart-reading: feed price chart screenshot to the agent for technical commentary
- [ ] **Portfolio agent** — given user holdings, agent proactively flags concentration risk, earnings catalysts, valuation drift

---

## Resume-Ready Summary Table

| Capability | Status | Resume Keyword |
|---|---|---|
| 14-metric weighted Buffett score + sector-adjusted thresholds | ✅ Done | Domain modeling |
| Valuation engine (DCF / Graham / EPV / ROIC) | ✅ Done | Quantitative analysis |
| Moat classification | ✅ Done | Heuristic ML |
| Streaming LLM recommendation + RAG chat | ✅ Done | LLM integration, SSE |
| **Self-authored agent harness** | Phase 7 | **Agent system design** |
| **Multi-agent orchestration (1 + 5)** | Phase 7 | **Multi-agent / agentic AI** |
| **MCP server** | Phase 7 | **MCP, interoperability** |
| **Model routing + prompt caching** | Phase 7 | **LLM cost engineering** |
| **Resumable agent runs in Postgres** | Phase 7 | **Stateful workflows** |
| **OAuth + multi-tenancy + RBAC** | Phase 8 | **Auth, security** |
| **Postgres + pgvector + Redis + Celery** | Phase 8 | **Production data stack** |
| **Langfuse + OTel + Prometheus + Sentry** | Phase 8 | **Observability** |
| **Docker + GitHub Actions CI/CD** | Phase 8 | **DevOps** |
| **SEC EDGAR hybrid + GraphRAG** | Phase 9 | **Advanced RAG** |
| **LLM-as-judge eval harness in CI** | Phase 9 | **LLM eval / quality engineering** |
| **Public launch + collected metrics** | Phase 10 | **Shipping** |

---

*Last updated: 2026-05-12 · v0.5-beta (Phase 7.1 complete sans persistence — SSE streaming + 6 tools: quote, score, valuation, moat, price history, technicals)*
