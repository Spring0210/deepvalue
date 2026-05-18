"""Orchestrator (Planner → Subagents → Synthesizer) contract.

The scripted LLM dispatches `complete()` calls to a per-role queue based on
sentinel strings in the system prompt — that way one fake drives the planner,
each fundamentals subagent, and the synthesizer inside a single run.

All tests are offline: no real Anthropic, no real yfinance."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest
from pydantic import BaseModel

from app.agent.llm import LLMTurn
from app.agent.models import (
    AgentRunStatus,
    Finding,
    LLMUsage,
    OrchestratorStepKind,
    ResearchPlan,
    SubagentRole,
    Subtask,
    ToolCall,
)
from app.agent.orchestrator import Orchestrator
from app.agent.tools.registry import ToolRegistry


# ── scripted LLM ──────────────────────────────────────────────────────────────


@dataclass
class _RoleScriptedLLM:
    """Replays LLMTurns from per-role queues. Role detected by a sentinel
    substring in the `system` arg, since each agent has its own prompt."""

    planner:      list[LLMTurn] = field(default_factory=list)
    fundamentals: list[LLMTurn] = field(default_factory=list)
    synthesis:    list[LLMTurn] = field(default_factory=list)

    _p_idx: int = 0
    _f_idx: int = 0
    _s_idx: int = 0

    async def complete(self, *, system, messages, tools, model=None, **_) -> LLMTurn:
        if "DeepValue Planner" in system:
            queue, idx = self.planner, self._p_idx
            self._p_idx += 1
        elif "Fundamentals Subagent" in system:
            queue, idx = self.fundamentals, self._f_idx
            self._f_idx += 1
        elif "DeepValue Synthesizer" in system:
            queue, idx = self.synthesis, self._s_idx
            self._s_idx += 1
        else:
            raise RuntimeError(f"unrouted system prompt: {system[:60]!r}")

        if idx >= len(queue):
            return _final_turn("(out of script)")
        return queue[idx]


def _final_turn(text: str) -> LLMTurn:
    return LLMTurn(
        text=text,
        tool_calls=[],
        stop_reason="end_turn",
        usage=LLMUsage(model="claude-test", input_tokens=10, output_tokens=5, cost_usd=0.001),
        raw_assistant_blocks=[{"type": "text", "text": text}],
    )


def _tool_turn(calls: list[tuple[str, str, dict[str, Any]]]) -> LLMTurn:
    """Build a single assistant turn that requests one or more tool_uses."""
    tcs = [ToolCall(id=cid, name=name, args=args) for cid, name, args in calls]
    raw = [
        {"type": "tool_use", "id": c[0], "name": c[1], "input": c[2]}
        for c in calls
    ]
    return LLMTurn(
        text=None,
        tool_calls=tcs,
        stop_reason="tool_use",
        usage=LLMUsage(model="claude-test", input_tokens=20, output_tokens=10, cost_usd=0.002),
        raw_assistant_blocks=raw,
    )


# ── fixtures ──────────────────────────────────────────────────────────────────


def _build_master_registry() -> ToolRegistry:
    """Master registry exposing the 4 fundamentals tools as stub handlers."""
    reg = ToolRegistry()

    class _Args(BaseModel):
        ticker: str

    async def stub_quote(args: _Args):
        return {"ticker": args.ticker, "name": f"Stub Co ({args.ticker})", "price": 100.0}

    async def stub_score(args: _Args):
        return {"ticker": args.ticker, "weighted_score": 78.3, "trend_adjustment": 1.5}

    async def stub_valuation(args: _Args):
        return {"ticker": args.ticker, "dcf_value": 120.0, "margin_of_safety_pct": 16.7}

    async def stub_moat(args: _Args):
        return {"ticker": args.ticker, "moat_type": "Intangible Assets", "strength": "Wide"}

    reg.register("get_stock_quote",   "d", _Args, stub_quote,     timeout_s=2, max_retries=0)
    reg.register("get_buffett_score", "d", _Args, stub_score,     timeout_s=2, max_retries=0)
    reg.register("get_valuation",     "d", _Args, stub_valuation, timeout_s=2, max_retries=0)
    reg.register("get_moat",          "d", _Args, stub_moat,      timeout_s=2, max_retries=0)
    return reg


def _planner_turn(*, plan: dict) -> LLMTurn:
    return _final_turn(json.dumps(plan))


def _finding_turn(*, ticker: str) -> LLMTurn:
    payload = {
        "role":      "fundamentals",
        "ticker":    ticker,
        "summary":   f"{ticker} looks high quality with a moderate margin of safety.",
        "bullets":   [
            "Buffett score 78.3/100",
            "Intrinsic value $120 vs $100 price (16.7% margin)",
            "Wide moat — intangible assets",
        ],
        "citations": ["get_stock_quote", "get_buffett_score", "get_valuation", "get_moat"],
    }
    return _final_turn(json.dumps(payload))


def _fundamentals_two_turn_script(ticker: str) -> list[LLMTurn]:
    """Subagent script: turn 1 parallel-calls 4 tools, turn 2 emits Finding JSON."""
    return [
        _tool_turn([
            ("tu1", "get_stock_quote",   {"ticker": ticker}),
            ("tu2", "get_buffett_score", {"ticker": ticker}),
            ("tu3", "get_valuation",     {"ticker": ticker}),
            ("tu4", "get_moat",          {"ticker": ticker}),
        ]),
        _finding_turn(ticker=ticker),
    ]


def _good_plan_one_ticker(ticker: str = "AAPL") -> dict:
    return {
        "rationale": "Single-ticker quality + valuation question.",
        "subtasks":  [{"role": "fundamentals", "ticker": ticker}],
    }


# ── happy path ────────────────────────────────────────────────────────────────


async def test_orchestrate_happy_path_single_ticker():
    llm = _RoleScriptedLLM(
        planner=[_planner_turn(plan=_good_plan_one_ticker("AAPL"))],
        fundamentals=_fundamentals_two_turn_script("AAPL"),
        synthesis=[_final_turn("## Bottom Line\nBUY — wide moat at fair value.\n")],
    )
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("Should I buy AAPL?")

    assert run.status == AgentRunStatus.COMPLETED
    assert run.final_text and "Bottom Line" in run.final_text

    kinds = [s.kind for s in run.steps]
    assert kinds == [
        OrchestratorStepKind.PLAN,
        OrchestratorStepKind.SUBAGENT,
        OrchestratorStepKind.SYNTH,
        OrchestratorStepKind.FINAL,
    ]

    assert run.plan is not None and len(run.plan.subtasks) == 1
    assert run.plan.subtasks[0].role == SubagentRole.FUNDAMENTALS
    assert len(run.findings) == 1
    assert run.findings[0].ticker == "AAPL"
    assert "moat" in " ".join(run.findings[0].bullets).lower()


async def test_orchestrate_stream_yields_steps_in_order():
    llm = _RoleScriptedLLM(
        planner=[_planner_turn(plan=_good_plan_one_ticker("MSFT"))],
        fundamentals=_fundamentals_two_turn_script("MSFT"),
        synthesis=[_final_turn("## Bottom Line\nHOLD.\n")],
    )
    orch = Orchestrator(llm=llm, registry=_build_master_registry())

    received = []
    last_run = None
    async for step, run in orch.stream("Analyze MSFT"):
        received.append(step.kind)
        last_run = run

    assert received == [
        OrchestratorStepKind.PLAN,
        OrchestratorStepKind.SUBAGENT,
        OrchestratorStepKind.SYNTH,
        OrchestratorStepKind.FINAL,
    ]
    assert last_run.status == AgentRunStatus.COMPLETED


# ── failure modes ─────────────────────────────────────────────────────────────


async def test_planner_invalid_then_valid_recovers_via_runner_repair():
    """Planner's first reply is unparseable; AgentRunner's repair loop kicks in."""
    bad  = _final_turn("not even json")
    good = _planner_turn(plan=_good_plan_one_ticker("NVDA"))
    llm = _RoleScriptedLLM(
        planner=[bad, good],
        fundamentals=_fundamentals_two_turn_script("NVDA"),
        synthesis=[_final_turn("## Bottom Line\nBUY.\n")],
    )
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("Buy NVDA?")
    assert run.status == AgentRunStatus.COMPLETED
    assert run.plan_run is not None
    # The plan_run records the repair internally; orchestrator coordination
    # trail still shows PLAN as the first step.
    assert run.steps[0].kind == OrchestratorStepKind.PLAN


async def test_planner_exhausts_repairs_then_orchestrator_errors():
    bad = _final_turn("still not json")
    # max_repairs=2 default + 1 initial = 3 attempts. Give 4 bad turns to be safe.
    llm = _RoleScriptedLLM(planner=[bad, bad, bad, bad])
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("garbage in")

    assert run.status == AgentRunStatus.FAILED
    assert run.error is not None
    assert run.steps[-1].kind == OrchestratorStepKind.ERROR
    assert run.plan is None
    assert run.findings == []
    assert run.synth_run is None


async def test_subagent_failure_propagates_when_only_one_subtask():
    """Subagent returns garbage even after repairs → no findings → orchestrator FAILED."""
    bad = _final_turn("not a finding")
    llm = _RoleScriptedLLM(
        planner=[_planner_turn(plan=_good_plan_one_ticker("AAPL"))],
        # First turn calls tools (good), second+ turns return garbage.
        fundamentals=[
            _tool_turn([("tu1", "get_stock_quote", {"ticker": "AAPL"})]),
            bad, bad, bad, bad,
        ],
    )
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("AAPL?")
    assert run.status == AgentRunStatus.FAILED
    # SUBAGENT step recorded with error, then ERROR coordinator step.
    kinds = [s.kind for s in run.steps]
    assert OrchestratorStepKind.SUBAGENT in kinds
    assert kinds[-1] == OrchestratorStepKind.ERROR
    assert len(run.findings) == 0


async def test_unsupported_role_lands_as_subagent_error_then_overall_failed():
    """Plan asks for a NEWS subagent (not implemented) → SUBAGENT step w/ error."""
    plan = {
        "rationale": "User wants news.",
        "subtasks":  [{"role": "news", "ticker": "AAPL"}],
    }
    llm = _RoleScriptedLLM(planner=[_planner_turn(plan=plan)])
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("Latest on AAPL?")
    # One SUBAGENT step with the error, then overall ERROR (no findings).
    sub_steps = [s for s in run.steps if s.kind == OrchestratorStepKind.SUBAGENT]
    assert len(sub_steps) == 1
    assert sub_steps[0].finding is None
    assert sub_steps[0].error and "not implemented" in sub_steps[0].error
    assert run.status == AgentRunStatus.FAILED


# ── cost rollup ───────────────────────────────────────────────────────────────


async def test_cost_rollup_sums_planner_subagents_and_synth():
    llm = _RoleScriptedLLM(
        planner=[_planner_turn(plan=_good_plan_one_ticker("AAPL"))],
        fundamentals=_fundamentals_two_turn_script("AAPL"),
        synthesis=[_final_turn("## Bottom Line\nBUY.\n")],
    )
    orch = Orchestrator(llm=llm, registry=_build_master_registry())
    run = await orch.run("AAPL?")

    # planner: 1 LLM turn × (10 in / 5 out)
    # subagent: 1 tool turn (20 in / 10 out) + 1 final turn (10 in / 5 out)
    # synth:    1 final turn (10 in / 5 out)
    expected_in  = 10 + 20 + 10 + 10
    expected_out = 5 + 10 + 5 + 5
    assert run.total_input_tokens  == expected_in
    assert run.total_output_tokens == expected_out
    assert run.total_cost_usd > 0


# ── registry.subset ───────────────────────────────────────────────────────────


def test_registry_subset_exposes_only_requested_tools():
    master = _build_master_registry()
    sub    = master.subset(["get_stock_quote", "get_moat"])
    assert set(sub.names()) == {"get_stock_quote", "get_moat"}
    # Handlers are shared, not duplicated.
    assert sub.get("get_stock_quote").handler is master.get("get_stock_quote").handler


def test_registry_subset_unknown_tool_raises():
    master = _build_master_registry()
    with pytest.raises(KeyError):
        master.subset(["get_nonexistent"])
