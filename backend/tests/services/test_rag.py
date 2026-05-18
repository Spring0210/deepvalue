"""Tests for the RAG layer: provider routing, knowledge-file scanning,
index signature, and metadata propagation.

These tests never touch a real LLM or load the sentence-transformer model.
The embeddings call (`init_rag` → `_get_embeddings`) is mocked out so the
suite stays in the <5s budget called out in CLAUDE.md §6."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


# ── provider dispatch in stream_chat / stream_recommendation ──────────────────

def _consume(gen):
    return [x for x in gen]


def test_stream_chat_dispatches_to_anthropic(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "GROQ_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")

    monkeypatch.setattr(rag, "retrieve", lambda q, k=3: "[source: test]\nstub context")

    called = {"anthropic": 0, "groq": 0}
    def fake_anthropic(*, system_msg, messages, model, max_tokens, temperature):
        called["anthropic"] += 1
        assert "Buffett" in system_msg
        assert messages[-1]["role"] == "user"
        yield "data: hi\n\n"
    def fake_groq(*, messages, model, max_tokens, temperature):
        called["groq"] += 1
        yield "data: hi\n\n"

    monkeypatch.setattr(rag, "_stream_anthropic", fake_anthropic)
    monkeypatch.setattr(rag, "_stream_groq", fake_groq)

    out = _consume(rag.stream_chat("Is AAPL a good buy?", "AAPL", []))
    assert any("data: hi" in s for s in out)
    assert out[-1] == "data: [DONE]\n\n"
    assert called == {"anthropic": 1, "groq": 0}


def test_stream_chat_falls_back_to_groq_when_no_anthropic(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(rag, "GROQ_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "groq")
    monkeypatch.setattr(rag, "retrieve", lambda q, k=3: "stub")

    called = {"anthropic": 0, "groq": 0}
    def fake_anthropic(**_): called["anthropic"] += 1; yield "data: x\n\n"
    def fake_groq(**_):      called["groq"] += 1;      yield "data: x\n\n"
    monkeypatch.setattr(rag, "_stream_anthropic", fake_anthropic)
    monkeypatch.setattr(rag, "_stream_groq", fake_groq)

    _consume(rag.stream_chat("q", "X", []))
    assert called == {"anthropic": 0, "groq": 1}


def test_stream_recommendation_dispatches_to_anthropic(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(rag, "retrieve", lambda q, k=3: "ctx")

    called = {"anthropic": 0, "groq": 0}
    def fake_anthropic(**_): called["anthropic"] += 1; yield "data: y\n\n"
    def fake_groq(**_):      called["groq"] += 1;      yield "data: y\n\n"
    monkeypatch.setattr(rag, "_stream_anthropic", fake_anthropic)
    monkeypatch.setattr(rag, "_stream_groq", fake_groq)

    ratios = [{"name": "GM", "value": 0.5, "passes": True, "threshold": "≥40%",
               "category": "Margins", "weight": 0.1}]
    quote = {"name": "KO", "sector": "Staples", "price": 60, "marketCap": 250e9}
    out = _consume(rag.stream_recommendation("KO", ratios, 82.0, quote))
    assert called == {"anthropic": 1, "groq": 0}
    assert out[-1] == "data: [DONE]\n\n"


def test_stream_chat_returns_error_frame_on_exception(monkeypatch):
    monkeypatch.setattr(rag, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(rag, "CHAT_PROVIDER", "anthropic")
    monkeypatch.setattr(rag, "retrieve", lambda q, k=3: "ctx")

    def boom(**_):
        raise RuntimeError("simulated upstream failure")
        yield  # pragma: no cover — make it a generator
    monkeypatch.setattr(rag, "_stream_anthropic", boom)

    out = _consume(rag.stream_chat("q", "X", []))
    assert any(s.startswith("data: [ERROR]") for s in out)
    assert out[-1] == "data: [DONE]\n\n"
