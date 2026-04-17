# BuffettAI — Value Investing Stock Analyzer

A full-stack AI-powered US equity analysis platform built on Warren Buffett's value investing framework and modern quantitative metrics. Search any publicly traded stock to get a weighted Buffett score, full financial statement data, and a streaming AI investment recommendation grounded in a RAG knowledge base.

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

### Extended Quote Data
Beyond price and P/E, every stock analysis includes: **Sector / Industry**, **Forward P/E**, **PEG Ratio**, **EV/EBITDA**, **FCF Yield**, **ROE**, **ROA**, **Revenue Growth**, **Earnings Growth**, and **Dividend Yield** — all sourced from Yahoo Finance with no API key required.

### AI Investment Recommendation
Click **Generate AI Investment Analysis** for a streaming, sector-aware recommendation structured as: Verdict (BUY / HOLD / AVOID) → Strengths → Concerns → Buffett Alignment → Modern Context. The prompt injects the company's business summary, all 14 weighted metrics, and modern valuation data for grounded, specific output.

### RAG Chat Advisor
Ask any investment question in natural language. Answers are grounded via FAISS vector search over a Buffett knowledge base and augmented with the current stock's ratio data, then streamed token-by-token from Groq LLaMA.

### Financial Statements
4 years of Income Statement, Balance Sheet, and Cash Flow data in collapsible tables with formatted values.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| Backend | FastAPI · Python 3.11 · Uvicorn |
| Financial Data | **yfinance** — no API key required |
| AI / RAG | LangChain · FAISS · sentence-transformers · Groq API (LLaMA 3.1) |
| Streaming | Server-Sent Events (SSE) |

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
| GET | `/api/stock/{ticker}/quote` | Price, market cap, ROE, PEG, FCF yield, sector… |
| GET | `/api/stock/{ticker}/ratios` | 14 Buffett ratios + weighted score (0–100) |
| GET | `/api/stock/{ticker}/financials` | Income statement, balance sheet, cash flow (4 yrs) |
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
│   │   │   ├── stock.py             # Quote / financials / ratios / recommendation
│   │   │   └── chat.py              # SSE streaming chat
│   │   ├── services/
│   │   │   ├── financial.py         # yfinance wrapper + LRU cache
│   │   │   ├── buffett.py           # 14 ratio calculations + weighted score
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
        └── components/
            ├── Header.tsx
            ├── StockSearch.tsx
            ├── Dashboard/
            │   ├── index.tsx            # Tabs: Ratios | Chart | Statements | AI Pick
            │   ├── StockOverview.tsx    # Price + 8 extended stats
            │   ├── RatioTable.tsx       # Score ring + grouped ratio cards
            │   ├── RatioChart.tsx       # Pass/fail bar chart
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
- TTL-based cache (replace `lru_cache`)
- Multi-turn conversation history in chat
- Upgrade recommendation model to LLaMA 70B
- DCF / Graham Number intrinsic value calculator
- Stock screener with batch Buffett scoring

---

## License

MIT
