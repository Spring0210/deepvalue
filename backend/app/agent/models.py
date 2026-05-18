from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_ms() -> int:
    return int(time.time() * 1000)


class LLMUsage(BaseModel):
    model:               str
    input_tokens:        int = 0
    output_tokens:       int = 0
    cache_read_tokens:   int = 0   # Anthropic prompt-cache hits
    cache_write_tokens:  int = 0   # Anthropic prompt-cache writes
    cost_usd:            float = 0.0
    latency_ms:          int = 0


class ToolCall(BaseModel):
    """One tool invocation requested by the LLM in a single assistant turn."""
    id:    str                       # Anthropic tool_use_id, used to match tool_result back
    name:  str
    args:  dict[str, Any]


class ToolResult(BaseModel):
    """Result of dispatching a ToolCall. Never raises — failures encoded as error."""
    call_id:    str
    name:       str
    ok:         bool
    output:     Optional[Any] = None
    error:      Optional[str] = None
    latency_ms: int = 0
    attempts:   int = 1


class StepKind(str, Enum):
    LLM        = "llm"           # one assistant turn (with thought + maybe tool_calls)
    TOOL_BATCH = "tool_batch"    # parallel dispatch of one or more tools
    FINAL      = "final"         # terminal answer
    ERROR      = "error"         # unrecoverable failure
    REPAIR     = "repair"        # corrective user message after structured-output parse failure


class AgentStep(BaseModel):
    """One step in an agent run. Flat schema so each row maps to one persisted record."""
    idx:        int
    kind:       StepKind
    started_at: int = Field(default_factory=_now_ms)

    # LLM step
    text:       Optional[str] = None            # assistant message text (if any)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage:      Optional[LLMUsage] = None

    # Tool batch step
    tool_results: list[ToolResult] = Field(default_factory=list)

    # Error step
    error: Optional[str] = None


class AgentRunStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CAPPED    = "capped"        # hit iteration cap


class AgentRun(BaseModel):
    id:         str = Field(default_factory=_new_id)
    query:      str
    status:     AgentRunStatus = AgentRunStatus.RUNNING
    started_at: int = Field(default_factory=_now_ms)
    finished_at: Optional[int] = None

    steps:      list[AgentStep] = Field(default_factory=list)
    final_text: Optional[str] = None
    structured_output: Optional[dict[str, Any]] = None   # populated when output_schema is set

    total_cost_usd:   float = 0.0
    total_latency_ms: int = 0
    total_input_tokens:  int = 0
    total_output_tokens: int = 0

    error: Optional[str] = None

    def append(self, step: AgentStep) -> None:
        self.steps.append(step)
        if step.usage:
            self.total_cost_usd      += step.usage.cost_usd
            self.total_input_tokens  += step.usage.input_tokens
            self.total_output_tokens += step.usage.output_tokens

    def finish(self, status: AgentRunStatus, final_text: Optional[str] = None, error: Optional[str] = None) -> None:
        self.status = status
        self.final_text = final_text
        self.error = error
        self.finished_at = _now_ms()
        self.total_latency_ms = self.finished_at - self.started_at


# ── Multi-agent orchestration ────────────────────────────────────────────────


class SubagentRole(str, Enum):
    """Specialized roles the orchestrator can dispatch to. Only FUNDAMENTALS
    is wired in v0.6; the rest are reserved so the planner schema is stable
    when we ship the remaining subagents."""
    FUNDAMENTALS = "fundamentals"
    NEWS         = "news"
    TECHNICAL    = "technical"
    VALUATION    = "valuation"
    RISK         = "risk"


class Subtask(BaseModel):
    """One unit of work the orchestrator hands to a single subagent."""
    role:   SubagentRole
    ticker: str = Field(..., pattern=r"^[A-Za-z0-9.\-]{1,10}$")
    focus:  Optional[str] = Field(
        default=None,
        description="Free-form hint, e.g. 'moat depth' or 'recent earnings beat'.",
    )


class ResearchPlan(BaseModel):
    """Planner output. The orchestrator runs the subtasks in parallel."""
    rationale: str = Field(..., description="One- to two-sentence justification for the chosen subtasks.")
    subtasks:  list[Subtask] = Field(..., min_length=1, max_length=8)


class Finding(BaseModel):
    """Structured result a subagent returns to the orchestrator."""
    role:      SubagentRole
    ticker:    str
    summary:   str = Field(..., description="One short paragraph, grounded in tool results.")
    bullets:   list[str] = Field(default_factory=list, max_length=6)
    citations: list[str] = Field(
        default_factory=list,
        description="Names of the tools whose outputs back the claims (e.g. 'get_buffett_score').",
    )


class OrchestratorStepKind(str, Enum):
    PLAN     = "plan"        # planner produced a ResearchPlan
    SUBAGENT = "subagent"    # one subagent finished (or failed)
    SYNTH    = "synth"       # synthesizer produced the final report
    FINAL    = "final"       # terminal — coordinator finished cleanly
    ERROR    = "error"       # unrecoverable failure at the coordination layer


class OrchestratorStep(BaseModel):
    """Slim event marker for the coordination trail. Full child AgentRun
    objects live on OrchestratorRun, not here, so SSE payloads stay small."""
    idx:        int
    kind:       OrchestratorStepKind
    started_at: int = Field(default_factory=_now_ms)

    # PLAN
    plan: Optional[ResearchPlan] = None

    # SUBAGENT
    role:    Optional[SubagentRole] = None
    ticker:  Optional[str] = None
    finding: Optional[Finding] = None

    # SYNTH / FINAL
    text: Optional[str] = None

    # ERROR
    error: Optional[str] = None


class OrchestratorRun(BaseModel):
    """Top-level multi-agent run. Owns the planner / subagent / synthesis
    sub-runs, the structured plan and findings, and a cost rollup."""
    id:          str = Field(default_factory=_new_id)
    query:       str
    status:      AgentRunStatus = AgentRunStatus.RUNNING
    started_at:  int = Field(default_factory=_now_ms)
    finished_at: Optional[int] = None

    steps:         list[OrchestratorStep] = Field(default_factory=list)
    plan:          Optional[ResearchPlan]  = None
    plan_run:      Optional[AgentRun]      = None
    subagent_runs: list[AgentRun]          = Field(default_factory=list)
    findings:      list[Finding]           = Field(default_factory=list)
    synth_run:     Optional[AgentRun]      = None
    final_text:    Optional[str]           = None

    total_cost_usd:      float = 0.0
    total_latency_ms:    int = 0
    total_input_tokens:  int = 0
    total_output_tokens: int = 0

    error: Optional[str] = None

    def append(self, step: OrchestratorStep) -> None:
        self.steps.append(step)

    def add_cost(self, child: AgentRun) -> None:
        """Roll a child AgentRun's tokens + cost into the orchestrator total."""
        self.total_cost_usd      += child.total_cost_usd
        self.total_input_tokens  += child.total_input_tokens
        self.total_output_tokens += child.total_output_tokens

    def finish(
        self,
        status: AgentRunStatus,
        final_text: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.status = status
        self.final_text = final_text
        self.error = error
        self.finished_at = _now_ms()
        self.total_latency_ms = self.finished_at - self.started_at
