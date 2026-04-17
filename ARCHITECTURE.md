# BuffettAI — Architecture Reference

> Last updated: 2026-04-17 · Current version: v0.2

---

## Project Overview

An AI-powered US equity analysis platform that combines Warren Buffett's fundamental investing criteria with modern quantitative metrics. Users search any publicly traded stock to receive a weighted Buffett score (0–100), full financial statement data, and a streaming AI investment recommendation grounded in a RAG knowledge base.

---

## Tech Stack

### Backend — Python 3.11

| Layer | Technology | Notes |
|-------|-----------|-------|
| Web Framework | **FastAPI 0.111** | Async-capable REST API, auto OpenAPI docs at `/docs` |
| Server | **Uvicorn** | ASGI server with hot-reload in dev |
| Financial Data | **yfinance ≥ 1.3.0** | Yahoo Finance — no API key required; covers US/HK/A-shares |
| Embeddings | **sentence-transformers `all-MiniLM-L6-v2`** | 384-dim general-purpose embeddings |
| Vector Store | **FAISS (CPU)** | Local similarity search, index saved to disk on first run |
| RAG Orchestration | **LangChain 0.2** | Text splitting, document loading |
| LLM | **Groq — `llama-3.1-8b-instant`** | Fast free-tier inference; used for both chat and recommendations |
| HTTP Client | **httpx** | Async-capable; used internally |
| Config | **python-dotenv** | Loads `backend/.env` |

### Frontend — React + TypeScript

| Layer | Technology | Notes |
|-------|-----------|-------|
| Framework | **React 18 + TypeScript** | Strict mode enabled |
| Build Tool | **Vite 5** | Dev server on `:5173`, proxies `/api` → `:8000` |
| Styling | **Tailwind CSS** | Utility classes + inline `style` for dynamic colors |
| Charts | **Recharts** | Bar chart for ratio visualization |
| HTTP Client | **Axios** | REST calls; `fetch` used for SSE streaming |
| State | **React Context + useState** | Single `StockContext` holds all dashboard state |
| Streaming | **Fetch ReadableStream** | Parses `text/event-stream` (SSE) for live token output |

---

## Directory Structure

```
buffett-analyzer/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI entry: CORS, router registration, FAISS init on startup
│   │   ├── config.py                    # Loads .env: GROQ_API_KEY, GROQ_MODEL
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── stock.py             # GET  /api/stock/{ticker}/quote
│   │   │       │                        # GET  /api/stock/{ticker}/financials
│   │   │       │                        # GET  /api/stock/{ticker}/ratios  (+ weighted_score)
│   │   │       │                        # POST /api/stock/recommendation   (SSE stream)
│   │   │       └── chat.py              # POST /api/chat  (SSE stream)
│   │   ├── services/
│   │   │   ├── financial.py             # yfinance wrapper; lru_cache per ticker
│   │   │   │                            # get_stock_quote() — price + extended info (ROE, PEG, FCF yield…)
│   │   │   │                            # get_stock_data()  — income / balance / cashflow DataFrames
│   │   │   ├── buffett.py               # 14 Buffett ratios as BuffettRatio dataclass
│   │   │   │                            # compute_ratios()        → list[BuffettRatio]
│   │   │   │                            # compute_weighted_score() → float 0–100
│   │   │   └── rag.py                   # FAISS build/load, retrieve(), stream_chat(), stream_recommendation()
│   │   └── data/
│   │       ├── buffett_knowledge.txt    # RAG source: ~30 chunks on Buffett principles
│   │       └── faiss_index/             # Auto-generated on first run (git-ignored)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html
│   ├── vite.config.ts                   # Proxy: /api → http://localhost:8000
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                      # Root layout: Header | Dashboard | ChatWindow
│       ├── index.css                    # Tailwind + scrollbar overrides + SF Pro font stack
│       ├── types/index.ts               # BuffettRatio, StockQuote, StockFinancials, Message
│       ├── api/client.ts                # fetchQuote, fetchRatios, fetchFinancials,
│       │                                # streamChat, streamRecommendation
│       ├── context/StockContext.tsx     # ticker, quote, ratios, weightedScore, financials, loading, error
│       └── components/
│           ├── Header.tsx               # Branding + StockSearch
│           ├── StockSearch.tsx          # Ticker input → triggers search()
│           └── Dashboard/
│               ├── index.tsx            # Tab bar: Ratios | Chart | Statements | AI Pick
│               ├── StockOverview.tsx    # Price, change, market cap, P/E, ROE, PEG, FCF yield…
│               ├── RatioTable.tsx       # Score ring + 14 ratio cards grouped by statement type
│               ├── RatioChart.tsx       # Recharts bar chart (pass=green / fail=red)
│               ├── StatementTable.tsx   # Collapsible Income / Balance / Cash Flow tables
│               └── AIRecommendation.tsx # Weighted score gauge + weight breakdown + streaming AI analysis
│           └── Chatbot/
│               └── ChatWindow.tsx       # Single-turn Q&A chat with RAG context injection
│
├── ARCHITECTURE.md                      # This file
├── ROADMAP.md                           # Feature roadmap + known issues backlog
└── README.md
```

---

## API Reference

### Stock Endpoints

```
GET  /api/stock/{ticker}/quote
     Response: StockQuote
       { name, price, change, changesPercentage, marketCap, pe, exchange,
         sector, industry, summary, forwardPE, pegRatio, roe, roa,
         revenueGrowth, earningsGrowth, fcfYield, dividendYield, evToEbitda }

GET  /api/stock/{ticker}/financials
     Response: StockFinancials
       { financials: {date: {field: value}},
         balanceSheet: {date: {field: value}},
         cashflow: {date: {field: value}} }

GET  /api/stock/{ticker}/ratios
     Response:
       { ticker, weighted_score: float,
         ratios: BuffettRatio[] }
     BuffettRatio: { name, value, threshold, passes, description,
                     buffett_logic, category, equation, weight }

POST /api/stock/recommendation           SSE stream
     Body: { ticker, ratios, weighted_score, quote }
     Response: text/event-stream tokens → [DONE]
```

### Chat Endpoint

```
POST /api/chat                           SSE stream
     Body: { question: string, ticker: string, ratios: BuffettRatio[] }
     Response: text/event-stream tokens → [DONE]
```

---

## Data Flow

### Stock Analysis (on ticker search)

```
User types ticker → StockSearch calls search()
        │
        ▼
StockContext fires 3 parallel requests:
  ├── GET /api/stock/{ticker}/quote      → StockQuote (yfinance .info)
  ├── GET /api/stock/{ticker}/ratios     → 14 BuffettRatios + weighted_score
  └── GET /api/stock/{ticker}/financials → raw DataFrames converted to dicts
        │
        ▼ (backend)
financial.py: yf.Ticker(ticker) → .info / .financials / .balance_sheet / .cashflow
        │  (lru_cache per ticker — no TTL, resets on server restart)
        ▼
buffett.py: compute_ratios(data) → 14 BuffettRatio objects
            compute_weighted_score(ratios) → normalized 0–100 float
        │
        ▼ (frontend)
StockContext stores: ticker, quote, ratios, weightedScore, financials
        │
        ├── StockOverview  renders price + 8 extended stats
        ├── RatioTable     renders score ring + grouped ratio cards
        ├── RatioChart     renders pass/fail bar chart
        ├── StatementTable renders collapsible financial tables
        └── AIRecommendation (on demand — user clicks Generate)
```

### RAG Chat Flow

```
User message → ChatWindow
        │
        ▼
POST /api/chat { question, ticker, ratios }
        │
        ▼
rag.py: embed question with all-MiniLM-L6-v2
        → FAISS similarity_search(k=3) on buffett_knowledge.txt
        → top-3 chunks as rag_context
        │
        ▼
Prompt assembled (single user message — see known issues):
  [Role definition]
  [RAG context chunks]
  [Stock ratio table: name / value / status / threshold]
  [User question]
        │
        ▼
Groq llama-3.1-8b-instant streams tokens
        │
        ▼
SSE: "data: <token>\n\n" … "data: [DONE]\n\n"
        │
        ▼
Frontend ReadableStream appends tokens to last assistant message
```

### AI Recommendation Flow

```
User clicks "Generate AI Investment Analysis"
        │
        ▼
POST /api/stock/recommendation
  { ticker, ratios (14 items w/ weight), weighted_score, quote (+ sector/ROE/PEG…) }
        │
        ▼
rag.py: retrieve sector-aware Buffett context (k=4)
        │
        ▼
Rich prompt assembled:
  [Analyst role + value investing framing]
  [RAG chunks]
  [Company snapshot: sector, industry, price, market cap, ROE, PEG,
   FCF yield, revenue growth, business summary, weighted score]
  [14 metrics table: status / value / threshold / weight]
  [Structured output instructions: VERDICT / STRENGTHS / CONCERNS /
   BUFFETT ALIGNMENT / MODERN CONTEXT]
        │
        ▼
Groq llama-3.1-8b-instant (max_tokens=800, temperature=0.6) streams
        │
        ▼
AIRecommendation parses sections and renders formatted output
```

---

## Buffett Ratio Reference (v0.2 — 14 metrics)

| # | Name | Equation | Threshold | Category | Weight |
|---|------|----------|-----------|----------|--------|
| 1 | Gross Margin | Gross Profit / Revenue | ≥ 40% | Income Statement | 13% |
| 2 | SG&A Margin | SG&A / Gross Profit | ≤ 30% | Income Statement | 7% |
| 3 | R&D Margin | R&D / Gross Profit | ≤ 30% | Income Statement | 4% |
| 4 | Depreciation Margin | Depreciation / Gross Profit | ≤ 10% | Income Statement | 6% |
| 5 | Interest Expense Margin | Interest Expense / Operating Income | ≤ 15% | Income Statement | 8% |
| 6 | Effective Tax Rate | Tax Provision / Pre-Tax Income | 15–30% | Income Statement | 5% |
| 7 | Net Profit Margin | Net Income / Revenue | ≥ 20% | Income Statement | 11% |
| 8 | EPS Growth (YoY) | EPS(N) / EPS(N-1) | > 1.0 | Income Statement | 10% |
| 9 | Cash vs Current Debt | Cash / Current Debt | > 1.0 | Balance Sheet | 8% |
| 10 | Adj. Debt-to-Equity | Total Debt / (Assets − Debt) | < 0.80 | Balance Sheet | 9% |
| 11 | Preferred Stock | Balance sheet value | = $0 | Balance Sheet | 1% |
| 12 | Retained Earnings Growth | RE(N) / RE(N-1) | > 1.0 | Balance Sheet | 9% |
| 13 | Treasury Stock | Balance sheet value | Exists | Balance Sheet | 1% |
| 14 | CapEx Margin | CapEx / Net Income | < 25% | Cash Flow | 8% |

**Weighted Score formula:**
```
score = Σ(weight_i for pass_i == True) / Σ(weight_i for pass_i != None) × 100
```
N/A metrics are excluded from both numerator and denominator (score normalized to scored metrics only).

---

## Environment Variables

```bash
# backend/.env  (never commit — see .env.example)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

No other API keys required. yfinance fetches Yahoo Finance data without authentication.

---

## Local Development

```bash
# Backend (Python 3.11)
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs

# Frontend
cd frontend
npm install
npm run dev       # http://localhost:5173  (proxies /api → :8000)
```

---

## Key Design Decisions

| Decision | Alternative | Rationale |
|----------|------------|-----------|
| yfinance over FMP | FMP REST API | No API key needed; broader ticker coverage (HK, A-shares); FMP free tier limited to major US stocks only |
| FAISS local over Pinecone | Pinecone / Weaviate | Zero external dependencies; works offline; adequate for <10k chunks |
| Groq over OpenAI | OpenAI GPT-4o | Free tier; ~10× faster inference; LLaMA quality sufficient for structured financial output |
| SSE over WebSocket | WebSocket | Simpler for one-directional streaming; no ws library needed on either side |
| React Context over Zustand | Zustand / Redux | App state is single-ticker; adding Zustand would be premature optimization |
| Tailwind + inline style | MUI / Ant Design | Full control over Apple HIG dark design without fighting component defaults |
| lru_cache (current) | Redis / TTL cache | Acceptable for development; known limitation — see ROADMAP §0 Known Issues |

---

## Known Issues & Technical Debt

See **ROADMAP.md → Phase 0: Technical Debt** for the full prioritized backlog. Summary:

| Severity | Issue |
|----------|-------|
| P0 | `lru_cache` has no TTL — data never refreshes while server is running |
| P0 | Chat is single-turn — no conversation history passed to LLM |
| P0 | CORS origin hardcoded to `localhost:5173` — breaks on deployment |
| P1 | LLM model `8b-instant` too small for deep financial reasoning |
| P1 | AI Pick recommendation state lost on tab switch |
| P1 | Prompt uses single `user` message — no system/user separation |
| P1 | Ticker input not sanitized — prompt injection risk |
| P2 | yfinance calls are synchronous — blocks FastAPI event loop under load |
| P2 | Search clears stale data immediately — causes loading flash |
| P2 | No React Error Boundary — component crash = blank page |
| P3 | RAG uses small 384-dim embeddings with no re-ranking step |
| P3 | Knowledge base is a single static file — no domain specialization |
