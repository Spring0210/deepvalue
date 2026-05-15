"""AnthropicClient wire-format contract:
 - system string is converted to a single cache-eligible text block (ephemeral)
 - last tool entry is marked with `cache_control` so the tools array caches as a unit
 - empty tools array stays empty (no spurious marker)
 - cache_read / cache_creation token counts from the API surface into LLMUsage
 - opt-out: cache_system=False / cache_tools=False keeps the legacy plain shape"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent.llm import AnthropicClient


@dataclass
class _RawUsage:
    input_tokens:                 int = 0
    output_tokens:                int = 0
    cache_read_input_tokens:      int = 0
    cache_creation_input_tokens:  int = 0


@dataclass
class _RawResp:
    content:     list[Any]
    stop_reason: str
    usage:       _RawUsage


class _FakeMessages:
    """Captures the kwargs passed to messages.create and returns a canned response."""

    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] = {}
        self.response = _RawResp(
            content=[type("Block", (), {"type": "text", "text": "ok"})()],
            stop_reason="end_turn",
            usage=_RawUsage(input_tokens=4, output_tokens=2),
        )

    async def create(self, **kwargs: Any) -> _RawResp:
        self.last_kwargs = kwargs
        return self.response


def _patched_client(*, cache_system: bool = True, cache_tools: bool = True) -> tuple[AnthropicClient, _FakeMessages]:
    client = AnthropicClient(
        api_key="test", default_model="claude-sonnet-4-5",
        cache_system=cache_system, cache_tools=cache_tools,
    )
    fake = _FakeMessages()
    client._client.messages = fake                                                # type: ignore[attr-defined]
    return client, fake


async def test_system_wrapped_in_cache_eligible_block_by_default():
    client, fake = _patched_client()
    await client.complete(system="you are an agent", messages=[{"role": "user", "content": "hi"}], tools=[])

    system_param = fake.last_kwargs["system"]
    assert isinstance(system_param, list)
    assert system_param == [{
        "type":          "text",
        "text":          "you are an agent",
        "cache_control": {"type": "ephemeral"},
    }]


async def test_last_tool_marked_with_cache_control():
    client, fake = _patched_client()
    tools = [
        {"name": "a", "description": "a", "input_schema": {"type": "object"}},
        {"name": "b", "description": "b", "input_schema": {"type": "object"}},
    ]
    await client.complete(system="s", messages=[{"role": "user", "content": "hi"}], tools=tools)

    sent_tools = fake.last_kwargs["tools"]
    assert sent_tools[0].get("cache_control") is None, "only the tail should be marked"
    assert sent_tools[-1]["cache_control"] == {"type": "ephemeral"}
    # Original list must not be mutated — the registry returns a fresh list per call,
    # but mutating shared dicts inside would leak across requests.
    assert "cache_control" not in tools[-1]


async def test_empty_tools_stays_empty():
    client, fake = _patched_client()
    await client.complete(system="s", messages=[{"role": "user", "content": "hi"}], tools=[])
    assert fake.last_kwargs["tools"] == []


async def test_opt_out_keeps_legacy_string_and_unmarked_tools():
    client, fake = _patched_client(cache_system=False, cache_tools=False)
    tools = [{"name": "a", "description": "a", "input_schema": {"type": "object"}}]
    await client.complete(system="s", messages=[{"role": "user", "content": "hi"}], tools=tools)

    assert fake.last_kwargs["system"] == "s"
    assert fake.last_kwargs["tools"] == tools
    assert "cache_control" not in fake.last_kwargs["tools"][0]


async def test_cache_token_counts_flow_into_usage():
    client, fake = _patched_client()
    fake.response = _RawResp(
        content=[type("Block", (), {"type": "text", "text": "ok"})()],
        stop_reason="end_turn",
        usage=_RawUsage(
            input_tokens=100, output_tokens=20,
            cache_read_input_tokens=80, cache_creation_input_tokens=5,
        ),
    )
    turn = await client.complete(system="s", messages=[{"role": "user", "content": "hi"}], tools=[])

    assert turn.usage.cache_read_tokens  == 80
    assert turn.usage.cache_write_tokens == 5
    # Cost should reflect the 10% / 125% multipliers on cached vs written tokens —
    # i.e. strictly cheaper than the same input with no caching.
    no_cache_cost = (100 + 80 + 5) * 3.00 / 1_000_000 + 20 * 15.00 / 1_000_000
    assert turn.usage.cost_usd < no_cache_cost


async def test_empty_system_is_passed_through_when_caching():
    """Empty system → empty system. Anthropic 400s on a zero-length cache block."""
    client, fake = _patched_client()
    await client.complete(system="", messages=[{"role": "user", "content": "hi"}], tools=[])
    assert fake.last_kwargs["system"] == ""
