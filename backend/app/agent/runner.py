"""AgentRunner — the plan-act-observe loop.

Single-agent for v0.5-MVP. Loop:

  user_query
      │
      ▼
  ┌─► LLM turn → text + tool_calls + usage          (AgentStep[LLM])
  │       │
  │       ├─ no tool_calls (stop_reason == "end_turn") → FINAL step, done
  │       │
  │       └─ tool_calls present
  │             ↓
  │       Dispatcher runs them in parallel          (AgentStep[TOOL_BATCH])
  │             ↓
  │       Append tool_results to messages, loop ───┘

Hard cap on iterations so a broken model can't burn the budget."""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.agent.llm import AnthropicClient, LLMTurn
from app.agent.models import (
    AgentRun,
    AgentRunStatus,
    AgentStep,
    StepKind,
    ToolResult,
)
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry


class AgentRunner:
    def __init__(
        self,
        *,
        llm:         AnthropicClient,
        registry:    ToolRegistry,
        dispatcher:  ToolDispatcher,
        system:      str,
        max_iters:   int = 8,
    ) -> None:
        self._llm        = llm
        self._registry   = registry
        self._dispatcher = dispatcher
        self._system     = system
        self._max_iters  = max_iters

    async def run(self, query: str, *, model: str | None = None) -> AgentRun:
        run = AgentRun(query=query)
        async for _ in self._drive(run, model=model):
            pass
        return run

    async def stream(
        self, query: str, *, model: str | None = None,
    ) -> AsyncIterator[tuple[AgentStep, AgentRun]]:
        """Yield (step, run-snapshot) tuples as each step lands. The final
        yield is the terminal FINAL or ERROR step; callers can read
        `run.status` / `run.final_text` from the snapshot to know we're done."""
        run = AgentRun(query=query)
        async for step in self._drive(run, model=model):
            yield step, run

    async def _drive(
        self, run: AgentRun, *, model: str | None = None,
    ) -> AsyncIterator[AgentStep]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": run.query}]
        tool_schemas = self._registry.anthropic_schemas()

        for step_idx in range(self._max_iters):
            try:
                turn: LLMTurn = await self._llm.complete(
                    system=self._system,
                    messages=messages,
                    tools=tool_schemas,
                    model=model,
                )
            except Exception as exc:                                  # noqa: BLE001
                err_step = AgentStep(
                    idx=step_idx, kind=StepKind.ERROR,
                    error=f"{type(exc).__name__}: {exc}",
                )
                run.append(err_step)
                run.finish(AgentRunStatus.FAILED, error=str(exc))
                yield err_step
                return

            llm_step = AgentStep(
                idx=step_idx, kind=StepKind.LLM,
                text=turn.text, tool_calls=turn.tool_calls, usage=turn.usage,
            )
            run.append(llm_step)
            yield llm_step

            # Always echo the assistant turn back into history so tool_use ids match.
            messages.append({"role": "assistant", "content": turn.raw_assistant_blocks})

            # Terminal: no tools requested → final answer.
            if not turn.tool_calls:
                final = turn.text or ""
                final_step = AgentStep(idx=step_idx + 1, kind=StepKind.FINAL, text=final)
                run.append(final_step)
                run.finish(AgentRunStatus.COMPLETED, final_text=final)
                yield final_step
                return

            results = await self._dispatcher.dispatch_many(turn.tool_calls)
            tool_step = AgentStep(
                idx=step_idx + 1, kind=StepKind.TOOL_BATCH, tool_results=results,
            )
            run.append(tool_step)
            yield tool_step

            messages.append({
                "role":    "user",
                "content": [_tool_result_block(r) for r in results],
            })

        # Iteration cap hit — surface the most recent assistant text as best-effort.
        last_text = next(
            (s.text for s in reversed(run.steps) if s.kind == StepKind.LLM and s.text),
            None,
        )
        cap_step = AgentStep(
            idx=len(run.steps), kind=StepKind.FINAL, text=last_text,
        )
        run.append(cap_step)
        run.finish(
            AgentRunStatus.CAPPED,
            final_text=last_text,
            error=f"Hit max_iters={self._max_iters} without end_turn.",
        )
        yield cap_step


def _tool_result_block(result: ToolResult) -> dict[str, Any]:
    """Anthropic tool_result content block. Content must be a string for portability."""
    if result.ok:
        import json
        return {
            "type":        "tool_result",
            "tool_use_id": result.call_id,
            "content":     json.dumps(result.output, default=str),
        }
    return {
        "type":        "tool_result",
        "tool_use_id": result.call_id,
        "is_error":    True,
        "content":     f"Tool '{result.name}' failed: {result.error}",
    }
