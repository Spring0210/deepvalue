"""structured.parse_structured contract:
 - clean JSON parses + validates
 - ```json …``` and ``` …``` fences are tolerated
 - empty / non-JSON text raises StructuredOutputError with raw attached
 - schema-mismatching JSON raises with validation details
 - schema_hint embeds the JSON Schema in the addendum"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field

from app.agent.structured import (
    StructuredOutputError,
    parse_structured,
    schema_hint,
)


class _Verdict(BaseModel):
    ticker:   str
    verdict:  str = Field(pattern=r"^(buy|hold|sell)$")
    score:    int = Field(ge=0, le=100)


def test_parse_structured_happy_path():
    raw = json.dumps({"ticker": "AAPL", "verdict": "buy", "score": 82})
    out = parse_structured(raw, _Verdict)
    assert isinstance(out, _Verdict)
    assert out.ticker == "AAPL" and out.verdict == "buy" and out.score == 82


def test_parse_structured_strips_json_fences():
    raw = '```json\n{"ticker": "MSFT", "verdict": "hold", "score": 55}\n```'
    out = parse_structured(raw, _Verdict)
    assert out.ticker == "MSFT"


def test_parse_structured_strips_plain_fences():
    raw = '```\n{"ticker": "NVDA", "verdict": "sell", "score": 30}\n```'
    out = parse_structured(raw, _Verdict)
    assert out.verdict == "sell"


def test_parse_structured_empty_raises():
    with pytest.raises(StructuredOutputError) as exc_info:
        parse_structured("", _Verdict)
    assert "empty" in str(exc_info.value).lower()
    assert exc_info.value.raw == ""


def test_parse_structured_non_json_raises():
    with pytest.raises(StructuredOutputError) as exc_info:
        parse_structured("the verdict is buy at 82", _Verdict)
    assert "JSON" in str(exc_info.value)


def test_parse_structured_schema_mismatch_raises():
    raw = json.dumps({"ticker": "AAPL", "verdict": "maybe", "score": 82})  # bad verdict
    with pytest.raises(StructuredOutputError) as exc_info:
        parse_structured(raw, _Verdict)
    assert "schema" in str(exc_info.value).lower()
    assert exc_info.value.raw == raw


def test_parse_structured_missing_field_raises():
    raw = json.dumps({"ticker": "AAPL", "verdict": "buy"})  # missing score
    with pytest.raises(StructuredOutputError) as exc_info:
        parse_structured(raw, _Verdict)
    assert "score" in str(exc_info.value)


def test_schema_hint_includes_schema_json():
    hint = schema_hint(_Verdict)
    assert "Output format" in hint
    assert "ticker" in hint and "verdict" in hint and "score" in hint
    assert "JSON Schema" in hint
