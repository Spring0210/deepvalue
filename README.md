# BuffettAI — Value Investing Stock Analyzer

A full-stack AI-powered equity analysis platform built on Warren Buffett's value investing framework and modern quantitative metrics. Search any publicly traded stock — US, Hong Kong, or A-share — to get a weighted Buffett score, intrinsic value estimates, competitive moat classification, full financial statement data, and a streaming AI investment recommendation grounded in a RAG knowledge base.

![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.1-F55036?style=flat)
![yfinance](https://img.shields.io/badge/yfinance-1.3-blueviolet?style=flat)

---

## Features

### Buffett Score (0–100)
14 financial metrics derived from Buffett's principles, each assigned a weight based on its importance in modern value investing. The composite score is normalized across non-N/A metrics — so missing data never artificially deflates the result.

| Category | Metrics |
|----------|---------|
| Income Statement | Gross Margin, SG&A Margin, R&D Margin, Depreciation Margin, Interest Expense Margin, Effective Tax Rate, Net Profit Margin, EPS Growth |
| Balance Sheet | Cash vs Current Debt, Adj. Debt-to-Equity, Preferred Stock, Retained Earnings Growth, Treasury Stock |
| Cash Flow | CapEx Margin |

### Intrinsic Value (Valuation Engine)
Two independent models with live-adjustable assumptions:

- **Graham Number** — `√(22.5 × EPS × Book Value per Share)`. Classic Ben Graham formula for the maximum price to pay for a quality stock.
- **DCF Calculator** — 10-year free cash flow projection discounted at WACC, plus Gordon Growth terminal value. Sliders for growth rate, discount rate, and terminal rate update the result in real time.

Both models display a **Margin of Safety** gauge and a price-vs-intrinsic-value bar.

### Competitive Moat Classification
Automated Wide / Narrow / None moat rating based on gross margin, ROE, FCF yield, operating margins, and revenue growth. Each moat dimension is scored and the dominant type (Brand, Network Effect, Cost Advantage, etc.) is identified.

### Extended Quote Data
Beyond price and P/E, every analysis includes: **Sector / Industry**, **Forward P/E**, **PEG Ratio**, **EV/EBITDA**, **FCF Yield**, **ROE**, **ROA**, **Revenue Growth**, **Earnings Growth**, **Dividend Yield**, **52-Week Range**, and **Analyst Price Targets** — all sourced from Yahoo Finance with no API key required.

### AI Investment Recommendation
Click **Generate AI Investment Analysis** for a streaming, sector-aware recommendation structured as: Verdict (BUY / HOLD / AVOID) → Strengths → Concerns → Buffett Alignment → Modern Context. The prompt injects the company's business summary, all 14 weighted metrics, and modern valuation data for grounded, specific output.

### RAG Chat Advisor
Ask any investment question in natural language. Answers are grounded via FAISS vector search over a Buffett knowledge base and augmented with the current stock's ratio data, then streamed token-by-token from Groq LLaMA.

### Financial Statements
4 years of Income Statement, Balance Sheet, and Cash Flow data in collapsible tables with formatted values.

### Multi-Market Support
Currency symbols are displayed correctly for each market — `$` for US stocks, `HK$` for Hong Kong, `¥` for A-shares, and so on.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| Backend | FastAPI · Python 3.11 · Uvicorn |
| Financial Data | **yfinance** — no API key required |
| AI / RAG | LangChain · FAISS · sentence-transformers · Groq API (LLaMA 3.1) |
| Streaming | Server-Sent Events (SSE) |
| Caching | `cachetools.TTLCache` — 15-min quote / 30-min history |

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
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
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

> The Vite dev server proxies `/api` requests to `localhost:8000` automatically.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stock/{ticker}/quote` | Price, market cap, ROE, PEG, FCF yield, sector, currency… |
| GET | `/api/stock/{ticker}/ratios` | 14 Buffett ratios + weighted score (0–100) |
| GET | `/api/stock/{ticker}/financials` | Income statement, balance sheet, cash flow (4 yrs) |
| GET | `/api/stock/{ticker}/history` | OHLCV price history (multiple periods + intervals) |
| GET | `/api/stock/{ticker}/valuation` | Graham Number + DCF inputs |
| GET | `/api/stock/{ticker}/moat` | Competitive moat strength + type classification |
| POST | `/api/stock/recommendation` | SSE — streaming AI investment recommendation |
| POST | `/api/chat` | SSE — streaming RAG chat with stock context |

---

## Weighted Scoring

Each metric carries a weight reflecting its importance. The score is normalized to exclude N/A metrics:

```
Score = Σ(weight_i  where passes == True)
        ─────────────────────────────────── × 100
        Σ(weight_i  where passes != None)
```

| Weight | Metrics |
|--------|---------|
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

## Project Structure

```
buffett-analyzer/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry, CORS, lifespan (FAISS init)
│   │   ├── config.py                # Env vars
│   │   ├── api/routes/
│   │   │   ├── stock.py             # Quote / financials / ratios / valuation / moat / history
│   │   │   └── chat.py              # SSE streaming chat
│   │   ├── services/
│   │   │   ├── financial.py         # yfinance wrapper + TTLCache
│   │   │   ├── buffett.py           # 14 ratio calculations + weighted score
│   │   │   ├── valuation.py         # Graham Number + DCF intrinsic value
│   │   │   ├── moat.py              # Competitive moat classification
│   │   │   └── rag.py               # FAISS index, retrieval, Groq streaming
│   │   └── data/
│   │       └── buffett_knowledge.txt
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── api/client.ts
        ├── context/StockContext.tsx
        ├── types/index.ts
        ├── utils/currency.ts            # Currency symbol helper (USD/HKD/CNY…)
        └── components/
            ├── Header.tsx
            ├── StockSearch.tsx
            ├── Dashboard/
            │   ├── index.tsx            # Tabs: Ratios | Chart | Valuation | Statements | AI
            │   ├── StockOverview.tsx    # Price + extended stats + analyst targets
            │   ├── RatioTable.tsx       # Score ring + grouped ratio cards
            │   ├── RatioChart.tsx       # Pass/fail bar chart
            │   ├── PriceHistoryChart.tsx # Area chart with period selector
            │   ├── ValuationPanel.tsx   # Graham Number + DCF calculator
            │   ├── MoatCard.tsx         # Moat strength + dimension scores
            │   ├── StatementTable.tsx   # Collapsible financial tables
            │   └── AIRecommendation.tsx # Score gauge + streaming AI analysis
            └── Chatbot/
                └── ChatWindow.tsx
```

---

## Supported Tickers

Any ticker supported by Yahoo Finance, including:

- **US stocks**: `AAPL`, `MSFT`, `KO`, `BRK-B`, `NVDA`
- **Hong Kong**: `0700.HK` (Tencent), `9988.HK` (Alibaba)
- **A-shares**: `600519.SS` (Kweichow Moutai), `000858.SZ` (Wuliangye)

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the full feature roadmap and known technical debt backlog.

Key upcoming items:
- Stock screener with batch Buffett scoring
- Upgrade recommendation model to LLaMA 70B
- Multi-turn conversation history in chat
- Portfolio-level analysis across multiple tickers

---

## License

MIT
