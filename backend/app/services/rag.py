from pathlib import Path
from typing import Iterator
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL, GROQ_RECOMMENDATION_MODEL

_DATA_DIR = Path(__file__).parent.parent / "data"
_KB_PATH = _DATA_DIR / "buffett_knowledge.txt"
_INDEX_PATH = _DATA_DIR / "faiss_index"

_vector_db: FAISS | None = None
_embeddings: HuggingFaceEmbeddings | None = None
_groq_client: Groq | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def init_rag() -> None:
    """Build or load the FAISS vector index. Called once at app startup."""
    global _vector_db
    embeddings = _get_embeddings()

    if _INDEX_PATH.exists():
        print("Loading existing FAISS index...")
        _vector_db = FAISS.load_local(
            str(_INDEX_PATH), embeddings, allow_dangerous_deserialization=True
        )
    else:
        print("Building FAISS index from knowledge base...")
        text = _KB_PATH.read_text(encoding="utf-8")
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = splitter.create_documents([text])
        _vector_db = FAISS.from_documents(docs, embeddings)
        _vector_db.save_local(str(_INDEX_PATH))
        print(f"FAISS index built with {len(docs)} chunks and saved.")


def retrieve(query: str, k: int = 3) -> str:
    """Return top-k relevant chunks from the knowledge base."""
    if _vector_db is None:
        init_rag()
    docs = _vector_db.similarity_search(query, k=k)  # type: ignore[union-attr]
    return "\n\n".join(d.page_content for d in docs)


def _build_chat_system_message() -> str:
    return (
        "You are an expert investment analyst well-versed in Warren Buffett's investment philosophy. "
        "Use the provided financial data and Buffett's principles to answer the user's questions. "
        "Be specific, concise, and reference actual numbers when available. "
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
        "Avoid generic statements. Every claim must be backed by a specific number from the data provided."
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


def stream_recommendation(
    ticker: str,
    ratios: list[dict],
    weighted_score: float,
    quote: dict,
) -> Iterator[str]:
    """Stream an AI investment recommendation as SSE tokens."""
    try:
        client = _get_groq()
        system_msg, user_msg = _build_recommendation_prompt(ticker, ratios, weighted_score, quote)

        stream = client.chat.completions.create(
            model=GROQ_RECOMMENDATION_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            stream=True,
            max_tokens=800,
            temperature=0.6,
        )

        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield f"data: {token}\n\n"

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
    """
    Stream an LLM response with full conversation history.
    history: list of {role, content} dicts from previous turns (excluding the current question).
    Yields SSE tokens ending with 'data: [DONE]\\n\\n'.
    """
    try:
        client = _get_groq()
        system_content = _build_chat_system_message()
        user_content   = _build_chat_user_message(question, ticker, ratios)

        messages: list[dict] = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            stream=True,
            max_tokens=1024,
            temperature=0.7,
        )

        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"
