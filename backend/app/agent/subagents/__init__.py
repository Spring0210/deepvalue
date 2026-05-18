"""Specialized subagents dispatched by the orchestrator.

Each subagent is an `AgentRunner` with:
- a narrow tool subset (so the model can't reach for off-role tools)
- a role-specific system prompt
- `output_schema=Finding` so the result is a structured contract.

Adding a new specialist (News, Risk, Technical, Valuation) means: pick the
tool subset, write a system prompt, build a `subagent_for_<role>()` factory."""

from app.agent.subagents.fundamentals import (
    FUNDAMENTALS_TOOLS,
    fundamentals_runner,
)

__all__ = ["FUNDAMENTALS_TOOLS", "fundamentals_runner"]
