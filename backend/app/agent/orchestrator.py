"""Orchestrator — the top-level multi-agent loop.

Phases (each yields one OrchestratorStep):

  1. PLAN     Planner agent (no tools, structured-output → ResearchPlan)
                produces a list of Subtasks from the user query.
  2. SUBAGENT One AgentRunner per Subtask runs in parallel. Each returns a
                structured Finding (via its own output_schema). Failed
                subagents land as SUBAGENT steps with `finding=None` and
                `error=...`; the run continues with whatever findings made it.
  3. SYNTH    Synthesizer agent (no tools, free-form text) is given the
                original query + serialized findings and produces the final
                multi-section report.
  4. FINAL    Terminal step. Status COMPLETED unless every subagent failed
                (then FAILED).

Cost / tokens roll up from every child AgentRun into OrchestratorRun. The
stream() generator yields each OrchestratorStep as it lands so callers (the
SSE route) can push incremental events to the UI."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

from app.agent.llm import AnthropicClient
from app.agent.models import (
    AgentRun,
    AgentRunStatus,
    Finding,
    OrchestratorRun,
    OrchestratorStep,
    OrchestratorStepKind,
    ResearchPlan,
    SubagentRole,
    Subtask,
)
from app.agent.prompts import PLANNER_SYSTEM, SYNTHESIS_SYSTEM
from app.agent.runner import AgentRunner
from app.agent.subagents import fundamentals_runner, technical_runner
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.registry import ToolRegistry


class Orchestrator:
    """Multi-agent coordinator: Planner → N Subagents (parallel) → Synthesizer."""

    def __init__(
        self,
        *,
        llm:            AnthropicClient,
        registry:       ToolRegistry,
        max_iters:      int = 8,
        subagent_iters: int = 6,
    ) -> None:
        self._llm            = llm
        self._registry       = registry
        self._max_iters      = max_iters
        self._subagent_iters = subagent_iters

    # ── public entry points ──────────────────────────────────────────────

    async def run(self, query: str, *, model: Optional[str] = None) -> OrchestratorRun:
        run = OrchestratorRun(query=query)
        async for _ in self._drive(run, model=model):
            pass
        return run

    async def stream(
        self, query: str, *, model: Optional[str] = None,
    ) -> AsyncIterator[tuple[OrchestratorStep, OrchestratorRun]]:
        run = OrchestratorRun(query=query)
        async for step in self._drive(run, model=model):
            yield step, run

    # ── core loop ────────────────────────────────────────────────────────

    async def _drive(
        self, run: OrchestratorRun, *, model: Optional[str] = None,
    ) -> AsyncIterator[OrchestratorStep]:
        # 1. PLAN ────────────────────────────────────────────────────────
        plan_run = await self._planner_runner().run(run.query, model=model)
        run.plan_run = plan_run
        run.add_cost(plan_run)

        if plan_run.status != AgentRunStatus.COMPLETED or not plan_run.structured_output:
            err = (
                plan_run.error
                or f"Planner did not produce a valid plan (status={plan_run.status.value})."
            )
            err_step = OrchestratorStep(
                idx=len(run.steps), kind=OrchestratorStepKind.ERROR, error=err,
            )
            run.append(err_step)
            run.finish(AgentRunStatus.FAILED, error=err)
            yield err_step
            return

        try:
            plan = ResearchPlan.model_validate(plan_run.structured_output)
        except Exception as exc:                                       # noqa: BLE001
            err = f"Planner output failed ResearchPlan validation: {exc}"
            err_step = OrchestratorStep(
                idx=len(run.steps), kind=OrchestratorStepKind.ERROR, error=err,
            )
            run.append(err_step)
            run.finish(AgentRunStatus.FAILED, error=err)
            yield err_step
            return

        run.plan = plan
        plan_step = OrchestratorStep(
            idx=len(run.steps), kind=OrchestratorStepKind.PLAN, plan=plan,
        )
        run.append(plan_step)
        yield plan_step

        # 2. SUBAGENTS (parallel) ────────────────────────────────────────
        async def _exec(subtask: Subtask) -> tuple[Subtask, AgentRun, Optional[Finding], Optional[str]]:
            try:
                runner = self._subagent_runner_for(subtask)
            except ValueError as exc:
                # Unsupported role — synthesize a placeholder AgentRun so the
                # step still has cost/latency rollup hooks.
                placeholder = AgentRun(query=_subtask_prompt(subtask))
                placeholder.finish(AgentRunStatus.FAILED, error=str(exc))
                return subtask, placeholder, None, str(exc)

            child = await runner.run(_subtask_prompt(subtask), model=model)
            finding: Optional[Finding] = None
            err: Optional[str] = None
            if child.status == AgentRunStatus.COMPLETED and child.structured_output:
                try:
                    finding = Finding.model_validate(child.structured_output)
                except Exception as exc:                               # noqa: BLE001
                    err = f"Subagent output failed Finding validation: {exc}"
            else:
                err = child.error or f"Subagent did not complete (status={child.status.value})."
            return subtask, child, finding, err

        results = await asyncio.gather(*(_exec(t) for t in plan.subtasks))

        for subtask, child, finding, err in results:
            run.subagent_runs.append(child)
            run.add_cost(child)
            if finding is not None:
                run.findings.append(finding)
            sub_step = OrchestratorStep(
                idx=len(run.steps),
                kind=OrchestratorStepKind.SUBAGENT,
                role=subtask.role,
                ticker=subtask.ticker,
                finding=finding,
                error=err,
            )
            run.append(sub_step)
            yield sub_step

        if not run.findings:
            err = "All subagents failed; nothing to synthesize."
            err_step = OrchestratorStep(
                idx=len(run.steps), kind=OrchestratorStepKind.ERROR, error=err,
            )
            run.append(err_step)
            run.finish(AgentRunStatus.FAILED, error=err)
            yield err_step
            return

        # 3. SYNTH ───────────────────────────────────────────────────────
        synth_input = _synthesis_prompt(run.query, run.findings)
        synth_run = await self._synth_runner().run(synth_input, model=model)
        run.synth_run = synth_run
        run.add_cost(synth_run)

        if synth_run.status != AgentRunStatus.COMPLETED or not synth_run.final_text:
            err = synth_run.error or "Synthesizer did not produce a final report."
            err_step = OrchestratorStep(
                idx=len(run.steps), kind=OrchestratorStepKind.ERROR, error=err,
            )
            run.append(err_step)
            run.finish(AgentRunStatus.FAILED, error=err)
            yield err_step
            return

        synth_step = OrchestratorStep(
            idx=len(run.steps),
            kind=OrchestratorStepKind.SYNTH,
            text=synth_run.final_text,
        )
        run.append(synth_step)
        yield synth_step

        # 4. FINAL ───────────────────────────────────────────────────────
        final_step = OrchestratorStep(
            idx=len(run.steps),
            kind=OrchestratorStepKind.FINAL,
            text=synth_run.final_text,
        )
        run.append(final_step)
        run.finish(AgentRunStatus.COMPLETED, final_text=synth_run.final_text)
        yield final_step

    # ── runner factories ─────────────────────────────────────────────────

    def _planner_runner(self) -> AgentRunner:
        empty = ToolRegistry()
        return AgentRunner(
            llm=self._llm,
            registry=empty,
            dispatcher=ToolDispatcher(empty),
            system=PLANNER_SYSTEM,
            # 1 shot + up to default max_repairs=2 → 3 LLM turns; +1 safety.
            max_iters=4,
            output_schema=ResearchPlan,
        )

    def _synth_runner(self) -> AgentRunner:
        empty = ToolRegistry()
        return AgentRunner(
            llm=self._llm,
            registry=empty,
            dispatcher=ToolDispatcher(empty),
            system=SYNTHESIS_SYSTEM,
            max_iters=2,
        )

    def _subagent_runner_for(self, subtask: Subtask) -> AgentRunner:
        if subtask.role == SubagentRole.FUNDAMENTALS:
            return fundamentals_runner(
                llm=self._llm,
                registry=self._registry,
                max_iters=self._subagent_iters,
            )
        if subtask.role == SubagentRole.TECHNICAL:
            return technical_runner(
                llm=self._llm,
                registry=self._registry,
                max_iters=self._subagent_iters,
            )
        raise ValueError(
            f"Subagent role '{subtask.role.value}' is not implemented yet "
            "(reserved for a future phase)."
        )


# ── prompt helpers ───────────────────────────────────────────────────────


def _subtask_prompt(subtask: Subtask) -> str:
    """User message a subagent sees for one subtask."""
    parts = [f"Ticker: {subtask.ticker.upper()}"]
    if subtask.focus:
        parts.append(f"User focus: {subtask.focus}")
    parts.append(
        "Run the fundamentals workflow described in your system prompt and "
        "return a single Finding JSON object."
    )
    return "\n".join(parts)


def _synthesis_prompt(query: str, findings: list[Finding]) -> str:
    """User message the synthesizer sees: original query + JSON findings.

    Findings are serialized as JSON (not prose) so the synth model treats
    them as data, not as another agent's opinion to argue with."""
    payload = [f.model_dump(mode="json") for f in findings]
    return (
        f"Original user question:\n{query}\n\n"
        f"Findings from {len(findings)} specialist subagent run(s) "
        f"(each grounded in tool outputs):\n"
        f"{json.dumps(payload, indent=2, default=str)}\n\n"
        "Produce the final report in the section format defined in your "
        "system prompt. Cite only numbers that appear above."
    )
