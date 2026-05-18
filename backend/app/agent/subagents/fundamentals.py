"""Fundamentals subagent — Buffett-style quality + valuation lens on ONE ticker.

The subagent is an `AgentRunner` configured with:
- a 4-tool subset of the master registry (quote / score / valuation / moat)
- `FUNDAMENTALS_SYSTEM` prompt
- `output_schema=Finding` so its terminal turn must produce a structured
  Finding the orchestrator can consume.

The orchestrator builds one runner per subtask via `fundamentals_runner()`."""

from __future__ import annotations

from app.agent.llm import AnthropicClient
from app.agent.models import Finding
from app.agent.prompts import FUNDAMENTALS_SYSTEM
from app.agent.runner import AgentRunner
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry

# Tools this role is allowed to call. The orchestrator's master registry must
# expose all four; missing tools raise at runner construction time.
FUNDAMENTALS_TOOLS: list[str] = [
    "get_stock_quote",
    "get_buffett_score",
    "get_valuation",
    "get_moat",
]


def fundamentals_runner(
    *,
    llm:       AnthropicClient,
    registry:  ToolRegistry,
    max_iters: int = 6,
) -> AgentRunner:
    """Build a FundamentalsSubagent runner sharing the master registry's
    handlers but exposing only the 4 fundamentals tools to the LLM."""
    sub_registry   = registry.subset(FUNDAMENTALS_TOOLS)
    sub_dispatcher = ToolDispatcher(sub_registry)
    return AgentRunner(
        llm=llm,
        registry=sub_registry,
        dispatcher=sub_dispatcher,
        system=FUNDAMENTALS_SYSTEM,
        max_iters=max_iters,
        output_schema=Finding,
    )
