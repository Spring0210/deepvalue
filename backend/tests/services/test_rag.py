"""Tests for the RAG layer: provider routing, knowledge-file scanning,
index signature, metadata propagation, and event-typed SSE framing.

These tests never touch a real LLM or load the sentence-transformer model.
The embeddings call (`init_rag` → `_get_embeddings`) is mocked out so the
suite stays in the <5s budget called out in CLAUDE.md §6."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import rag


# ── _compute_signature ────────────────────────────────────────────────────────

def test_signature_stable_for_same_files(tmp_path: Path):
    f1 = tmp_path / "a.txt"; f1.write_text("alpha")
    f2 = tmp_path / "b.txt"; f2.write_text("beta")
    sig1 = rag._compute_signature([f1, f2])
    sig2 = rag._compute_signature([f1, f2])
    assert sig1 == sig2


def test_signature_changes_on_edit(tmp_path: Path):
    f = tmp_path / "a.txt"; f.write_text("alpha")
    sig1 = rag._compute_signature([f])
    # mtime resolution is 1s in compute_signature; force a different timestamp.
    import os, time
    new_time = f.stat().st_mtime + 10
    os.utime(f, (new_time, new_time))
    f.write_text("alpha plus an edit that grows the file")
    sig2 = rag._compute_signature([f])
    assert sig1 != sig2


def test_signature_changes_when_new_file_added(tmp_path: Path):
    f1 = tmp_path / "a.txt"; f1.write_text("alpha")
    sig1 = rag._compute_signature([f1])
    f2 = tmp_path / "b.txt"; f2.write_text("beta")
    sig2 = rag._compute_signature([f1, f2])
    assert sig1 != sig2


# ── _resolve_provider ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "anthropic_key, groq_key, override, expected",
    [
        ("k", "k",  "anthropic", "anthropic"),
        ("k", "k",  "groq",      "groq"),
        ("k", "",   "anthropic", "anthropic"),
        ("",  "k",  "anthropic", "groq"),     # override asks for anthropic but key missing → fallback
        ("",  "k",  "groq",      "groq"),
        ("k", "",   "groq",      "anthropic"),# override asks for groq but key missing → fallback
    ],
)
def test_resolve_provider(monkeypatch, anthropic_key, groq_key, override, expected):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", anthropic_key)
    monkeypatch.setattr(rag, "GROQ_API_KEY", groq_key)
    monkeypatch.setattr(rag, "CHAT_PROVIDER", override)
    assert rag._resolve_provider() == expected


# ── _build_documents ──────────────────────────────────────────────────────────

def test_build_documents_attaches_source_metadata(tmp_path: Path):
    f1 = tmp_path / "buffett_knowledge.txt"
    f1.write_text("Buffett looks for a moat. " * 80)
    f2 = tmp_path / "2020.txt"
    f2.write_text("In 2020 we held GEICO. " * 80)
    docs = rag._build_documents([f1, f2])
    assert len(docs) > 0
    sources = {d.metadata["source"] for d in docs}
    assert sources == {"buffett_knowledge", "2020"}
    # And content actually carries through:
    assert any("moat" in d.page_content for d in docs)
    assert any("GEICO" in d.page_content for d in docs)


# ── _knowledge_files ──────────────────────────────────────────────────────────

def test_knowledge_files_picks_up_letters_dir(tmp_path: Path, monkeypatch):
    kb   = tmp_path / "buffett_knowledge.txt"
    kb.write_text("rules")
    letters = tmp_path / "buffett_letters"
    letters.mkdir()
    (letters / "2020.txt").write_text("...")
    (letters / "2021.txt").write_text("...")
    (letters / "ignore.md").write_text("not a .txt — should be skipped")

    monkeypatch.setattr(rag, "_KB_PATH", kb)
    monkeypatch.setattr(rag, "_LETTERS_DIR", letters)

    files = rag._knowledge_files()
    names = [f.name for f in files]
    assert "buffett_knowledge.txt" in names
    assert "2020.txt" in names
    assert "2021.txt" in names
    assert "ignore.md" not in names


# ── retrieve_with_sources ────────────────────────────────────────────────────

def test_retrieve_with_sources_assigns_ids_and_truncates(monkeypatch):
    long_text = "moat " * 200  # > 280 chars, forces snippet truncation
    class FakeDoc:
        def __init__(self, page_content, source):
            self.page_content = page_content
            self.metadata = {"source": source}
    class FakeDB:
        def similarity_search(self, _q, k=3):
            return [
                FakeDoc(long_text, "buffett_knowledge"),
                FakeDoc("short letter content", "2020"),
            ]
    monkeypatch.setattr(rag, "_vector_db", FakeDB())

    ctx, sources = rag.retrieve_with_sources("any q", k=2)
    assert "[1]" in ctx and "[2]" in ctx
    assert [s["id"] for s in sources] == [1, 2]
    assert [s["source"] for s in sources] == ["buffett_knowledge", "2020"]
    assert sources[0]["snippet"].endswith("…")        # truncated
    assert not sources[1]["snippet"].endswith("…")    # short, untruncated
    assert len(sources[0]["snippet"]) <= 281


# ── event-typed SSE framing ──────────────────────────────────────────────────

def _consume(gen):
    return [x for x in gen]


def _parse_sse(frames: list[str]) -> list[tuple[str, dict]]:
    """Decode list of `event: X\\ndata: {...}\\n\\n` strings into (event, payload)."""
    out: list[tuple[str, dict]] = []
    for frame in frames:
        body = frame.strip("\n")
        event = ""
        data_lines: list[str] = []
        for line in body.split("\n"):
            if   line.startswith("event: "): event = line[7:]
            elif line.startswith("data: "):  data_lines.append(line[6:])
        if data_lines:
            out.append((event, json.loads("\n".join(data_lines))))
    return out


def test_stream_chat_emits_sources_then_tokens_then_done(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "GROQ_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(
        rag, "retrieve_with_sources",
        lambda q, k=3: ("[1] (source: kb)\ncontext", [{"id": 1, "source": "kb", "snippet": "context"}]),
    )

    called = {"anthropic": 0, "groq": 0}
    def fake_anthropic_tokens(*, system_msg, messages, model, max_tokens, temperature):
        called["anthropic"] += 1
        assert "Buffett" in system_msg
        assert messages[-1]["role"] == "user"
        yield "Hello "
        yield "world"
    monkeypatch.setattr(rag, "_stream_anthropic_tokens", fake_anthropic_tokens)
    monkeypatch.setattr(rag, "_stream_groq_tokens", lambda **_: (called.__setitem__("groq", called["groq"] + 1), iter([]))[1])

    events = _parse_sse(_consume(rag.stream_chat("Is AAPL a good buy?", "AAPL", [])))
    kinds = [e for e, _ in events]
    assert kinds == ["sources", "token", "token", "done"]
    assert events[0][1]["items"][0]["source"] == "kb"
    assert events[1][1]["text"] == "Hello "
    assert events[2][1]["text"] == "world"
    assert called == {"anthropic": 1, "groq": 0}


def test_stream_chat_token_payload_survives_newlines(monkeypatch):
    """The whole point of switching to event-typed JSON SSE — a token that
    contains a newline must not be silently dropped at the boundary."""
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(rag, "retrieve_with_sources", lambda q, k=3: ("ctx", []))
    monkeypatch.setattr(
        rag, "_stream_anthropic_tokens",
        lambda **_: iter(["## Heading\nBody line"]),
    )
    events = _parse_sse(_consume(rag.stream_chat("q", "X", [])))
    token_events = [d for e, d in events if e == "token"]
    assert token_events[0]["text"] == "## Heading\nBody line"


def test_stream_chat_falls_back_to_groq_when_no_anthropic(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(rag, "GROQ_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "groq")
    monkeypatch.setattr(rag, "retrieve_with_sources", lambda q, k=3: ("ctx", []))

    called = {"anthropic": 0, "groq": 0}
    def fake_anthropic(**_): called["anthropic"] += 1; yield "x"
    def fake_groq(**_):      called["groq"] += 1;      yield "x"
    monkeypatch.setattr(rag, "_stream_anthropic_tokens", fake_anthropic)
    monkeypatch.setattr(rag, "_stream_groq_tokens", fake_groq)

    _consume(rag.stream_chat("q", "X", []))
    assert called == {"anthropic": 0, "groq": 1}


def test_stream_recommendation_emits_token_then_done(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(rag, "retrieve", lambda q, k=3: "ctx")

    called = {"anthropic": 0}
    def fake(**_): called["anthropic"] += 1; yield "verdict"
    monkeypatch.setattr(rag, "_stream_anthropic_tokens", fake)
    monkeypatch.setattr(rag, "_stream_groq_tokens", lambda **_: iter([]))

    ratios = [{"name": "GM", "value": 0.5, "passes": True, "threshold": "≥40%",
               "category": "Margins", "weight": 0.1}]
    quote = {"name": "KO", "sector": "Staples", "price": 60, "marketCap": 250e9}
    events = _parse_sse(_consume(rag.stream_recommendation("KO", ratios, 82.0, quote)))
    kinds = [e for e, _ in events]
    # Recommendation does NOT emit a sources event — citation UI is chat-only for now.
    assert "sources" not in kinds
    assert kinds[-1] == "done"
    assert called == {"anthropic": 1}


def test_stream_chat_emits_error_event_on_exception(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(rag, "retrieve_with_sources", lambda q, k=3: ("ctx", []))

    def boom(**_):
        raise RuntimeError("simulated upstream failure")
        yield  # pragma: no cover — make it a generator
    monkeypatch.setattr(rag, "_stream_anthropic_tokens", boom)

    events = _parse_sse(_consume(rag.stream_chat("q", "X", [])))
    error_events = [d for e, d in events if e == "error"]
    assert error_events and "simulated upstream failure" in error_events[0]["error"]
