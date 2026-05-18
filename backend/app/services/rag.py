import hashlib
from pathlib import Path
from typing import Iterator

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_CHAT_MODEL,
    ANTHROPIC_RECO_MODEL,
    CHAT_PROVIDER,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_RECOMMENDATION_MODEL,
)

_DATA_DIR    = Path(__file__).parent.parent / "data"
_KB_PATH     = _DATA_DIR / "buffett_knowledge.txt"
_LETTERS_DIR = _DATA_DIR / "buffett_letters"
_INDEX_PATH  = _DATA_DIR / "faiss_index"
_SIGNATURE   = _INDEX_PATH / ".signature"

_vector_db: FAISS | None = None
_embeddings: HuggingFaceEmbeddings | None = None
_groq_client = None
_anthropic_client = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _resolve_provider() -> str:
    """Pick provider for chat / recommendation. Anthropic when its key is present
    and CHAT_PROVIDER hasn't forced a downgrade; otherwise Groq."""
    if CHAT_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if CHAT_PROVIDER == "groq" and GROQ_API_KEY:
        return "groq"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return "groq"


def _knowledge_files() -> list[Path]:
    """All text sources scanned into the index — order is stable for hashing."""
    files: list[Path] = []
    if _KB_PATH.exists():
        files.append(_KB_PATH)
    if _LETTERS_DIR.exists():
        files.extend(sorted(_LETTERS_DIR.glob("*.txt")))
    return files


def _compute_signature(files: list[Path]) -> str:
    """Hash of (path, size, mtime) for every source file. Cheap, deterministic,
    catches new files + edits without re-reading content."""
    h = hashlib.sha256()
    for f in files:
        stat = f.stat()
        h.update(f.name.encode())
        h.update(str(stat.st_size).encode())
        h.update(str(int(stat.st_mtime)).encode())
    return h.hexdigest()


def _build_documents(files: list[Path]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs: list[Document] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        source = f.stem
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata={"source": source}))
    return docs


def init_rag() -> None:
    """Build or load the FAISS vector index. Called once at app startup.
    Rebuilds when the on-disk signature no longer matches the knowledge files,
    so dropping new letters into data/buffett_letters/ auto-refreshes the index."""
    global _vector_db
    embeddings = _get_embeddings()
    files = _knowledge_files()
    if not files:
        raise RuntimeError(f"No knowledge files found under {_DATA_DIR}")

    current_sig = _compute_signature(files)
    stored_sig = _SIGNATURE.read_text().strip() if _SIGNATURE.exists() else None

    if _INDEX_PATH.exists() and stored_sig == current_sig:
        print(f"Loading existing FAISS index ({len(files)} source files)...")
        _vector_db = FAISS.load_local(
            str(_INDEX_PATH), embeddings, allow_dangerous_deserialization=True
        )
        return

    print(f"Building FAISS index from {len(files)} source file(s)...")
    docs = _build_documents(files)
    _vector_db = FAISS.from_documents(docs, embeddings)
    _INDEX_PATH.mkdir(parents=True, exist_ok=True)
    _vector_db.save_local(str(_INDEX_PATH))
    _SIGNATURE.write_text(current_sig)
    print(f"FAISS index built with {len(docs)} chunks from {len(files)} sources.")


def retrieve(query: str, k: int = 3) -> str:
    """Return top-k relevant chunks. Each chunk is prefixed with its source so
    the LLM can cite which document a fact came from."""
    if _vector_db is None:
        init_rag()
    docs = _vector_db.similarity_search(query, k=k)  # type: ignore[union-attr]
    parts = []
    for d in docs:
        src = d.metadata.get("source", "unknown")
        parts.append(f"[source: {src}]\n{d.page_content}")
    return "\n\n".join(parts)


def _build_chat_system_message() -> str:
    return (
        "You are an expert investment analyst well-versed in Warren Buffett's investment philosophy. "
        "Use the provided financial data and Buffett's principles to answer the user's questions. "
        "Be specific, concise, and reference actual numbers when available. "
        "When you quote a fact from the knowledge base, cite its [source: ...] tag. "
        "Do not make direct buy/sell recommendations — provide objective analysis."
    )


def _build_chat_user_message(question: str, ticker: str, ratios: list[dict]) -> str:
    rag_context = retrieve(question)

    ratio_lines = []
    for r in ratios:
        val = r.get("value")
        if val is not None:
            val_str = f"{val * 100:.1f}%"
        else:
            val_str = "N/A"
        status = "PASS" if r.get("passes") is True else ("FAIL" if r.get("passes") is False else "N/A")
        ratio_lines.append(f"  • {r['name']}: {val_str}  (threshold: {r['threshold']})  [{status}]")

    stock_context = (
        f"Stock: {ticker.upper()}\n" + "\n".join(ratio_lines)
        if ratio_lines
        else "No stock data loaded."
    )

    return (
        "─── BUFFETT KNOWLEDGE BASE ───\n"
        f"{rag_context}\n\n"
        "─── CURRENT STOCK DATA ───\n"
        f"{stock_context}\n\n"
        "─── USER QUESTION ───\n"
        f"{question}"
    )


def _build_recommendation_prompt(
    ticker: str,
    ratios: list[dict],
    weighted_score: float,
    quote: dict,
) -> tuple[str, str]:
    """Returns (system_message, user_message)."""
    sector   = quote.get("sector", "")
    industry = quote.get("industry", "")
    rag_query = f"Warren Buffett {sector} {industry} competitive advantage moat valuation"
    rag_context = retrieve(rag_query, k=4)

    def pct(v):
        return f"{v*100:.1f}%" if v is not None else "N/A"
    def money(n):
        if not n: return "N/A"
        if abs(n) >= 1e12: return f"${n/1e12:.2f}T"
        if abs(n) >= 1e9:  return f"${n/1e9:.2f}B"
        return f"${n/1e6:.1f}M"
    def num(v, decimals=1):
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    name    = quote.get("name", ticker)
    price   = quote.get("price")
    mktcap  = quote.get("marketCap")
    summary = quote.get("summary", "")

    snapshot = (
        f"COMPANY: {name} ({ticker.upper()})\n"
        f"Sector: {sector or 'N/A'}  |  Industry: {industry or 'N/A'}\n"
        f"Price: ${price}  |  Market Cap: {money(mktcap)}\n"
        f"Trailing P/E: {num(quote.get('pe'))}  |  Forward P/E: {num(quote.get('forwardPE'))}  "
        f"|  PEG Ratio: {num(quote.get('pegRatio'))}\n"
        f"EV/EBITDA: {num(quote.get('evToEbitda'))}  |  "
        f"FCF Yield: {pct(quote.get('fcfYield'))}  |  "
        f"Dividend Yield: {pct(quote.get('dividendYield'))}\n"
        f"ROE: {pct(quote.get('roe'))}  |  ROA: {pct(quote.get('roa'))}\n"
        f"Revenue Growth (YoY): {pct(quote.get('revenueGrowth'))}  |  "
        f"Earnings Growth (YoY): {pct(quote.get('earningsGrowth'))}\n"
    )
    if summary:
        snapshot += f"Business: {summary}\n"

    score_line = (
        f"\nBUFFETT WEIGHTED SCORE: {weighted_score:.1f}/100  "
        f"({'Strong moat zone' if weighted_score >= 70 else 'Watch zone' if weighted_score >= 55 else 'Avoid zone'})\n"
    )

    by_cat: dict[str, list[str]] = {}
    for r in ratios:
        cat    = r.get("category", "Other")
        val    = r.get("value")
        status = "PASS" if r.get("passes") is True else ("FAIL" if r.get("passes") is False else " N/A")
        weight = r.get("weight", 0)
        if val is not None:
            val_str = f"{val*100:.1f}%" if abs(val) < 5 else f"{val:.2f}x"
        else:
            val_str = "N/A"
        threshold = r.get("threshold", "")
        line = f"  [{status}] {r['name']:<28} {val_str:>8}  (rule: {threshold}, wt: {weight:.0%})"
        by_cat.setdefault(cat, []).append(line)

    metrics_block = ""
    for cat, lines in by_cat.items():
        metrics_block += f"\n{cat}:\n" + "\n".join(lines) + "\n"

    system_msg = (
        "You are a senior equity analyst at a value-focused investment firm. "
        "You combine Warren Buffett's timeless principles — durable competitive advantage, "
        "honest management, predictable earnings, sensible price — with modern metrics "
        "like ROIC, FCF yield, and PEG ratio. "
        "Your analysis must be concrete, data-driven, and sector-aware. "
        "Avoid generic statements. Every claim must be backed by a specific number from the data provided.\n\n"
        "EXAMPLE OUTPUT (follow this format and quality level exactly):\n\n"
        "VERDICT: BUY — KO earns a Buffett score of 82/100; six decades of brand moat "
        "and a 24.1% net margin at a reasonable 22x forward P/E justify a long-term position.\n\n"
        "STRENGTHS:\n"
        "- Gross margin of 58.1% (threshold ≥40%) reflects unmatched pricing power; "
        "consumers pay a premium that private-label competitors cannot sustainably undercut.\n"
        "- CapEx at 9.3% of net income (threshold <25%) confirms the business runs on intangible "
        "assets — recipes and distribution — not depreciating machinery.\n\n"
        "CONCERNS:\n"
        "- Revenue growth of 2.1% YoY lags inflation; organic volume is stagnant in developed "
        "markets, capping the long-term earnings compounding rate.\n"
        "- SG&A at 28.7% of gross profit is near the 30% ceiling; any incremental spend on "
        "health-conscious line extensions could breach the threshold.\n\n"
        "BUFFETT ALIGNMENT:\n"
        "KO has a textbook wide moat — global distribution and brand intangibles have held for "
        "six decades. At 22x forward earnings and a 3.1% FCF yield, the price is fair but not a bargain.\n\n"
        "MODERN CONTEXT:\n"
        "Health-trend headwinds require a conservative 2–3% DCF terminal growth rate rather than "
        "the 4–5% Buffett could have assumed in the 1980s; the moat is durable but narrower than it once was.\n\n"
        "--- END EXAMPLE ---"
    )

    user_msg = (
        "─── BUFFETT PRINCIPLES (RAG) ───\n"
        f"{rag_context}\n\n"
        "─── STOCK SNAPSHOT ───\n"
        f"{snapshot}"
        f"{score_line}"
        f"{metrics_block}\n"
        "─── OUTPUT FORMAT ───\n"
        "Write exactly these five sections. Be specific. Cite actual numbers.\n\n"
        "VERDICT: [BUY / HOLD / AVOID] — one sentence with the core reason and the weighted score\n\n"
        "STRENGTHS:\n"
        "- 2–3 bullet points. Each must cite a specific metric value and explain WHY it signals a competitive advantage\n"
        "  Example: 'Gross margin of 47.3% (threshold ≥40%) signals pricing power — Apple charges premium prices competitors cannot match'\n\n"
        "CONCERNS:\n"
        "- 2–3 bullet points. Cite specific failing or borderline metrics and explain the investment risk they represent\n\n"
        "BUFFETT ALIGNMENT:\n"
        "- 2 sentences. Assess: (1) Does this company have a durable moat? "
        "(2) Is the current price sensible given the quality (reference P/E or FCF yield)?\n\n"
        "MODERN CONTEXT:\n"
        "- 1–2 sentences. Which Buffett rules need reinterpretation for this company's sector/era, and why?\n\n"
        "Total length: 300–400 words. Tone: decisive, analytical, institutional."
    )

    return system_msg, user_msg


def _stream_anthropic(
    system_msg: str,
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
) -> Iterator[str]:
    """Anthropic streaming → SSE token frames. Anthropic takes `system` as a
    top-level field, not a message role, so callers pass user/assistant history
    in `messages` and the system prompt separately."""
    client = _get_anthropic()
    with client.messages.stream(
        model=model,
        system=system_msg,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    ) as stream:
        for token in stream.text_stream:
            if token:
                yield f"data: {token}\n\n"


def _stream_groq(
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
) -> Iterator[str]:
    client = _get_groq()
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield f"data: {token}\n\n"


def stream_recommendation(
    ticker: str,
    ratios: list[dict],
    weighted_score: float,
    quote: dict,
) -> Iterator[str]:
    """Stream an AI investment recommendation as SSE tokens.
    Uses Anthropic Sonnet when configured; falls back to Groq."""
    try:
        system_msg, user_msg = _build_recommendation_prompt(ticker, ratios, weighted_score, quote)
        provider = _resolve_provider()

        if provider == "anthropic":
            yield from _stream_anthropic(
                system_msg=system_msg,
                messages=[{"role": "user", "content": user_msg}],
                model=ANTHROPIC_RECO_MODEL,
                max_tokens=800,
                temperature=0.6,
            )
        else:
            yield from _stream_groq(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                model=GROQ_RECOMMENDATION_MODEL,
                max_tokens=800,
                temperature=0.6,
            )

        yield "data: [DONE]\n\n"

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"


def stream_chat(
    question: str,
    ticker: str,
    ratios: list[dict],
    history: list[dict] | None = None,
) -> Iterator[str]:
    """Stream an LLM response with full conversation history.
    Anthropic Haiku when configured; falls back to Groq."""
    try:
        system_msg   = _build_chat_system_message()
        user_msg     = _build_chat_user_message(question, ticker, ratios)
        provider     = _resolve_provider()

        history = history or []
        messages = [*history, {"role": "user", "content": user_msg}]

        if provider == "anthropic":
            yield from _stream_anthropic(
                system_msg=system_msg,
                messages=messages,
                model=ANTHROPIC_CHAT_MODEL,
                max_tokens=1024,
                temperature=0.7,
            )
        else:
            yield from _stream_groq(
                messages=[{"role": "system", "content": system_msg}, *messages],
                model=GROQ_MODEL,
                max_tokens=1024,
                temperature=0.7,
            )

        yield "data: [DONE]\n\n"

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"
