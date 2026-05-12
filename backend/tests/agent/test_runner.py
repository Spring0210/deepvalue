"""AgentRunner contract:
 - run() returns AgentRun with COMPLETED status when LLM ends turn
 - tool_calls produce a TOOL_BATCH step in the trail
 - max_iters cap → CAPPED status, final_text falls back to last LLM text
 - LLM exception → FAILED status with ERROR step
 - stream() yields steps in order and matches run() trail when LLM is deterministic"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel

from app.agent.llm import LLMTurn
from app.agent.models import AgentRunStatus, LLMUsage, StepKind, ToolCall
from app.agent.runner import AgentRunner
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Args(BaseModel):
    x: int = 0


@dataclass
class _ScriptedLLM:
    """Replays a queue of LLMTurns in order. Raise via `raise_on_turn`."""
    turns:         list[LLMTurn]
    raise_on_turn: Optional[int] = None
    _call_idx:     int = 0

    async def complete(self, *, system, messages, tools, model=None, **_) -> LLMTurn:
        idx = self._call_idx
        self._call_idx += 1
        if self.raise_on_turn is not None and idx == self.raise_on_turn:
            raise RuntimeError("simulated LLM failure")
        if idx >= len(self.turns):
            # Default: end with empty text if script runs out (defensive).
            return _final_turn("(no more scripted turns)")
        return self.turns[idx]


def _final_turn(text: str) -> LLMTurn:
    return LLMTurn(
        text=text,
        tool_calls=[],
        stop_reason="end_turn",
        usage=LLMUsage(model="claude-test", input_tokens=10, output_tokens=5, cost_usd=0.001),
        raw_assistant_blocks=[{"type": "text", "text": text}],
    )


def _tool_turn(call_id: str, name: str, args: dict[str, Any]) -> LLMTurn:
    return LLMTurn(
        text=None,
        tool_calls=[ToolCall(id=call_id, name=name, args=args)],
        stop_reason="tool_use",
        usage=LLMUsage(model="claude-test", input_tokens=20, output_tokens=10, cost_usd=0.002),
        raw_assistant_blocks=[
            {"type": "tool_use", "id": call_id, "name": name, "input": args},
        ],
    )


def _build(turns, *, raise_on_turn=None, max_iters=4):
    registry = ToolRegistry()

    async def ok_tool(args: _Args):
        return {"echo": args.x}

    registry.register(
        name="ping", description="t", args_model=_Args,
        handler=ok_tool, timeout_s=2.0, max_retries=0,
    )
    return AgentRunner(
        llm=_ScriptedLLM(turns=turns, raise_on_turn=raise_on_turn),
        registry=registry,
        dispatcher=ToolDispatcher(registry),
        system="sys",
        max_iters=max_iters,
    )


# ── run() ─────────────────────────────────────────────────────────────────────

async def test_run_completes_when_llm_ends_turn():
    runner = _build([_final_turn("verdict text")])
    run = await runner.run("query")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.final_text == "verdict text"
    kinds = [s.kind for s in run.steps]
    assert kinds == [StepKind.LLM, StepKind.FINAL]


async def test_run_handles_tool_call_then_final():
    runner = _build([
        _tool_turn("tu1", "ping", {"x": 7}),
        _final_turn("done"),
    ])
    run = await runner.run("query")
    assert run.status == AgentRunStatus.COMPLETED
    kinds = [s.kind for s in run.steps]
    assert kinds == [StepKind.LLM, StepKind.TOOL_BATCH, StepKind.LLM, StepKind.FINAL]

    tb_step = run.steps[1]
    assert len(tb_step.tool_results) == 1
    assert tb_step.tool_results[0].ok is True
    assert tb_step.tool_results[0].output == {"echo": 7}


async def test_run_failed_on_llm_exception():
    runner = _build([_final_turn("ignored")], raise_on_turn=0)
    run = await runner.run("query")
    assert run.status == AgentRunStatus.FAILED
    assert run.error is not None and "simulated LLM" in run.error
    assert run.steps[-1].kind == StepKind.ERROR


async def test_run_hits_cap_when_llm_loops_on_tools():
    # Three tool turns + max_iters=2 → cap fires
    turns = [_tool_turn("t1", "ping", {"x": 1}) for _ in range(5)]
    runner = _build(turns, max_iters=2)
    run = await runner.run("query")
    assert run.status == AgentRunStatus.CAPPED
    assert run.error is not None and "max_iters" in run.error


async def test_run_accumulates_usage_and_cost():
    runner = _build([
        _tool_turn("tu1", "ping", {"x": 1}),
        _final_turn("ok"),
    ])
    run = await runner.run("query")
    # 2 LLM turns × the scripted token counts above
    assert run.total_input_tokens == 30
    assert run.total_output_tokens == 15
    assert run.total_cost_usd > 0


# ── stream() ──────────────────────────────────────────────────────────────────

async def test_stream_yields_steps_in_order():
    runner = _build([
        _tool_turn("tu1", "ping", {"x": 1}),
        _final_turn("done"),
    ])
    received_kinds = []
    async for step, run in runner.stream("query"):
        received_kinds.append(step.kind)
    # Same shape as run() trail
    assert received_kinds == [
        StepKind.LLM, StepKind.TOOL_BATCH, StepKind.LLM, StepKind.FINAL,
    ]


async def test_stream_completes_run_state_after_iteration():
    runner = _build([_final_turn("only one")])
    last_run = None
    async for _step, run in runner.stream("query"):
        last_run = run
    assert last_run is not None
    assert last_run.status == AgentRunStatus.COMPLETED
    assert last_run.final_text == "only one"
    assert last_run.finished_at is not None


async def test_stream_yields_error_step_on_llm_failure():
    runner = _build([_final_turn("ignored")], raise_on_turn=0)
    steps = []
    async for step, _ in runner.stream("query"):
        steps.append(step)
    assert steps[-1].kind == StepKind.ERROR


# ── structured output ─────────────────────────────────────────────────────────

class _Verdict(BaseModel):
    ticker:  str
    verdict: str
    score:   int


def _build_structured(turns, *, max_repairs=2, max_iters=6):
    registry = ToolRegistry()
    return AgentRunner(
        llm=_ScriptedLLM(turns=turns),
        registry=registry,
        dispatcher=ToolDispatcher(registry),
        system="sys",
        max_iters=max_iters,
        output_schema=_Verdict,
        max_repairs=max_repairs,
    )


async def test_structured_happy_path_populates_structured_output():
    payload = '{"ticker": "AAPL", "verdict": "buy", "score": 82}'
    runner = _build_structured([_final_turn(payload)])
    run = await runner.run("q")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.structured_output == {"ticker": "AAPL", "verdict": "buy", "score": 82}
    assert run.final_text == payload


async def test_structured_invalid_then_valid_emits_repair_step():
    bad = "not even close to JSON"
    good = '{"ticker": "MSFT", "verdict": "hold", "score": 60}'
    runner = _build_structured([_final_turn(bad), _final_turn(good)])
    run = await runner.run("q")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.structured_output == {"ticker": "MSFT", "verdict": "hold", "score": 60}
    kinds = [s.kind for s in run.steps]
    # LLM(bad) → REPAIR → LLM(good) → FINAL
    assert kinds == [StepKind.LLM, StepKind.REPAIR, StepKind.LLM, StepKind.FINAL]
    repair = next(s for s in run.steps if s.kind == StepKind.REPAIR)
    assert repair.error and "JSON" in repair.error


async def test_structured_exhausts_repairs_then_fails():
    bad = "still not JSON"
    # max_repairs=1 → 1 failed attempt + 1 repair attempt = 2 LLM turns before giving up
    runner = _build_structured(
        [_final_turn(bad), _final_turn(bad), _final_turn(bad)],
        max_repairs=1,
    )
    run = await runner.run("q")
    assert run.status == AgentRunStatus.FAILED
    assert run.structured_output is None
    assert run.error and "repair attempts" in run.error
    assert run.steps[-1].kind == StepKind.ERROR
    assert sum(1 for s in run.steps if s.kind == StepKind.REPAIR) == 1


async def test_structured_schema_mismatch_triggers_repair():
    # Valid JSON but schema mismatch (score is wrong type) → repair, then good.
    bad = '{"ticker": "NVDA", "verdict": "buy", "score": "high"}'
    good = '{"ticker": "NVDA", "verdict": "buy", "score": 91}'
    runner = _build_structured([_final_turn(bad), _final_turn(good)])
    run = await runner.run("q")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.structured_output["score"] == 91
    repair = next(s for s in run.steps if s.kind == StepKind.REPAIR)
    assert "schema" in (repair.error or "").lower()


async def test_no_schema_keeps_structured_output_none():
    # Baseline: existing behaviour unchanged when no output_schema is set.
    runner = _build([_final_turn("free-form prose")])
    run = await runner.run("q")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.structured_output is None
    assert run.final_text == "free-form prose"
