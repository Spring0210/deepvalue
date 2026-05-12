# DeepValue Agent — CLAUDE.md

> Persistent project memory. Read this file every session before touching code.
> ROADMAP.md is the source of truth for what to build next; this file is the
> source of truth for **how** to build it.

---

## 1. What this project is

AI-native, multi-agent investment research platform. Users ask natural-language
questions; an orchestrator agent dispatches specialized subagents, calls
financial tools, and produces a structured, source-grounded report.

Current version: **v0.5-beta** — self-authored agent harness, 6 tools wired,
SSE streaming live. Roadmap details: `ROADMAP.md` (always check it first).

Resume narrative: see top of `ROADMAP.md`.

---

## 2. Tech stack

**Backend** (`backend/`)
- FastAPI 0.111, Python 3.11
- Anthropic SDK 0.39 (agent harness) + Groq SDK 0.9 (chat / streaming reco)
- yfinance (data), pandas, cachetools (TTL cache)
- slowapi (rate limit), pydantic v2
- Tests: pytest + pytest-asyncio (see §6)

**Frontend** (`frontend/`)
- React 18 + TypeScript, Vite, TailwindCSS, recharts, axios
- localStorage for watchlist (no DB yet)

**Data**
- yfinance only (no FMP / Alpha Vantage). No API keys for data.
- FAISS file-based vector store for RAG chat (will move to pgvector in Phase 8).

---

## 3. Run commands (copy-paste)

```bash
# Backend (port 8000)
cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Frontend (port 5173)
cd frontend && npm run dev

# Tests
cd backend && .venv/bin/python -m pytest -q

# Single test file
cd backend && .venv/bin/python -m pytest tests/services/test_valuation.py -q

# Type check (frontend)
cd frontend && npx tsc --noEmit

# Lint backend (when installed)
cd backend && .venv/bin/python -m ruff check app/
```

Backend venv lives at `backend/.venv/`. Do not create a new one — use the existing
`.venv/bin/python` for everything.

---

## 4. Required env vars

`backend/.env` (gitignored; example in `backend/.env.example`):
- `ANTHROPIC_API_KEY` — agent harness; without it `/api/agent/*` returns 503.
- `GROQ_API_KEY` — RAG chat + streaming recommendation.
- `ANTHROPIC_MODEL` (default `claude-sonnet-4-5`).
- `AGENT_MAX_ITERS` (default 8).
- `ALLOWED_ORIGINS` (CSV; default `http://localhost:5173`).

Tests must not require these keys. The agent harness tests use a fake LLM client.

---

## 5. Design invariants — DO NOT VIOLATE

These are decisions that took a real conversation to get right. Re-deriving them
is wasted work; breaking them silently breaks downstream features.

### Backend / data
- **All yfinance calls are async + cached.** Use `get_stock_quote` /
  `get_stock_data` / `get_price_history` from `app/services/financial.py`.
  Never call `yf.Ticker(...)` directly in a route or tool handler — bypasses
  the TTL cache and blocks the event loop.
- **All ticker inputs are validated.** Routes call `_validate_ticker()`;
  agent tool args use the `pattern=r"^[A-Za-z0-9.\-]{1,10}$"` regex.
- **CORS origins come from env.** Never hardcode `localhost:5173`.

### Buffett scoring (`app/services/buffett.py`)
- 14 ratios, weights sum to 1.0 (validated by `compute_weighted_score`).
- Sector-adjusted thresholds live in `_sector_threshold()`. When adding a new
  metric, add its threshold there too.
- Trend bonus/penalty is additive on top of the base score, clamped to [0, 100].

### Agent harness (`app/agent/`)
- **Tools never raise.** Failures land in `ToolResult.error`; dispatcher
  catches everything. If a tool handler can raise, wrap or fix it.
- **Tool output must be JSON-serializable.** No dataclasses, no `pd.DataFrame`,
  no numpy scalars. Convert inside the handler.
- **Tool args are Pydantic models.** The JSON schema is auto-generated; never
  hand-write it.
- **One assistant turn = one `AgentStep` of kind `LLM`** with optional
  `tool_calls`. Tool batch results are a separate `TOOL_BATCH` step. Final
  answer is a `FINAL` step. The shape is persistence-ready (one row each).
- **The LLM client is the only place `anthropic` is imported.** Keep cost
  accounting + cache-token tracking centralized.

### Frontend
- Stale-while-revalidate: never clear `ratios` / `financials` on a new search
  until new data arrives. (`StockContext.tsx` enforces this.)
- AI Pick recommendation is in `StockContext`, not local to the tab —
  switching tabs must not destroy it.

---

## 6. Testing rules

**Run before saying a module is done.** Every new service module gets a test
file under `backend/tests/services/`. Every agent harness change gets a test
under `backend/tests/agent/`.

- Tests must be **offline**: no real network calls, no real `ANTHROPIC_API_KEY`,
  no real yfinance. Mock with `monkeypatch` or in-test fakes.
- Tests must be **fast**: < 5s per file. Use small synthetic series, not
  realistic 5-year datasets.
- Test the **boundary cases first**: empty input, `None` fields, division-by-zero,
  thresholds. Happy paths catch nothing.
- `pytest-asyncio` mode is `auto` (set in `pyproject.toml`). Async test
  functions need no decorator.

**Coverage target for now:** every pure-function module in `services/` and the
agent harness (`registry`, `dispatcher`, `runner`). Routes are covered by the
harness tests via FastAPI's `TestClient` when needed.

---

## 7. Commit + push rules

- Conventional commits: `feat(area): summary`, `fix:`, `refactor:`, `docs:`,
  `test:`. Area examples: `agent`, `valuation`, `moat`, `frontend`, `infra`.
- **Never add `Co-Authored-By: Claude`** to commit messages. (User preference.)
- Body lines under ~78 chars, bullet-list the substantive changes.
- One ROADMAP item → one commit when feasible. If a change touches two items,
  commit twice with the smaller of the two as a prep commit first.
- Run the full pytest suite before `git push`. If anything is red, fix or revert.
- Push to `origin/main`. No PRs in this repo yet.

---

## 8. /loop continuation playbook

When the user runs `/loop /next-roadmap-item` (dynamic mode), each turn:

1. **Read `ROADMAP.md`** (always — never trust memory of its state).
2. **Pick the first unchecked `[ ]` item under an in-flight Phase.** Skip items
   that depend on infrastructure not yet built (Phase 8 Postgres etc.).
3. **If the item is ambiguous or > ~300 LOC of work, stop and ask** the user
   to pick a sub-scope. Do not auto-decompose silently — that's how scope
   creep starts.
4. **Implement** end-to-end: code + tests in the same turn.
5. **Run `pytest -q`.** If red, fix before claiming done. Never `--skip` a
   failing test to make the loop progress.
6. **Tick the ROADMAP line** (`[ ]` → `[x]`) and update the "Status" line of
   the relevant Phase if it has one.
7. **Commit** with a conventional message. Do not push from inside `/loop` —
   the user pushes manually when satisfied (push is shared state).
8. **Brief summary back to the user**: file paths touched, test counts, what
   was unblocked. Then continue with `ScheduleWakeup` to the next iteration,
   or stop if the next item needs a human decision.

Stop conditions (call them out explicitly, don't silently continue):
- Next item is gated on a missing API key, infrastructure, or design decision.
- Tests went red and the root cause is non-obvious after one investigation.
- User has been quiet ≥ 3 iterations and the work is touching shared state
  (deploys, schema, prompts users will see).

---

## 9. Anti-patterns observed in past sessions

- **Adding new abstractions during a bugfix.** Don't. Fix narrowly.
- **Writing comments that restate the code.** Only comment WHY, not WHAT.
- **Mocking what the test is actually testing.** Test real `compute_*`
  functions; only mock the network boundary.
- **Touching the frontend "while I'm here".** Frontend changes are their own
  ROADMAP item.
- **Bumping versions, renaming files, or refactoring during a feature commit.**
  Separate commits, separate review.

---

*Last touched: 2026-05-12 · maintainer of this file: whoever last committed.*
