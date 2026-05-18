"""Technical subagent — momentum + entry-timing lens on ONE ticker.

Mirrors `fundamentals.py`: an `AgentRunner` configured with a narrow tool
subset, the TECHNICAL_SYSTEM prompt, and `output_schema=Finding` so the
terminal turn must produce a Finding the orchestrator can consume.

Tools exposed to this role: `get_stock_quote`, `get_price_history`, and
`get_technicals` — enough for trend / overbought / drawdown reads without
muddying the prompt with quality + valuation considerations."""

from __future__ import annotations

from app.agent.llm import AnthropicClient
from app.agent.models import Finding
from app.agent.prompts import TECHNICAL_SYSTEM
from app.agent.runner import AgentRunner
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry

TECHNICAL_TOOLS: list[str] = [
    "get_stock_quote",
    "get_price_history",
    "get_technicals",
]


def technical_runner(
    *,
    llm:       AnthropicClient,
    registry:  ToolRegistry,
    max_iters: int = 6,
) -> AgentRunner:
    """Build a TechnicalSubagent runner sharing the master registry's
    handlers but exposing only the 3 technical tools to the LLM."""
    sub_registry   = registry.subset(TECHNICAL_TOOLS)
    sub_dispatcher = ToolDispatcher(sub_registry)
    return AgentRunner(
        llm=llm,
        registry=sub_registry,
        dispatcher=sub_dispatcher,
        system=TECHNICAL_SYSTEM,
        max_iters=max_iters,
        output_schema=Finding,
    )
