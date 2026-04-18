# BuffettAI — Product Roadmap

> Goal: A professional-grade US equity analysis platform that combines Warren Buffett's timeless value investing principles with modern quantitative investment concepts to provide actionable stock selection guidance.

---

## Current State (v0.2)

- 14 Buffett metrics with weighted scoring (0–100), grouped by Income Statement / Balance Sheet / Cash Flow
- yfinance data backend — no API key required (US/HK/A-shares)
- Extended quote data: ROE, PEG, FCF Yield, Forward P/E, EV/EBITDA, Revenue Growth, Sector/Industry
- RAG-powered chat advisor (Groq LLaMA 3.1-8B + FAISS)
- Streaming AI investment recommendation with sector-aware prompts
- Financial statement viewer (Income / Balance / Cash Flow)
- Apple HIG dark UI — bar chart, ratio cards, score gauge

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

- [ ] **No rate limiting on API routes**
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
- [ ] EV/EBITDA (enterprise value multiple)
- [ ] Insider ownership percentage

### 1.2 AI Recommendation Quality
- [x] Company business summary in prompt context
- [x] Sector/industry framing
- [x] Multi-year trend data for key metrics
- [x] Modern metrics (ROE, FCF Yield, PEG) in context
- [ ] Few-shot example in system prompt
- [ ] Prompt caching for repeated tickers

### 1.3 Scoring Refinements
- [ ] Industry-adjusted thresholds (e.g., R&D threshold higher for tech)
- [ ] Trend bonus: metrics that improved 3 years in a row get +weight
- [ ] Penalty system: metrics in freefall get negative weight

### 1.4 StockOverview Panel
- [x] Sector & Industry display
- [x] ROE, Forward P/E, FCF Yield display
- [ ] 52-week high/low bar
- [ ] Analyst consensus (from yfinance `.info`)

---

## Phase 2 — Valuation Engine (Month 2)

**Goal:** Give users a concrete estimate of intrinsic value and margin of safety.

### 2.1 Intrinsic Value Models
- [ ] **DCF Calculator** — 10-year discounted cash flow with user-adjustable growth rate and discount rate
- [ ] **Graham Number** — √(22.5 × EPS × BVPS) — classic Ben Graham formula
- [ ] **FCF Yield Valuation** — fair value based on normalized FCF yield vs 10Y Treasury
- [ ] **Earnings Power Value (EPV)** — Bruce Greenwald's no-growth DCF variant

### 2.2 Margin of Safety
- [ ] Display current price vs estimated intrinsic value range
- [ ] Visual margin-of-safety gauge (price vs value)
- [ ] "Buffett Circle of Competence" check — flag highly complex businesses

### 2.3 Modern Valuation Metrics
- [ ] **ROIC** (Return on Invested Capital) — Buffett's preferred efficiency metric
- [ ] **EV/EBITDA** comparison vs sector median
- [ ] **Price-to-FCF** ratio
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
- [ ] Save stocks to personal watchlist (localStorage)
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
- [ ] Auto-classify moat type based on metrics:
  - Network Effect (platform companies, high gross margin)
  - Switching Costs (high retention, recurring revenue)
  - Cost Advantage (low CapEx, economies of scale)
  - Intangible Assets (brand, patents — high gross margin + low R&D need)
  - Efficient Scale (regulated monopolies, utilities)
- [ ] Moat strength rating: Wide / Narrow / None

### 4.3 Industry-Aware Scoring
- [ ] Sector-specific metric weights (tech vs consumer vs financials vs utilities)
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

## Technical Debt & Infrastructure

- [ ] Replace `lru_cache` with Redis for production-grade caching
- [ ] Rate limiting on API routes
- [ ] Error monitoring (Sentry)
- [ ] Unit tests for `buffett.py` ratio calculations
- [ ] CI/CD pipeline (GitHub Actions → Docker)
- [ ] Environment config validation on startup

---

## Metric Priority Matrix

| Metric | Current | Phase 1 | Phase 2 | Phase 3+ |
|--------|---------|---------|---------|----------|
| 14 Buffett Ratios | ✅ | ✅ | ✅ | ✅ |
| Weighted Score | ✅ | ✅ | ✅ | ✅ |
| AI Recommendation | ✅ | Improved | ✅ | ✅ |
| ROE / ROA | — | ✅ | ✅ | ✅ |
| ROIC | — | — | ✅ | ✅ |
| DCF / Graham Number | — | — | ✅ | ✅ |
| Margin of Safety | — | — | ✅ | ✅ |
| Moat Classification | — | — | — | ✅ |
| Stock Screener | — | — | ✅ | ✅ |
| Portfolio Tracker | — | — | — | ✅ |
| Peer Comparison | — | — | — | ✅ |

---

*Last updated: 2026-04-17 · v0.2*
