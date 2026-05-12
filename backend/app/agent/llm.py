"""Anthropic Messages API wrapper with token + cost accounting.

This is the only place the rest of the harness imports `anthropic`. The
`complete()` method takes message history + tool schemas, returns a single
typed `LLMTurn` describing what the model said and what tools it wants to call.
Cost is computed from a per-model price table; cache hits/writes are tracked
separately so we can quantify prompt-caching savings later."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import Any, Optional

from anthropic import AsyncAnthropic

from app.agent.models import LLMUsage, ToolCall

# USD per 1M tokens. Source: Anthropic public pricing as of 2026-Q2.
# Cache reads are 10% of input price; cache writes are 125% of input price.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # model_id_prefix:        (input_per_mtok, output_per_mtok)
    "claude-opus-4":          (15.00, 75.00),
    "claude-sonnet-4":        ( 3.00, 15.00),
    "claude-haiku-4":         ( 1.00,  5.00),
    "claude-3-5-sonnet":      ( 3.00, 15.00),
    "claude-3-5-haiku":       ( 0.80,  4.00),
    "claude-3-opus":          (15.00, 75.00),
}


def _price_for(model: str) -> tuple[float, float]:
    for prefix, price in _PRICE_PER_MTOK.items():
        if model.startswith(prefix):
            return price
    return (3.00, 15.00)  # Sonnet-ish fallback so cost is never zero on unknown models


@dataclass
class LLMTurn:
    text:        Optional[str]           # assistant prose, if any
    tool_calls:  list[ToolCall]          # tool_use blocks (may be empty)
    stop_reason: str                     # "end_turn" | "tool_use" | "max_tokens" | …
    usage:       LLMUsage
    raw_assistant_blocks: list[dict[str, Any]]   # echoed back into next-turn history


class AnthropicClient:
    def __init__(self, api_key: str, default_model: str) -> None:
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._client = AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    async def complete(
        self,
        *,
        system:      str,
        messages:    list[dict[str, Any]],
        tools:       list[dict[str, Any]],
        model:       Optional[str] = None,
        max_tokens:  int = 2048,
        temperature: float = 0.3,
    ) -> LLMTurn:
        model = model or self._default_model
        t0 = time.perf_counter()

        resp = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools or [],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        text_parts:   list[str]      = []
        tool_calls:   list[ToolCall] = []
        raw_blocks:   list[dict[str, Any]] = []

        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
                raw_blocks.append({"type": "text", "text": block.text})
            elif btype == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input)))
                raw_blocks.append({
                    "type":  "tool_use",
                    "id":    block.id,
                    "name":  block.name,
                    "input": dict(block.input),
                })

        usage = _build_usage(model, resp.usage, latency_ms)
        return LLMTurn(
            text=("\n".join(text_parts).strip() or None),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "",
            usage=usage,
            raw_assistant_blocks=raw_blocks,
        )

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            await self._client.close()


def _build_usage(model: str, raw_usage: Any, latency_ms: int) -> LLMUsage:
    input_tokens       = getattr(raw_usage, "input_tokens", 0)
    output_tokens      = getattr(raw_usage, "output_tokens", 0)
    cache_read_tokens  = getattr(raw_usage, "cache_read_input_tokens", 0) or 0
    cache_write_tokens = getattr(raw_usage, "cache_creation_input_tokens", 0) or 0

    in_per_mtok, out_per_mtok = _price_for(model)
    cost = (
        (input_tokens       * in_per_mtok)
        + (cache_read_tokens  * in_per_mtok * 0.10)
        + (cache_write_tokens * in_per_mtok * 1.25)
        + (output_tokens      * out_per_mtok)
    ) / 1_000_000

    return LLMUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        cost_usd=round(cost, 6),
        latency_ms=latency_ms,
    )
