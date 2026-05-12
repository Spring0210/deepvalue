"""ToolDispatcher contract:
 - never raises (failures land in ToolResult.error)
 - retries on transient errors up to spec.max_retries+1 total attempts
 - timeouts are encoded as error, not propagated
 - parallel batch returns results in input order
 - unknown tool name → error result, not KeyError"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.agent.models import ToolCall
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry


class _Args(BaseModel):
    x: int


def _make_registry_with(handler, *, timeout_s=5.0, max_retries=2):
    reg = ToolRegistry()
    reg.register(
        name="tool",
        description="test tool",
        args_model=_Args,
        handler=handler,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    return reg


# ── happy path ────────────────────────────────────────────────────────────────

async def test_dispatch_returns_ok_result():
    async def ok(args: _Args):
        return {"doubled": args.x * 2}

    reg = _make_registry_with(ok)
    disp = ToolDispatcher(reg)
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="tool", args={"x": 21})])
    assert out.ok is True
    assert out.output == {"doubled": 42}
    assert out.attempts == 1


# ── retries ───────────────────────────────────────────────────────────────────

async def test_dispatch_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky(args: _Args):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    reg = _make_registry_with(flaky, max_retries=2)
    disp = ToolDispatcher(reg)
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="tool", args={"x": 1})])
    assert out.ok is True
    assert out.attempts == 3


async def test_dispatch_gives_up_after_max_retries():
    async def always_fails(args: _Args):
        raise RuntimeError("nope")

    reg = _make_registry_with(always_fails, max_retries=1)
    disp = ToolDispatcher(reg)
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="tool", args={"x": 1})])
    assert out.ok is False
    assert "RuntimeError" in (out.error or "")
    assert out.attempts == 2  # 1 try + 1 retry


# ── timeout ───────────────────────────────────────────────────────────────────

async def test_dispatch_timeout_becomes_error_result():
    async def slow(args: _Args):
        await asyncio.sleep(1.0)
        return "should not get here"

    reg = _make_registry_with(slow, timeout_s=0.05, max_retries=0)
    disp = ToolDispatcher(reg)
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="tool", args={"x": 1})])
    assert out.ok is False
    assert "timeout" in (out.error or "").lower()


# ── invalid args ──────────────────────────────────────────────────────────────

async def test_dispatch_bad_args_no_handler_call():
    called = {"n": 0}

    async def handler(args: _Args):
        called["n"] += 1
        return "ok"

    reg = _make_registry_with(handler)
    disp = ToolDispatcher(reg)
    # 'x' missing → pydantic validation error
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="tool", args={})])
    assert out.ok is False
    assert "Invalid arguments" in (out.error or "")
    assert called["n"] == 0


# ── unknown tool ──────────────────────────────────────────────────────────────

async def test_dispatch_unknown_tool_is_error_not_raise():
    reg = ToolRegistry()  # empty
    disp = ToolDispatcher(reg)
    [out] = await disp.dispatch_many([ToolCall(id="c1", name="missing", args={})])
    assert out.ok is False
    assert "Unknown tool" in (out.error or "")


# ── parallel dispatch ─────────────────────────────────────────────────────────

async def test_dispatch_many_preserves_order_and_runs_in_parallel():
    async def slow(args: _Args):
        await asyncio.sleep(0.05)
        return args.x

    reg = _make_registry_with(slow, timeout_s=2.0)
    disp = ToolDispatcher(reg)

    calls = [ToolCall(id=f"c{i}", name="tool", args={"x": i}) for i in range(5)]
    import time
    t0 = time.perf_counter()
    results = await disp.dispatch_many(calls)
    elapsed = time.perf_counter() - t0

    # Order preserved
    assert [r.output for r in results] == [0, 1, 2, 3, 4]
    # If they ran sequentially this would be ~0.25s; parallel should be well under.
    assert elapsed < 0.20


# ── registry schemas ──────────────────────────────────────────────────────────

def test_registry_anthropic_schema_strips_titles():
    reg = _make_registry_with(lambda args: None)
    [schema] = reg.anthropic_schemas()
    assert schema["name"] == "tool"
    assert "input_schema" in schema
    # No `title` key at any level — Anthropic ignores it; we strip it for cleanliness.
    assert "title" not in schema["input_schema"]
    for prop in schema["input_schema"].get("properties", {}).values():
        assert "title" not in prop


def test_registry_duplicate_register_raises():
    reg = _make_registry_with(lambda args: None)
    try:
        reg.register("tool", "dup", _Args, lambda args: None)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected ValueError on duplicate register")
